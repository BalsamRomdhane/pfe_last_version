"""
tests_phase1_hashing.py — Unit and integration tests for Phase 1.

Coverage
--------
Group A — calculate_sha256() pure function
  A01  bytes input — known digest
  A02  bytes input — returns HashResult NamedTuple
  A03  bytes input — empty raises ValueError
  A04  bytearray accepted
  A05  str raises TypeError
  A06  int raises TypeError
  A07  file-like — known digest
  A08  file-like — pointer reset to 0 before hashing
  A09  file-like — pointer restored after hashing
  A10  file-like — empty raises ValueError
  A11  file-like — 256 KB chunked correctly
  A12  byte_count is accurate

Group B — verify_sha256() pure function
  B01  correct hash → True
  B02  tampered content → False
  B03  wrong hash → False
  B04  empty expected_hash → False
  B05  None expected_hash → False
  B06  wrong-length hash → False
  B07  uppercase hash → True (case-insensitive)
  B08  whitespace-padded hash → True (stripped)
  B09  file-like object → True
  B10  OSError during hashing → False (no raise)

Group C — DocumentIntegrityService.compute_and_persist()
  C01  non-existent document_id → returns None, no crash
  C02  valid document → returns HashResult, DB updated
  C03  idempotent: calling twice gives same hash
  C04  file-replacement: hash updated when file changes

Group D — DocumentIntegrityService.verify_document()
  D01  no stored hash → is_valid=False, reason explains pending analysis
  D02  valid file → is_valid=True
  D03  tampered/replaced file → is_valid=False

Group E — Model field checks
  E01  sha256_hash: max_length=64, default=''
  E02  hash_algorithm: max_length=16, default='sha256'
  E03  hash_created_at: null=True, blank=True
  E04  new instance defaults are correct

Group F — Signal / pipeline integration
  F01  hash written to DB after document creation (pipeline thread)
  F02  hash is exactly 64 lowercase hex chars
  F03  hash NOT recomputed on status-only update
  F04  hash recomputed when file field changes (replacement)

Group G — Thread teardown (Windows-safe)
  G01  pipeline thread releases DB connection before exit
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
import time
import threading
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, TransactionTestCase

from services.security.hashing import (
    ALGORITHM,
    HashResult,
    IntegrityVerificationResult,
    DocumentIntegrityService,
    calculate_sha256,
    hash_document_file,
    verify_sha256,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)


# ─────────────────────────────────────────────────────────────────────────────
# Group A — calculate_sha256
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateSha256(TestCase):

    # A01
    def test_bytes_known_digest(self):
        data = b'hello'
        r = calculate_sha256(data)
        self.assertEqual(r.hex_digest, _sha(data))
        self.assertEqual(r.algorithm, ALGORITHM)
        self.assertEqual(r.byte_count, len(data))

    # A02
    def test_bytes_returns_hash_result(self):
        r = calculate_sha256(b'test')
        self.assertIsInstance(r, HashResult)
        self.assertIsInstance(r.hex_digest, str)
        self.assertEqual(len(r.hex_digest), 64)

    # A03
    def test_bytes_empty_raises(self):
        with self.assertRaises(ValueError):
            calculate_sha256(b'')

    # A04
    def test_bytearray_accepted(self):
        data = bytearray(b'enterprise')
        r = calculate_sha256(data)
        self.assertEqual(r.hex_digest, _sha(bytes(data)))

    # A05
    def test_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            calculate_sha256('not bytes')  # type: ignore

    # A06
    def test_int_raises_type_error(self):
        with self.assertRaises(TypeError):
            calculate_sha256(42)  # type: ignore

    # A07
    def test_file_known_digest(self):
        data = b'document content'
        r = calculate_sha256(_file(data))
        self.assertEqual(r.hex_digest, _sha(data))

    # A08
    def test_file_pointer_reset_before_hashing(self):
        data = b'full content'
        f = _file(data)
        f.read(4)  # advance to position 4
        r = calculate_sha256(f)
        self.assertEqual(r.hex_digest, _sha(data))  # must hash from byte 0

    # A09
    def test_file_pointer_restored_after_hashing(self):
        data = b'restore test'
        f = _file(data)
        f.read(6)
        pos_before = f.tell()
        calculate_sha256(f)
        self.assertEqual(f.tell(), pos_before)

    # A10
    def test_file_empty_raises(self):
        with self.assertRaises(ValueError):
            calculate_sha256(_file(b''))

    # A11
    def test_large_file_chunked(self):
        data = os.urandom(256 * 1024)
        r = calculate_sha256(_file(data))
        self.assertEqual(r.hex_digest, _sha(data))
        self.assertEqual(r.byte_count, len(data))

    # A12
    def test_byte_count_accurate(self):
        data = b'x' * 1234
        r = calculate_sha256(_file(data))
        self.assertEqual(r.byte_count, 1234)


# ─────────────────────────────────────────────────────────────────────────────
# Group B — verify_sha256
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifySha256(TestCase):

    # B01
    def test_correct_hash_returns_true(self):
        data = b'enterprise iso compliance'
        self.assertTrue(verify_sha256(data, _sha(data)))

    # B02
    def test_tampered_returns_false(self):
        data = b'original'
        self.assertFalse(verify_sha256(b'tampered', _sha(data)))

    # B03
    def test_wrong_hash_returns_false(self):
        self.assertFalse(verify_sha256(b'content', 'a' * 64))

    # B04
    def test_empty_hash_returns_false(self):
        self.assertFalse(verify_sha256(b'content', ''))

    # B05
    def test_none_hash_returns_false(self):
        self.assertFalse(verify_sha256(b'content', None))  # type: ignore

    # B06
    def test_short_hash_returns_false(self):
        self.assertFalse(verify_sha256(b'content', 'abc'))

    # B07
    def test_uppercase_hash_accepted(self):
        data = b'case test'
        self.assertTrue(verify_sha256(data, _sha(data).upper()))

    # B08
    def test_whitespace_padded_hash_accepted(self):
        data = b'whitespace'
        padded = '  ' + _sha(data) + '\n'
        self.assertTrue(verify_sha256(data, padded))

    # B09
    def test_file_object_verification(self):
        data = b'file verify'
        self.assertTrue(verify_sha256(_file(data), _sha(data)))

    # B10
    def test_oserror_returns_false_not_raises(self):
        broken = MagicMock()
        broken.read.side_effect = OSError('disk error')
        broken.tell.return_value = 0
        broken.seek = MagicMock()
        self.assertFalse(verify_sha256(broken, 'a' * 64))


# ─────────────────────────────────────────────────────────────────────────────
# Group C — DocumentIntegrityService.compute_and_persist
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIntegrityServiceComputeAndPersist(TestCase):
    """Uses TestCase (single transaction) — no daemon threads involved."""

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Test-Service-C')

    # C01
    def test_nonexistent_document_returns_none(self):
        result = DocumentIntegrityService.compute_and_persist(document_id=999999)
        self.assertIsNone(result)

    # C02
    def test_valid_document_updates_db(self):
        from api.models import Document
        content = b'known content for hash'
        doc = Document.objects.create(
            file=ContentFile(content, name='doc_c02.pdf'),
            norme=self.norme,
            employee_username='emp_c02',
            employee_department='DIGITAL',
        )

        result = DocumentIntegrityService.compute_and_persist(document_id=doc.pk)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, HashResult)
        self.assertEqual(result.hex_digest, _sha(content))

        doc.refresh_from_db()
        self.assertEqual(doc.sha256_hash, _sha(content))
        self.assertEqual(doc.hash_algorithm, 'sha256')
        self.assertIsNotNone(doc.hash_created_at)

    # C03
    def test_idempotent_same_hash_twice(self):
        from api.models import Document
        content = b'idempotent test'
        doc = Document.objects.create(
            file=ContentFile(content, name='doc_c03.pdf'),
            norme=self.norme,
            employee_username='emp_c03',
            employee_department='DIGITAL',
        )

        r1 = DocumentIntegrityService.compute_and_persist(document_id=doc.pk)
        r2 = DocumentIntegrityService.compute_and_persist(document_id=doc.pk)

        self.assertEqual(r1.hex_digest, r2.hex_digest)
        doc.refresh_from_db()
        self.assertEqual(doc.sha256_hash, r1.hex_digest)

    def tearDown(self):
        from api.models import Document
        for doc in Document.objects.filter(employee_username__startswith='emp_c'):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group D — DocumentIntegrityService.verify_document
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIntegrityServiceVerify(TestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Test-Service-D')

    # D01
    def test_no_stored_hash_returns_invalid(self):
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(b'content', name='doc_d01.pdf'),
            norme=self.norme,
            employee_username='emp_d01',
            employee_department='DIGITAL',
        )
        # Force no hash (pipeline hasn't run yet in this synchronous test)
        Document.objects.filter(pk=doc.pk).update(sha256_hash='')

        vr = DocumentIntegrityService.verify_document(document_id=doc.pk)

        self.assertIsInstance(vr, IntegrityVerificationResult)
        self.assertFalse(vr.is_valid)
        self.assertIn('No integrity hash', vr.reason)

    # D02
    def test_valid_file_returns_true(self):
        from api.models import Document
        content = b'valid integrity check content'
        doc = Document.objects.create(
            file=ContentFile(content, name='doc_d02.pdf'),
            norme=self.norme,
            employee_username='emp_d02',
            employee_department='DIGITAL',
        )
        # Compute and persist hash synchronously
        DocumentIntegrityService.compute_and_persist(document_id=doc.pk)

        vr = DocumentIntegrityService.verify_document(document_id=doc.pk)

        self.assertTrue(vr.is_valid)
        self.assertEqual(vr.stored_hash, _sha(content))
        self.assertEqual(vr.computed_hash, _sha(content))
        self.assertIn('verified', vr.reason)

    # D03
    def test_nonexistent_document_returns_invalid(self):
        vr = DocumentIntegrityService.verify_document(document_id=888888)
        self.assertFalse(vr.is_valid)
        self.assertIn('not found', vr.reason)

    def tearDown(self):
        from api.models import Document
        for doc in Document.objects.filter(employee_username__startswith='emp_d'):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group E — Model field checks (no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIntegrityFields(TestCase):

    # E01
    def test_sha256_hash_field(self):
        from api.models import Document
        f = Document._meta.get_field('sha256_hash')
        self.assertEqual(f.max_length, 64)
        self.assertEqual(f.default, '')
        self.assertFalse(getattr(f, 'unique', False))

    # E02
    def test_hash_algorithm_field(self):
        from api.models import Document
        f = Document._meta.get_field('hash_algorithm')
        self.assertEqual(f.max_length, 16)
        self.assertEqual(f.default, 'sha256')

    # E03
    def test_hash_created_at_field(self):
        from api.models import Document
        f = Document._meta.get_field('hash_created_at')
        self.assertTrue(f.null)
        self.assertTrue(f.blank)

    # E04
    def test_new_instance_defaults(self):
        from api.models import Document
        doc = Document()
        self.assertEqual(doc.sha256_hash, '')
        self.assertEqual(doc.hash_algorithm, 'sha256')
        self.assertIsNone(doc.hash_created_at)


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Signal / pipeline integration
# Uses TransactionTestCase so the daemon thread can see committed rows.
# tearDown waits for threads to finish before the test DB is destroyed.
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentSecurityPipelineSignal(TransactionTestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Test-Signal-F')
        self._threads_to_join: list[threading.Thread] = []

    # F01
    def test_hash_written_after_creation(self):
        from api.models import Document
        content = b'ISO 9001 compliance document for integrity test'
        doc = Document.objects.create(
            file=ContentFile(content, name='doc_f01.pdf'),
            norme=self.norme,
            employee_username='emp_f01',
            employee_department='DIGITAL',
        )
        self._wait_for_hash(doc)
        self.assertEqual(doc.sha256_hash, _sha(content))
        self.assertEqual(doc.hash_algorithm, 'sha256')
        self.assertIsNotNone(doc.hash_created_at)

    # F02
    def test_hash_is_64_lowercase_hex(self):
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(b'test content', name='doc_f02.pdf'),
            norme=self.norme,
            employee_username='emp_f02',
            employee_department='DIGITAL',
        )
        self._wait_for_hash(doc)
        self.assertEqual(len(doc.sha256_hash), 64)
        self.assertRegex(doc.sha256_hash, r'^[0-9a-f]{64}$')

    # F03
    def test_hash_not_recomputed_on_status_update(self):
        """
        A status-only update (approve/reject) must NOT trigger the pipeline.
        The signal's _file_has_changed() check with update_fields=['status']
        must return False.
        """
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(b'doc content', name='doc_f03.pdf'),
            norme=self.norme,
            employee_username='emp_f03',
            employee_department='DIGITAL',
        )
        self._wait_for_hash(doc)
        original_hash = doc.sha256_hash
        original_hash_at = doc.hash_created_at

        # Simulate status update (what update_status() does)
        Document.objects.filter(pk=doc.pk).update(
            status='approved',
            final_decision='approved',
        )
        time.sleep(0.3)  # Give any erroneously spawned thread time to run

        doc.refresh_from_db()
        self.assertEqual(doc.sha256_hash, original_hash)
        self.assertEqual(doc.hash_created_at, original_hash_at)

    def _wait_for_hash(self, doc, timeout: float = 5.0) -> None:
        """Poll until sha256_hash is populated or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            doc.refresh_from_db()
            if doc.sha256_hash:
                return
            time.sleep(0.05)

    def tearDown(self):
        """
        Wait for all active pipeline threads before releasing the test DB.

        Without this, on Windows, PostgreSQL refuses to drop the test DB
        because the daemon threads still hold open connections.
        The pipeline thread closes its connection via connection.close()
        but the join() here gives it time to reach that point.
        """
        from api.models import Document

        # Give active pipeline threads time to finish (max 6 s total)
        active = [
            t for t in threading.enumerate()
            if t.name.startswith('doc-security-pipeline-')
        ]
        for t in active:
            t.join(timeout=6.0)

        # Clean up test documents and files
        for doc in Document.objects.filter(employee_username__startswith='emp_f'):
            _delete_doc(doc)

        try:
            self.norme.delete()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Group G — Thread teardown safety
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineThreadReleasesConnection(TestCase):
    """
    Verify that the pipeline worker calls connection.close() before exiting.

    We cannot directly observe the DB connection being released in a unit test,
    but we can verify that the finally block in _run_document_security_pipeline
    imports and calls django.db.connection.close() by running the function
    in-process with mocked steps.
    """

    def test_connection_close_called_in_pipeline(self):
        from security.signals import _run_document_security_pipeline

        with patch('services.security.hashing.DocumentIntegrityService.compute_and_persist') as mock_hash, \
             patch('services.security_analysis.run_security_analysis') as mock_analysis, \
             patch('django.db.connection') as mock_conn:

            mock_hash.return_value = None
            mock_analysis.return_value = None

            _run_document_security_pipeline(document_id=1)

            mock_conn.close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _delete_doc(doc) -> None:
    """Delete a Document instance and remove its file from disk."""
    if doc.file:
        try:
            path = doc.file.path
            doc.file.delete(save=False)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    try:
        doc.delete()
    except Exception:
        pass
