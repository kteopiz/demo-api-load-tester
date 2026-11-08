import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from main import ROOT, allocate_counts, build_workload
from mock_api import Handler, forecast
from utils.coords import load_cached_coords
from utils.urls import generate_urls


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.coords = load_cached_coords(ROOT / 'data/synthetic_locations.csv')

    def test_exact_counts_and_hot_membership(self):
        for total in (1, 2, 3, 7, 10, 11, 100, 101):
            for percentage in (0, 1, 20, 50, 99, 100):
                with self.subTest(total=total, percentage=percentage):
                    payloads, counts, hot = build_workload(total, percentage, 24, self.coords, random.Random(42))
                    self.assertEqual(len(payloads), total)
                    self.assertEqual(sum(counts.values()), total)
                    self.assertEqual(hot, round(total * percentage / 100))
                    self.assertEqual(sum((p['location']['latitude'], p['location']['longitude']) in self.coords for p in payloads), hot)
                    for profile, count in counts.items():
                        self.assertEqual(sum(p['profile'] == profile for p in payloads), count)
                    for payload in payloads:
                        self.assertEqual(payload['hours'], 1 if payload['profile'] == 'feature_4' else 24)

    def test_reproducibility_and_serialization(self):
        first = build_workload(31, 30, 24, self.coords, random.Random(7))[0]
        second = build_workload(31, 30, 24, self.coords, random.Random(7))[0]
        self.assertEqual(first, second)
        for line, payload in zip(generate_urls(first, 'http://localhost:8000/'), first):
            endpoint, body = line.split(' POST ', 1)
            self.assertEqual(endpoint, 'http://localhost:8000/forecast')
            self.assertEqual(json.loads(body), payload)
            self.assertTrue(forecast(payload)['synthetic'])

    def test_invalid_inputs(self):
        for total, percent, hours in ((0, 20, 24), (1, -1, 24), (1, 101, 24), (1, 20, 0), (1, 20, 169)):
            with self.assertRaises(ValueError):
                build_workload(total, percent, hours, self.coords, random.Random(1))
        for weights in ({}, {'x': 0}, {'x': -1}, {'x': float('nan')}):
            with self.assertRaises(ValueError):
                allocate_counts(10, weights)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'locations.csv'
            path.write_text('latitude,longitude\nnan,10\n')
            with self.assertRaises(ValueError):
                load_cached_coords(path)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_generated_workload_over_http(self):
        coords = load_cached_coords(ROOT / 'data/synthetic_locations.csv')
        payloads = build_workload(12, 50, 3, coords, random.Random(42))[0]
        for line in generate_urls(payloads, self.base):
            endpoint, body = line.split(' POST ', 1)
            request = Request(endpoint, data=body.encode(), headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
                self.assertTrue(result['synthetic'])
                self.assertEqual(len(result['forecast']), json.loads(body)['hours'])

    def test_health_and_errors(self):
        with urlopen(self.base + '/health', timeout=5) as response:
            self.assertEqual(json.load(response)['status'], 'ok')
        for path, body, status in (('/forecast', b'{}', 400), ('/forecast', b'{', 400), ('/missing', b'{}', 404)):
            with self.assertRaises(HTTPError) as raised:
                urlopen(Request(self.base + path, data=body), timeout=5)
            self.assertEqual(raised.exception.code, status)
            raised.exception.close()


if __name__ == '__main__':
    unittest.main()
