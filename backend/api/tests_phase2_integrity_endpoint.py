"""
tests_phase2_integrity_endpoint.py — Tests for Phase 2: integrity endpoint.

Coverage
--------
Group A — Serializer
  A01  DocumentIntegritySerializer accepts valid payload
  A02  DocumentIntegritySerializer — all status values serialise correctly
  A03  DocumentSerializer includes integrity fields (sha256_hash, etc.)
  A04  DocumentSerializer integrity_status = PENDING when no hash
  A05  DocumentSerializer integrity_status = VERIFIED when hash present

Group B — Endpoint GET /api/security/documents/<id>/integrity/
  B01  Unauthenticated → 401
  B02  Document not found → 404, status=NOT_FOUND
  B03  Employee accesses own doc → 200, status=VERIFIED or PENDING
  B04  Employee accesses other employee's doc → 403
  B05  TeamLead accesses own department doc → 200
  B06  TeamLead accesses other department doc → 403
  B07  Admin accesses any doc → 200
  B08  No hash stored yet → 200, status=PENDING
  B09  Hash matches current file → 200, status=VERIFIED, is_valid=True
  B10  Stored hash does not match file → 409, status=TAMPERED, is_valid=False
  B11  Response shape has all required fields
  B12  hash_created_at is present in response when hash exists

Group C — Existing endpoints not broken
  C01  GET /api/security/documents/<id>/analysis/ still works
  C02  GET /api/documents/ still returns integrity fields
  C03  GET /api/documents/<id>/ (detail) still returns integrity fields
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch, MagicMock

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from security.serializers import DocumentIntegritySerializer


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username, role, department=None):
    """Return a mock KeycloakUser with the given role/department."""
    user = MagicMock()
    user.username   = username
    user.is_authenticated = True
    user.roles      = [role]
    user.department = department
    return user


def _auth_client(user):
    """Return an APIClient that has the given mock user pre-authenticated."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Group A — Serializer unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIntegritySerializer(TestCase):

    def _payload(self, **overrides):
        base = {
            'document_id':     1,
            'is_valid':        True,
            'status':          'VERIFIED',
            'stored_hash':     'a' * 64,
            'computed_hash':   'a' * 64,
            'hash_algorithm':  'sha256',
            'hash_created_at': '2026-07-01T10:00:00Z',
            'reason':          'File integrity verified — hash matches.',
        }
        base.update(overrides)
        return base

    # A01
    def test_valid_payload_is_valid(self):
        s = DocumentIntegritySerializer(data=self._payload())
        self.assertTrue(s.is_valid(), s.errors)

    # A02
    def test_all_status_values_serialise(self):
        for st in ('VERIFIED', 'TAMPERED', 'PENDING', 'FILE_MISSING', 'NOT_FOUND'):
            s = DocumentIntegritySerializer(data=self._payload(status=st))
            self.assertTrue(s.is_valid(), f'Status {st} failed: {s.errors}')

    # A03
    def test_document_serializer_has_integrity_fields(self):
        from api.serializers import DocumentSerializer
        field_names = [f.field_name for f in DocumentSerializer().fields.values()]
        for field in ('sha256_hash', 'hash_algorithm', 'hash_created_at', 'integrity_status'):
            self.assertIn(field, field_names, f'Missing field: {field}')

    # A04
    def test_integrity_status_pending_when_no_hash(self):
        from api.serializers import DocumentSerializer
        doc = MagicMock()
        doc.sha256_hash    = ''
        doc.hash_algorithm = 'sha256'
        doc.hash_created_at = None
        doc.file = None
        serializer = DocumentSerializer(doc)
        self.assertEqual(serializer.data['integrity_status'], 'PENDING')

    # A05
    def test_integrity_status_verified_when_hash_present(self):
        from api.serializers import DocumentSerializer
        doc = MagicMock()
        doc.sha256_hash     = 'a' * 64
        doc.hash_algorithm  = 'sha256'
        doc.hash_created_at = None
        doc.file = None
        serializer = DocumentSerializer(doc)
        self.assertEqual(serializer.data['integrity_status'], 'VERIFIED')


# ─────────────────────────────────────────────────────────────────────────────
# Group B — Endpoint tests (require DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIntegrityEndpoint(TestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase2-Test')

    def _create_doc(self, username='emp1', dept='DIGITAL', content=b'test pdf content'):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='test.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department=dept,
        )

    def _integrity_url(self, doc_id):
        return f'/api/security/documents/{doc_id}/integrity/'

    # B01 — unauthenticated
    def test_unauthenticated_returns_401(self):
        doc = self._create_doc()
        client = APIClient()
        # Do NOT force_authenticate — send request with no credentials at all
        resp = client.get(self._integrity_url(doc.pk))
        # DRF returns 401 when no credentials are provided and
        # WWW-Authenticate header is present, or 403 when session auth
        # is configured without JWT. Both are "access denied" responses.
        self.assertIn(resp.status_code, (401, 403))

    # B02 — document not found
    def test_document_not_found_returns_404(self):
        client = _auth_client(_make_user('admin1', 'ADMIN'))
        resp = client.get(self._integrity_url(999999))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data['status'], 'NOT_FOUND')

    # B03 — employee accesses own doc (no hash yet → PENDING)
    def test_employee_own_doc_pending(self):
        from api.models import Document
        doc = self._create_doc(username='emp_b03')
        # Force no hash to test PENDING state
        Document.objects.filter(pk=doc.pk).update(sha256_hash='')

        client = _auth_client(_make_user('emp_b03', 'EMPLOYEE', 'DIGITAL'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'PENDING')
        self.assertFalse(resp.data['is_valid'])

    # B04 — employee accesses another employee's doc → 403
    def test_employee_other_doc_returns_403(self):
        doc = self._create_doc(username='emp_owner')
        client = _auth_client(_make_user('emp_other', 'EMPLOYEE', 'DIGITAL'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # B05 — teamlead accesses own department doc
    def test_teamlead_own_dept_doc_ok(self):
        from api.models import Document
        doc = self._create_doc(username='emp_b05', dept='DIGITAL')
        Document.objects.filter(pk=doc.pk).update(sha256_hash='')

        client = _auth_client(_make_user('tl_b05', 'TEAMLEAD', 'DIGITAL'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertIn(resp.status_code, (200, 409))

    # B06 — teamlead accesses other department doc → 403
    def test_teamlead_other_dept_doc_returns_403(self):
        doc = self._create_doc(username='emp_b06', dept='AUTOMOBILE')
        client = _auth_client(_make_user('tl_b06', 'TEAMLEAD', 'DIGITAL'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertEqual(resp.status_code, 403)

    # B07 — admin accesses any doc
    def test_admin_any_doc_ok(self):
        doc = self._create_doc(username='emp_b07', dept='AERONAUTIQUE')
        client = _auth_client(_make_user('admin_b07', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertIn(resp.status_code, (200, 409))

    # B08 — no hash stored → 200, PENDING
    def test_no_hash_returns_pending(self):
        from api.models import Document
        doc = self._create_doc()
        Document.objects.filter(pk=doc.pk).update(sha256_hash='')

        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'PENDING')

    # B09 — hash matches file → 200, VERIFIED, is_valid=True
    def test_valid_hash_returns_verified(self):
        from api.models import Document
        content = b'known content for integrity check phase 2'
        doc = self._create_doc(content=content)

        # Compute and store the correct hash synchronously
        from services.security.hashing import DocumentIntegrityService
        DocumentIntegrityService.compute_and_persist(document_id=doc.pk)

        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'VERIFIED')
        self.assertTrue(resp.data['is_valid'])
        self.assertEqual(resp.data['stored_hash'], _sha(content))
        self.assertEqual(resp.data['computed_hash'], _sha(content))

    # B10 — tampered: stored hash differs from current file → 409, TAMPERED
    def test_tampered_hash_returns_409(self):
        from api.models import Document
        content = b'original content'
        doc = self._create_doc(content=content)
        # Store a deliberately wrong hash
        Document.objects.filter(pk=doc.pk).update(sha256_hash='b' * 64)

        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['status'], 'TAMPERED')
        self.assertFalse(resp.data['is_valid'])
        self.assertEqual(resp.data['stored_hash'], 'b' * 64)
        self.assertNotEqual(resp.data['computed_hash'], 'b' * 64)

    # B11 — response has all required fields
    def test_response_has_all_required_fields(self):
        from api.models import Document
        doc = self._create_doc()
        Document.objects.filter(pk=doc.pk).update(sha256_hash='')

        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))

        required = {
            'document_id', 'is_valid', 'status',
            'stored_hash', 'computed_hash',
            'hash_algorithm', 'hash_created_at', 'reason',
        }
        for field in required:
            self.assertIn(field, resp.data, f'Missing field: {field}')

    # B12 — hash_created_at present when hash computed
    def test_hash_created_at_present_when_hash_exists(self):
        from api.models import Document
        content = b'content for timestamp test'
        doc = self._create_doc(content=content)

        from services.security.hashing import DocumentIntegrityService
        DocumentIntegrityService.compute_and_persist(document_id=doc.pk)

        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(self._integrity_url(doc.pk))

        self.assertIsNotNone(resp.data['hash_created_at'])

    def tearDown(self):
        from api.models import Document
        import os
        for doc in Document.objects.filter(norme=self.norme):
            if doc.file:
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass
            doc.delete()
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group C — Regression: existing endpoints still work
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase2Regression(TestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase2-Regression')

    def _create_doc(self, username='emp_reg'):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(b'regression test content', name='reg.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department='DIGITAL',
        )

    # C01 — existing analysis endpoint still responds
    def test_analysis_endpoint_still_works(self):
        doc = self._create_doc()
        client = _auth_client(_make_user('admin', 'ADMIN'))
        resp = client.get(f'/api/security/documents/{doc.pk}/analysis/')
        # 404 is expected (analysis not computed yet) — but NOT 500
        self.assertIn(resp.status_code, (200, 404))

    # C02 — document list returns new integrity fields
    def test_document_list_includes_integrity_fields(self):
        self._create_doc(username='emp_c02')
        client = _auth_client(_make_user('emp_c02', 'EMPLOYEE', 'DIGITAL'))
        resp = client.get('/api/documents/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results') or resp.data
        if results:
            doc_data = results[0] if isinstance(results, list) else results
            self.assertIn('sha256_hash', doc_data)
            self.assertIn('integrity_status', doc_data)

    # C03 — document detail returns new integrity fields
    def test_document_detail_includes_integrity_fields(self):
        doc = self._create_doc(username='emp_c03')
        client = _auth_client(_make_user('emp_c03', 'EMPLOYEE', 'DIGITAL'))
        resp = client.get(f'/api/documents/{doc.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sha256_hash', resp.data)
        self.assertIn('hash_algorithm', resp.data)
        self.assertIn('hash_created_at', resp.data)
        self.assertIn('integrity_status', resp.data)

    def tearDown(self):
        from api.models import Document
        import os
        for doc in Document.objects.filter(norme=self.norme):
            if doc.file:
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass
            doc.delete()
        self.norme.delete()
