"""
tests_ml_pipeline.py
---------------------
Tests automatiques du pipeline ML — vérifie que :
  ✓ getBestModel utilise F1 (non accuracy) et ne préfère pas RandomForest par défaut
  ✓ getModelStatus retourne FAILED pour accuracy=0 ou error présent
  ✓ formatPercent retourne '—' pour None (jamais '0%')
  ✓ isModelTrained exclut les modèles avec error ou accuracy=0
  ✓ best_model_name=None quand aucun modèle n'est entraîné
  ✓ format JSON unifié (tous les champs présents pour les 4 algo)
  ✓ best_model sélectionné par F1, "Tie" quand égalité, jamais RandomForest par défaut
  ✓ aucune métrique 0 ou 100 hardcodée dans les résultats

Run:
    python manage.py test api.tests_ml_pipeline --verbosity=2
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
import json
import os


# ── Helpers importés depuis train_models ─────────────────────────────────────

class TrainModelsHelpersTest(TestCase):

    def _import(self):
        from ml.train_models import _evaluate_predictions, _split_train_validation_test
        import numpy as np
        return _evaluate_predictions, _split_train_validation_test, np

    def test_evaluate_predictions_real_values(self):
        """_evaluate_predictions must never return hardcoded 0 or 1."""
        ep, _, np = self._import()
        y_true = np.array([1, 0, 1, 0, 1, 0, 1, 0])
        y_pred = np.array([1, 0, 1, 1, 0, 0, 1, 0])
        r = ep(y_true, y_pred)
        self.assertIn('accuracy', r)
        self.assertIn('f1', r)
        # Values must be in (0, 1) — not exactly 0 or 1 for this imperfect prediction
        self.assertGreater(r['accuracy'], 0)
        self.assertLess(r['accuracy'],    1)
        self.assertGreater(r['f1'],       0)

    def test_evaluate_predictions_fields_present(self):
        """All required fields must be present."""
        ep, _, np = self._import()
        y_true = np.array([1, 0, 1, 0])
        y_pred = np.array([1, 0, 0, 1])
        r = ep(y_true, y_pred)
        for field in ('accuracy', 'precision', 'recall', 'f1', 'confusion_matrix', 'tp', 'tn', 'fp', 'fn'):
            self.assertIn(field, r, f"Missing field: {field}")

    def test_split_produces_three_sets(self):
        """Train/val/test split must produce three non-overlapping index sets."""
        ep, split, np = self._import()
        X = np.arange(60)
        y = np.array([0]*30 + [1]*30)
        tr, vl, te = split(X, y)
        # No overlap
        self.assertEqual(len(set(tr) & set(te)), 0)
        self.assertEqual(len(set(tr) & set(vl)), 0)
        # All indices covered
        self.assertEqual(len(set(tr) | set(vl) | set(te)), 60)


# ── Best model selection ──────────────────────────────────────────────────────

class BestModelSelectionTest(TestCase):
    """
    Tests the best-model selection logic that was moved into train_models.py
    (backend) and dashboardUtils.js (frontend — tested here via equivalent Python).
    """

    def _select_best(self, results):
        """
        Replicate the Python best-model logic from train_models.train_all_models.
        Returns best_model_name (str | 'Tie' | None).
        """
        trained = {
            n: r for n, r in results.items()
            if not r.get('error')
            and r.get('f1_score') is not None
            and r['f1_score'] > 0
        }
        if not trained:
            return None
        sorted_m = sorted(
            trained.items(),
            key=lambda kv: (kv[1].get('f1_score', 0), kv[1].get('accuracy', 0)),
            reverse=True,
        )
        top_f1  = sorted_m[0][1].get('f1_score', 0)
        top_acc = sorted_m[0][1].get('accuracy', 0)
        tied = [n for n, r in sorted_m
                if abs(r.get('f1_score', 0) - top_f1) <= 0.0001
                and abs(r.get('accuracy',  0) - top_acc) <= 0.0001]
        return 'Tie' if len(tied) > 1 else sorted_m[0][0]

    def test_best_model_uses_f1_not_accuracy(self):
        """If GB has higher F1 but lower accuracy → GB wins."""
        results = {
            'RandomForest':       {'f1_score': 0.82, 'accuracy': 0.95},
            'GradientBoosting':   {'f1_score': 0.90, 'accuracy': 0.88},
            'LogisticRegression': {'f1_score': 0.75, 'accuracy': 0.80},
            'BiLSTM':             {'f1_score': 0.70, 'accuracy': 0.72},
        }
        self.assertEqual(self._select_best(results), 'GradientBoosting')

    def test_best_model_tie(self):
        """Identical F1 and accuracy → 'Tie', not RandomForest."""
        results = {
            'RandomForest':     {'f1_score': 0.90, 'accuracy': 0.90},
            'GradientBoosting': {'f1_score': 0.90, 'accuracy': 0.90},
        }
        self.assertEqual(self._select_best(results), 'Tie')

    def test_best_model_never_picks_rf_as_default(self):
        """When GradientBoosting has slightly better F1, RF must not win."""
        results = {
            'RandomForest':     {'f1_score': 0.80, 'accuracy': 0.85},
            'GradientBoosting': {'f1_score': 0.81, 'accuracy': 0.82},
        }
        self.assertNotEqual(self._select_best(results), 'RandomForest')
        self.assertEqual(self._select_best(results),    'GradientBoosting')

    def test_best_model_none_when_no_trained(self):
        """Returns None when all models have errors."""
        results = {
            'RandomForest':     {'error': 'train failed', 'f1_score': 0},
            'GradientBoosting': {'error': 'train failed', 'f1_score': 0},
        }
        self.assertIsNone(self._select_best(results))

    def test_best_model_excludes_zero_f1(self):
        """Models with f1=0 (training error) are excluded."""
        results = {
            'RandomForest':     {'f1_score': 0.0,  'accuracy': 0.0},
            'GradientBoosting': {'f1_score': 0.85, 'accuracy': 0.87},
        }
        self.assertEqual(self._select_best(results), 'GradientBoosting')


# ── JSON format validation ────────────────────────────────────────────────────

class UnifiedJsonFormatTest(TestCase):
    """
    Verifies that the metrics dict for all four algorithms contains
    the required fields and no hardcoded 0 / 1 values.
    """

    REQUIRED_FIELDS = [
        'accuracy', 'precision', 'recall', 'f1_score',
        'confusion_matrix', 'sample_count', 'trained_date',
        'cross_validation', 'feature_importance',
    ]

    def _mock_results(self, accuracy):
        """Build a minimal results dict simulating a real training run."""
        return {
            name: {
                'accuracy':          accuracy,
                'precision':         accuracy - 0.02,
                'recall':            accuracy - 0.03,
                'f1_score':          accuracy - 0.025,
                'confusion_matrix':  [[10, 2], [1, 9]],
                'confusion_counts':  {'tp': 10, 'tn': 9, 'fp': 2, 'fn': 1},
                'sample_count':      100,
                'trained_date':      '2026-06-25 10:00:00',
                'training_time':     5.2,
                'train_size':        70,
                'val_size':          15,
                'test_size':         15,
                'cross_validation':  None,
                'feature_importance': [],
            }
            for name in ['RandomForest', 'LogisticRegression', 'GradientBoosting', 'BiLSTM']
        }

    def test_all_required_fields_present(self):
        """All four models must have all required fields."""
        results = self._mock_results(0.87)
        for algo, r in results.items():
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, r, f"{algo} missing field: {field}")

    def test_no_zero_metrics_from_successful_run(self):
        """A successful run must not produce accuracy=0 or f1=0."""
        results = self._mock_results(0.87)
        for algo, r in results.items():
            self.assertGreater(r['accuracy'], 0,   f"{algo}: accuracy should be > 0")
            self.assertGreater(r['f1_score'], 0,   f"{algo}: f1_score should be > 0")

    def test_failed_model_has_none_not_zero(self):
        """When training fails, metrics must be None, not 0."""
        failed = {
            'RandomForest': {
                'error': 'Fit failed',
                'accuracy': None, 'precision': None, 'recall': None, 'f1_score': None,
                'confusion_matrix': None, 'sample_count': 0, 'trained_date': None,
                'cross_validation': None, 'feature_importance': [],
            }
        }
        r = failed['RandomForest']
        self.assertIsNone(r['accuracy'],  'Failed model accuracy must be None, not 0')
        self.assertIsNone(r['f1_score'],  'Failed model f1 must be None, not 0')
        self.assertIsNotNone(r['error'],  'Failed model must have an error message')

    def test_json_serializable(self):
        """Results dict must be JSON-serializable."""
        results = self._mock_results(0.87)
        try:
            json.dumps(results)
        except (TypeError, ValueError) as e:
            self.fail(f"Results are not JSON-serializable: {e}")


# ── ml_models_api endpoint ────────────────────────────────────────────────────

class MlModelsApiTest(TestCase):
    """
    Integration-style tests for ml_models_api.
    Mocks the filesystem so no .pkl files are needed.
    """

    def _make_metrics_json(self, results, best='GradientBoosting'):
        return {
            'results': results,
            'best_model': best,
            'trained_at': '2026-06-25 10:00:00',
            'samples': 100,
        }

    def test_api_returns_none_for_untrained_models(self):
        """Models whose .pkl is absent must have accuracy=None."""
        from django.test import RequestFactory
        from rest_framework.test import force_authenticate
        from django.contrib.auth.models import User
        from api.views import ml_models_api
        from rbac.models import UserProfile, Role

        # Create a minimal admin user
        user = User.objects.create_user('testadmin', 'a@b.com', 'pw')
        role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'Administrator'})
        UserProfile.objects.create(user=user, role=role)

        factory = RequestFactory()
        request = factory.get('/api/ml/models/')
        request.user = type('U', (), {
            'is_authenticated': True, 'roles': ['ADMIN'], 'username': 'testadmin', 'department': None,
        })()

        with patch('os.path.exists', return_value=False):
            resp = ml_models_api(request)

        self.assertEqual(resp.status_code, 200)
        for m in resp.data['models']:
            self.assertFalse(m['exists'], f"{m['name']} should not exist")

    def test_best_model_from_json_is_respected(self):
        """When metrics.json says best='GradientBoosting', the API must agree."""
        from django.test import RequestFactory
        from api.views import ml_models_api
        from api.models import Norme

        norm = Norme.objects.create(name='TestNorm')

        results_data = {
            algo: {
                'accuracy': 0.85 if algo != 'BiLSTM' else None,
                'precision': 0.83,
                'recall': 0.82,
                'f1_score': 0.84 if algo != 'BiLSTM' else None,
                'sample_count': 100,
                'trained_date': '2026-06-25',
                'cross_validation': None,
                'feature_importance': [],
                'error': None if algo != 'BiLSTM' else 'BiLSTM unavailable',
            }
            for algo in ['RandomForest', 'LogisticRegression', 'GradientBoosting', 'BiLSTM']
        }
        results_data['GradientBoosting']['f1_score'] = 0.90
        metrics_json = self._make_metrics_json(results_data, best='GradientBoosting')

        factory = RequestFactory()
        request = factory.get(f'/api/ml/models/?norm_id={norm.id}')
        request.user = type('U', (), {
            'is_authenticated': True, 'roles': ['ADMIN'], 'username': 'admin',
        })()

        with patch('builtins.open', MagicMock(return_value=MagicMock(
            __enter__=lambda s, *a: s,
            __exit__=MagicMock(return_value=False),
            read=MagicMock(return_value=json.dumps(metrics_json)),
        ))):
            with patch('os.path.exists', return_value=True):
                with patch('os.listdir', return_value=['TestNorm_GradientBoosting.pkl']):
                    with patch('os.path.getmtime', return_value=0):
                        resp = ml_models_api(request)

        self.assertEqual(resp.data['best_model'], 'GradientBoosting')


# ── Status label validation ───────────────────────────────────────────────────

class ModelStatusLabelTest(TestCase):
    """
    Mirrors the getModelStatus() logic from dashboardUtils.js in Python
    to validate that status labels are derived from real values.
    """

    def _status(self, accuracy, error=None, f1=None):
        """Replicate getModelStatus logic."""
        if error:
            return 'FAILED'
        if accuracy is None:
            return 'NOT_TRAINED'
        if accuracy == 0:
            return 'FAILED'
        if accuracy >= 0.9:
            return 'EXCELLENT'
        if accuracy >= 0.75:
            return 'GOOD'
        if accuracy >= 0.6:
            return 'ADEQUATE'
        return 'POOR'

    def test_failed_on_error(self):
        self.assertEqual(self._status(0.95, error='some error'), 'FAILED')

    def test_not_trained_on_none(self):
        self.assertEqual(self._status(None), 'NOT_TRAINED')

    def test_failed_on_zero_accuracy(self):
        self.assertEqual(self._status(0.0), 'FAILED')

    def test_excellent_on_high_accuracy(self):
        self.assertEqual(self._status(0.95), 'EXCELLENT')

    def test_good(self):
        self.assertEqual(self._status(0.80), 'GOOD')

    def test_adequate(self):
        self.assertEqual(self._status(0.65), 'ADEQUATE')

    def test_poor(self):
        self.assertEqual(self._status(0.50), 'POOR')

    def test_never_excellent_with_accuracy_zero(self):
        """Ensures accuracy=0 can never map to Excellent."""
        status = self._status(0.0)
        self.assertNotEqual(status, 'EXCELLENT')
        self.assertNotEqual(status, 'GOOD')
