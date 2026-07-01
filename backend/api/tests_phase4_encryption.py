"""
tests_phase4_encryption.py — Tests for Phase 4: AES-256-GCM encryption.

Coverage
--------
Group A — encrypt_document / decrypt_document (pure functions)
  A01  round-trip: encrypt then decrypt returns original plaintext
  A02  different nonce each call (no nonce reuse)
  A03  tampered ciphertext raises InvalidTag
  A04  wrong key raises InvalidTag
  A05  empty plaintext raises ValueError from AESGCM (or encrypts to 0-byte body)
  A06  key wrong length raises ValueError
  A07  payload too short raises ValueError on decrypt
  A08  nonce is first 12 bytes of ciphertext

Group B — EncryptionService.should_encrypt()
  B01  PUBLIC → False
  B02  INTERNAL → False (default, no env var)
  B03  INTERNAL → True when ENCRYPT_INTERNAL_DOCS=True
  B04  CONFIDENTIAL → True
  B05  RESTRICTED → True
  B06  unknown level → False

Group C — EncryptionService.encrypt_if_needed() (requires DB)
  C01  PUBLIC doc → skipped=True, encrypted=False
  C02  CONFIDENTIAL doc, key set → encrypted=True, file replaced
  C03  RESTRICTED doc, key set → encrypted=True
  C04  already encrypted → skipped=True (idempotent)
  C05  no key configured → skipped=True, reason mentions missing key
  C06  document not found → returns None
  C07  Document.encrypted field updated to True after encryption
  C08  Document.encrypted_at field set after encryption
  C09  Document.encrypted_key_id = 'env_key' after encryption

Group D — EncryptionService.decrypt_in_memory() (requires DB)
  D01  non-encrypted doc → returns None (caller reads file directly)
  D02  encrypted doc, key set → returns correct plaintext bytes
  D03  document not found → returns None
  D04  key not set → raises PermissionError
  D05  tampered ciphertext → returns None (InvalidTag caught, logged)

Group E — extract_document_text() integration
  E01  plaintext doc: reads text normally
  E02  encrypted doc: decrypts in memory, extracts text
  E03  encrypted doc, no key: returns empty string (no crash)

Group F — Model fields
  F01  Document.encrypted default is False
  F02  Document.encryption_iv default is ''
  F03  Document.encrypted_at default is None
  F04  Document.encrypted_key_id default is ''

Group G — Serializer exposes encryption fields
  G01  DocumentSerializer includes 'encrypted' field (read-only)
  G02  DocumentSerializer includes 'encrypted_at' field
  G03  DocumentSerializer includes 'encrypted_key_id' field

Group H — Pipeline integration
  H01  pipeline step3 is active (no longer a stub comment)
  H02  regression: existing endpoints not broken after Phase 4
"""
from __future__ import annotations

import base64
import io
import os
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

# ── helpers ──────────────────────────────────────────────────────────────────

def _gen_key() -> bytes:
    """Generate a fresh valid 32-byte AES-256 key."""
    return os.urandom(32)


def _key_b64(key: bytes | None = None) -> str:
    """Return a URL-safe base64 string for use in DOCUMENT_ENCRYPTION_KEY."""
    return base64.urlsafe_b64encode(key or _gen_key()).decode()


def _make_user(username, role, department=None):
    user = MagicMock()
    user.username = username
    user.is_authenticated = True
    user.roles = [role]
    user.department = department
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Group A — pure cryptographic functions
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryptDecryptPure(TestCase):

    def setUp(self):
        from services.security.encryption import encrypt_document, decrypt_document
        self.enc = encrypt_document
        self.dec = decrypt_document

    # A01
    def test_round_trip(self):
        key = _gen_key()
        data = b'ISO 9001 compliance document content'
        payload = self.enc(data, key)
        recovered = self.dec(payload, key)
        self.assertEqual(recovered, data)

    # A02
    def test_different_nonce_each_call(self):
        key = _gen_key()
        data = b'same content'
        p1 = self.enc(data, key)
        p2 = self.enc(data, key)
        self.assertNotEqual(p1.nonce, p2.nonce)
        self.assertNotEqual(p1.ciphertext, p2.ciphertext)

    # A03
    def test_tampered_ciphertext_raises(self):
        from cryptography.exceptions import InvalidTag
        key = _gen_key()
        payload = self.enc(b'original', key)
        # Flip a byte in the ciphertext body (after nonce)
        ct = bytearray(payload.ciphertext)
        ct[20] ^= 0xFF
        from services.security.encryption import EncryptedPayload
        bad = EncryptedPayload(ciphertext=bytes(ct), nonce=payload.nonce)
        with self.assertRaises(InvalidTag):
            self.dec(bad, key)

    # A04
    def test_wrong_key_raises_invalid_tag(self):
        from cryptography.exceptions import InvalidTag
        key1 = _gen_key()
        key2 = _gen_key()
        payload = self.enc(b'secret', key1)
        with self.assertRaises(InvalidTag):
            self.dec(payload, key2)

    # A05
    def test_key_wrong_length_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.enc(b'data', b'tooshort')

    # A06
    def test_payload_too_short_raises(self):
        key = _gen_key()
        from services.security.encryption import EncryptedPayload
        bad = EncryptedPayload(ciphertext=b'\x00' * 5, nonce=b'\x00' * 12)
        with self.assertRaises(ValueError):
            self.dec(bad, key)

    # A07
    def test_nonce_is_first_12_bytes(self):
        key = _gen_key()
        payload = self.enc(b'data', key)
        self.assertEqual(payload.nonce, payload.ciphertext[:12])

    # A08
    def test_decrypt_accepts_raw_bytes(self):
        key = _gen_key()
        data = b'raw bytes decryption test'
        payload = self.enc(data, key)
        recovered = self.dec(payload.ciphertext, key)
        self.assertEqual(recovered, data)


# ─────────────────────────────────────────────────────────────────────────────
# Group B — should_encrypt()
# ─────────────────────────────────────────────────────────────────────────────

class TestShouldEncrypt(TestCase):

    def setUp(self):
        from services.security.encryption import EncryptionService
        self.svc = EncryptionService

    # B01
    def test_public_never_encrypted(self):
        self.assertFalse(self.svc.should_encrypt('PUBLIC'))

    # B02
    def test_internal_false_by_default(self):
        with patch.dict(os.environ, {'ENCRYPT_INTERNAL_DOCS': 'False'}):
            self.assertFalse(self.svc.should_encrypt('INTERNAL'))

    # B03
    def test_internal_true_when_env_set(self):
        with patch.dict(os.environ, {'ENCRYPT_INTERNAL_DOCS': 'True'}):
            self.assertTrue(self.svc.should_encrypt('INTERNAL'))

    # B04
    def test_confidential_always_true(self):
        self.assertTrue(self.svc.should_encrypt('CONFIDENTIAL'))

    # B05
    def test_restricted_always_true(self):
        self.assertTrue(self.svc.should_encrypt('RESTRICTED'))

    # B06
    def test_unknown_level_false(self):
        self.assertFalse(self.svc.should_encrypt('UNKNOWN_LEVEL'))


# ─────────────────────────────────────────────────────────────────────────────
# Group C — EncryptionService.encrypt_if_needed() (DB required)
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryptIfNeeded(TestCase):
    """
    Uses TestCase (single transaction).  The pipeline daemon thread is NOT
    involved here — we call EncryptionService.encrypt_if_needed() directly
    and synchronously to avoid race conditions in unit tests.
    """

    _TEST_KEY = _gen_key()          # stable key for the whole class
    _TEST_KEY_B64 = _key_b64(_TEST_KEY)

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase4-C')

    def _doc(self, content=b'test content', username='emp_c'):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='doc.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department='DIGITAL',
        )

    def _set_analysis(self, doc, level):
        from security.models import DocumentSecurityAnalysis
        DocumentSecurityAnalysis.objects.update_or_create(
            document=doc,
            defaults={'confidentiality_level': level},
        )

    # C01 — PUBLIC → skipped
    def test_public_skipped(self):
        from services.security.encryption import EncryptionService
        doc = self._doc(username='emp_c01')
        self._set_analysis(doc, 'PUBLIC')

        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            # Reset key cache for this test
            import services.security.encryption as enc_mod
            enc_mod._KEY_LOADED = False
            result = EncryptionService.encrypt_if_needed(doc.pk)

        self.assertIsNotNone(result)
        self.assertTrue(result.skipped)
        self.assertFalse(result.encrypted)
        doc.refresh_from_db()
        self.assertFalse(doc.encrypted)

    # C02 — CONFIDENTIAL + key → encrypted
    def test_confidential_encrypted(self):
        from services.security.encryption import EncryptionService
        content = b'confidential iso document payload for encryption test'
        doc = self._doc(content=content, username='emp_c02')
        self._set_analysis(doc, 'CONFIDENTIAL')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.encrypt_if_needed(doc.pk)

        self.assertIsNotNone(result)
        self.assertTrue(result.encrypted)
        self.assertFalse(result.skipped)
        doc.refresh_from_db()
        self.assertTrue(doc.encrypted)

    # C03 — RESTRICTED + key → encrypted
    def test_restricted_encrypted(self):
        from services.security.encryption import EncryptionService
        doc = self._doc(content=b'restricted payload', username='emp_c03')
        self._set_analysis(doc, 'RESTRICTED')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.encrypt_if_needed(doc.pk)

        self.assertTrue(result.encrypted)
        doc.refresh_from_db()
        self.assertTrue(doc.encrypted)

    # C04 — already encrypted → idempotent
    def test_already_encrypted_skipped(self):
        from services.security.encryption import EncryptionService
        from api.models import Document
        doc = self._doc(username='emp_c04')
        self._set_analysis(doc, 'CONFIDENTIAL')
        Document.objects.filter(pk=doc.pk).update(encrypted=True)

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.encrypt_if_needed(doc.pk)

        self.assertTrue(result.skipped)
        self.assertTrue(result.encrypted)

    # C05 — no key → skipped, reason mentions missing key
    def test_no_key_skipped(self):
        from services.security.encryption import EncryptionService
        doc = self._doc(username='emp_c05')
        self._set_analysis(doc, 'CONFIDENTIAL')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.encrypt_if_needed(doc.pk)

        self.assertTrue(result.skipped)
        self.assertFalse(result.encrypted)
        self.assertIn('DOCUMENT_ENCRYPTION_KEY', result.reason)

    # C06 — document not found → None
    def test_document_not_found_returns_none(self):
        from services.security.encryption import EncryptionService
        result = EncryptionService.encrypt_if_needed(999999)
        self.assertIsNone(result)

    # C07 — encrypted field updated
    def test_encrypted_field_updated(self):
        from services.security.encryption import EncryptionService
        from api.models import Document
        doc = self._doc(content=b'payload c07', username='emp_c07')
        self._set_analysis(doc, 'RESTRICTED')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            EncryptionService.encrypt_if_needed(doc.pk)

        doc.refresh_from_db()
        self.assertTrue(doc.encrypted)

    # C08 — encrypted_at set
    def test_encrypted_at_set(self):
        from services.security.encryption import EncryptionService
        from api.models import Document
        doc = self._doc(content=b'payload c08', username='emp_c08')
        self._set_analysis(doc, 'CONFIDENTIAL')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            EncryptionService.encrypt_if_needed(doc.pk)

        doc.refresh_from_db()
        self.assertIsNotNone(doc.encrypted_at)

    # C09 — encrypted_key_id = 'env_key'
    def test_encrypted_key_id_is_env_key(self):
        from services.security.encryption import EncryptionService
        from api.models import Document
        doc = self._doc(content=b'payload c09', username='emp_c09')
        self._set_analysis(doc, 'CONFIDENTIAL')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            EncryptionService.encrypt_if_needed(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.encrypted_key_id, 'env_key')

    def tearDown(self):
        from api.models import Document
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        for doc in Document.objects.filter(norme=self.norme):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group D — decrypt_in_memory() (DB required)
# ─────────────────────────────────────────────────────────────────────────────

class TestDecryptInMemory(TestCase):

    _TEST_KEY = _gen_key()
    _TEST_KEY_B64 = _key_b64(_TEST_KEY)

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase4-D')

    def _encrypted_doc(self, plaintext=b'secret payload'):
        """Create a document with an already-encrypted file on disk."""
        from api.models import Document
        from services.security.encryption import encrypt_document, EncryptionService
        payload = encrypt_document(plaintext, self._TEST_KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_d',
            employee_department='DIGITAL',
            encrypted=True,
            encrypted_key_id='env_key',
        )
        return doc, plaintext

    # D01 — non-encrypted returns None
    def test_non_encrypted_returns_none(self):
        from api.models import Document
        from services.security.encryption import EncryptionService
        doc = Document.objects.create(
            file=ContentFile(b'plain', name='plain.pdf'),
            norme=self.norme,
            employee_username='emp_d01',
            employee_department='DIGITAL',
            encrypted=False,
        )
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.decrypt_in_memory(doc.pk)
        self.assertIsNone(result)

    # D02 — encrypted doc returns correct plaintext
    def test_encrypted_doc_decrypts_correctly(self):
        from services.security.encryption import EncryptionService
        doc, original = self._encrypted_doc(b'confidential content for decryption test')

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.decrypt_in_memory(doc.pk)

        self.assertIsNotNone(result)
        self.assertEqual(result, original)

    # D03 — document not found → None
    def test_not_found_returns_none(self):
        from services.security.encryption import EncryptionService
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.decrypt_in_memory(999999)
        self.assertIsNone(result)

    # D04 — key not set → PermissionError
    def test_no_key_raises_permission_error(self):
        from services.security.encryption import EncryptionService
        doc, _ = self._encrypted_doc()

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            with self.assertRaises(PermissionError):
                EncryptionService.decrypt_in_memory(doc.pk)

    # D05 — tampered ciphertext → None (InvalidTag caught)
    def test_tampered_ciphertext_returns_none(self):
        from api.models import Document
        from services.security.encryption import EncryptionService, encrypt_document
        payload = encrypt_document(b'original', self._TEST_KEY)
        tampered = bytearray(payload.ciphertext)
        tampered[25] ^= 0xFF
        doc = Document.objects.create(
            file=ContentFile(bytes(tampered), name='tampered.pdf'),
            norme=self.norme,
            employee_username='emp_d05',
            employee_department='DIGITAL',
            encrypted=True,
        )

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            result = EncryptionService.decrypt_in_memory(doc.pk)
        self.assertIsNone(result)

    def tearDown(self):
        from api.models import Document
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        for doc in Document.objects.filter(norme=self.norme):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group E — extract_document_text() with encryption awareness
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractDocumentTextEncrypted(TestCase):

    _TEST_KEY = _gen_key()
    _TEST_KEY_B64 = _key_b64(_TEST_KEY)

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase4-E')

    # E01 — plaintext doc: reads text normally (existing behaviour)
    def test_plaintext_doc_reads_normally(self):
        from api.models import Document
        from api.utils import extract_document_text
        # Use a minimal valid DOCX bytes fixture (empty paragraph)
        # Rather than a real DOCX, we verify the non-encrypted path works
        # by mocking extract_text (which is already tested elsewhere).
        doc = Document.objects.create(
            file=ContentFile(b'not a real pdf', name='plain.txt'),
            norme=self.norme,
            employee_username='emp_e01',
            employee_department='DIGITAL',
            encrypted=False,
        )
        # With a fake file content, extract_text will fail gracefully;
        # what matters is that the plaintext path is taken (no decryption).
        with patch('api.utils.extract_text', return_value='extracted text') as mock_ext:
            result = extract_document_text(doc)
        mock_ext.assert_called_once()
        self.assertEqual(result, 'extracted text')

    # E02 — encrypted doc: decrypts in memory, extracts text
    def test_encrypted_doc_decrypts_before_extraction(self):
        from api.models import Document
        from api.utils import extract_document_text
        from services.security.encryption import encrypt_document

        plaintext = b'decrypted document text for extraction'
        payload = encrypt_document(plaintext, self._TEST_KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc.pdf'),
            norme=self.norme,
            employee_username='emp_e02',
            employee_department='DIGITAL',
            encrypted=True,
        )

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': self._TEST_KEY_B64}):
            enc_mod._KEY_LOADED = False
            with patch('api.utils.extract_text', return_value='decrypted text') as mock_ext:
                result = extract_document_text(doc)

        mock_ext.assert_called_once()
        self.assertEqual(result, 'decrypted text')

    # E03 — encrypted doc, no key: returns empty string, no crash
    def test_encrypted_doc_no_key_returns_empty(self):
        from api.models import Document
        from api.utils import extract_document_text
        from services.security.encryption import encrypt_document

        payload = encrypt_document(b'content', self._TEST_KEY)
        doc = Document.objects.create(
            file=ContentFile(payload.ciphertext, name='enc2.pdf'),
            norme=self.norme,
            employee_username='emp_e03',
            employee_department='DIGITAL',
            encrypted=True,
        )

        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        with patch.dict(os.environ, {'DOCUMENT_ENCRYPTION_KEY': ''}):
            enc_mod._KEY_LOADED = False
            result = extract_document_text(doc)

        self.assertEqual(result, '')

    def tearDown(self):
        from api.models import Document
        import services.security.encryption as enc_mod
        enc_mod._KEY_LOADED = False
        for doc in Document.objects.filter(norme=self.norme):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Model field defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryptionModelFields(TestCase):

    def _doc(self):
        from api.models import Document
        return Document()

    # F01
    def test_encrypted_default_false(self):
        from api.models import Document
        f = Document._meta.get_field('encrypted')
        self.assertFalse(f.default)

    # F02
    def test_encryption_iv_default_empty(self):
        from api.models import Document
        f = Document._meta.get_field('encryption_iv')
        self.assertEqual(f.default, '')

    # F03
    def test_encrypted_at_default_none(self):
        from api.models import Document
        f = Document._meta.get_field('encrypted_at')
        self.assertTrue(f.null)
        self.assertTrue(f.blank)

    # F04
    def test_encrypted_key_id_default_empty(self):
        from api.models import Document
        f = Document._meta.get_field('encrypted_key_id')
        self.assertEqual(f.default, '')

    # F05 — instance defaults
    def test_new_instance_defaults(self):
        doc = self._doc()
        self.assertFalse(doc.encrypted)
        self.assertEqual(doc.encryption_iv, '')
        self.assertIsNone(doc.encrypted_at)
        self.assertEqual(doc.encrypted_key_id, '')


# ─────────────────────────────────────────────────────────────────────────────
# Group G — Serializer exposes encryption fields
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryptionSerializerFields(TestCase):

    def _field_names(self):
        from api.serializers import DocumentSerializer
        return list(DocumentSerializer().fields.keys())

    # G01
    def test_serializer_has_encrypted(self):
        self.assertIn('encrypted', self._field_names())

    # G02
    def test_serializer_has_encrypted_at(self):
        self.assertIn('encrypted_at', self._field_names())

    # G03
    def test_serializer_has_encrypted_key_id(self):
        self.assertIn('encrypted_key_id', self._field_names())

    # G04 — encrypted is read-only
    def test_encrypted_is_read_only(self):
        from api.serializers import DocumentSerializer
        field = DocumentSerializer().fields['encrypted']
        self.assertTrue(field.read_only)


# ─────────────────────────────────────────────────────────────────────────────
# Group H — Pipeline & regression
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase4PipelineRegression(TestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase4-H')

    # H01 — pipeline step3 is active (not a stub comment)
    def test_pipeline_step3_is_active(self):
        """Verify the pipeline function actually calls EncryptionService."""
        from security.signals import _run_document_security_pipeline

        with patch('services.security.hashing.DocumentIntegrityService.compute_and_persist') as m1, \
             patch('services.security.classification.ClassificationService.run') as m2, \
             patch('services.security.encryption.EncryptionService.encrypt_if_needed') as m3, \
             patch('services.security_analysis.run_security_analysis') as m4, \
             patch('django.db.connection') as mock_conn:

            m1.return_value = None
            m2.return_value = None
            m3.return_value = None
            m4.return_value = None

            _run_document_security_pipeline(document_id=1)

            # All four steps must have been called
            m1.assert_called_once_with(1)
            m2.assert_called_once_with(1)
            m3.assert_called_once_with(1)
            m4.assert_called_once()
            mock_conn.close.assert_called_once()

    # H02 — regression: existing endpoints still work
    def test_existing_endpoints_not_broken(self):
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(b'regression test', name='reg.pdf'),
            norme=self.norme,
            employee_username='emp_h02',
            employee_department='DIGITAL',
        )
        client = APIClient()
        client.force_authenticate(user=_make_user('admin', 'ADMIN'))

        # Phase 2 integrity endpoint
        resp = client.get(f'/api/security/documents/{doc.pk}/integrity/')
        self.assertIn(resp.status_code, (200, 409))

        # Phase 1 — document list includes encryption fields
        client2 = APIClient()
        client2.force_authenticate(user=_make_user('emp_h02', 'EMPLOYEE', 'DIGITAL'))
        resp2 = client2.get('/api/documents/')
        self.assertEqual(resp2.status_code, 200)
        results = resp2.data.get('results') or resp2.data
        if results:
            item = results[0] if isinstance(results, list) else results
            self.assertIn('encrypted', item)

    def tearDown(self):
        from api.models import Document
        for doc in Document.objects.filter(norme=self.norme):
            _delete_doc(doc)
        self.norme.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper
# ─────────────────────────────────────────────────────────────────────────────

def _delete_doc(doc) -> None:
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
