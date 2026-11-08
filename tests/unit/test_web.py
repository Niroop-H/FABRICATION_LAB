"""HTTP contract tests for the stateless Vercel application."""
import unittest
from app import app


class TestWeb(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.payload = dict(temperature_c=1000, duration_s=1800,
                            initial_thickness_nm=2, ambient='DRY_O2')

    def test_page_assets_and_health(self):
        for path in ('/', '/calculator', '/assets/app.js', '/assets/style.css', '/assets/fab.js', '/assets/fab.css', '/api/health'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        self.assertEqual(self.client.get('/api/health').json['persistence'], 'none')

    def test_run_is_repeatable_and_grows_oxide(self):
        first = self.client.post('/api/simulate/oxidation', json=self.payload)
        second = self.client.post('/api/simulate/oxidation', json=self.payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json, second.json)
        self.assertGreater(first.json['final_thickness_nm'], 2)
        self.assertGreater(len(first.json['profile']), 1)
        self.assertEqual(first.headers['Cache-Control'], 'no-store')

    def test_wet_ambient(self):
        self.payload['ambient'] = 'WET_H2O'
        self.assertEqual(self.client.post('/api/simulate/oxidation', json=self.payload).status_code, 200)

    def test_rejects_invalid_input(self):
        for key, value in [('temperature_c', 799), ('duration_s', 7201),
                           ('initial_thickness_nm', -1), ('ambient', []),
                           ('temperature_c', True), ('duration_s', '1800'),
                           ('temperature_c', float('nan')), ('duration_s', None)]:
            with self.subTest(key=key, value=value):
                response = self.client.post('/api/simulate/oxidation', json={**self.payload, key:value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json)

    def test_bad_json_and_methods(self):
        for payload in ([], 'text', {}):
            self.assertEqual(self.client.post('/api/simulate/oxidation', json=payload).status_code, 400)
        self.assertEqual(self.client.get('/api/simulate/oxidation').status_code, 405)
        self.assertEqual(self.client.post('/api/simulate/oxidation', data='{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/simulate/oxidation', data='x'*17000, content_type='application/json').status_code, 413)
