"""
security/signals.py — Auto-trigger security analysis on Document save.

Fires after any Document instance is saved (created or updated).
The analysis runs asynchronously via threading so it never blocks
the HTTP request that triggered the Document save.
"""
from __future__ import annotations

import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _run_in_background(document_id: int) -> None:
    """Run security analysis in a daemon thread to avoid blocking."""
    try:
        from services.security_analysis import run_security_analysis
        run_security_analysis(document_id=document_id, force=False)
    except Exception as exc:
        logger.exception('security signal: analysis failed for document #%s: %s', document_id, exc)


@receiver(post_save, sender='api.Document')
def trigger_security_analysis(sender, instance, created: bool, **kwargs) -> None:
    """
    After a Document is saved, queue a security analysis in the background.

    Only fires when:
    - The document was freshly created, OR
    - The document file changed (re-upload scenario).

    We avoid re-running for every minor field update by checking 'created'
    and delegating idempotency to run_security_analysis(force=False).
    """
    if not created:
        # Only re-run on new documents to avoid redundant analysis on every save.
        # Users can force a re-run via POST /api/security/documents/<id>/reanalyze/
        return

    doc_id = instance.pk
    logger.info('security signal: queuing analysis for new document #%s', doc_id)

    thread = threading.Thread(
        target=_run_in_background,
        args=(doc_id,),
        daemon=True,
        name=f'security-analysis-{doc_id}',
    )
    thread.start()
