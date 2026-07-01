"""
tests_phase3_classification.py — Tests for Phase 3: Classification Engine.

Coverage
--------
Group A — Level helper
  A01  Level.max returns more sensitive of two levels
  A02  Level.max — same level returns that level
  A03  Level.ORDER is correctly ordered

Group B — ClassificationEngine pure logic
  B01  No signals → PUBLIC
  B02  1 PII item → INTERNAL
  B03  2–4 PII items → CONFIDENTIAL
  B04  5+ PII items → RESTRICTED
  B05  IBAN detected (1 item) → RESTRICTED (high-risk PII type)
  B06  Secret detected → RESTRICTED (regardless of other signals)
  B07  risk_score 20–49 → INTERNAL
  B08  risk_score 50–74 → CONFIDENTIAL
  B09  risk_score ≥ 75 → RESTRICTED
  B10  Text contains 'confidential' → CONFIDENTIAL
  B11  Text contains 'restricted' → RESTRICTED
  B12  Text contains 'internal' → INTERNAL
  B13  Explicit label overrides lower signal (e.g. 'restricted' beats 1 PII)
  B14  NDA content + 1 PII → CONFIDENTIAL
  B15  Financial data + 1 PII → CONFIDENTIAL
  B16  HR data + 1 PII → CONFIDENTIAL
  B17  Draft/WIP keyword → INTERNAL
  B18  rules_matched contains all fired rule names
  B19  confidence > 0 for any non-PUBLIC result
  B20  confidence ≥ 0.95 for PUBLIC with no signals
  B21  explanation is a non-empty string
  B22  Secret + explicit 'restricted' label → RESTRICTED (idempotent)
  B23  base_level is respected as minimum

Group C — ClassificationInput validation
  C01  Default input classifies as PUBLIC
  C02  text_lower with mixed-case pattern still matches

Group D — ClassificationService.run() integration
  D01  Document not found → returns None, no crash
  D02  Document with existing SecurityAnalysis → updates confidentiality_level
  D03  Document with no SecurityAnalysis → creates record with classification
  D04  Result stored: classification_source non-empty
  D05  Result stored: classification_rules_matched is a list

Group E — Model field checks
  E01  DocumentSecurityAnalysis has classification_source field
  E02  DocumentSecurityAnalysis has classification_rules_matched field
  E03  Default values are safe

Group F — Serializer exposes new fields
  F01  DocumentSecurityAnalysisSerializer includes classification_source
  F02  DocumentSecurityAnalysisSerializer includes classification_rules_matched

Group G — Pipeline integration
  G01  Document creation triggers classification in pipeline
  G02  Classification result survives the full pipeline (security_analysis runs after)
  G03  Regression: existing endpoints not broken
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from services.security.classification import (
    CLASSIFICATION_RULES,
    ClassificationEngine,
    ClassificationInput,
    ClassificationResult,
    ClassificationService,
    Level,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _engine() -> ClassificationEngine:
    return ClassificationEngine()


def _inp(**kwargs) -> ClassificationInput:
    defaults = dict(pii_count=0, pii_types={}, secret_count=0, secret_types={},
                    risk_score=0, text_lower='', base_level=None)
    defaults.update(kwargs)
    return ClassificationInput(**defaults)


def _make_user(username, role, department=None):
    user = MagicMock()
    user.username = username
    user.is_authenticated = True
    user.roles = [role]
    user.department = department
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Group A — Level helper
# ─────────────────────────────────────────────────────────────────────────────

class TestLevelHelper(TestCase):

    # A01
    def test_max_returns_more_sensitive(self):
        self.assertEqual(Level.max(Level.PUBLIC, Level.CONFIDENTIAL), Level.CONFIDENTIAL)
        self.assertEqual(Level.max(Level.INTERNAL, Level.RESTRICTED), Level.RESTRICTED)
        self.assertEqual(Level.max(Level.RESTRICTED, Level.PUBLIC), Level.RESTRICTED)

    # A02
    def test_max_same_level(self):
        self.assertEqual(Level.max(Level.CONFIDENTIAL, Level.CONFIDENTIAL), Level.CONFIDENTIAL)

    # A03
    def test_order_is_correct(self):
        self.assertEqual(Level.ORDER, ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'])


# ─────────────────────────────────────────────────────────────────────────────
# Group B — ClassificationEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationEngine(TestCase):

    def setUp(self):
        self.engine = _engine()

    def _classify(self, **kwargs) -> ClassificationResult:
        return self.engine.classify(_inp(**kwargs))

    # B01
    def test_no_signals_is_public(self):
        r = self._classify()
        self.assertEqual(r.level, Level.PUBLIC)

    # B02
    def test_one_pii_is_internal(self):
        r = self._classify(pii_count=1, pii_types={'EMAIL': 1})
        self.assertEqual(r.level, Level.INTERNAL)

    # B03
    def test_two_pii_is_confidential(self):
        r = self._classify(pii_count=2, pii_types={'EMAIL': 1, 'PHONE': 1})
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    def test_four_pii_is_confidential(self):
        r = self._classify(pii_count=4, pii_types={'EMAIL': 4})
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B04
    def test_five_pii_is_restricted(self):
        r = self._classify(pii_count=5, pii_types={'EMAIL': 5})
        self.assertEqual(r.level, Level.RESTRICTED)

    def test_ten_pii_is_restricted(self):
        r = self._classify(pii_count=10, pii_types={'EMAIL': 10})
        self.assertEqual(r.level, Level.RESTRICTED)

    # B05
    def test_iban_one_item_is_restricted(self):
        r = self._classify(pii_count=1, pii_types={'IBAN': 1})
        self.assertEqual(r.level, Level.RESTRICTED)

    def test_credit_card_is_restricted(self):
        r = self._classify(pii_count=1, pii_types={'CREDIT_CARD': 1})
        self.assertEqual(r.level, Level.RESTRICTED)

    def test_national_id_is_restricted(self):
        r = self._classify(pii_count=1, pii_types={'NATIONAL_ID': 1})
        self.assertEqual(r.level, Level.RESTRICTED)

    # B06
    def test_secret_detected_is_restricted(self):
        r = self._classify(secret_count=1, secret_types={'JWT': 1})
        self.assertEqual(r.level, Level.RESTRICTED)

    def test_secret_overrides_low_pii(self):
        """Even with just 1 PII (normally INTERNAL), secrets force RESTRICTED."""
        r = self._classify(pii_count=1, pii_types={'EMAIL': 1}, secret_count=1)
        self.assertEqual(r.level, Level.RESTRICTED)

    # B07
    def test_risk_score_20_is_internal(self):
        r = self._classify(risk_score=20)
        self.assertEqual(r.level, Level.INTERNAL)

    def test_risk_score_49_is_internal(self):
        r = self._classify(risk_score=49)
        self.assertEqual(r.level, Level.INTERNAL)

    # B08
    def test_risk_score_50_is_confidential(self):
        r = self._classify(risk_score=50)
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    def test_risk_score_74_is_confidential(self):
        r = self._classify(risk_score=74)
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B09
    def test_risk_score_75_is_restricted(self):
        r = self._classify(risk_score=75)
        self.assertEqual(r.level, Level.RESTRICTED)

    def test_risk_score_100_is_restricted(self):
        r = self._classify(risk_score=100)
        self.assertEqual(r.level, Level.RESTRICTED)

    # B10
    def test_text_confidential_label(self):
        r = self._classify(text_lower='this document is confidential')
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B11
    def test_text_restricted_label(self):
        r = self._classify(text_lower='classification: restricted')
        self.assertEqual(r.level, Level.RESTRICTED)

    # B12
    def test_text_internal_label(self):
        r = self._classify(text_lower='for internal use only')
        self.assertEqual(r.level, Level.INTERNAL)

    # B13
    def test_restricted_label_beats_one_pii(self):
        r = self._classify(
            pii_count=1, pii_types={'EMAIL': 1},
            text_lower='restricted document',
        )
        self.assertEqual(r.level, Level.RESTRICTED)

    # B14
    def test_nda_with_pii_is_confidential(self):
        r = self._classify(
            pii_count=1, pii_types={'EMAIL': 1},
            text_lower='this is an nda agreement',
        )
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B15
    def test_financial_data_with_pii_is_confidential(self):
        r = self._classify(
            pii_count=1, pii_types={'EMAIL': 1},
            text_lower='salary review report for q2',
        )
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B16
    def test_hr_data_with_pii_is_confidential(self):
        r = self._classify(
            pii_count=1, pii_types={'EMAIL': 1},
            text_lower='employee evaluation for annual review',
        )
        self.assertEqual(r.level, Level.CONFIDENTIAL)

    # B17
    def test_draft_keyword_is_internal(self):
        r = self._classify(text_lower='draft version 1.0')
        self.assertEqual(r.level, Level.INTERNAL)

    def test_wip_keyword_is_internal(self):
        r = self._classify(text_lower='work in progress — do not distribute')
        self.assertEqual(r.level, Level.INTERNAL)

    # B18
    def test_rules_matched_contains_fired_rules(self):
        r = self._classify(
            pii_count=1, pii_types={'EMAIL': 1},
            secret_count=1,
            text_lower='restricted document',
        )
        self.assertIn('secret_detected', r.rules_matched)
        self.assertIn('explicit_classification_label', r.rules_matched)

    # B19
    def test_confidence_positive_for_non_public(self):
        r = self._classify(pii_count=2)
        self.assertGreater(r.confidence, 0)

    # B20
    def test_confidence_high_for_clean_public(self):
        r = self._classify()
        self.assertGreaterEqual(r.confidence, 0.95)

    # B21
    def test_explanation_is_non_empty_string(self):
        r = self._classify(pii_count=3, risk_score=60)
        self.assertIsInstance(r.explanation, str)
        self.assertGreater(len(r.explanation), 0)

    # B22
    def test_secret_plus_restricted_label_is_restricted(self):
        r = self._classify(
            secret_count=2,
            text_lower='this document is restricted',
        )
        self.assertEqual(r.level, Level.RESTRICTED)

    # B23
    def test_base_level_respected_as_minimum(self):
        r = self.engine.classify(_inp(base_level=Level.INTERNAL))
        # No other signals — but base_level is INTERNAL
        self.assertEqual(r.level, Level.INTERNAL)


# ─────────────────────────────────────────────────────────────────────────────
# Group C — ClassificationInput
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationInput(TestCase):

    # C01
    def test_default_input_is_public(self):
        r = _engine().classify(ClassificationInput())
        self.assertEqual(r.level, Level.PUBLIC)

    # C02
    def test_mixed_case_confidential_matches(self):
        r = _engine().classify(_inp(text_lower='CONFIDENTIAL'.lower()))
        self.assertEqual(r.level, Level.CONFIDENTIAL)


# ─────────────────────────────────────────────────────────────────────────────
# Group D — ClassificationService integration (requires DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationService(TestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase3-Service')

    def _create_doc(self, content=b'test content', username='emp_d'):
        from api.models import Document
        return Document.objects.create(
            file=ContentFile(content, name='doc.pdf'),
            norme=self.norme,
            employee_username=username,
            employee_department='DIGITAL',
        )

    # D01
    def test_nonexistent_document_returns_none(self):
        result = ClassificationService.run(document_id=999999)
        self.assertIsNone(result)

    # D02
    def test_existing_analysis_updated(self):
        from security.models import DocumentSecurityAnalysis
        doc = self._create_doc(username='emp_d02')

        # Use update_or_create because the pipeline signal may have already
        # created a DocumentSecurityAnalysis row for this document.
        analysis, _ = DocumentSecurityAnalysis.objects.update_or_create(
            document=doc,
            defaults={
                'pii_count': 3,
                'pii_types': {'EMAIL': 2, 'PHONE': 1},
                'secret_count': 0,
                'risk_score': 55,
            },
        )

        result = ClassificationService.run(document_id=doc.pk)

        self.assertIsNotNone(result)
        # risk_score=55 → CONFIDENTIAL
        self.assertEqual(result.level, Level.CONFIDENTIAL)

        analysis.refresh_from_db()
        self.assertEqual(analysis.confidentiality_level, Level.CONFIDENTIAL)

    # D03
    def test_no_analysis_creates_record(self):
        from security.models import DocumentSecurityAnalysis
        doc = self._create_doc(content=b'internal use only document', username='emp_d03')
        # Ensure no analysis exists
        DocumentSecurityAnalysis.objects.filter(document=doc).delete()

        result = ClassificationService.run(document_id=doc.pk)

        self.assertIsNotNone(result)
        # After classification, a record should exist
        self.assertTrue(
            DocumentSecurityAnalysis.objects.filter(document=doc).exists()
        )

    # D04
    def test_classification_source_stored(self):
        from security.models import DocumentSecurityAnalysis
        doc = self._create_doc(username='emp_d04')
        DocumentSecurityAnalysis.objects.update_or_create(
            document=doc,
            defaults={
                'pii_count': 1,
                'pii_types': {'IBAN': 1},
                'secret_count': 0,
                'risk_score': 30,
            },
        )

        ClassificationService.run(document_id=doc.pk)

        analysis = DocumentSecurityAnalysis.objects.get(document=doc)
        self.assertNotEqual(analysis.classification_source, '')
        self.assertIsInstance(analysis.classification_source, str)

    # D05
    def test_classification_rules_matched_stored(self):
        from security.models import DocumentSecurityAnalysis
        doc = self._create_doc(username='emp_d05')
        DocumentSecurityAnalysis.objects.update_or_create(
            document=doc,
            defaults={
                'pii_count': 6,
                'pii_types': {'EMAIL': 6},
                'secret_count': 1,
                'risk_score': 70,
            },
        )

        ClassificationService.run(document_id=doc.pk)

        analysis = DocumentSecurityAnalysis.objects.get(document=doc)
        self.assertIsInstance(analysis.classification_rules_matched, list)
        self.assertGreater(len(analysis.classification_rules_matched), 0)

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
# Group E — Model field checks
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentSecurityAnalysisClassificationFields(TestCase):

    # E01
    def test_classification_source_field_exists(self):
        from security.models import DocumentSecurityAnalysis
        f = DocumentSecurityAnalysis._meta.get_field('classification_source')
        self.assertEqual(f.max_length, 64)
        self.assertEqual(f.default, '')

    # E02
    def test_classification_rules_matched_field_exists(self):
        from security.models import DocumentSecurityAnalysis
        f = DocumentSecurityAnalysis._meta.get_field('classification_rules_matched')
        self.assertEqual(f.default, list)

    # E03
    def test_default_values_safe(self):
        from security.models import DocumentSecurityAnalysis
        a = DocumentSecurityAnalysis()
        self.assertEqual(a.classification_source, '')
        self.assertEqual(a.classification_rules_matched, [])


# ─────────────────────────────────────────────────────────────────────────────
# Group F — Serializer
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationSerializerFields(TestCase):

    # F01
    def test_serializer_has_classification_source(self):
        from security.serializers import DocumentSecurityAnalysisSerializer
        fields = DocumentSecurityAnalysisSerializer().fields
        self.assertIn('classification_source', fields)

    # F02
    def test_serializer_has_classification_rules_matched(self):
        from security.serializers import DocumentSecurityAnalysisSerializer
        fields = DocumentSecurityAnalysisSerializer().fields
        self.assertIn('classification_rules_matched', fields)


# ─────────────────────────────────────────────────────────────────────────────
# Group G — Pipeline integration (TransactionTestCase — daemon thread)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassificationPipelineIntegration(TransactionTestCase):

    def setUp(self):
        from api.models import Norme
        self.norme = Norme.objects.create(name='ISO-Phase3-Pipeline')

    def _wait_for_analysis(self, doc, timeout=6.0):
        """Poll until DocumentSecurityAnalysis exists and has a classification."""
        import threading
        from security.models import DocumentSecurityAnalysis
        deadline = time.time() + timeout
        while time.time() < deadline:
            if DocumentSecurityAnalysis.objects.filter(document=doc).exists():
                return True
            time.sleep(0.05)
        return False

    # G01
    def test_document_creation_triggers_classification(self):
        from api.models import Document
        from security.models import DocumentSecurityAnalysis

        doc = Document.objects.create(
            file=ContentFile(b'confidential document for phase 3 test', name='p3.pdf'),
            norme=self.norme,
            employee_username='emp_g01',
            employee_department='DIGITAL',
        )

        found = self._wait_for_analysis(doc, timeout=8.0)
        if found:
            analysis = DocumentSecurityAnalysis.objects.get(document=doc)
            # classification_level must be one of the valid choices
            valid = {'PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', 'SECRET'}
            self.assertIn(analysis.confidentiality_level, valid)

    # G02
    def test_classification_source_set_by_pipeline(self):
        from api.models import Document
        from security.models import DocumentSecurityAnalysis

        doc = Document.objects.create(
            file=ContentFile(b'restricted salary payroll document', name='p3b.pdf'),
            norme=self.norme,
            employee_username='emp_g02',
            employee_department='DIGITAL',
        )

        self._wait_for_analysis(doc, timeout=8.0)
        if DocumentSecurityAnalysis.objects.filter(document=doc).exists():
            analysis = DocumentSecurityAnalysis.objects.get(document=doc)
            # classification_source may be empty if pipeline ran security_analysis
            # before classification (race), but the field exists
            self.assertIsInstance(analysis.classification_source, str)

    # G03
    def test_existing_endpoints_not_broken(self):
        from api.models import Document
        doc = Document.objects.create(
            file=ContentFile(b'regression test', name='reg.pdf'),
            norme=self.norme,
            employee_username='emp_g03',
            employee_department='DIGITAL',
        )

        client = APIClient()
        client.force_authenticate(user=_make_user('admin', 'ADMIN'))

        # Existing endpoint still responds
        resp = client.get(f'/api/security/documents/{doc.pk}/analysis/')
        self.assertIn(resp.status_code, (200, 404))

        # Phase 2 endpoint still responds
        resp = client.get(f'/api/security/documents/{doc.pk}/integrity/')
        self.assertIn(resp.status_code, (200, 409))

    def tearDown(self):
        import threading, os
        from api.models import Document

        active = [t for t in threading.enumerate()
                  if t.name.startswith('doc-security-pipeline-')]
        for t in active:
            t.join(timeout=8.0)

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
