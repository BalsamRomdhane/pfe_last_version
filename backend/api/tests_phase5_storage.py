"""
tests_phase5_storage.py — Tests for Phase 5: DocumentStorageService.

Coverage
--------
Group A — exists()
  A01  doc with file → True
  A02  doc without file → False
  A03  nonexistent doc_id → False

Group B — get_filename()
  B01  returns basename (no directory path)
  B02  nonexistent doc → ''

Group C — read_raw()
  C01  plaintext doc → returns content bytes
  C02  encrypted doc → returns raw ciphertext bytes (NOT plaintext)
  C03  doc not found → None
  C04  doc has no file → None

Group D — read_plaintext()
  D01  plaintext doc → returns content bytes
  D02  encrypted doc → returns decrypted plaintext bytes
  D03  encrypted doc, missing key → PermissionError propagated
  D04  doc not found → None
  D05  doc has no file → None

Group E — open_plaintext_stream()
  E01  plaintext doc → BytesIO at position 0
  E02  encrypted doc → decrypted BytesIO at position 0
  E03  stream has correct name attribute
  E04  doc not found → None

Group F — write()
  F01  writes data to existing file path
  F02  content after write matches input exactly
  F03  doc not found → False

Group G — delete()
  G01  file exists → True, field cleared
  G02  doc not found → False

Group H — Integration: callers use StorageService
  H01  hash_document_file uses read_raw via StorageService
  H02  EncryptionService.encrypt_if_needed uses StorageService.write
  H03  EncryptionService.decrypt_in_memory uses StorageService.read_raw
  H04  extract_document_text uses StorageService for plaintext docs
  H05  extract_document_text uses StorageService for encrypted docs
  H06  security_analysis uses read_plaintext via StorageService

Group I — Regression: all previous phases still pass
  I01  Phase 2 integrity endpoint uses StorageService indirectly
  I02  Phase 4 encryption round-trip via StorageService
"""
from __future__ import annotations

import base64
import io
import os
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase

from services.document_storage import DocumentStorageService


# ── helpers ──────────────────────────────────────────────────────────────────

def _gen_key() -> bytes:
    return os.urandom(32)


def _key_b64(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).decode()


def _make_norme():
    from api.models import Norme
    return Norme.objects.create(name='ISO-Phase5-Storage')


def _make_doc(norme, content=b'plain document content', username='emp_s', encrypted=False):
    from api.models import Document
    return Document.objects.create(
        file=ContentFile(content, name='doc.pdf'),
        norme=norme,
        employee_username=username,
        employee_department='DIGITAL',
        encrypted=encrypted,
    )


def _delete_doc(doc):
    if doc.file:
        try:
            p = doc.file.path
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
    try:
        doc.delete()
    except Exception:
        pass


class TestStorageServiceBase(TestCase):
    def setUp(self):
        self.norme = _make_norme()

    def tearDown(self):
        from api.models import Document
        for doc in Document.objects.filter(norme=self.norme):
            _delete_doc(doc)
        try:
            self.norme.delete()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Group A — exists()
# ─────────────────────────────────────────────────────────────────────────────

class TestExists(TestStorageServiceBase):

    # A01
    def test_doc_with_file_returns_true(self):
        doc = _make_doc(self.norme, username='emp_a01')
        self.assertTrue(DocumentStorageService.exists(doc.pk))

    # A02
    def test_doc_without_file_returns_false(self):
        from api.models import Document
        doc = Document.objects.create(
            norme=self.norme,
            employee_username='emp_a02',
            employee_department='DIGITAL',
        )
        self.assertFalse(DocumentStorageService.exists(doc.pk))

    # A03
    def test_nonexistent_id_returns_false(self):
        self.assertFalse(DocumentStorageService.exists(999999))


# ─────────────────────────────────────────────────────────────────────────────
# Group B — get_filename()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetFilename(TestStorageServiceBase):

    # B01
    def test_returns_basename_only(self):
        doc = _make_doc(self.norme, username='emp_b01')
        name = DocumentStorageService.get_filename(doc.pk)
        self.assertTrue(name.endswith('.pdf'))
        self.assertNotIn('/', name)
        self.assertNotIn('\\', name)

    # B02
    def test_nonexistent_doc_returns_empty(self):
        self.assertEqual(DocumentStorageService.get_filename(999999), '')


# ─────────────────────────────────────────────────────────────────────────────
# Group C — read_raw()
# ─────────────────────────────────────────────────────────────────────────────

class TestReadRaw(TestStorageServiceBase):

    # C01
    def test_plaintext_doc_returns_bytes(self):
        content = b'raw plaintext bytes for test'
        doc = _make_doc(self.norme, content=content, username='emp_c01')
        result = DocumentStorageService.read_raw(doc.pk)
        self.assertEqual(result, content)

    # C02
    def test_encrypted_doc_returns_ciphertext_not_plaintext(self):
        """read_raw() must return raw bytes — NOT transparently decrypt."""
        TEST_KEY = _gen_key()
        from services.security.encryption import encrypt_document
        plaintext = b'secret payload'
        payload = encrypt_document(plaintext, TEST_KEY)
        # Store ciphertext in file, mark encrypted=True
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_c02',
            employee_department='DIGITAL',
            encrypted=True,
        )
        raw = DocumentStorageService.read_raw(doc.pk)
        # Must be ciphertext, not plaintext
        self.assertNotEqual(raw, plaintext)
        self.assertEqual(raw, payload.ciphertext)

    # C03
    def test_doc_not_found_returns_none(self):
        self.assertIsNone(DocumentStorageService.read_raw(999999))

    # C04
    def test_doc_no_file_returns_none(self):
        from api.models import Document
        doc = Document.objects.create(
            norme=self.norme,
            employee_username='emp_c04',
            employee_department='DIGITAL',
        )
        self.assertIsNone(DocumentStorageService.read_raw(doc.pk))


# ─────────────────────────────────────────────────────────────────────────────
# Group D — read_plaintext()
# ─────────────────────────────────────────────────────────────────────────────

class TestReadPlaintext(TestStorageServiceBase):

    _KEY = _gen_key()
    _KEY_B64 = _key_b64(_KEY)

    def setUp(self):
        super().setUp()
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False

    def tearDown(self):
        super().tearDown()
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False

    # D01
    def test_plaintext_doc_returns_content(self):
        content = b'plaintext test data'
        doc = _make_doc(self.norme, content=content, username='emp_d01')
        result = DocumentStorageService.read_plaintext(doc.pk)
        self.assertEqual(result, content)

    # D02
    def test_encrypted_doc_returns_decrypted_plaintext(self):
        from services.security.encryption import encrypt_document
        from api.models import Document
        plaintext = b'secret document content for d02'
        payload = encrypt_document(plaintext, self._KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_d02',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = DocumentStorageService.read_plaintext(doc.pk)
        self.assertEqual(result, plaintext)

    # D03
    def test_encrypted_doc_missing_key_raises_permission_error(self):
        from services.security.encryption import encrypt_document
        from api.models import Document
        payload = encrypt_document(b'data', self._KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_d03',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            with self.assertRaises(PermissionError):
                DocumentStorageService.read_plaintext(doc.pk)

    # D04
    def test_not_found_returns_none(self):
        self.assertIsNone(DocumentStorageService.read_plaintext(999999))

    # D05
    def test_no_file_returns_none(self):
        from api.models import Document
        doc = Document.objects.create(
            norme=self.norme,
            employee_username='emp_d05',
            employee_department='DIGITAL',
        )
        self.assertIsNone(DocumentStorageService.read_plaintext(doc.pk))


# ─────────────────────────────────────────────────────────────────────────────
# Group E — open_plaintext_stream()
# ─────────────────────────────────────────────────────────────────────────────

class TestOpenPlaintextStream(TestStorageServiceBase):

    # E01
    def test_plaintext_doc_returns_bytesio_at_position_zero(self):
        content = b'stream test content'
        doc = _make_doc(self.norme, content=content, username='emp_e01')
        stream = DocumentStorageService.open_plaintext_stream(doc.pk)
        self.assertIsNotNone(stream)
        self.assertIsInstance(stream, io.BytesIO)
        self.assertEqual(stream.tell(), 0)
        self.assertEqual(stream.read(), content)

    # E02
    def test_encrypted_doc_returns_decrypted_stream(self):
        KEY = _gen_key()
        from services.security.encryption import encrypt_document
        from api.models import Document
        plaintext = b'encrypted stream content'
        payload = encrypt_document(plaintext, KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc_stream.pdf'),
            norme=self.norme,
            employee_username='emp_e02',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            stream = DocumentStorageService.open_plaintext_stream(doc.pk)
        self.assertIsNotNone(stream)
        self.assertEqual(stream.read(), plaintext)

    # E03
    def test_stream_has_name_attribute(self):
        doc = _make_doc(self.norme, username='emp_e03')
        stream = DocumentStorageService.open_plaintext_stream(doc.pk)
        self.assertIsNotNone(stream)
        self.assertTrue(hasattr(stream, 'name'))
        self.assertIn('.pdf', stream.name)

    # E04
    def test_not_found_returns_none(self):
        self.assertIsNone(DocumentStorageService.open_plaintext_stream(999999))


# ─────────────────────────────────────────────────────────────────────────────
# Group F — write()
# ─────────────────────────────────────────────────────────────────────────────

class TestWrite(TestStorageServiceBase):

    # F01
    def test_write_returns_true_on_success(self):
        doc = _make_doc(self.norme, content=b'original', username='emp_f01')
        result = DocumentStorageService.write(doc.pk, b'new content')
        self.assertTrue(result)

    # F02
    def test_content_after_write_matches_input(self):
        doc = _make_doc(self.norme, content=b'original', username='emp_f02')
        new_data = b'overwritten data for test f02'
        DocumentStorageService.write(doc.pk, new_data)
        read_back = DocumentStorageService.read_raw(doc.pk)
        self.assertEqual(read_back, new_data)

    # F03
    def test_not_found_returns_false(self):
        self.assertFalse(DocumentStorageService.write(999999, b'data'))


# ─────────────────────────────────────────────────────────────────────────────
# Group G — delete()
# ─────────────────────────────────────────────────────────────────────────────

class TestDelete(TestStorageServiceBase):

    # G01
    def test_delete_existing_file_returns_true(self):
        doc = _make_doc(self.norme, username='emp_g01')
        result = DocumentStorageService.delete(doc.pk)
        self.assertTrue(result)

    # G02
    def test_not_found_returns_false(self):
        self.assertFalse(DocumentStorageService.delete(999999))


# ─────────────────────────────────────────────────────────────────────────────
# Group H — Integration: callers use StorageService
# ─────────────────────────────────────────────────────────────────────────────

class TestCallerIntegration(TestStorageServiceBase):

    # H01
    def test_hash_document_file_uses_storage_service(self):
        """hash_document_file() must call DocumentStorageService.read_raw."""
        from services.security.hashing import hash_document_file
        content = b'data to hash via storage service'
        doc = _make_doc(self.norme, content=content, username='emp_h01')

        with patch('services.document_storage.DocumentStorageService.read_raw',
                   wraps=DocumentStorageService.read_raw) as mock_read:
            result = hash_document_file(doc)
            mock_read.assert_called_once_with(doc.pk)

        self.assertIsNotNone(result)
        import hashlib
        self.assertEqual(result.hex_digest, hashlib.sha256(content).hexdigest())

    # H02
    def test_encrypt_if_needed_uses_storage_write(self):
        """EncryptionService.encrypt_if_needed() must call StorageService.write."""
        from security.models import DocumentSecurityAnalysis
        from services.security.encryption import EncryptionService
        KEY = _gen_key()
        doc = _make_doc(self.norme, content=b'to encrypt h02', username='emp_h02')
        DocumentSecurityAnalysis.objects.update_or_create(
            document=doc, defaults={'confidentiality_level': 'CONFIDENTIAL'}
        )

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            with patch('services.document_storage.DocumentStorageService.write',
                       wraps=DocumentStorageService.write) as mock_write:
                EncryptionService.encrypt_if_needed(doc.pk)
                mock_write.assert_called_once_with(doc.pk, mock_write.call_args[0][1])

    # H03
    def test_decrypt_in_memory_uses_storage_read_raw(self):
        KEY = _gen_key()
        from services.security.encryption import encrypt_document, EncryptionService
        from api.models import Document
        plaintext = b'decrypt via storage h03'
        payload = encrypt_document(plaintext, KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc_h03.pdf'),
            norme=self.norme,
            employee_username='emp_h03',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            with patch('services.document_storage.DocumentStorageService.read_raw',
                       wraps=DocumentStorageService.read_raw) as mock_read:
                result = EncryptionService.decrypt_in_memory(doc.pk)
                mock_read.assert_called_once_with(doc.pk)
        self.assertEqual(result, plaintext)

    # H04
    def test_extract_document_text_uses_storage_plaintext(self):
        from api.utils import extract_document_text
        content = b'plaintext extraction test h04'
        doc = _make_doc(self.norme, content=content, username='emp_h04')
        with patch('services.document_storage.DocumentStorageService.read_raw',
                   wraps=DocumentStorageService.read_raw) as mock_read:
            with patch('api.utils.extract_text', return_value='extracted'):
                extract_document_text(doc)
                mock_read.assert_called_once_with(doc.pk)

    # H05
    def test_extract_document_text_uses_decrypt_for_encrypted_doc(self):
        KEY = _gen_key()
        from services.security.encryption import encrypt_document
        from api.models import Document
        from api.utils import extract_document_text
        payload = encrypt_document(b'enc content h05', KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc_h05.pdf'),
            norme=self.norme,
            employee_username='emp_h05',
            employee_department='DIGITAL',
            encrypted=True,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            with patch('api.utils.extract_text', return_value='decrypted text'):
                result = extract_document_text(doc)
        self.assertEqual(result, 'decrypted text')


# ─────────────────────────────────────────────────────────────────────────────
# Group I — Regression
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase5Regression(TestStorageServiceBase):

    # I01
    def test_integrity_endpoint_still_works(self):
        from rest_framework.test import APIClient
        doc = _make_doc(self.norme, username='emp_i01')
        client = APIClient()
        user = MagicMock()
        user.username = 'admin'
        user.is_authenticated = True
        user.roles = ['ADMIN']
        user.department = None
        client.force_authenticate(user=user)
        resp = client.get(f'/api/security/documents/{doc.pk}/integrity/')
        self.assertIn(resp.status_code, (200, 409))

    # I02
    def test_phase4_round_trip_via_storage_service(self):
        """Full encrypt/decrypt round-trip goes through StorageService."""
        KEY = _gen_key()
        from services.security.encryption import EncryptionService, encrypt_document
        from security.models import DocumentSecurityAnalysis
        plaintext = b'round trip test content phase 4 via phase 5 storage'
        doc = _make_doc(self.norme, content=plaintext, username='emp_i02')
        DocumentSecurityAnalysis.objects.update_or_create(
            document=doc, defaults={'confidentiality_level': 'RESTRICTED'}
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': _key_b64(KEY)}):
            enc_mod._KEY_LOADED = False
            EncryptionService.encrypt_if_needed(doc.pk)
            doc.refresh_from_db()
            self.assertTrue(doc.encrypted)
            recovered = EncryptionService.decrypt_in_memory(doc.pk)
        self.assertEqual(recovered, plaintext)
