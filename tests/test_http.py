"""HTTP behavior tests use a temporary database and ephemeral loopback port."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from app import create_server


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'test.sqlite', cache_dir=Path(self.temp.name) / 'sources')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.url + path, data=data, headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_health_identifies_local_demonstrator(self):
        status, body = self.request('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(body['name'], 'RAIZTRACE')
        self.assertEqual(body['version'], '1.0.0')
        self.assertTrue(body['local_only'])

    def test_cross_origin_mutation_is_rejected(self):
        status, body = self.request('/api/shipments', {}, {'Origin': 'https://example.org'})
        self.assertEqual(status, 403)
        self.assertEqual(body['error']['code'], 'origin_forbidden')

    def test_non_object_json_is_rejected_before_dispatch(self):
        status, body = self.request('/api/shipments', [1, 2, 3])
        self.assertEqual(status, 400)
        self.assertEqual(body['error']['code'], 'invalid_json')

    def test_inventory_returns_explained_volume_and_no_credit(self):
        status, body = self.request('/api/inventory', {'diameter_cm': 60, 'height_m': 15, 'form_factor': 0.7})
        self.assertEqual(status, 200)
        self.assertAlmostEqual(body['volume_m3'], 2.9688, places=4)
        self.assertIn('formula', body)
        self.assertIn('não modifica crédito', body['notice'])

    def test_reservation_flow_preserves_balance_and_passport(self):
        status, state = self.request('/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(state['lots'][0]['available_milli'], 15000)
        payload = {'lot_id': 'AM-DEMO-001', 'volume_m3': '10', 'recipient': 'Destino fictício', 'vehicle': 'DEMO', 'invoice': 'NF-DEMO', 'gross_kg': 20000, 'tare_kg': 12000}
        status, passport = self.request('/api/shipments', payload, {'Idempotency-Key': 'one'})
        self.assertEqual(status, 201)
        self.assertEqual(passport['balance_after_milli'], 5000)
        status, same = self.request('/api/shipments', payload, {'Idempotency-Key': 'one'})
        self.assertEqual(same['id'], passport['id'])
        status, error = self.request('/api/shipments', payload, {'Idempotency-Key': 'two'})
        self.assertEqual(status, 409)
        self.assertEqual(error['error']['code'], 'insufficient_balance')
        status, retrieved = self.request('/api/passports/' + passport['id'])
        self.assertEqual(retrieved, passport)
        with urllib.request.urlopen(self.url + '/passport/' + passport['id']) as response:
            printed = response.read().decode('utf-8')
        self.assertIn(passport['hash'], printed)
        self.assertIn('SEM VALIDADE OFICIAL', printed)
        self.assertEqual(self.request('/api/state')[1]['lots'][0]['available_milli'], 5000)

    def test_weighing_http_reports_difference(self):
        status, body = self.request('/api/weigh', {'volume_m3': 10, 'gross_kg': 25000, 'tare_kg': 12000})
        self.assertEqual(status, 200)
        self.assertEqual(body['difference_kg'], 3500)
        self.assertEqual(body['status'], 'divergent')

    def test_lab_http_separates_artificial_prediction_from_species(self):
        status, model = self.request('/api/ml/model')
        self.assertEqual(status, 200)
        self.assertEqual((model['train_count'], model['test_count']), (90, 30))
        status, result = self.request('/api/ml', {'features': [999, 999, 999]})
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'inconclusive')
        self.assertIsNone(result['label'])
        self.assertTrue(result['synthetic'])
        self.assertEqual(self.request('/api/ml', {'features': [True, 1, 2]})[0], 422)

    def test_territory_offline_is_honest_and_demo_is_separate(self):
        status, body = self.request('/api/territory')
        self.assertEqual(status, 200)
        self.assertEqual(body['alerts']['features'], [])
        self.assertTrue(all(s['status'] == 'unavailable' for s in body['sources']))
        self.assertTrue(all(f['properties']['simulated'] for f in body['demo']['features']))
        self.assertIn('notice', body)

    def test_static_assets_are_local_and_private_files_are_not_served(self):
        with urllib.request.urlopen(self.url + '/static/vendor/leaflet.js') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'Leaflet', response.read())
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        for path in ('/app.py', '/data/raiztrace.sqlite', '/static/../app.py', '/static/%2e%2e/app.py'):
            self.assertEqual(self.request(path)[0], 404)

    def test_hostile_numbers_and_nesting_get_json_errors_not_dropped_connections(self):
        huge = int('9' * 400)
        for path, body in (('/api/weigh', {'volume_m3': huge, 'gross_kg': 2, 'tare_kg': 1}),
                           ('/api/inventory', {'diameter_cm': huge, 'height_m': 1, 'form_factor': 0.5}),
                           ('/api/assessments', {'quantity_m3': huge, 'hypothesis': 'h', 'reviewer': 'r'})):
            status, payload = self.request(path, body)
            self.assertEqual(status, 422, path)
            self.assertIn('error', payload)
        status, payload = self.request('/api/shipments', {'lot_id': 'AM-DEMO-001', 'volume_m3': huge, 'recipient': 'a', 'vehicle': 'b', 'invoice': 'c', 'gross_kg': 2, 'tare_kg': 1}, {'Idempotency-Key': 'x'})
        self.assertEqual(status, 422)
        nested = ('[' * 5000) + (']' * 5000)
        request = urllib.request.Request(self.url + '/api/weigh', data=('{"a":' + nested + '}').encode(), headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            with error:
                self.assertEqual(error.status, 400)

    def test_json_responses_carry_protective_headers(self):
        with urllib.request.urlopen(self.url + '/api/health') as response:
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_unrecognized_host_is_rejected(self):
        status, body = self.request('/api/health', headers={'Host': 'attacker.example'})
        self.assertEqual(status, 403)
        self.assertEqual(body['error']['code'], 'host_forbidden')

    def test_review_simulation_is_motivated_definitive_and_auditable(self):
        status, assessment = self.request('/api/assessments', {'quantity_m3': 5, 'hypothesis': 'Diferença hipotética de volume', 'reviewer': 'Revisor demonstrativo'})
        self.assertEqual(status, 201)
        self.assertEqual(assessment['fine_brl'], '1500.00')
        self.assertEqual(assessment['fee_brl'], '60.00')
        review = {'assessment_id': assessment['id'], 'decision': 'disagree', 'reviewer': 'Revisor demonstrativo', 'reason': ''}
        self.assertEqual(self.request('/api/review', review)[0], 422)
        review['reason'] = 'Solicitar medição de campo antes de qualquer enquadramento.'
        self.assertEqual(self.request('/api/review', review)[0], 200)
        self.assertEqual(self.request('/api/review', review)[0], 409)
        self.assertTrue(self.request('/api/audit')[1]['valid'])
        self.assertEqual(self.request('/api/state')[1]['lots'][0]['available_milli'], 15000)

    def test_refresh_network_failure_is_explicit_not_validation(self):
        from unittest.mock import patch
        with patch('integrations.SourceService._default_fetch', side_effect=OSError('offline')):
            status, result = self.request('/api/sources/refresh', {})
        self.assertEqual(status, 200)
        self.assertTrue(all(s['status'] == 'unavailable' for s in result['sources']))
        self.assertTrue(all('error' in s for s in result['sources']))
        self.assertEqual(result['spatial']['count'], 0)
        self.assertEqual(result['spatial']['status'], 'not_evaluated')
        self.assertIsNone(result['proximity'])

    def test_territory_with_real_snapshots_reports_proximity(self):
        import shutil
        from app import ROOT
        shutil.copytree(ROOT / 'data' / 'sources', self.server.cache_dir, dirs_exist_ok=True)
        status, body = self.request('/api/territory')
        self.assertEqual(status, 200)
        proximity = body['proximity']
        self.assertTrue(proximity['plot_inside_municipality'])
        self.assertEqual(proximity['alerts_evaluated'], 200)
        self.assertGreater(proximity['nearest']['distance_km'], 0)
        self.assertEqual(proximity['source_fetched_at'], body['spatial']['source_fetched_at'])


if __name__ == '__main__':
    unittest.main()
