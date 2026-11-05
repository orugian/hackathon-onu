"""Simultaneous HTTP reservations: exactly one of two 10 m³ requests succeeds against 15 m³."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from app import create_server


class ConcurrentHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(port=0, db_path=Path(self.temp.name) / 'c.sqlite', cache_dir=Path(self.temp.name) / 's')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self, key, results):
        payload = {'lot_id': 'AM-DEMO-001', 'volume_m3': '10', 'recipient': 'Destino fictício', 'vehicle': 'DEMO', 'invoice': key, 'gross_kg': 20000, 'tare_kg': 12000}
        request = urllib.request.Request(self.url + '/api/shipments', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Idempotency-Key': key})
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                results.append((response.status, time.perf_counter() - started))
        except urllib.error.HTTPError as error:
            with error:
                results.append((error.status, time.perf_counter() - started))

    def test_two_simultaneous_reservations_accept_only_one_and_respond_under_one_second(self):
        results = []
        barrier = threading.Barrier(2)

        def worker(key):
            barrier.wait()
            self.post(key, results)

        threads = [threading.Thread(target=worker, args=(k,)) for k in ('A', 'B')]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertTrue(all(elapsed < 1.0 for _, elapsed in results), results)
        with urllib.request.urlopen(self.url + '/api/state') as response:
            state = json.loads(response.read())
        self.assertEqual(state['lots'][0]['available_milli'], 5000)
        self.assertTrue(state['integrity']['valid'])


if __name__ == '__main__':
    unittest.main()
