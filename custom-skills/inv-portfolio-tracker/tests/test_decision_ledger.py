"""Isolated subprocess acceptance tests; never use the production default DB."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'scripts/decision_ledger.py'

class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'ledger.sqlite3'

    def cli(self, command, data=None, ok=True):
        args = [sys.executable, '-B', str(CLI), '--db', str(self.db), command]
        if data is not None:
            args += ['--json', json.dumps(data)]
        p = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0 if ok else 1, p.stdout + p.stderr)
        try:
            return json.loads(p.stdout)
        except ValueError:
            self.fail('CLI did not return JSON: ' + p.stdout + p.stderr)

    def test_atomic_idempotent_append_and_readonly_audit(self):
        self.cli('init')
        batch = {'key':'first','records':[{'kind':'research','id':'TSM','symbol':'TSM','version':1,'status':'partial'}]}
        self.cli('apply', batch)
        before = self.db.read_bytes()
        self.cli('apply', batch)
        report = self.cli('audit')
        self.assertEqual(report['coverage'], 1)
        self.assertEqual(report['rows'][0]['status'], 'partial')
        self.assertEqual(before, self.db.read_bytes())
        bad = {'key':'bad','records':[{'kind':'research','id':'MSFT','symbol':'MSFT','version':1,'status':'partial'}, {'kind':'nonsense'}]}
        self.cli('apply', bad, ok=False)
        self.assertEqual(self.cli('audit')['coverage'], 1)

    def put(self, key, *records, ok=True):
        return self.cli('apply', {'key':key, 'records':list(records)}, ok=ok)

    def record(self, kind, id='x', version=1, **kw):
        return dict(kind=kind, id=id, version=version, symbol='TSM', **kw)

    def test_research_gates_and_financial_event_invalidation(self):
        self.cli('init')
        self.put('partial', self.record('research', status='partial'))
        self.put('quote', self.record('quote', source='fixture', date='2026-09-25', status='verified', price_position=99))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'partial')
        self.put('empty-ready', self.record('research',version=2,status='decision_ready', evidence_ids=[]),ok=False)
        self.put('anomaly', self.record('evidence', source='fixture',date='2026-09-25',basis='earningsGrowth',status='anomalous'))
        self.put('bad-ready', self.record('research',version=2,status='decision_ready',evidence_ids=['x']),ok=False)
        self.put('price-trigger', self.record('condition', status='active', purpose='valuation', metric='price_position'),ok=False)
        self.put('valid', self.record('evidence',id='v',source='fixture',date='2026-09-25',basis='original report',status='verified'), self.record('research',version=2,status='decision_ready',evidence_ids=['v']))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'decision_ready')
        self.put('results', self.record('event',event_type='financial_report',date='2026-09-26',source='fixture announcement'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        self.put('recycle',self.record('research',version=3,status='decision_ready',evidence_ids=['v']),ok=False)

    def test_conflicts_unknown_discussion_and_issue_closure(self):
        self.cli('init')
        self.put('base',self.record('research',status='partial'))
        self.put('lines',self.record('condition',id='watch',status='active',purpose='reminder',metric='price',source='fixture',line='1-2'),self.record('condition',id='watch',version=2,status='active',purpose='reminder',metric='price',source='fixture',line='3-4'))
        report=self.cli('audit')
        self.assertEqual(report['conditions'][0]['status'],'suspended')
        self.assertEqual(report['conditions'][0]['evaluation'],'unknown')
        self.put('discussion',self.record('decision',stage='suggestion',text='consider selling'))
        self.assertFalse(any(r.get('stage')=='executed' for r in self.cli('audit')['records']))
        self.put('issue',self.record('issue',status='open',impact='rating',next_action='verify report'))
        self.put('badclose',self.record('issue',version=2,status='closed',impact='rating',next_action='done'),ok=False)
        self.put('proof',self.record('evidence',id='proof',source='fixture',date='2026-09-25',basis='original',status='verified'))
        self.put('close',self.record('issue',version=2,status='closed',impact='rating',next_action='review conclusion',closure_evidence_ids=['proof']))
        self.assertEqual(self.cli('audit')['rows'][0]['status'],'needs_review')
        self.put('network',self.record('quote',source='fixture',date='2026-09-25',status='upstream_failed'))
        self.assertEqual(self.cli('audit')['conditions'][0]['evaluation'],'unknown')
        self.put('false execution',self.record('decision',id='bad',stage='executed',text='discussed'),ok=False)

    def test_ready_is_revoked_by_later_open_issue(self):
        self.cli('init')
        self.put('ready', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'), self.record('research', status='decision_ready', evidence_ids=['x']))
        self.put('issue', self.record('issue', status='open', impact='rating', next_action='verify'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')

    def test_schema_and_identity_cannot_bypass_gate(self):
        self.cli('init')
        self.put('e', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'))
        self.put('string-refs', self.record('research', status='decision_ready', evidence_ids='x'), ok=False)
        self.put('bad-date', self.record('research', status='partial', reviewed_through='9999'), ok=False)
        self.put('blank-source', self.record('evidence', id='blank', source=' ', date='2026-09-25', basis='original', status='verified'), ok=False)
        self.put('identity', dict(self.record('evidence', version=2, source='fixture', date='2026-09-25', basis='original', status='verified'), symbol='MSFT'), ok=False)
        self.put('missing-condition', self.record('condition', purpose='reminder', source='fixture', status='active'), ok=False)

    def test_later_evidence_and_conflicts_revoke_ready(self):
        self.cli('init')
        self.put('ready', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'), self.record('research', status='decision_ready', evidence_ids=['x']))
        self.put('downgrade', self.record('evidence', version=2, source='fixture', date='2026-09-25', basis='original', status='invalidated'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        self.put('restore', self.record('evidence', version=3, source='fixture', date='2026-09-25', basis='original', status='verified'))
        self.put('lines', self.record('condition', id='a', purpose='reminder', metric='price', source='fixture', line='1', status='active'), self.record('condition', id='b', purpose='reminder', metric='price', source='fixture', line='2', status='active'))
        report = self.cli('audit')
        self.assertTrue(all(c['status']=='suspended' for c in report['conditions']))
        self.assertEqual(report['rows'][0]['status'], 'needs_review')
        self.assertTrue(all(c['status']=='suspended' for c in report['records'] if c['kind']=='condition'))

    def test_closed_issue_requires_explicit_versioned_review(self):
        self.cli('init')
        self.put('base', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'), self.record('research', status='partial'), self.record('issue', status='open', impact='rating', next_action='verify'))
        self.put('close', self.record('issue', version=2, status='closed', impact='rating', next_action='review', closure_evidence_ids=['x']))
        self.put('skip-review', self.record('research', version=2, status='decision_ready', evidence_ids=['x']), ok=False)
        self.put('review', self.record('research', version=2, status='decision_ready', evidence_ids=['x'], reviewed_issues={'x':2}, review_source='fixture conclusion review'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'decision_ready')
        self.put('reopen', self.record('issue', version=3, status='open', impact='rating', next_action='new evidence'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')

    def test_malformed_batches_fail_cleanly_without_writes(self):
        self.cli('init')
        before = self.db.read_bytes()
        for data in ([], {'key':' ', 'records':[]}, {'key':'x', 'records':[None]}, {'key':'x', 'records':{}}, {'key':'x', 'records':[self.record('event', source='fixture', event_type='typo', date='2026-09-25')]}):
            with self.subTest(data=data):
                self.cli('apply', data, ok=False)
                self.assertEqual(before, self.db.read_bytes())

if __name__ == '__main__':
    unittest.main()
