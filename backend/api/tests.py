from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models import Norme, Rule, Document, RuleTrainingSample, TrainingSample, DocumentTrainingSample
from api.views import dashboard_stats_api, dataset_stats_api
from ml.dataset_builder import buildTrainingDataset
from ml.train_models import load_dataset


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.norm = Norme.objects.create(name='ISO Dashboard Norm')
        self.rule = Rule.objects.create(norme=self.norm, title='Rule A', description='Rule A desc')

    def test_dashboard_training_samples_use_evidence_repository(self):
        approved_doc = Document.objects.create(
            file='documents/approved.pdf',
            norme=self.norm,
            employee_username='tester-approved',
            status='approved',
        )
        rejected_doc = Document.objects.create(
            file='documents/rejected.pdf',
            norme=self.norm,
            employee_username='tester-rejected',
            status='rejected',
        )

        RuleTrainingSample.objects.create(
            document=approved_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence approved sample',
            label='approved',
            confidence_score=0.9,
        )
        RuleTrainingSample.objects.create(
            document=rejected_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence rejected sample',
            label='rejected',
            confidence_score=0.2,
        )
        RuleTrainingSample.objects.create(
            document=approved_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence pending sample',
            label='pending',
            confidence_score=0.4,
        )

        TrainingSample.objects.create(
            document=approved_doc,
            norm_id=self.norm.id,
            rule_id=self.rule.id,
            standard='ISO Dashboard Norm',
            label='pending',
        )

        request = self.factory.get('/api/dashboard-stats/')
        user = SimpleNamespace(
            is_authenticated=True,
            is_anonymous=False,
            roles=['ADMIN'],
            username='admin',
            department='',
        )
        force_authenticate(request, user=user)

        response = dashboard_stats_api(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_training_samples'], 2)
        self.assertEqual(response.data['total_evidence_samples'], 3)


class DatasetStatsViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.norm = Norme.objects.create(name='ISO Stats Norm')
        self.rule = Rule.objects.create(norme=self.norm, title='Rule A', description='Rule A desc')

    def test_dataset_stats_api_accepts_drf_request_wrapper(self):
        doc = Document.objects.create(file='documents/stats.pdf', norme=self.norm, employee_username='tester', status='approved')
        RuleTrainingSample.objects.create(
            document=doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence sample',
            label='approved',
            confidence_score=0.9,
        )

        request = self.factory.get('/api/dataset-stats/', {'norm_id': self.norm.id})
        user = SimpleNamespace(is_authenticated=True, is_anonymous=False, username='admin', roles=['ADMIN'], department='')
        force_authenticate(request, user=user)

        response = dataset_stats_api(request)

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['total_samples'], 1)

    def test_classification_stats_use_training_samples_not_evidence_rows(self):
        approved_doc = Document.objects.create(
            file='documents/classification-approved.pdf',
            norme=self.norm,
            employee_username='tester-class-approved',
            status='approved',
        )
        rejected_doc = Document.objects.create(
            file='documents/classification-rejected.pdf',
            norme=self.norm,
            employee_username='tester-class-rejected',
            status='rejected',
        )
        TrainingSample.objects.create(
            document=approved_doc,
            norm_id=self.norm.id,
            rule_id=self.rule.id,
            standard=self.norm.name,
            label='approved',
            feature_vector={'rule_a': 1},
            features={'rule_a': 1},
        )
        TrainingSample.objects.create(
            document=rejected_doc,
            norm_id=self.norm.id,
            rule_id=self.rule.id,
            standard=self.norm.name,
            label='rejected',
            feature_vector={'rule_a': 0},
            features={'rule_a': 0},
        )
        RuleTrainingSample.objects.create(
            document=approved_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence row',
            label='approved',
            confidence_score=0.9,
        )
        RuleTrainingSample.objects.create(
            document=rejected_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence row 2',
            label='rejected',
            confidence_score=0.2,
        )
        RuleTrainingSample.objects.create(
            document=approved_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence row 3',
            label='pending',
            confidence_score=0.4,
        )

        request = self.factory.get(
            '/api/dataset-stats/',
            {'norm_id': self.norm.id, 'dataset_type': 'classification'}
        )
        user = SimpleNamespace(
            is_authenticated=True,
            is_anonymous=False,
            username='admin',
            roles=['ADMIN'],
            department='',
        )
        force_authenticate(request, user=user)

        response = dataset_stats_api(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_samples'], 2)
        self.assertEqual(response.data['approved_samples'], 1)
        self.assertEqual(response.data['rejected_samples'], 1)

    def test_document_dataset_stats_use_dedicated_document_training_samples(self):
        doc = Document.objects.create(
            file='documents/documents.pdf',
            norme=self.norm,
            employee_username='tester-doc',
            status='approved',
        )
        DocumentTrainingSample.objects.create(
            document=doc,
            standard=self.norm.name,
            total_rules=1,
            passed_rules=1,
            failed_rules=0,
            compliance_score=100,
            feature_vector=[1],
            label='approved',
        )

        request = self.factory.get(
            '/api/dataset-stats/',
            {'norm_id': self.norm.id, 'dataset_type': 'document'}
        )
        user = SimpleNamespace(
            is_authenticated=True,
            is_anonymous=False,
            username='admin',
            roles=['ADMIN'],
            department='',
        )
        force_authenticate(request, user=user)

        response = dataset_stats_api(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_samples'], 1)
        self.assertEqual(response.data['approved_samples'], 1)
        self.assertEqual(response.data['coverage_rate'], 100.0)


class TrainingDatasetBuilderTests(TestCase):
    def setUp(self):
        self.norm = Norme.objects.create(name='ISO Test Norm')
        self.rule = Rule.objects.create(norme=self.norm, title='Rule A', description='Rule A desc')

    def test_load_dataset_can_force_document_level_source(self):
        doc = Document.objects.create(
            file='documents/doc.pdf',
            norme=self.norm,
            employee_username='tester-doc',
            status='approved',
        )
        TrainingSample.objects.create(
            document=doc,
            norm_id=self.norm.id,
            standard='ISO Test Norm',
            label='approved',
            features={'rule_a': 1},
            feature_vector={'rule_a': 1},
            final_decision='approved',
        )
        RuleTrainingSample.objects.create(
            document=doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence row',
            label='rejected',
            confidence_score=0.2,
        )

        X, y = load_dataset(standard=self.norm.name, source='document')

        self.assertEqual(len(X), 1)
        self.assertEqual(len(y), 1)
        self.assertEqual(int(y[0]), 1)

    def test_build_training_dataset_uses_evidence_repository(self):
        approved_doc = Document.objects.create(
            file='documents/approved.pdf',
            norme=self.norm,
            employee_username='tester-approved',
            status='approved',
        )
        rejected_doc = Document.objects.create(
            file='documents/rejected.pdf',
            norme=self.norm,
            employee_username='tester-rejected',
            status='rejected',
        )

        RuleTrainingSample.objects.create(
            document=approved_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence approved sample',
            label='approved',
            confidence_score=0.9,
            semantic_score=0.8,
            recommendation='ok',
        )
        RuleTrainingSample.objects.create(
            document=rejected_doc,
            norm=self.norm,
            rule=self.rule,
            rule_title='Rule A',
            evidence_text='Evidence rejected sample',
            label='rejected',
            confidence_score=0.2,
            semantic_score=0.1,
            recommendation='fix',
        )

        result = buildTrainingDataset(self.norm.id)

        self.assertTrue(result['success'])
        self.assertEqual(result['statistics']['total_samples'], 2)
        self.assertEqual(result['statistics']['approved_count'], 1)
        self.assertEqual(result['statistics']['rejected_count'], 1)

        self.assertTrue(TrainingSample.objects.filter(document=approved_doc).exists())
        self.assertTrue(TrainingSample.objects.filter(document=rejected_doc).exists())
        self.assertEqual(
            TrainingSample.objects.get(document=approved_doc).label,
            'approved',
        )
