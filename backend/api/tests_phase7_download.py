"""
tests_phase7_download.py — Tests for Phase 7: secure download + watermark.

Coverage
--------
Group A — WatermarkInfo
  A01  lines contains username, date, time, classification
  A02  single_line contains all key info
  A03  downloaded_at defaults to now (UTC)

Group B — add_watermark() — PDF
  B01  returns bytes (not raises) on valid minimal PDF input
  B02  returns original bytes if input is not a valid PDF (graceful degradation)
  B03  output is larger than input (watermark adds content)

Group C — add_watermark() — DOCX
  C01  returns bytes on valid DOCX input
  C02  returns original bytes on invalid input (graceful degradation)

Group D — add_watermark() — unknown format
  D01  returns original bytes unchanged (no crash)

Group E — Endpoint RBAC GET /api/security/documents/<id>/download/
  E01  Unauthenticated → 401/403
  E02  EMPLOYEE own doc → 200
  E03  EMPLOYEE other doc → 403
  E04  TEAMLEAD own dept → 200
  E05  TEAMLEAD other dept → 403
  E06  ADMIN any doc → 200
  E07  Document not found → 404

Group F — Response headers
  F01  Content-Disposition: attachment
  F02  Cache-Control: no-store
  F03  X-Content-Type-Options: nosniff
  F04  Content-Length header present

Group G — Content
  G01  Plaintext doc body is not empty
  G02  watermark=false returns original bytes unchanged
  G03  No file → 422
  G04  Encrypted doc missing key → 403

Group H — secure_download_url in serializers
  H01  DocumentSerializer includes secure_download_url
  H02  secure_download_url points to /api/security/documents/<id>/download/
  H03  DocumentSecurityAnalysisSerializer includes secure_download_url

Group I — Frontend hook
  I01  useSecureDocumentView hook file exists

Group J — Regression
  J01  GET /api/documents/ returns secure_download_url
  J02  GET /api/security/documents/<id>/view/ still works
  J03  GET /api/security/documents/<id>/integrity/ still works
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _gen_key():
    return os.urandom(32)


def _key_b64(k):
    return base64.urlsafe_b64encode(k).decode()


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


def _download_url(doc_id, **params):
    url = f'/api/security/documents/{doc_id}/download/'
    if params:
        url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
    return url


def _minimal_docx() -> bytes:
    """Return a minimal valid DOCX file as bytes."""
    from docx import Document as DocxDoc
    buf = io.BytesIO()
    doc = DocxDoc()
    doc.add_paragraph('Test document for Phase 7 watermark.')
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _minimal_pdf() -> bytes:
    """Return a minimal valid PDF file as bytes using reportlab."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, 'Phase 7 test document')
    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Group A — WatermarkInfo
# ─────────────────────────────────────────────────────────────────────────────

class TestWatermarkInfo(TestCase):

    def setUp(self):
        from services.security.watermark import WatermarkInfo
        self.WatermarkInfo = WatermarkInfo

    # A01
    def test_lines_contain_key_fields(self):
        wm = self.WatermarkInfo(username='john.doe', classification='CONFIDENTIAL')
        joined = ' '.join(wm.lines)
        self.assertIn('john.doe', joined)
        self.assertIn('CONFIDENTIAL', joined)
        self.assertIn(wm.date_str, joined)
        self.assertIn(wm.time_str, joined)

    # A02
    def test_single_line_contains_all_info(self):
        wm = self.WatermarkInfo(username='alice', classification='RESTRICTED')
        self.assertIn('alice', wm.single_line)
        self.assertIn('RESTRICTED', wm.single_line)

    # A03
    def test_downloaded_at_defaults_to_utc_now(self):
        before = datetime.now(tz=timezone.utc)
        wm = self.WatermarkInfo(username='u')
        after = datetime.now(tz=timezone.utc)
        self.assertGreaterEqual(wm.downloaded_at, before)
        self.assertLessEqual(wm.downloaded_at, after)


# ─────────────────────────────────────────────────────────────────────────────
# Group B — add_watermark() PDF
# ─────────────────────────────────────────────────────────────────────────────

class TestWatermarkPDF(TestCase):

    def setUp(self):
        from services.security.watermark import WatermarkInfo, add_watermark
        self.add_watermark = add_watermark
        self.wm = WatermarkInfo(username='tester', classification='CONFIDENTIAL')

    # B01
    def test_valid_pdf_returns_bytes(self):
        pdf = _minimal_pdf()
        result = self.add_watermark(pdf, 'report.pdf', self.wm)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    # B02
    def test_invalid_pdf_returns_original_bytes(self):
        bad = b'this is not a pdf at all'
        result = self.add_watermark(bad, 'report.pdf', self.wm)
        self.assertEqual(result, bad)  # graceful degradation

    # B03
    def test_watermarked_pdf_larger_than_original(self):
        pdf = _minimal_pdf()
        result = self.add_watermark(pdf, 'report.pdf', self.wm)
        # Watermark adds stamps — result should be larger
        self.assertGreater(len(result), len(pdf))


# ─────────────────────────────────────────────────────────────────────────────
# Group C — add_watermark() DOCX
# ─────────────────────────────────────────────────────────────────────────────

class TestWatermarkDOCX(TestCase):

    def setUp(self):
        from services.security.watermark import WatermarkInfo, add_watermark
        self.add_watermark = add_watermark
        self.wm = WatermarkInfo(username='tester', classification='INTERNAL')

    # C01
    def test_valid_docx_returns_bytes(self):
        docx = _minimal_docx()
        result = self.add_watermark(docx, 'report.docx', self.wm)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    # C02
    def test_invalid_docx_returns_original(self):
        bad = b'not a docx'
        result = self.add_watermark(bad, 'report.docx', self.wm)
        self.assertEqual(result, bad)


# ─────────────────────────────────────────────────────────────────────────────
# Group D — add_watermark() unknown format
# ─────────────────────────────────────────────────────────────────────────────

class TestWatermarkUnknown(TestCase):

    # D01
    def test_unknown_format_returns_original(self):
        from services.security.watermark import WatermarkInfo, add_watermark
        data = b'some text content'
        wm = WatermarkInfo(username='u')
        result = add_watermark(data, 'file.txt', wm)
        self.assertEqual(result, data)


# ─────────────────────────────────────────────────────────────────────────────
# Base for endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

class Phase7Base(TestCase):
    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase7')

    def _doc(self, content=b'test content', username='emp1', dept='DIGITAL', encrypted=False):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='doc.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department=dept,
            encrypted=encrypted,
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
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group E — RBAC
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadRBAC(Phase7Base):

    # E01
    def test_unauthenticated_denied(self):
        doc = self._doc()
        resp = APIClient().get(_download_url(doc.pk))
        self.assertIn(resp.status_code, (401, 403))

    # E02
    def test_employee_own_doc_allowed(self):
        doc = self._doc(username='emp_e02', content=_minimal_pdf())
        resp = _client(_user('emp_e02', 'EMPLOYEE', 'DIGITAL')).get(
            _download_url(doc.pk, watermark='false')
        )
        self.assertEqual(resp.status_code, 200)

    # E03
    def test_employee_other_doc_forbidden(self):
        doc = self._doc(username='emp_owner')
        resp = _client(_user('emp_other', 'EMPLOYEE', 'DIGITAL')).get(_download_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # E04
    def test_teamlead_own_dept_allowed(self):
        doc = self._doc(username='emp_e04', dept='DIGITAL', content=_minimal_pdf())
        resp = _client(_user('tl_e04', 'TEAMLEAD', 'DIGITAL')).get(
            _download_url(doc.pk, watermark='false')
        )
        self.assertEqual(resp.status_code, 200)

    # E05
    def test_teamlead_other_dept_forbidden(self):
        doc = self._doc(username='emp_e05', dept='AUTOMOBILE')
        resp = _client(_user('tl_e05', 'TEAMLEAD', 'DIGITAL')).get(_download_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # E06
    def test_admin_any_doc_allowed(self):
        doc = self._doc(username='emp_e06', dept='AERONAUTIQUE', content=_minimal_pdf())
        resp = _client(_user('admin', 'ADMIN')).get(
            _download_url(doc.pk, watermark='false')
        )
        self.assertEqual(resp.status_code, 200)

    # E07
    def test_not_found_returns_404(self):
        resp = _client(_user('admin', 'ADMIN')).get(_download_url(999999))
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Response headers
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadHeaders(Phase7Base):

    def _get(self, doc):
        return _client(_user('admin', 'ADMIN')).get(
            _download_url(doc.pk, watermark='false')
        )

    # F01
    def test_content_disposition_attachment(self):
        doc = self._doc(content=_minimal_pdf())
        resp = self._get(doc)
        self.assertEqual(resp.status_code, 200)
        disposition = resp.get('Content-Disposition', '')
        self.assertIn('attachment', disposition)

    # F02
    def test_cache_control_no_store(self):
        doc = self._doc(content=_minimal_pdf())
        resp = self._get(doc)
        self.assertIn('no-store', resp.get('Cache-Control', ''))

    # F03
    def test_x_content_type_options_nosniff(self):
        doc = self._doc(content=_minimal_pdf())
        resp = self._get(doc)
        self.assertEqual(resp.get('X-Content-Type-Options'), 'nosniff')

    # F04
    def test_content_length_present(self):
        doc = self._doc(content=_minimal_pdf())
        resp = self._get(doc)
        self.assertIn('Content-Length', resp)


# ─────────────────────────────────────────────────────────────────────────────
# Group G — Content
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadContent(Phase7Base):

    # G01
    def test_body_not_empty(self):
        content = _minimal_pdf()
        doc = self._doc(content=content)
        resp = _client(_user('admin', 'ADMIN')).get(
            _download_url(doc.pk, watermark='false')
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.content), 0)

    # G02
    def test_watermark_false_returns_original_bytes(self):
        content = _minimal_pdf()
        doc = self._doc(content=content)
        resp = _client(_user('admin', 'ADMIN')).get(
            _download_url(doc.pk, watermark='false')
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, content)

    # G03
    def test_no_file_returns_422(self):
        from api.models import Document
        doc = Document.objects.create(
            norme=self.norme,
            employee_username='emp_g03',
            employee_department='DIGITAL',
        )
        resp = _client(_user('admin', 'ADMIN')).get(_download_url(doc.pk))
        self.assertEqual(resp.status_code, 422)

    # G04
    def test_encrypted_missing_key_returns_403(self):
        KEY = _gen_key()
        from services.security.encryption import encrypt_document
        from api.models import Document
        payload = encrypt_document(b'secret', KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_g04',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            resp = _client(_user('admin', 'ADMIN')).get(_download_url(doc.pk))
        self.assertEqual(resp.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# Group H — Serializer fields
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadUrlSerializer(TestCase):

    # H01
    def test_document_serializer_has_secure_download_url(self):
        from api.serializers import DocumentSerializer
        self.assertIn('secure_download_url', DocumentSerializer().fields)

    # H02
    def test_download_url_correct_path(self):
        from api.models import Norme, Document
        norme = Norme.objects.create(name='ISO-H02-Phase7')
        doc = Document.objects.create(
            file=ContentFile(b'x', name='h02.pdf'),
            norme=norme,
            employee_username='emp_h02',
            employee_department='DIGITAL',
        )
        from api.serializers import DocumentSerializer
        data = DocumentSerializer(doc, context={}).data
        self.assertIn(f'/api/security/documents/{doc.pk}/download/', data['secure_download_url'])
        # cleanup
        if doc.file:
            try:
                os.remove(doc.file.path)
            except OSError:
                pass
        doc.delete()
        norme.delete()

    # H03
    def test_analysis_serializer_has_secure_download_url(self):
        from security.serializers import DocumentSecurityAnalysisSerializer
        self.assertIn('secure_download_url', DocumentSecurityAnalysisSerializer().fields)


# ─────────────────────────────────────────────────────────────────────────────
# Group I — Frontend hook
# ─────────────────────────────────────────────────────────────────────────────

class TestFrontendHook(TestCase):

    # I01
    def test_secure_document_view_hook_exists(self):
        hook_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))),
            'frontend', 'src', 'hooks', 'useSecureDocumentView.js',
        )
        self.assertTrue(
            os.path.exists(hook_path),
            f'Hook not found at: {hook_path}',
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group J — Regression
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase7Regression(Phase7Base):

    # J01
    def test_document_list_has_secure_download_url(self):
        doc = self._doc(username='emp_j01')
        resp = _client(_user('emp_j01', 'EMPLOYEE', 'DIGITAL')).get('/api/documents/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results') or resp.data
        if results:
            item = results[0] if isinstance(results, list) else results
            self.assertIn('secure_download_url', item)

    # J02
    def test_view_endpoint_still_works(self):
        doc = self._doc(username='emp_j02')
        resp = _client(_user('admin', 'ADMIN')).get(
            f'/api/security/documents/{doc.pk}/view/'
        )
        self.assertIn(resp.status_code, (200, 422))

    # J03
    def test_integrity_endpoint_still_works(self):
        doc = self._doc(username='emp_j03')
        resp = _client(_user('admin', 'ADMIN')).get(
            f'/api/security/documents/{doc.pk}/integrity/'
        )
        self.assertIn(resp.status_code, (200, 409))
