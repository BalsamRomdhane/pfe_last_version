"""
services/document_storage.py — DocumentStorageService.

Single entry point for all document file I/O.

Motivation
----------
Before Phase 5, file access was scattered across four modules:
  - services/security/hashing.py      document.file.open / .read / .close
  - services/security/encryption.py   document.file.open / .read / .close
                                       open(file_path, 'wb')
  - api/utils.py                       open(file_path, 'rb')
  - services/security_analysis.py     document.file.seek / .read

This service consolidates all file I/O behind one interface so that:
  - Encrypted files are transparently decrypted before any consumer reads them.
  - Consumers never hold a path to a plaintext file on disk.
  - Storage backends (local disk, S3, Azure Blob) can be swapped without
    touching any of the consuming services.

Public API
----------
  DocumentStorageService
    .read_plaintext(document_id)    → bytes | None
    .read_raw(document_id)          → bytes | None
    .write(document_id, data)       → bool
    .delete(document_id)            → bool
    .open_plaintext_stream(doc_id)  → io.BytesIO | None
    .get_filename(document_id)      → str
    .exists(document_id)            → bool

Design principles
-----------------
1. PLAINTEXT NEVER ON DISK
   read_plaintext() decrypts in memory when document.encrypted=True.
   The plaintext bytes returned exist only in the caller's memory.

2. TRANSPARENT ENCRYPTION AWARENESS
   Callers do NOT need to know whether a document is encrypted.
   read_plaintext() always returns the original content.
   read_raw() returns whatever is on disk (may be ciphertext).

3. LAZY IMPORTS
   Django model imports are deferred inside methods to avoid circular
   imports at module load time.

4. FAIL SAFE
   All methods return None / False on error and log the exception.
   They never raise — the caller decides how to handle failures.

5. BACKWARD COMPATIBILITY
   Existing callers (hashing, encryption, security_analysis) are updated
   to use DocumentStorageService, but the public APIs of those services
   remain unchanged.

Extensibility (future phases)
------------------------------
  Phase 6 — Secure view/download endpoints call open_plaintext_stream()
             for streaming responses.
  Phase 8 — AuditService wraps this service to log every read/write/delete.
"""
from __future__ import annotations

import io
import logging
import os

logger = logging.getLogger(__name__)


class DocumentStorageService:
    """
    Centralised document file I/O service.

    All methods are @staticmethod — no instantiation required.
    Call as: DocumentStorageService.read_plaintext(document_id)
    """

    # ── Existence check ───────────────────────────────────────────────────────

    @staticmethod
    def exists(document_id: int) -> bool:
        """
        Return True if the document has a file stored on the backend.

        Does NOT check whether the document is encrypted.
        """
        from api.models import Document
        try:
            doc = Document.objects.get(pk=document_id)
            return bool(doc.file and doc.file.name)
        except Document.DoesNotExist:
            return False
        except Exception as exc:
            logger.error('DocumentStorageService.exists[%s]: %s', document_id, exc)
            return False

    # ── Filename helper ───────────────────────────────────────────────────────

    @staticmethod
    def get_filename(document_id: int) -> str:
        """
        Return the basename of the stored file (e.g. 'report.pdf').

        Returns '' if the document or file does not exist.
        """
        from api.models import Document
        try:
            doc = Document.objects.get(pk=document_id)
            if not doc.file:
                return ''
            return os.path.basename(doc.file.name or '')
        except Document.DoesNotExist:
            return ''
        except Exception as exc:
            logger.error('DocumentStorageService.get_filename[%s]: %s', document_id, exc)
            return ''

    # ── Raw read (ciphertext or plaintext — whatever is on disk) ─────────────

    @staticmethod
    def read_raw(document_id: int) -> bytes | None:
        """
        Read the raw bytes from storage without decryption.

        Used by:
          - hashing.py — hash must be computed on the plaintext BEFORE
            encryption (Phase 1 runs before Phase 4), so the file is still
            plaintext at that point.
          - Phase 8 audit — store a digest of the raw ciphertext.

        Returns
        -------
        bytes  — file content (may be ciphertext if encrypted=True)
        None   — on any error (logged)
        """
        from api.models import Document
        try:
            doc = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('DocumentStorageService.read_raw: Document #%s not found.', document_id)
            return None

        if not doc.file:
            logger.warning('DocumentStorageService.read_raw: Document #%s has no file.', document_id)
            return None

        try:
            doc.file.open('rb')
            try:
                data = doc.file.read()
            finally:
                doc.file.close()
            return data
        except FileNotFoundError:
            logger.error(
                'DocumentStorageService.read_raw: File not found for Document #%s (path=%s).',
                document_id, getattr(doc.file, 'name', '?'),
            )
            return None
        except Exception as exc:
            logger.error('DocumentStorageService.read_raw[%s]: %s', document_id, exc)
            return None

    # ── Plaintext read (decrypt transparently if encrypted) ──────────────────

    @staticmethod
    def read_plaintext(document_id: int) -> bytes | None:
        """
        Read and return the PLAINTEXT content of a document.

        If the document is encrypted (document.encrypted=True), the file is
        decrypted in memory using EncryptionService. The plaintext is NEVER
        written to disk.

        Returns
        -------
        bytes  — original plaintext content
        None   — if the document is missing, unreadable, or decryption fails

        Raises
        ------
        PermissionError  — if the document is encrypted but the key is missing.
                           Callers (views) should translate this to HTTP 403.
        """
        from api.models import Document

        try:
            doc = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error(
                'DocumentStorageService.read_plaintext: Document #%s not found.',
                document_id,
            )
            return None

        if not doc.file:
            logger.warning(
                'DocumentStorageService.read_plaintext: Document #%s has no file.',
                document_id,
            )
            return None

        # ── Encrypted path: delegate to EncryptionService ──────────────────
        if doc.encrypted:
            from services.security.encryption import EncryptionService
            # PermissionError (missing key) is intentionally not caught —
            # views must handle it and return HTTP 403.
            plaintext = EncryptionService.decrypt_in_memory(document_id)
            if plaintext is None:
                logger.error(
                    'DocumentStorageService.read_plaintext: Decryption returned None for #%s.',
                    document_id,
                )
            return plaintext

        # ── Plaintext path: read directly from storage ─────────────────────
        try:
            doc.file.open('rb')
            try:
                data = doc.file.read()
            finally:
                doc.file.close()
            return data
        except FileNotFoundError:
            logger.error(
                'DocumentStorageService.read_plaintext: File not found for Document #%s.',
                document_id,
            )
            return None
        except Exception as exc:
            logger.error('DocumentStorageService.read_plaintext[%s]: %s', document_id, exc)
            return None

    # ── Plaintext stream (for streaming HTTP responses) ───────────────────────

    @staticmethod
    def open_plaintext_stream(document_id: int) -> io.BytesIO | None:
        """
        Return a BytesIO stream of the plaintext content.

        The stream is positioned at byte 0. The stream is backed by an
        in-memory buffer — no plaintext file is created on disk.

        Used by Phase 6 (secure view/download endpoints) for
        StreamingHttpResponse / FileResponse.

        Returns
        -------
        io.BytesIO  — seekable in-memory stream of plaintext
        None        — on any error

        Raises
        ------
        PermissionError  — if encrypted and key is missing (propagated from
                           read_plaintext).
        """
        plaintext = DocumentStorageService.read_plaintext(document_id)
        if plaintext is None:
            return None

        stream = io.BytesIO(plaintext)
        stream.name = DocumentStorageService.get_filename(document_id)
        stream.seek(0)
        return stream

    # ── Write ──────────────────────────────────────────────────────────────────

    @staticmethod
    def write(document_id: int, data: bytes) -> bool:
        """
        Overwrite the document's stored file with ``data``.

        Used by EncryptionService to replace the plaintext with ciphertext
        in one atomic write.

        The file path is read from the Django FileField — the filename/path
        on disk is not changed.

        Returns
        -------
        True   — write succeeded
        False  — on any error (logged)
        """
        from api.models import Document

        try:
            doc = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('DocumentStorageService.write: Document #%s not found.', document_id)
            return False

        if not doc.file:
            logger.warning('DocumentStorageService.write: Document #%s has no file.', document_id)
            return False

        try:
            file_path = doc.file.path
            with open(file_path, 'wb') as fh:
                fh.write(data)
            logger.debug(
                'DocumentStorageService.write: Document #%s — %d bytes written.',
                document_id, len(data),
            )
            return True
        except Exception as exc:
            logger.error('DocumentStorageService.write[%s]: %s', document_id, exc)
            return False

    # ── Delete ─────────────────────────────────────────────────────────────────

    @staticmethod
    def delete(document_id: int) -> bool:
        """
        Delete the document's file from storage.

        This does NOT delete the Document database row.
        Used by admin commands and Phase 8 secure-deletion.

        Returns
        -------
        True   — file deleted (or file did not exist)
        False  — on error (logged)
        """
        from api.models import Document

        try:
            doc = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('DocumentStorageService.delete: Document #%s not found.', document_id)
            return False

        if not doc.file or not doc.file.name:
            return True  # nothing to delete

        try:
            doc.file.delete(save=True)  # save=True updates the field in DB
            logger.info(
                'DocumentStorageService.delete: File deleted for Document #%s.',
                document_id,
            )
            return True
        except Exception as exc:
            logger.error('DocumentStorageService.delete[%s]: %s', document_id, exc)
            return False
