"""
tests_phase6_secure_view.py — Tests for Phase 6: secure document view endpoint.

Coverage
--------
Group A — RBAC
  A01  Unauthenticated → 401/403
  A02  EMPLOYEE own doc → 200
  A03  EMPLOYEE other doc → 403
  A04  TEAMLEAD own dept doc → 200
  A05  TEAMLEAD other dept doc → 403
  A06  ADMIN any doc → 200
  A07  Document not found → 404

Group B — Response headers and content type
  B01  PDF doc → Content-Type: application/pdf
  B02  Content-Disposition: inline (not attachment)
  B03  Cache-Control: no-store (no browser caching)
  B04  X-Content-Type-Options: nosniff

Group C — Content correctness
  C01  Plaintext doc: response body = original file bytes
  C02  Encrypted doc: response body = decrypted plaintext (not ciphertext)
  C03  No file attached → 422

Group D — Encrypted document security
  D01  Missing encryption key → 403 (not 500)
  D02  Plaintext never written to disk during encrypted view

Group E — secure_view_url in serializer
  E01  DocumentSerializer includes secure_view_url field
  E02  secure_view_url points to /api/security/documents/<id>/view/
  E03  DocumentSecurityAnalysisSerializer includes secure_view_url

Group F — Regression: existing endpoints not broken
  F01  GET /api/documents/ still returns secure_view_url
  F02  GET /api/security/documents/<id>/integrity/ still works
  F03  GET /api/security/documents/<id>/analysis/ still works
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _gen_key() -> bytes:
    return os.urandom(32)


def _key_b64(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).decode()


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


def _view_url(doc_id):
    return f'/api/security/documents/{doc_id}/view/'


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class Phase6Base(TestCase):
    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase6')

    def _doc(self, content=b'test pdf content', username='emp1',
             dept='DIGITAL', encrypted=False):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='test.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department=dept,
            encrypted=encrypted,
        )

    def tearDown(self):
        from api.models import Document
        import os as _os
        for doc in Document.objects.filter(norme=self.norme):
            if doc.file:
                try:
                    _os.remove(doc.file.path)
                except OSError:
                    pass
            doc.delete()
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group A — RBAC
# ─────────────────────────────────────────────────────────────────────────────

class TestSecureViewRBAC(Phase6Base):

    # A01
    def test_unauthenticated_denied(self):
        doc = self._doc()
        resp = APIClient().get(_view_url(doc.pk))
        self.assertIn(resp.status_code, (401, 403))

    # A02
    def test_employee_own_doc_allowed(self):
        doc = self._doc(username='emp_a02')
        resp = _client(_user('emp_a02', 'EMPLOYEE', 'DIGITAL')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 200)

    # A03
    def test_employee_other_doc_forbidden(self):
        doc = self._doc(username='emp_owner')
        resp = _client(_user('emp_other', 'EMPLOYEE', 'DIGITAL')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # A04
    def test_teamlead_own_dept_allowed(self):
        doc = self._doc(username='emp_a04', dept='DIGITAL')
        resp = _client(_user('tl_a04', 'TEAMLEAD', 'DIGITAL')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 200)

    # A05
    def test_teamlead_other_dept_forbidden(self):
        doc = self._doc(username='emp_a05', dept='AUTOMOBILE')
        resp = _client(_user('tl_a05', 'TEAMLEAD', 'DIGITAL')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # A06
    def test_admin_any_doc_allowed(self):
        doc = self._doc(username='emp_a06', dept='AERONAUTIQUE')
        resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 200)

    # A07
    def test_not_found(self):
        resp = _client(_user('admin', 'ADMIN')).get(_view_url(999999))
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Group B — Response headers
# ─────────────────────────────────────────────────────────────────────────────

class TestSecureViewHeaders(Phase6Base):

    def _get(self, doc):
        return _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))

    # B01
    def test_pdf_content_type(self):
        doc = self._doc(content=b'%PDF-1.4 content')
        resp = self._get(doc)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/pdf', resp.get('Content-Type', ''))

    # B02
    def test_content_disposition_inline(self):
        doc = self._doc()
        resp = self._get(doc)
        disposition = resp.get('Content-Disposition', '')
        self.assertIn('inline', disposition)
        self.assertNotIn('attachment', disposition)

    # B03
    def test_cache_control_no_store(self):
        doc = self._doc()
        resp = self._get(doc)
        cache = resp.get('Cache-Control', '')
        self.assertIn('no-store', cache)

    # B04
    def test_x_content_type_options_nosniff(self):
        doc = self._doc()
        resp = self._get(doc)
        self.assertEqual(resp.get('X-Content-Type-Options'), 'nosniff')


# ─────────────────────────────────────────────────────────────────────────────
# Group C — Content correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestSecureViewContent(Phase6Base):

    # C01
    def test_plaintext_body_matches_original(self):
        content = b'original document bytes for phase 6'
        doc = self._doc(content=content)
        resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b''.join(resp.streaming_content), content)

    # C02
    def test_encrypted_doc_serves_plaintext(self):
        KEY = _gen_key()
        from services.security.encryption import encrypt_document
        from api.models import Document
        plaintext = b'secret encrypted content for secure view test'
        payload = encrypt_document(plaintext, KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_c02',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))

        self.assertEqual(resp.status_code, 200)
        served = b''.join(resp.streaming_content)
        self.assertEqual(served, plaintext)
        self.assertNotEqual(served, payload.ciphertext)

    # C03
    def test_no_file_returns_422(self):
        from api.models import Document
        doc = Document.objects.create(
            norme=self.norme,
            employee_username='emp_c03',
            employee_department='DIGITAL',
        )
        resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))
        self.assertEqual(resp.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Group D — Encrypted document security
# ─────────────────────────────────────────────────────────────────────────────

class TestSecureViewEncryptedSecurity(Phase6Base):

    # D01
    def test_missing_key_returns_403_not_500(self):
        from services.security.encryption import encrypt_document
        from api.models import Document
        KEY = _gen_key()
        payload = encrypt_document(b'secret data', KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_d01',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))
        # Must be 403, NOT 500
        self.assertEqual(resp.status_code, 403)

    # D02
    def test_plaintext_not_written_to_disk(self):
        """The decrypted content must never appear as a new file on disk."""
        KEY = _gen_key()
        from services.security.encryption import encrypt_document
        from api.models import Document
        from services.document_storage import DocumentStorageService
        plaintext = b'never on disk test d02'
        payload = encrypt_document(plaintext, KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc_d02.pdf'),
            norme=self.norme,
            employee_username='emp_d02',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False

        files_before = set()
        media_dir = os.path.join('media', 'documents')
        if os.path.exists(media_dir):
            for root, dirs, files in os.walk(media_dir):
                for f in files:
                    files_before.add(os.path.join(root, f))

        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            resp = _client(_user('admin', 'ADMIN')).get(_view_url(doc.pk))
            # consume streaming content
            b''.join(resp.streaming_content)

        files_after = set()
        if os.path.exists(media_dir):
            for root, dirs, files in os.walk(media_dir):
                for f in files:
                    files_after.add(os.path.join(root, f))

        new_files = files_after - files_before
        self.assertEqual(
            new_files, set(),
            msg=f'New file(s) appeared on disk after secure view: {new_files}',
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group E — secure_view_url in serializers
# ─────────────────────────────────────────────────────────────────────────────

class TestSecureViewUrl(Phase6Base):

    # E01
    def test_document_serializer_has_secure_view_url(self):
        from api.serializers import DocumentSerializer
        self.assertIn('secure_view_url', DocumentSerializer().fields)

    # E02
    def test_secure_view_url_correct_path(self):
        from api.serializers import DocumentSerializer
        doc = self._doc(username='emp_e02')
        data = DocumentSerializer(doc, context={}).data
        self.assertIn(f'/api/security/documents/{doc.pk}/view/', data['secure_view_url'])

    # E03
    def test_analysis_serializer_has_secure_view_url(self):
        from security.serializers import DocumentSecurityAnalysisSerializer
        self.assertIn('secure_view_url', DocumentSecurityAnalysisSerializer().fields)


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Regression
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase6Regression(Phase6Base):

    # F01
    def test_document_list_includes_secure_view_url(self):
        doc = self._doc(username='emp_f01')
        resp = _client(_user('emp_f01', 'EMPLOYEE', 'DIGITAL')).get('/api/documents/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results') or resp.data
        if results:
            item = results[0] if isinstance(results, list) else results
            self.assertIn('secure_view_url', item)

    # F02
    def test_integrity_endpoint_still_works(self):
        doc = self._doc(username='emp_f02')
        resp = _client(_user('admin', 'ADMIN')).get(
            f'/api/security/documents/{doc.pk}/integrity/'
        )
        self.assertIn(resp.status_code, (200, 409))

    # F03
    def test_analysis_endpoint_still_works(self):
        doc = self._doc(username='emp_f03')
        resp = _client(_user('admin', 'ADMIN')).get(
            f'/api/security/documents/{doc.pk}/analysis/'
        )
        self.assertIn(resp.status_code, (200, 404))
