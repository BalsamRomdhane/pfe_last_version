"""
services/security/hashing.py — SHA-256 document integrity service.

Public API
----------
  calculate_sha256(source)               → HashResult
  verify_sha256(source, expected_hash)   → bool
  hash_document_file(document)           → HashResult | None

  DocumentIntegrityService               ← orchestration class used by signals
    .compute_and_persist(document_id)    → HashResult | None
    .verify_document(document_id)        → IntegrityVerificationResult

Design decisions
----------------
- Uses stdlib `hashlib` only — zero extra dependencies.
- Reads in 8 KB chunks → handles 20 MB documents without full memory load.
- File pointer is always restored after hashing (safe for subsequent readers).
- `verify_sha256` uses `hmac.compare_digest` for constant-time comparison.
- `DocumentIntegrityService` is the single entry point for signal/view code.
  Raw functions are kept public for direct use in tests and future services
  (e.g. EncryptionService verifying content before encrypting).
- NO circular imports: this module only imports from stdlib + django.utils.
  Django model imports are done inside methods (lazy) to avoid app-registry
  issues at module load time.

Extensibility (future phases)
------------------------------
  Phase 3 — ClassificationService will call calculate_sha256 before classifying.
  Phase 4 — EncryptionService will call verify_sha256 before encrypting to ensure
             the file was not modified between upload and encryption.
  Phase 5 — DocumentStorageService will delegate hash operations here.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import logging
from typing import NamedTuple, Union

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
ALGORITHM  = 'sha256'
CHUNK_SIZE = 8 * 1024   # 8 KB — efficient for files up to 20 MB


# ── Result types ──────────────────────────────────────────────────────────────

class HashResult(NamedTuple):
    """Immutable result of a SHA-256 computation."""
    hex_digest: str    # 64-char lowercase hex string
    algorithm:  str    # always 'sha256'
    byte_count: int    # total bytes hashed


class IntegrityVerificationResult(NamedTuple):
    """Result of verifying a document's current file against its stored hash."""
    document_id:    int
    is_valid:       bool    # True = file matches stored hash
    stored_hash:    str     # hash value in the DB
    computed_hash:  str     # hash of the current file on disk
    reason:         str     # human-readable explanation


# ── Core pure functions ───────────────────────────────────────────────────────

def calculate_sha256(source: Union[bytes, bytearray, io.IOBase]) -> HashResult:
    """
    Compute the SHA-256 digest of bytes or a file-like object.

    The file pointer is saved before reading and restored afterwards,
    so subsequent reads by text extractors or encryptors are unaffected.

    Raises
    ------
    TypeError   If source is not bytes, bytearray, or a file-like object.
    ValueError  If source contains zero bytes.
    """
    hasher      = hashlib.sha256()
    total_bytes = 0

    if isinstance(source, (bytes, bytearray)):
        if not source:
            raise ValueError(
                'Cannot hash empty bytes — the document file appears to be empty.'
            )
        hasher.update(source)
        total_bytes = len(source)

    elif hasattr(source, 'read'):
        # Save and reset file pointer
        original_pos = None
        try:
            original_pos = source.tell()
            source.seek(0)
        except (AttributeError, OSError):
            pass  # non-seekable stream — hash from current position

        try:
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                total_bytes += len(chunk)
        finally:
            if original_pos is not None:
                try:
                    source.seek(original_pos)
                except OSError:
                    pass

        if total_bytes == 0:
            raise ValueError(
                'Cannot hash empty file — the document file appears to be empty.'
            )

    else:
        raise TypeError(
            f'Expected bytes, bytearray, or a file-like object; '
            f'got {type(source).__name__}.'
        )

    return HashResult(
        hex_digest=hasher.hexdigest(),
        algorithm=ALGORITHM,
        byte_count=total_bytes,
    )


def verify_sha256(
    source:        Union[bytes, bytearray, io.IOBase],
    expected_hash: str,
) -> bool:
    """
    Verify that a file or bytes matches an expected SHA-256 hash.

    Uses constant-time comparison (hmac.compare_digest) to prevent
    timing-based side-channel attacks.

    Returns False — never raises — on any error, so callers can treat
    a failed read as a tampered or corrupt document.
    """
    if not expected_hash or not isinstance(expected_hash, str):
        logger.warning('verify_sha256: expected_hash is empty or not a string.')
        return False

    expected = expected_hash.strip().lower()

    if len(expected) != 64:
        logger.warning(
            'verify_sha256: expected_hash has length %d (SHA-256 requires 64).',
            len(expected),
        )
        return False

    try:
        result = calculate_sha256(source)
        return hmac.compare_digest(result.hex_digest, expected)
    except Exception as exc:
        logger.error('verify_sha256: hashing failed — %s', exc)
        return False


def hash_document_file(document) -> HashResult | None:
    """
    Hash the file attached to a Django Document instance.

    Phase 5 — Uses DocumentStorageService.read_raw() so that file access
    is centralised. read_raw() returns whatever is physically on disk
    (plaintext before encryption, ciphertext after). Since Phase 1 always
    runs before Phase 4, the hash is always computed on the plaintext.

    Returns None if the file is absent or unreadable.
    """
    if not document.file:
        logger.warning(
            'hash_document_file: Document #%s has no file attached.',
            document.pk,
        )
        return None

    try:
        from services.document_storage import DocumentStorageService
        data = DocumentStorageService.read_raw(document.pk)
        if data is None:
            return None
        return calculate_sha256(data)

    except Exception as exc:
        logger.error(
            'hash_document_file: unexpected error for Document #%s — %s',
            document.pk, exc,
        )
        return None


# ── Service class ─────────────────────────────────────────────────────────────

class DocumentIntegrityService:
    """
    Orchestration class for document integrity operations.

    This is the single entry point used by:
      - security/signals.py  (called from the document security pipeline)
      - security/views.py    (Phase 2 — integrity endpoint)
      - Future: EncryptionService (Phase 4) calls verify_document() before
        encrypting to ensure the file was not modified in transit.

    All methods are @staticmethod so the class can be used without
    instantiation, keeping the signal code simple:
        DocumentIntegrityService.compute_and_persist(document_id)
    """

    @staticmethod
    def compute_and_persist(document_id: int) -> HashResult | None:
        """
        Compute the SHA-256 hash of a document file and write it to the DB.

        Idempotent: calling this multiple times (e.g. after file replacement)
        always updates to the current file state.

        Parameters
        ----------
        document_id : int
            PK of the api.Document to process.

        Returns
        -------
        HashResult if hashing succeeded and DB was updated.
        None if the file is missing or an error occurred.
        """
        from django.utils import timezone
        from api.models import Document

        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error(
                'DocumentIntegrityService: Document #%s not found.',
                document_id,
            )
            return None

        result = hash_document_file(document)
        if result is None:
            logger.warning(
                'DocumentIntegrityService: cannot hash Document #%s '
                '(file missing or unreadable).',
                document_id,
            )
            return None

        # update_fields: touch ONLY the three hash columns to avoid
        # overwriting concurrent writes from the security-analysis thread.
        Document.objects.filter(pk=document_id).update(
            sha256_hash=result.hex_digest,
            hash_algorithm=result.algorithm,
            hash_created_at=timezone.now(),
        )

        logger.info(
            'DocumentIntegrityService: Document #%s — %s=%s… (%d bytes)',
            document_id,
            result.algorithm,
            result.hex_digest[:16],
            result.byte_count,
        )
        return result

    @staticmethod
    def verify_document(document_id: int) -> IntegrityVerificationResult:
        """
        Verify the current file of a document against its stored SHA-256 hash.

        Used by Phase 2 (GET /api/documents/{id}/integrity/) to let TeamLeads
        and Employees confirm that a document has not been tampered with.

        Returns an IntegrityVerificationResult regardless of outcome —
        never raises, so the view can always produce a JSON response.
        """
        from api.models import Document

        # ── Fetch document ────────────────────────────────────────────────────
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            return IntegrityVerificationResult(
                document_id=document_id,
                is_valid=False,
                stored_hash='',
                computed_hash='',
                reason='Document not found.',
            )

        stored_hash = document.sha256_hash or ''

        # ── No stored hash yet ───────────────────────────────────────────────
        if not stored_hash:
            return IntegrityVerificationResult(
                document_id=document_id,
                is_valid=False,
                stored_hash='',
                computed_hash='',
                reason='No integrity hash on record — analysis may still be running.',
            )

        # ── Hash the current file ────────────────────────────────────────────
        result = hash_document_file(document)
        if result is None:
            return IntegrityVerificationResult(
                document_id=document_id,
                is_valid=False,
                stored_hash=stored_hash,
                computed_hash='',
                reason='File not found on storage — document may have been moved.',
            )

        computed_hash = result.hex_digest
        is_valid      = hmac.compare_digest(computed_hash, stored_hash.lower())

        reason = (
            'File integrity verified — hash matches.' if is_valid
            else 'INTEGRITY VIOLATION: current file hash does not match stored hash.'
        )

        return IntegrityVerificationResult(
            document_id=document_id,
            is_valid=is_valid,
            stored_hash=stored_hash,
            computed_hash=computed_hash,
            reason=reason,
        )
