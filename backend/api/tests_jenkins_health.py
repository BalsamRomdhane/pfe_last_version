"""
tests_jenkins_health.py
------------------------
Unit tests for services.mlops_service.get_jenkins_health().

Run with:
    python manage.py test api.tests_jenkins_health
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase


class JenkinsHealthServiceTest(TestCase):

    # ── helpers ────────────────────────────────────────────────────────

    def _health(self, env=None):
        """Call get_jenkins_health() with a custom env patch."""
        env = env or {}
        with patch.dict('os.environ', env, clear=False):
            # Re-import inside the patch so module-level vars are re-read
            from importlib import reload
            import services.mlops_service as svc
            reload(svc)
            return svc.get_jenkins_health()

    def _make_response(self, status_code, headers=None):
        r = MagicMock()
        r.status_code = status_code
        r.headers = headers or {}
        return r

    # ── Case 1: not configured ─────────────────────────────────────────

    def test_not_configured_when_token_empty(self):
        result = self._health({'JENKINS_TOKEN': '', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'not_configured')
        self.assertFalse(result['configured'])
        self.assertFalse(result['reachable'])
        self.assertFalse(result['connected'])
        self.assertFalse(result['remote_trigger'])
        self.assertTrue(result['local_training'])   # always true

    def test_not_configured_when_token_whitespace(self):
        result = self._health({'JENKINS_TOKEN': '   ', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'not_configured')
        self.assertTrue(result['local_training'])

    # ── Case 2: unreachable ────────────────────────────────────────────

    @patch('requests.get')
    def test_unreachable_on_connection_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('refused')
        result = self._health({'JENKINS_TOKEN': 'token', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'unreachable')
        self.assertTrue(result['configured'])
        self.assertFalse(result['reachable'])
        self.assertFalse(result['connected'])
        self.assertTrue(result['local_training'])

    @patch('requests.get')
    def test_unreachable_on_timeout(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout('timed out')
        result = self._health({'JENKINS_TOKEN': 'token', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'unreachable')
        self.assertFalse(result['reachable'])
        self.assertTrue(result['local_training'])

    # ── Case 3: auth failed ────────────────────────────────────────────

    @patch('requests.get')
    def test_auth_failed_on_401(self, mock_get):
        mock_get.return_value = self._make_response(401)
        result = self._health({'JENKINS_TOKEN': 'bad-token', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'auth_failed')
        self.assertTrue(result['reachable'])
        self.assertFalse(result['authenticated'])
        self.assertFalse(result['connected'])
        self.assertTrue(result['local_training'])

    @patch('requests.get')
    def test_auth_failed_on_403(self, mock_get):
        mock_get.return_value = self._make_response(403)
        result = self._health({'JENKINS_TOKEN': 'bad-token', 'JENKINS_URL': 'http://j:8080'})
        self.assertEqual(result['status'], 'auth_failed')
        self.assertTrue(result['reachable'])
        self.assertFalse(result['authenticated'])

    # ── Case 4: job not found ──────────────────────────────────────────

    @patch('requests.get')
    def test_job_not_found(self, mock_get):
        # First call (/api/json) → 200, second call (job) → 404
        mock_get.side_effect = [
            self._make_response(200, {'X-Jenkins': '2.440'}),
            self._make_response(404),
        ]
        result = self._health({
            'JENKINS_TOKEN': 'token',
            'JENKINS_URL': 'http://j:8080',
            'JENKINS_JOB_NAME': 'missing-job',
        })
        self.assertEqual(result['status'], 'job_not_found')
        self.assertTrue(result['authenticated'])
        self.assertFalse(result['connected'])
        self.assertFalse(result['remote_trigger'])
        self.assertTrue(result['local_training'])
        self.assertEqual(result['version'], '2.440')

    # ── Case 5: fully connected ────────────────────────────────────────

    @patch('requests.get')
    def test_connected(self, mock_get):
        mock_get.side_effect = [
            self._make_response(200, {'X-Jenkins': '2.440.3'}),
            self._make_response(200),
        ]
        result = self._health({
            'JENKINS_TOKEN': 'valid-token',
            'JENKINS_URL': 'http://j:8080',
            'JENKINS_JOB_NAME': 'compliance-ml-pipeline',
        })
        self.assertEqual(result['status'], 'connected')
        self.assertTrue(result['configured'])
        self.assertTrue(result['reachable'])
        self.assertTrue(result['authenticated'])
        self.assertTrue(result['connected'])
        self.assertTrue(result['remote_trigger'])
        self.assertTrue(result['local_training'])
        self.assertEqual(result['version'], '2.440.3')
        self.assertIn('message', result)
        self.assertIn('checked_at', result)

    # ── local_training always True ─────────────────────────────────────

    @patch('requests.get')
    def test_local_training_always_true(self, mock_get):
        """local_training must be True in every state."""
        import requests as req

        scenarios = [
            # not_configured
            ({'JENKINS_TOKEN': ''}, None),
            # unreachable
            ({'JENKINS_TOKEN': 'tok'}, req.exceptions.ConnectionError),
            # auth_failed
            ({'JENKINS_TOKEN': 'tok'}, None),  # handled below with side_effect list
        ]

        # not_configured
        r1 = self._health({'JENKINS_TOKEN': ''})
        self.assertTrue(r1['local_training'])

        # unreachable
        mock_get.side_effect = req.exceptions.ConnectionError()
        r2 = self._health({'JENKINS_TOKEN': 'tok', 'JENKINS_URL': 'http://j:8080'})
        self.assertTrue(r2['local_training'])

        # auth_failed
        mock_get.side_effect = None
        mock_get.return_value = self._make_response(401)
        r3 = self._health({'JENKINS_TOKEN': 'tok', 'JENKINS_URL': 'http://j:8080'})
        self.assertTrue(r3['local_training'])

        # connected
        mock_get.side_effect = [
            self._make_response(200, {'X-Jenkins': '2.x'}),
            self._make_response(200),
        ]
        r4 = self._health({'JENKINS_TOKEN': 'tok', 'JENKINS_URL': 'http://j:8080'})
        self.assertTrue(r4['local_training'])
