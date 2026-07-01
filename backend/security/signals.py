"""
security/signals.py — Document security pipeline triggered on Document save.

Architecture
------------
A single thread per document runs a sequential pipeline:

    Phase 1  → DocumentIntegrityService.compute_and_persist()  (SHA-256)
    Phase 3  → ClassificationService.run()                     (stub, Phase 3)
    Phase 4  → EncryptionService.encrypt_if_needed()           (stub, Phase 4)
    existing → run_security_analysis()                         (PII/secrets/risk)

Why one thread, not many?
  - Sequential execution guarantees ordering: hash is always computed before
    encryption (Phase 4 needs a valid hash before encrypting).
  - Simpler error handling: one try/except block, one log line per document.
  - Easier to test: mock one function, not three threads.
  - No risk of DB connection pool exhaustion from bursts of parallel threads.

File-replacement detection
  The signal fires on both creation AND update. For updates we only re-run
  the pipeline when the `file` field changed (detected via `update_fields`
  or by comparing the stored file name with the instance's current file name).
  Status-only updates (approve/reject) skip the pipeline entirely.

Thread safety
  `DocumentIntegrityService.compute_and_persist` uses `update_fields` so it
  only writes the three hash columns — no risk of overwriting concurrent writes.
  `run_security_analysis` uses `update_or_create` on DocumentSecurityAnalysis
  which is already safe.

Windows / test teardown
  The worker thread calls `django.db.connection.close()` before exiting so
  PostgreSQL connections are released promptly. This prevents the
  "database is being used by other users" error during test DB teardown.
"""
from __future__ import annotations

import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ── Pipeline worker ───────────────────────────────────────────────────────────

def _run_document_security_pipeline(document_id: int) -> None:
    """
    Sequential security pipeline executed in a background daemon thread.

    Steps
    -----
    1. SHA-256 hash computation and persistence  [Phase 1 — active]
    2. Classification                            [Phase 3 — stub]
    3. Encryption                                [Phase 4 — stub]
    4. Security analysis (PII/secrets/risk)      [existing — active]

    Each step is wrapped individually so a failure in one step does not
    prevent subsequent steps from running.
    """
    try:
        # ── Step 1 : Integrity hash (Phase 1) ────────────────────────────────
        try:
            from services.security.hashing import DocumentIntegrityService
            DocumentIntegrityService.compute_and_persist(document_id)
        except Exception as exc:
            logger.error(
                'pipeline[%s] step1-hash failed: %s', document_id, exc,
            )

        # ── Step 2 : Classification (Phase 3) ────────────────────────────────
        try:
            from services.security.classification import ClassificationService
            ClassificationService.run(document_id)
        except Exception as exc:
            logger.error(
                'pipeline[%s] step2-classification failed: %s', document_id, exc,
            )

        # ── Step 3 : Encryption (Phase 4) ────────────────────────────────────
        try:
            from services.security.encryption import EncryptionService
            EncryptionService.encrypt_if_needed(document_id)
        except Exception as exc:
            logger.error(
                'pipeline[%s] step3-encryption failed: %s', document_id, exc,
            )

        # ── Step 4 : Security analysis (existing) ────────────────────────────
        try:
            from services.security_analysis import run_security_analysis
            run_security_analysis(document_id=document_id, force=False)
        except Exception as exc:
            logger.error(
                'pipeline[%s] step4-security-analysis failed: %s', document_id, exc,
            )

    finally:
        # Release the PostgreSQL connection held by this thread.
        # Without this, Django keeps the connection open until the thread
        # is garbage-collected, which prevents test DB teardown on Windows.
        try:
            from django.db import connection
            connection.close()
        except Exception:
            pass


# ── File-change detection helper ─────────────────────────────────────────────

def _file_has_changed(instance, created: bool, update_fields) -> bool:
    """
    Determine whether the document pipeline should run for this save event.

    Rules
    -----
    - Always run on creation.
    - On update: run only if the `file` field changed.
      Detection strategy (in order of reliability):
        1. `update_fields` is provided and contains 'file' → definitive.
        2. `update_fields` is provided and does NOT contain 'file' → skip.
        3. `update_fields` is None (full save): compare instance.file.name
           with the name stored in the DB to detect an actual file swap.
    """
    if created:
        return True

    if update_fields is not None:
        return 'file' in update_fields

    # Full save with no update_fields hint — query the DB for the old name
    try:
        from api.models import Document
        old = Document.objects.filter(pk=instance.pk).values_list('file', flat=True).first()
        current = instance.file.name if instance.file else ''
        return old != current
    except Exception:
        # If we cannot determine whether the file changed, be conservative
        # and run the pipeline (better a redundant hash than a stale one).
        return True


# ── Signal receiver ───────────────────────────────────────────────────────────

@receiver(post_save, sender='api.Document')
def trigger_document_security_pipeline(
    sender,
    instance,
    created: bool,
    update_fields=None,
    **kwargs,
) -> None:
    """
    Single entry point: after a Document is saved, launch the security pipeline.

    Fires on:
      - Document creation   (new upload by Employee)
      - Document file swap  (admin replaces the file)

    Does NOT fire on:
      - Status updates (approve/reject) — no file change, no pipeline needed.
      - Teamlead username assignment    — irrelevant to security pipeline.
    """
    if not _file_has_changed(instance, created, update_fields):
        return

    doc_id = instance.pk
    event  = 'created' if created else 'file-replaced'
    logger.info(
        'security pipeline: queuing for Document #%s (%s)',
        doc_id, event,
    )

    thread = threading.Thread(
        target=_run_document_security_pipeline,
        args=(doc_id,),
        daemon=True,
        name=f'doc-security-pipeline-{doc_id}',
    )
    thread.start()
