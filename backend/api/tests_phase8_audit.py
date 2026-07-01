"""
tests_phase8_audit.py — Tests for Phase 8: Document security audit journal.

Coverage
--------
Group A — DocumentAuditService.log()
  A01  log() writes an AuditLog entry (entity_type=Document)
  A02  action field is stored correctly
  A03  performed_by is stored correctly
  A04  document_id is stored in new_value
  A05  result='success' by default
  A06  extra kwargs are stored in new_value
  A07  ip_address extracted from request X-Forwarded-For
  A08  ip_address extracted from REMOTE_ADDR when no X-Forwarded-For
  A09  exception in log() does not raise (fire-and-forget)
  A10  user_agent extracted from request

Group B — DocumentAuditService.get_document_history()
  B01  returns list of dicts for a document
  B02  returns empty list for unknown document_id
  B03  entries ordered newest first
  B04  only returns entries for the requested document

Group C — DocumentAuditService.get_recent_actions()
  C01  returns entries for all documents
  C02  action filter works

Group D — New action choices in compliance.AuditLog
  D01  VIEW action is a valid choice
  D02  DOWNLOAD action is a valid choice
  D03  DECRYPT action is a valid choice
  D04  INTEGRITY_CHECK action is a valid choice
  D05  ENCRYPT action is a valid choice
  D06  SECURITY_ANALYSIS action is a valid choice

Group E — Audit written by security endpoints
  E01  GET /view/ writes VIEW audit entry
  E02  GET /download/ writes DOWNLOAD audit entry
  E03  GET /integrity/ writes INTEGRITY_CHECK audit entry

Group F — Audit history endpoint
  F01  GET /api/security/documents/<id>/audit/ returns 200 for admin
  F02  GET /api/security/documents/<id>/audit/ returns 403 for other employee
  F03  GET /api/security/documents/<id>/audit/ returns 404 for unknown doc
  F04  response is a list
  F05  after a view action, history contains one VIEW entry

Group G — Regression
  G01  existing endpoints not broken
  G02  existing compliance.AuditLog entries still readable
"""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient

from services.security.document_audit import DocumentAuditService


# ── helpers ──────────────────────────────────────────────────────────────────

def _user(username, role, department=None):
    u = MagicMock()
    u.username = username
    u.is_authenticated = True
    u.roles = [role]
    u.department = department
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _mock_request(ip='10.0.0.1', ua='TestAgent/1.0'):
    r = MagicMock()
    r.META = {'REMOTE_ADDR': ip, 'HTTP_USER_AGENT': ua}
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class Phase8Base(TestCase):
    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase8')

    def _doc(self, content=b'audit test content', username='emp8', dept='DIGITAL'):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='audit.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department=dept,
        )

    def tearDown(self):
        from api.models import Document
        for doc in Document.objects.filter(norme=self.norme):
            if doc.file:
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass
            doc.delete()
        try:
            self.norme.delete()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Group A — DocumentAuditService.log()
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentAuditServiceLog(Phase8Base):

    def _count(self, doc_id, action=None):
        from compliance.models import AuditLog
        qs = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc_id))
        if action:
            qs = qs.filter(action=action)
        return qs.count()

    # A01
    def test_log_creates_audit_entry(self):
        doc = self._doc(username='emp_a01')
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_a01')
        self.assertEqual(self._count(doc.pk), 1)

    # A02
    def test_action_stored_correctly(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a02')
        DocumentAuditService.log(DocumentAuditService.DOWNLOAD, doc.pk, 'emp_a02')
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.action, 'DOWNLOAD')

    # A03
    def test_performed_by_stored(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a03')
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_a03')
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.performed_by, 'emp_a03')

    # A04
    def test_document_id_in_new_value(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a04')
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_a04')
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.new_value.get('document_id'), doc.pk)

    # A05
    def test_result_default_success(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a05')
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_a05')
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.new_value.get('result'), 'success')

    # A06
    def test_extra_kwargs_stored(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a06')
        DocumentAuditService.log(
            DocumentAuditService.VIEW, doc.pk, 'emp_a06',
            encrypted=True, classification='CONFIDENTIAL',
        )
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertTrue(entry.new_value.get('encrypted'))
        self.assertEqual(entry.new_value.get('classification'), 'CONFIDENTIAL')

    # A07
    def test_ip_from_x_forwarded_for(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a07')
        req = MagicMock()
        req.META = {'HTTP_X_FORWARDED_FOR': '203.0.113.5, 10.0.0.1', 'HTTP_USER_AGENT': ''}
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_a07', request=req)
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.ip_address, '203.0.113.5')

    # A08
    def test_ip_from_remote_addr(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a08')
        DocumentAuditService.log(
            DocumentAuditService.VIEW, doc.pk, 'emp_a08',
            request=_mock_request(ip='192.168.1.100'),
        )
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertEqual(entry.ip_address, '192.168.1.100')

    # A09
    def test_exception_does_not_raise(self):
        """log() must be fire-and-forget — never raises."""
        with patch('compliance.models.AuditLog.objects') as mock_mgr:
            mock_mgr.create.side_effect = Exception('DB error')
            # Must NOT raise
            DocumentAuditService.log(DocumentAuditService.VIEW, 999, 'user')

    # A10
    def test_user_agent_extracted(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_a10')
        DocumentAuditService.log(
            DocumentAuditService.VIEW, doc.pk, 'emp_a10',
            request=_mock_request(ua='Mozilla/5.0 (TestBrowser)'),
        )
        entry = AuditLog.objects.filter(entity_type='Document', entity_id=str(doc.pk)).first()
        self.assertIn('Mozilla', entry.user_agent)


# ─────────────────────────────────────────────────────────────────────────────
# Group B — get_document_history()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDocumentHistory(Phase8Base):

    # B01
    def test_returns_list_of_dicts(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_b01')
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='VIEW', performed_by='emp_b01',
        )
        history = DocumentAuditService.get_document_history(doc.pk)
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        self.assertIsInstance(history[0], dict)

    # B02
    def test_empty_for_unknown_document(self):
        history = DocumentAuditService.get_document_history(999999)
        self.assertEqual(history, [])

    # B03
    def test_newest_first_order(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_b03')
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='VIEW', performed_by='emp_b03',
        )
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='DOWNLOAD', performed_by='emp_b03',
        )
        history = DocumentAuditService.get_document_history(doc.pk)
        self.assertGreaterEqual(len(history), 2)
        self.assertGreaterEqual(
            history[0]['performed_at'],
            history[1]['performed_at'],
        )

    # B04
    def test_only_returns_entries_for_this_document(self):
        from compliance.models import AuditLog
        # Write directly via AuditLog.objects.create to stay in the TestCase
        # transaction and avoid any cross-thread visibility issues.
        doc1 = self._doc(username='emp_b04a')
        doc2 = self._doc(username='emp_b04b')

        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc1.pk),
            action='VIEW', performed_by='emp_b04a',
        )
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc2.pk),
            action='DOWNLOAD', performed_by='emp_b04b',
        )

        h1 = DocumentAuditService.get_document_history(doc1.pk)
        view_entries = [e for e in h1 if e.get('action') == 'VIEW']
        doc2_entries = [e for e in h1 if e.get('entity_id') == str(doc2.pk)]

        self.assertGreater(len(view_entries), 0, 'Expected VIEW entry for doc1')
        self.assertEqual(len(doc2_entries), 0, 'doc2 entries must not appear in doc1 history')


# ─────────────────────────────────────────────────────────────────────────────
# Group C — get_recent_actions()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetRecentActions(Phase8Base):

    # C01
    def test_returns_entries_across_documents(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_c01')
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='VIEW', performed_by='emp_c01',
        )
        recent = DocumentAuditService.get_recent_actions()
        self.assertIsInstance(recent, list)
        self.assertGreater(len(recent), 0)

    # C02
    def test_action_filter(self):
        from compliance.models import AuditLog
        doc = self._doc(username='emp_c02')
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='VIEW', performed_by='emp_c02',
        )
        AuditLog.objects.create(
            entity_type='Document', entity_id=str(doc.pk),
            action='DOWNLOAD', performed_by='emp_c02',
        )
        downloads = DocumentAuditService.get_recent_actions(action='DOWNLOAD')
        for entry in downloads:
            self.assertEqual(entry['action'], 'DOWNLOAD')


# ─────────────────────────────────────────────────────────────────────────────
# Group D — New action choices
# ─────────────────────────────────────────────────────────────────────────────

class TestNewActionChoices(TestCase):

    def _valid_choices(self):
        from compliance.models import AuditLog
        return [c[0] for c in AuditLog.action.field.choices]

    def test_view_is_valid(self):       self.assertIn('VIEW',              self._valid_choices())
    def test_download_is_valid(self):   self.assertIn('DOWNLOAD',          self._valid_choices())
    def test_decrypt_is_valid(self):    self.assertIn('DECRYPT',           self._valid_choices())
    def test_integrity_is_valid(self):  self.assertIn('INTEGRITY_CHECK',   self._valid_choices())
    def test_encrypt_is_valid(self):    self.assertIn('ENCRYPT',           self._valid_choices())
    def test_security_is_valid(self):   self.assertIn('SECURITY_ANALYSIS', self._valid_choices())


# ─────────────────────────────────────────────────────────────────────────────
# Group E — Audit written by security endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditWrittenByEndpoints(Phase8Base):

    def _count(self, doc_id, action):
        from compliance.models import AuditLog
        return AuditLog.objects.filter(
            entity_type='Document', entity_id=str(doc_id), action=action
        ).count()

    # E01
    def test_view_endpoint_writes_audit(self):
        from api.models import Norme, Document
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        import io
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, 'Audit test PDF')
        c.save()
        buf.seek(0)
        doc = Document.objects.create(
            file=ContentFile(buf.read(), name='audit_view.pdf'),
            norme=self.norme,
            employee_username='emp_e01',
            employee_department='DIGITAL',
        )
        _client(_user('emp_e01', 'EMPLOYEE', 'DIGITAL')).get(
            f'/api/security/documents/{doc.pk}/view/'
        )
        self.assertGreater(self._count(doc.pk, 'VIEW'), 0)

    # E02
    def test_download_endpoint_writes_audit(self):
        from api.models import Document
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        import io
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, 'Audit download PDF')
        c.save()
        buf.seek(0)
        doc = Document.objects.create(
            file=ContentFile(buf.read(), name='audit_dl.pdf'),
            norme=self.norme,
            employee_username='emp_e02',
            employee_department='DIGITAL',
        )
        _client(_user('emp_e02', 'EMPLOYEE', 'DIGITAL')).get(
            f'/api/security/documents/{doc.pk}/download/?watermark=false'
        )
        self.assertGreater(self._count(doc.pk, 'DOWNLOAD'), 0)

    # E03
    def test_integrity_endpoint_writes_audit(self):
        doc = self._doc(username='emp_e03')
        _client(_user('admin', 'ADMIN')).get(
            f'/api/security/documents/{doc.pk}/integrity/'
        )
        self.assertGreater(self._count(doc.pk, 'INTEGRITY_CHECK'), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Audit history endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditHistoryEndpoint(Phase8Base):

    def _url(self, doc_id):
        return f'/api/security/documents/{doc_id}/audit/'

    # F01
    def test_admin_can_access(self):
        doc = self._doc(username='emp_f01')
        resp = _client(_user('admin', 'ADMIN')).get(self._url(doc.pk))
        self.assertEqual(resp.status_code, 200)

    # F02
    def test_other_employee_forbidden(self):
        doc = self._doc(username='emp_owner')
        resp = _client(_user('emp_other', 'EMPLOYEE', 'DIGITAL')).get(self._url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # F03
    def test_unknown_doc_returns_404(self):
        resp = _client(_user('admin', 'ADMIN')).get(self._url(999999))
        self.assertEqual(resp.status_code, 404)

    # F04
    def test_response_is_list(self):
        doc = self._doc(username='emp_f04')
        resp = _client(_user('admin', 'ADMIN')).get(self._url(doc.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)

    # F05
    def test_history_contains_view_entry_after_viewing(self):
        doc = self._doc(username='emp_f05')
        # Log a VIEW entry directly
        DocumentAuditService.log(DocumentAuditService.VIEW, doc.pk, 'emp_f05')
        resp = _client(_user('admin', 'ADMIN')).get(self._url(doc.pk))
        self.assertEqual(resp.status_code, 200)
        actions = [e.get('action') for e in resp.data]
        self.assertIn('VIEW', actions)


# ─────────────────────────────────────────────────────────────────────────────
# Group G — Regression
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase8Regression(Phase8Base):

    # G01
    def test_existing_endpoints_work(self):
        doc = self._doc(username='emp_g01')
        c = _client(_user('admin', 'ADMIN'))
        self.assertIn(c.get(f'/api/security/documents/{doc.pk}/integrity/').status_code, (200, 409))
        self.assertIn(c.get(f'/api/security/documents/{doc.pk}/analysis/').status_code, (200, 404))

    # G02
    def test_existing_compliance_auditlog_entries_readable(self):
        """Existing compliance.AuditLog entries with old actions must still work."""
        from compliance.models import AuditLog
        entry = AuditLog.objects.create(
            entity_type='Document',
            entity_id='999',
            action='CREATE',
            performed_by='test_user',
        )
        fetched = AuditLog.objects.get(pk=entry.pk)
        self.assertEqual(fetched.action, 'CREATE')
        entry.delete()
