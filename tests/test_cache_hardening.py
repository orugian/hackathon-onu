"""Cache envelopes are trusted only through raw_text + sha256; derived fields are rebuilt."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from integrations import SourceService

ROOT = Path(__file__).resolve().parents[1]


class CacheHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name)
        shutil.copytree(ROOT / 'data' / 'sources', self.cache, dirs_exist_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, source_id, change):
        path = self.cache / f'{source_id}.json'
        envelope = json.loads(path.read_text(encoding='utf-8'))
        change(envelope)
        path.write_text(json.dumps(envelope), encoding='utf-8')

    def test_tampered_derived_geojson_is_ignored_in_favor_of_hashed_text(self):
        def tamper(env):
            env['raw']['features'] = env['raw']['features'][:1]
            env['feature_count'] = 1
            env['partial'] = False
            env['total_available'] = 'muitos'
            env['fetched_at'] = '<script>'
        self.edit('deter_alerts', tamper)
        result = SourceService(str(self.cache)).get()
        source = next(s for s in result['sources'] if s['id'] == 'deter_alerts')
        self.assertEqual(len(result['alerts']['features']), 200)
        self.assertEqual(source['feature_count'], 200)
        self.assertTrue(source['partial'])
        self.assertIsInstance(source['total_available'], int)
        self.assertNotEqual(source['fetched_at'], '<script>')

    def test_nan_inside_hashed_text_marks_source_unavailable(self):
        def poison(env):
            env['raw_text'] = env['raw_text'].replace('"areamunkm":', '"areamunkm":NaN,"x":', 1)
            env['sha256'] = hashlib.sha256(env['raw_text'].encode('utf-8')).hexdigest()
        self.edit('deter_alerts', poison)
        result = SourceService(str(self.cache)).get()
        source = next(s for s in result['sources'] if s['id'] == 'deter_alerts')
        self.assertEqual(source['status'], 'unavailable')
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
