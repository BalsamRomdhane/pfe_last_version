"""
services/security/encryption.py — AES-256-GCM document encryption service.

Public API
----------
  EncryptionService                           ← orchestration (DB read/write)
    .encrypt_if_needed(document_id)           → EncryptionResult | None
    .decrypt_in_memory(document_id)           → bytes | None
    .should_encrypt(classification_level)     → bool

  encrypt_document(plaintext, key)            → EncryptedPayload
  decrypt_document(payload, key)              → bytes

Algorithm
---------
  AES-256-GCM  (Galois/Counter Mode)
  - 256-bit key read exclusively from DOCUMENT_ENCRYPTION_KEY env var
  - 96-bit (12-byte) random nonce per encryption operation
  - GCM authentication tag (16 bytes) guarantees both confidentiality
    and integrity — if the ciphertext is tampered, decryption raises
    InvalidTag before any plaintext is released
  - The nonce is prepended to the ciphertext so the stored format is:
        [12-byte nonce] + [ciphertext + 16-byte GCM tag]
  - Total overhead per document: 28 bytes (nonce + tag)

Security properties
-------------------
  - Key is NEVER stored in code, git history, or database
  - Encrypted file replaces the original on disk (one file per document)
  - Decryption is ALWAYS in memory — no plaintext written to disk
  - Phase 1 hash was computed on the plaintext BEFORE encryption, so
    integrity verification still works after encryption

Encryption policy (configurable via environment)
-------------------------------------------------
  Classification  |  Encrypt?
  ────────────────┼──────────────────────────────────────────────────────
  PUBLIC          |  Never
  INTERNAL        |  Only if ENCRYPT_INTERNAL_DOCS=True  (default: False)
  CONFIDENTIAL    |  Always
  RESTRICTED      |  Always

Key management
--------------
  Generate a new 256-bit key:
      python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
  Set in .env:
      DOCUMENT_ENCRYPTION_KEY=<base64url-encoded 32 bytes>

  The key is loaded once at import time and cached.  A missing or invalid
  key raises ImproperlyConfigured at startup in production (DEBUG=False).

Extensibility (future phases)
------------------------------
  Phase 5 — DocumentStorageService calls decrypt_in_memory() before serving.
  Phase 6 — Secure download endpoint uses decrypt_in_memory() + streaming.
  Phase 8 — AuditService logs every decrypt_in_memory() call.
"""
from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
NONCE_SIZE   = 12    # bytes — AES-GCM standard nonce length
KEY_SIZE     = 32    # bytes — AES-256

# Levels that are always encrypted
_ALWAYS_ENCRYPT = frozenset({'CONFIDENTIAL', 'RESTRICTED'})
# Level encrypted only when ENCRYPT_INTERNAL_DOCS=True
_OPTIONAL_ENCRYPT = frozenset({'INTERNAL'})


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class EncryptedPayload:
    """
    Result of encrypt_document().

    Attributes
    ----------
    ciphertext  : bytes — nonce (12 B) prepended to AES-GCM output
    nonce       : bytes — the 12-byte random nonce (extracted for reference)
    key_id      : str   — identifies which key was used (currently 'env_key')
    algorithm   : str   — always 'AES-256-GCM'
    """
    ciphertext: bytes
    nonce:      bytes
    key_id:     str   = 'env_key'
    algorithm:  str   = 'AES-256-GCM'


@dataclass
class EncryptionResult:
    """Result returned by EncryptionService.encrypt_if_needed()."""
    document_id:  int
    encrypted:    bool    # True = file was encrypted (or was already encrypted)
    skipped:      bool    # True = encryption not needed for this classification
    reason:       str     # human-readable explanation


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_key() -> Optional[bytes]:
    """
    Load the AES-256 key from DOCUMENT_ENCRYPTION_KEY environment variable.

    The variable must be a URL-safe base64-encoded 32-byte value.

    Returns None if the variable is not set (encryption disabled).
    Raises ImproperlyConfigured if the variable is set but invalid.
    """
    raw = os.environ.get('DOCUMENT_ENCRYPTION_KEY', '').strip()
    if not raw:
        return None

    try:
        key = base64.urlsafe_b64decode(raw + '==')  # pad for urlsafe_b64decode
    except Exception as exc:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'DOCUMENT_ENCRYPTION_KEY is set but cannot be base64-decoded. '
            'Generate a valid key with: '
            'python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
        ) from exc

    if len(key) != KEY_SIZE:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            f'DOCUMENT_ENCRYPTION_KEY must encode exactly {KEY_SIZE} bytes '
            f'(got {len(key)} bytes after decoding). '
            f'Generate a valid key with: '
            f'python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
        )

    return key


# Module-level key cache — loaded once, never logged
_ENCRYPTION_KEY: Optional[bytes] = None
_KEY_LOADED = False


def _get_key() -> Optional[bytes]:
    """Return the cached encryption key, loading it on first call."""
    global _ENCRYPTION_KEY, _KEY_LOADED
    if not _KEY_LOADED:
        _ENCRYPTION_KEY = _load_key()
        _KEY_LOADED = True
    return _ENCRYPTION_KEY


def _require_key() -> bytes:
    """
    Return the encryption key, raising ValueError if it is not configured.
    Used by encrypt/decrypt operations that must succeed.
    """
    key = _get_key()
    if key is None:
        raise ValueError(
            'DOCUMENT_ENCRYPTION_KEY is not set. '
            'Encryption/decryption is unavailable. '
            'Set this variable in your .env file to enable document encryption.'
        )
    return key


# ── Core cryptographic functions ──────────────────────────────────────────────

def encrypt_document(plaintext: bytes, key: bytes) -> EncryptedPayload:
    """
    Encrypt ``plaintext`` using AES-256-GCM.

    A fresh 12-byte random nonce is generated for every call.
    The returned EncryptedPayload.ciphertext is:
        nonce (12 bytes) + AES-GCM output (len(plaintext) + 16-byte tag)

    Parameters
    ----------
    plaintext : bytes  — the document content to encrypt
    key       : bytes  — 32-byte AES-256 key

    Returns
    -------
    EncryptedPayload

    Raises
    ------
    ValueError  If key length is not exactly 32 bytes.
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f'Key must be {KEY_SIZE} bytes; got {len(key)}.')

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce  = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    # AESGCM.encrypt returns ciphertext + 16-byte GCM authentication tag
    ct = aesgcm.encrypt(nonce, plaintext, None)

    return EncryptedPayload(
        ciphertext=nonce + ct,
        nonce=nonce,
    )


def decrypt_document(payload: EncryptedPayload | bytes, key: bytes) -> bytes:
    """
    Decrypt an AES-256-GCM encrypted payload.

    Accepts either an EncryptedPayload object or raw bytes (nonce+ciphertext).

    Parameters
    ----------
    payload : EncryptedPayload | bytes
    key     : bytes — 32-byte AES-256 key

    Returns
    -------
    bytes — original plaintext

    Raises
    ------
    ValueError
        If key length or nonce extraction fails.
    cryptography.exceptions.InvalidTag
        If the ciphertext has been tampered with or the wrong key is used.
        This exception is intentionally NOT caught here — callers must
        handle it to avoid processing corrupt/tampered data.
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f'Key must be {KEY_SIZE} bytes; got {len(key)}.')

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if isinstance(payload, EncryptedPayload):
        raw = payload.ciphertext
    elif isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    else:
        raise TypeError(f'Expected EncryptedPayload or bytes, got {type(payload).__name__}.')

    if len(raw) < NONCE_SIZE + 16:  # minimum: nonce + empty plaintext + tag
        raise ValueError(
            f'Encrypted payload too short ({len(raw)} bytes). '
            'Data may be corrupt or not encrypted with this scheme.'
        )

    nonce = raw[:NONCE_SIZE]
    ct    = raw[NONCE_SIZE:]

    aesgcm = AESGCM(key)
    # decrypt raises InvalidTag automatically if authentication fails
    return aesgcm.decrypt(nonce, ct, None)


# ── Service class ─────────────────────────────────────────────────────────────

class EncryptionService:
    """
    Orchestration class: manages document encryption lifecycle.

    Called by the security pipeline in security/signals.py (Phase 4 active).
    Also callable directly from views for on-demand decryption.

    Encryption policy
    -----------------
    PUBLIC      → skipped (never encrypted)
    INTERNAL    → skipped unless ENCRYPT_INTERNAL_DOCS=True
    CONFIDENTIAL → always encrypted
    RESTRICTED   → always encrypted

    The pipeline order guarantees that:
    1. SHA-256 is computed on the PLAINTEXT (Phase 1)
    2. Classification determines the level (Phase 3)
    3. Encryption happens HERE, after classification (Phase 4)

    Therefore integrity verification (Phase 2 endpoint) must:
    - If document.encrypted = True: decrypt in memory, then hash
    - If document.encrypted = False: hash directly
    This logic is handled in DocumentIntegrityService.verify_document().
    """

    @staticmethod
    def should_encrypt(classification_level: str) -> bool:
        """
        Return True if a document with this classification must be encrypted.

        Checks the ENCRYPT_INTERNAL_DOCS env var for INTERNAL-level documents.
        """
        if classification_level in _ALWAYS_ENCRYPT:
            return True
        if classification_level in _OPTIONAL_ENCRYPT:
            encrypt_internal = os.environ.get(
                'ENCRYPT_INTERNAL_DOCS', 'False'
            ).lower() in ('true', '1', 'yes')
            return encrypt_internal
        return False  # PUBLIC

    @classmethod
    def encrypt_if_needed(cls, document_id: int) -> EncryptionResult | None:
        """
        Encrypt a document file if its classification requires it.

        Logic
        -----
        1. Load document + its security analysis (classification result).
        2. Determine whether encryption is needed.
        3. If yes and not already encrypted:
           a. Read plaintext from storage.
           b. Encrypt in memory using AES-256-GCM.
           c. Write ciphertext back to the same storage path.
           d. Update Document fields: encrypted=True, encryption_iv,
              encrypted_at, encrypted_key_id.
        4. If already encrypted or not needed: return early.

        Returns None on critical error (logged).
        """
        from api.models import Document
        from security.models import DocumentSecurityAnalysis

        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('EncryptionService: Document #%s not found.', document_id)
            return None

        # ── Determine classification level ────────────────────────────────────
        classification_level = 'PUBLIC'
        try:
            analysis = DocumentSecurityAnalysis.objects.get(document=document)
            classification_level = analysis.confidentiality_level or 'PUBLIC'
        except DocumentSecurityAnalysis.DoesNotExist:
            logger.warning(
                'EncryptionService: No security analysis for Document #%s — '
                'defaulting to PUBLIC (no encryption).',
                document_id,
            )

        # ── Check encryption policy ────────────────────────────────────────────
        if not cls.should_encrypt(classification_level):
            logger.info(
                'EncryptionService: Document #%s — classification=%s, skipping encryption.',
                document_id, classification_level,
            )
            return EncryptionResult(
                document_id=document_id,
                encrypted=False,
                skipped=True,
                reason=f'Classification {classification_level} does not require encryption.',
            )

        # ── Already encrypted? ─────────────────────────────────────────────────
        if document.encrypted:
            logger.info(
                'EncryptionService: Document #%s already encrypted — skipping.',
                document_id,
            )
            return EncryptionResult(
                document_id=document_id,
                encrypted=True,
                skipped=True,
                reason='Document was already encrypted.',
            )

        # ── Ensure key is available ────────────────────────────────────────────
        try:
            key = _require_key()
        except ValueError as exc:
            logger.warning(
                'EncryptionService: Cannot encrypt Document #%s — %s',
                document_id, exc,
            )
            return EncryptionResult(
                document_id=document_id,
                encrypted=False,
                skipped=True,
                reason=str(exc),
            )

        # ── Read plaintext ─────────────────────────────────────────────────────
        if not document.file:
            logger.warning(
                'EncryptionService: Document #%s has no file — skipping.',
                document_id,
            )
            return None

        try:
            from services.document_storage import DocumentStorageService
            plaintext = DocumentStorageService.read_raw(document_id)
            if plaintext is None:
                logger.error(
                    'EncryptionService: Cannot read file for Document #%s.',
                    document_id,
                )
                return None
        except Exception as exc:
            logger.error(
                'EncryptionService: Cannot read file for Document #%s — %s',
                document_id, exc,
            )
            return None

        # ── Encrypt ────────────────────────────────────────────────────────────
        try:
            payload = encrypt_document(plaintext, key)
        except Exception as exc:
            logger.error(
                'EncryptionService: Encryption failed for Document #%s — %s',
                document_id, exc,
            )
            return None

        # ── Write ciphertext back to storage ──────────────────────────────────
        try:
            from services.document_storage import DocumentStorageService
            if not DocumentStorageService.write(document_id, payload.ciphertext):
                logger.error(
                    'EncryptionService: write() failed for Document #%s.',
                    document_id,
                )
                return None
        except Exception as exc:
            logger.error(
                'EncryptionService: Cannot write encrypted file for Document #%s — %s',
                document_id, exc,
            )
            return None

        # ── Persist encryption metadata ───────────────────────────────────────
        from django.utils import timezone
        import base64 as _b64

        iv_b64 = _b64.b64encode(payload.nonce).decode()

        Document.objects.filter(pk=document_id).update(
            encrypted=True,
            encryption_iv=iv_b64,
            encrypted_at=timezone.now(),
            encrypted_key_id='env_key',
        )

        logger.info(
            'EncryptionService: Document #%s encrypted (level=%s, algo=%s, size=%d→%d bytes).',
            document_id,
            classification_level,
            payload.algorithm,
            len(plaintext),
            len(payload.ciphertext),
        )

        # Clear sensitive data from local scope
        del plaintext

        return EncryptionResult(
            document_id=document_id,
            encrypted=True,
            skipped=False,
            reason=f'Encrypted as {classification_level} ({payload.algorithm}).',
        )

    @classmethod
    def decrypt_in_memory(cls, document_id: int) -> bytes | None:
        """
        Decrypt a document file entirely in memory.

        The plaintext is NEVER written to disk. This method is called by:
          - Phase 6: secure view/download endpoints
          - api/utils.py: extract_document_text() for encrypted documents

        Returns
        -------
        bytes  — plaintext if decryption succeeded
        None   — if document is not encrypted (caller reads file directly)
        None   — on error (logged; caller should return 403 or 500)

        Raises
        ------
        PermissionError  — if the encryption key is not available
        """
        from api.models import Document
        from cryptography.exceptions import InvalidTag

        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('EncryptionService.decrypt_in_memory: Document #%s not found.', document_id)
            return None

        if not document.encrypted:
            # Not encrypted — caller must read the file directly
            return None

        try:
            key = _require_key()
        except ValueError as exc:
            raise PermissionError(
                f'Cannot decrypt Document #{document_id}: {exc}'
            ) from exc

        if not document.file:
            logger.error(
                'EncryptionService.decrypt_in_memory: Document #%s has no file.',
                document_id,
            )
            return None

        try:
            from services.document_storage import DocumentStorageService
            ciphertext = DocumentStorageService.read_raw(document_id)
            if ciphertext is None:
                logger.error(
                    'EncryptionService.decrypt_in_memory: Cannot read file for Document #%s.',
                    document_id,
                )
                return None
        except Exception as exc:
            logger.error(
                'EncryptionService.decrypt_in_memory: Cannot read file for Document #%s — %s',
                document_id, exc,
            )
            return None

        try:
            plaintext = decrypt_document(ciphertext, key)
        except InvalidTag:
            logger.critical(
                'EncryptionService.decrypt_in_memory: Document #%s — '
                'GCM authentication tag invalid. '
                'File may be TAMPERED or wrong key is configured.',
                document_id,
            )
            return None
        except Exception as exc:
            logger.error(
                'EncryptionService.decrypt_in_memory: Decryption failed for Document #%s — %s',
                document_id, exc,
            )
            return None

        logger.info(
            'EncryptionService.decrypt_in_memory: Document #%s decrypted in memory (%d bytes).',
            document_id,
            len(plaintext),
        )

        return plaintext
