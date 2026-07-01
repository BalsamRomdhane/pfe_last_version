"""
services/security/document_audit.py — Document security audit journal.

Public API
----------
  DocumentAuditService
    .log(action, document_id, username, request, **extra)  → None

  Action constants (mirrors compliance.AuditLog.Action):
    DocumentAuditService.VIEW
    DocumentAuditService.DOWNLOAD
    DocumentAuditService.DECRYPT
    DocumentAuditService.INTEGRITY_CHECK
    DocumentAuditService.ENCRYPT
    DocumentAuditService.SECURITY_ANALYSIS
    DocumentAuditService.CREATE
    DocumentAuditService.DELETE

Design
------
- Wraps `compliance.services.create_audit_log` — reuses the existing
  `compliance.AuditLog` model (entity_type='Document').
- All log calls are fire-and-forget: exceptions are caught and logged to
  the Python logger only. A failed audit write must NEVER block the user.
- IP address and User-Agent are extracted from the DRF request when provided.
- The `extra` dict is stored in `new_value` for full context.
- No Django imports at module level — safe to import anywhere.

Actions logged (Phase 8)
------------------------
  VIEW              — document opened via /view/ endpoint
  DOWNLOAD          — document downloaded via /download/ endpoint
  DECRYPT           — document decrypted in memory (view or download)
  INTEGRITY_CHECK   — /integrity/ endpoint called
  ENCRYPT           — security pipeline encrypted a document
  SECURITY_ANALYSIS — security analysis run on a document
  CREATE            — document uploaded (already logged in api/views.py,
                      this service can log it with security context too)
  DELETE            — document deleted

Each entry stores:
  entity_type  = 'Document'
  entity_id    = str(document_id)
  action       = one of the above
  performed_by = username
  ip_address   = from request (X-Forwarded-For or REMOTE_ADDR)
  user_agent   = from request
  new_value    = {
      'document_id': ...,
      'encrypted': bool,
      'classification': str,
      'result': 'success' | 'denied' | 'error',
      ... extra fields ...
  }

Extensibility
-------------
  Phase 11 — Admin Security Dashboard will query compliance.AuditLog
             filtering entity_type='Document' for the audit history tab.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocumentAuditService:
    """
    Audit service for document security events.

    All methods are @staticmethod — use without instantiation:
        DocumentAuditService.log(DocumentAuditService.VIEW, doc_id, user, request)
    """

    # ── Action constants ──────────────────────────────────────────────────────
    VIEW              = 'VIEW'
    DOWNLOAD          = 'DOWNLOAD'
    DECRYPT           = 'DECRYPT'
    INTEGRITY_CHECK   = 'INTEGRITY_CHECK'
    ENCRYPT           = 'ENCRYPT'
    SECURITY_ANALYSIS = 'SECURITY_ANALYSIS'
    CREATE            = 'CREATE'
    DELETE            = 'DELETE'
    UPDATE            = 'UPDATE'

    @staticmethod
    def log(
        action:      str,
        document_id: int,
        username:    str,
        request=None,
        result:      str = 'success',
        **extra:     Any,
    ) -> None:
        """
        Write a document security audit entry.

        Parameters
        ----------
        action      : str   — one of the action constants above
        document_id : int   — PK of the api.Document
        username    : str   — authenticated user performing the action
        request     : DRF/Django request object (optional, used for IP/UA)
        result      : str   — 'success', 'denied', or 'error' (default: 'success')
        **extra     : Any   — additional context stored in new_value JSON field

        This method NEVER raises — all exceptions are silently logged.
        """
        try:
            # ── Extract request context ───────────────────────────────────────
            ip_address = None
            user_agent = ''
            if request is not None:
                x_fwd = getattr(request, 'META', {}).get('HTTP_X_FORWARDED_FOR')
                if x_fwd:
                    ip_address = x_fwd.split(',')[0].strip()
                else:
                    ip_address = getattr(request, 'META', {}).get('REMOTE_ADDR')
                user_agent = getattr(request, 'META', {}).get('HTTP_USER_AGENT', '')[:512]

            # ── Build context payload ─────────────────────────────────────────
            new_value: dict[str, Any] = {
                'document_id': document_id,
                'result':      result,
            }
            new_value.update(extra)

            # ── Persist via compliance service ────────────────────────────────
            from compliance.models import AuditLog
            AuditLog.objects.create(
                entity_type  = 'Document',
                entity_id    = str(document_id),
                action       = action,
                performed_by = str(username),
                new_value    = new_value,
                ip_address   = ip_address,
                user_agent   = user_agent,
            )

        except Exception as exc:
            logger.warning(
                'DocumentAuditService.log: failed to write audit entry '
                '(action=%s, doc=%s, user=%s) — %s',
                action, document_id, username, exc,
            )

    @staticmethod
    def get_document_history(document_id: int) -> list[dict]:
        """
        Return the full audit history for a document, newest first.

        Used by Phase 11 Admin Security Dashboard.
        Returns a plain list of dicts (no ORM objects) to keep the
        response serialization simple.
        """
        try:
            from compliance.models import AuditLog
            logs = (
                AuditLog.objects
                .filter(entity_type='Document', entity_id=str(document_id))
                .order_by('-performed_at')
                .values(
                    'id', 'action', 'performed_by', 'performed_at',
                    'ip_address', 'new_value', 'reason',
                )
            )
            return list(logs)
        except Exception as exc:
            logger.error(
                'DocumentAuditService.get_document_history: failed for doc #%s — %s',
                document_id, exc,
            )
            return []

    @staticmethod
    def get_recent_actions(
        limit:  int = 100,
        action: Optional[str] = None,
    ) -> list[dict]:
        """
        Return recent document security audit entries (all documents).

        Used by Phase 11 Admin Security Dashboard audit history tab.
        """
        try:
            from compliance.models import AuditLog
            qs = AuditLog.objects.filter(entity_type='Document')
            if action:
                qs = qs.filter(action=action)
            return list(
                qs.order_by('-performed_at')
                .values(
                    'id', 'entity_id', 'action', 'performed_by',
                    'performed_at', 'ip_address', 'new_value',
                )[:limit]
            )
        except Exception as exc:
            logger.error('DocumentAuditService.get_recent_actions failed: %s', exc)
            return []
