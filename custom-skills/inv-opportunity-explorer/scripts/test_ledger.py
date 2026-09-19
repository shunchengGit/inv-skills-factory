"""Integration tests; all state is isolated in TemporaryDirectory."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name('ledger.py')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'nested' / 'ledger.sqlite3'

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', str(SCRIPT), '--db', str(self.db), *args], capture_output=True, text=True)
        self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def record(self, company='CN:600000', stage='screen_reject', date='2025-01-01', **changes):
        data = dict(company_id=company, name='Example', aliases=['HK:00001'], industry='bank', stage=stage, reviewed_at=date, reason='valuation', sources=['https://example.org/report'])
        data.update(changes)
        f = Path(self.tmp.name) / ('record-' + str(len(list(Path(self.tmp.name).glob('record-*')))) + '.json')
        f.write_text(json.dumps(data), encoding='utf-8')
        return self.cli('record', '--file', str(f))

    def check(self, company='CN:600000', mode='daily', date='2025-01-02', *extras, ok=True):
        return self.cli('check', '--company', company, '--mode', mode, '--as-of', date, *extras, ok=ok)

    def test_record_alias_history_and_idempotency(self):
        first = self.record()
        self.assertTrue(first['inserted'])
        duplicate = self.record(reason='must not overwrite')
        self.assertFalse(duplicate['inserted'])
        self.assertEqual(duplicate['review_id'], first['review_id'])
        self.record(company='HK:00001', stage='deep_done', date='2025-02-01', aliases=['US:EXAMPLE'])
        # Backfilled history must not become the latest review.
        self.record(stage='candidate', date='2024-12-01', aliases=[])
        rows = self.cli('status')['companies']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['company_id'], 'CN:600000')
        self.assertEqual(rows[0]['stage'], 'deep_done')
        self.assertEqual(rows[0]['aliases'], ['CN:600000', 'HK:00001', 'US:EXAMPLE'])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0], 3)
            payload = json.loads(db.execute('SELECT payload FROM reviews WHERE id=?', (first['review_id'],)).fetchone()[0])
            self.assertEqual(payload['reason'], 'valuation')

    def test_alias_collision_rolls_back_and_concurrent_idempotency(self):
        self.record()
        data = dict(company_id='OTHER', name='Other', aliases=['new-alias', 'HK:00001'], industry='bank', stage='candidate', reviewed_at='2025-01-01', reason='test', sources=[])
        f = Path(self.tmp.name) / 'collision.json'
        f.write_text(json.dumps(data))
        self.assertIn('error', self.cli('record', '--file', str(f), ok=False))
        self.assertEqual(len(self.cli('status')['companies']), 1)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM aliases WHERE alias='new-alias'").fetchone()[0], 0)
        data.update(company_id='CONCURRENT', aliases=['HK:CONCURRENT'])
        f.write_text(json.dumps(data))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.cli('record', '--file', str(f)), range(16)))
        self.assertEqual(sum(r['inserted'] for r in results), 1)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0], 2)

    def test_cooldown_boundaries_and_stage_transitions(self):
        for stage, days in [('screen_reject', 30), ('deep_done', 60), ('hard_reject', 180), ('historical_review', 60), ('partial', 7)]:
            with self.subTest(stage=stage):
                self.record(company=stage, stage=stage, aliases=[])
                for elapsed in [0, days - 1, days, days + 1]:
                    date = (dt.date(2025, 1, 1) + dt.timedelta(days=elapsed)).isoformat()
                    result = self.check(stage, 'daily', date)
                    self.assertEqual(result['allowed'], elapsed >= days)
                    self.assertFalse(result['auto_selected'])
                self.assertEqual(self.check(stage, 'weekly')['allowed'], stage == 'partial')
        self.record(stage='candidate')
        self.assertFalse(self.check('HK:00001', 'daily')['allowed'])
        self.assertTrue(self.check('HK:00001', 'weekly')['allowed'])
        self.record(stage='deep_done', date='2025-01-02')
        self.assertFalse(self.check('HK:00001', 'weekly', '2025-01-03')['allowed'])
        self.assertIn('error', self.check(date='2024-12-31', ok=False))

    def test_events_and_hard_risk(self):
        self.record()
        def event(kind='earnings', date='2025-01-02', evidence='https://example.org/new', hard=False, ok=True):
            extra = ['--event', kind, '--event-date', date, '--evidence', evidence]
            if hard:
                extra.append('--resolves-hard-risk')
            return self.check('CN:600000', 'daily', '2025-01-03', *extra, ok=ok)
        for kind in ['earnings', 'material', 'price']:
            self.assertTrue(event(kind)['allowed'])
        for date in ['2025-01-01', '2024-12-31', '2025-01-04', '2999-01-01', 'bad']:
            self.assertIn('error', event(date=date, ok=False))
        for evidence in ['', '   ', 'not-a-url']:
            self.assertIn('error', event(evidence=evidence, ok=False))
        self.assertIn('error', event(kind='rumor', ok=False))
        self.cli('check', '--company', 'unknown', '--mode', 'daily', '--event', 'earnings', ok=False)
        self.cli('check', '--company', 'unknown', '--mode', 'daily', '--resolves-hard-risk', ok=False)
        self.record(stage='hard_reject', reason='governance fraud')
        self.assertFalse(event('price', hard=True)['allowed'])
        self.assertFalse(event('earnings')['allowed'])
        self.assertFalse(event('material')['allowed'])
        self.assertTrue(event('earnings', hard=True)['allowed'])
        self.assertTrue(event('material', hard=True)['allowed'])
        self.assertEqual(self.cli('status')['companies'][0]['stage'], 'hard_reject')

    def test_invalid_records_are_json_errors_without_history(self):
        good = dict(company_id='X', name='X', aliases=[], industry='tech', stage='candidate', reviewed_at='2025-01-01', reason='review', sources=[])
        bad = [None, [], {}, dict(good, stage='bogus'), dict(good, reviewed_at='20250101'), dict(good, reviewed_at='2999-01-01'), dict(good, aliases='HK:X'), dict(good, aliases=[1]), dict(good, sources='url'), dict(good, sources=[None]), dict(good, company_id=' '), dict(good, reason=''), dict(good, report_path=123)]
        f = Path(self.tmp.name) / 'invalid.json'
        for data in bad:
            with self.subTest(data=data):
                f.write_text(json.dumps(data))
                self.assertIn('error', self.cli('record', '--file', str(f), ok=False))
        f.write_text('{invalid')
        self.assertIn('error', self.cli('record', '--file', str(f), ok=False))
        self.assertEqual(self.cli('status')['companies'], [])
        self.cli('check', '--company', ' ', '--mode', 'daily', ok=False)
        self.cli('check', '--company', 'X', '--mode', 'wrong', ok=False)
        self.cli('check', '--company', 'X', '--mode', 'daily', '--as-of', 'bad', ok=False)

    def test_init_and_unknown(self):
        self.assertEqual(self.cli('init')['status'], 'initialized')
        self.assertEqual(self.cli('status')['companies'], [])
        result = self.check()
        self.assertTrue(result['allowed'])
        self.assertFalse(result['auto_selected'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
