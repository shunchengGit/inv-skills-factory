"""Isolated subprocess acceptance tests; never use the production default DB."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any

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

    def card(self, **changes) -> dict[str, Any]:
        data = self.record('research', protocol_version=3, status='decision_ready',
            reviewed_through='2026-09-25', owner='responsible analyst',
            card=dict(sources=[dict(source='/tmp/report.md#sources', date='2026-09-25',
                locator='annual report p.4', excerpt='Revenue 100 million USD',
                units='million USD', status='verified', basis='annual report')],
                facts='Revenue 100 million USD in FY2025', assumptions='Growth may slow',
                opposition='Test slower growth; value remains above price',
                valuation_basis='Normalized earnings with stated multiple', conclusion='hold',
                review_conditions='Review on results or governance risk', important_unknowns=[]))
        data.update(changes)
        return data

    def test_v3_single_card_file_writes_reads_audits_renders_without_role_quota(self):
        self.cli('init')
        payload = Path(self.tmp.name) / 'card.json'
        payload.write_text(json.dumps({'key':'card', 'records':[self.card()]}))
        p = subprocess.run([sys.executable, '-B', str(CLI), '--db', str(self.db),
                            'apply', '--file', str(payload)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        report = self.cli('audit')
        self.assertEqual(report['rows'][0]['status'], 'decision_ready')
        self.assertEqual(len(report['records']), 1)
        before = self.db.read_bytes()
        rendered = subprocess.run([sys.executable, '-B', str(CLI), '--db', str(self.db),
                                   'render'], text=True, capture_output=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn('hold', rendered.stdout)
        self.assertEqual(before, self.db.read_bytes())

    def test_v3_ready_rejects_unknowns_missing_provenance_and_invalid_sources(self):
        import copy
        self.cli('init')
        bad_cards = []
        for field in ('facts', 'assumptions', 'opposition', 'valuation_basis', 'conclusion', 'review_conditions'):
            card = copy.deepcopy(self.card())
            card['card'][field] = ' '
            bad_cards.append(card)
        for field, value in [('important_unknowns', ['Cash conversion unverified']),
                             ('important_unknowns', 'none'), ('sources', [])]:
            card = copy.deepcopy(self.card())
            card['card'][field] = value
            bad_cards.append(card)
        for field, value in [('status', 'invalidated'), ('status', 'anomalous'),
                             ('anomalous', True), ('basis', 'price_position'),
                             ('basis', 'earningsGrowth'), ('units', ''), ('date', 'bad'),
                             ('locator', ''), ('excerpt', ''), ('source', '')]:
            card = copy.deepcopy(self.card())
            card['card']['sources'][0][field] = value
            bad_cards.append(card)
        bad_cards.append(self.card(owner=None))
        before = self.db.read_bytes()
        for index, card in enumerate(bad_cards):
            with self.subTest(index=index):
                self.put('bad-'+str(index), card, ok=False)
                self.assertEqual(before, self.db.read_bytes())
        partial = self.card(status='partial')
        partial['card']['important_unknowns'] = ['Cash conversion unverified']
        self.put('partial-with-unknown', partial)
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'partial')

    def test_v3_cannot_bypass_old_invalid_evidence(self):
        self.cli('init')
        self.put('old', self.record('evidence', id='old', source='fixture',
            date='2026-09-25', basis='original', status='invalidated'))
        self.put('bypass', self.card(), ok=False)
        self.put('resolve', self.record('evidence', id='old', version=2, source='fixture',
            date='2026-09-25', basis='original', status='verified'))
        self.put('ready', self.card())
        self.put('downgrade', self.record('evidence', id='old', version=3, source='fixture',
            date='2026-09-25', basis='original', status='anomalous'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')

    def test_v3_financial_event_and_suspended_conditions_remain_blockers(self):
        self.cli('init')
        self.put('ready', self.card())
        self.put('financial', self.record('event', source='fixture',
            date='2026-09-26', event_type='financial_report'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        self.put('stale', self.card(version=2, reviewed_through='2026-09-26'), ok=False)
        refreshed = self.card(version=2, reviewed_through='2026-09-26')
        refreshed['card']['sources'][0]['date'] = '2026-09-26'
        self.put('review', refreshed)
        self.put('paused', self.record('condition', status='suspended', purpose='reminder',
            metric='price', source='fixture', line='10'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        self.put('skip-paused', dict(refreshed, version=3), ok=False)

    def test_v3_suggestion_confirmation_execution_stay_separate(self):
        self.cli('init')
        self.put('ready', self.card())
        suggestion = self.record('decision', id='d', protocol_version=3, stage='suggestion',
            text='hold', research_id='x', research_version=1)
        self.put('suggest', suggestion)
        self.put('no-confirmation', dict(suggestion, version=2, stage='user_confirmed'), ok=False)
        confirmed = dict(suggestion, version=2, stage='user_confirmed', confirmation_source='user message')
        self.put('confirm', confirmed)
        self.put('no-fill', dict(confirmed, version=3, stage='executed'), ok=False)
        self.put('fill', dict(confirmed, version=3, stage='executed', execution_source='broker report'))
        self.put('holdings', self.card(version=2, shares=100), ok=False)
        self.assertEqual(next(r for r in self.cli('audit')['records'] if r['kind']=='decision')['stage'], 'executed')

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
        rec = dict(kind=kind, id=id, version=version, symbol='TSM', **kw)
        if kind == 'evidence' and rec.get('status') == 'verified':
            rec.setdefault('excerpt', 'original text excerpt')
            rec.setdefault('locator', 'p.1')
        if kind == 'issue' and rec.get('status') == 'open':
            rec.setdefault('owner', 'fixture analyst')
            rec.setdefault('due', '2026-10-01')
            rec.setdefault('next_event', 'filing review')
        return rec

    def ready_fields(self, primary='x'):
        roles = {'original': primary, 'independent':'second', 'contrarian':'against',
                 'valuation':'value', 'portfolio_comparison':'compare'}
        for role, ident in roles.items():
            if role == 'original':
                continue
            self.put('seed-'+ident, self.record('evidence', id=ident, source='fixture',
                source_group=ident, evidence_type='supporting' if role=='independent' else role,
                date='2026-09-25', basis='original', status='verified'))
        # Legacy fixture's primary evidence was written before the protocol existed;
        # add a version recording the role and source identity.
        self.put('seed-primary', self.record('evidence', id=primary, version=2,
            source='fixture', source_group='filing', evidence_type='original',
            date='2026-09-25', basis='original', status='verified'))
        return dict(protocol_version=2, evidence_ids=list(roles.values()),
                    readiness={role:[ident] for role, ident in roles.items()})

    def test_research_gates_and_financial_event_invalidation(self):
        self.cli('init')
        self.put('partial', self.record('research', status='partial'))
        self.put('quote', self.record('quote', source='fixture', date='2026-09-25', status='verified', price_position=99))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'partial')
        self.put('empty-ready', self.record('research',version=2,status='decision_ready', evidence_ids=[]),ok=False)
        self.put('anomaly', self.record('evidence', source='fixture',date='2026-09-25',basis='earningsGrowth',status='anomalous'))
        self.put('bad-ready', self.record('research',version=2,status='decision_ready',evidence_ids=['x']),ok=False)
        self.put('price-trigger', self.record('condition', status='active', purpose='valuation', metric='price_position'),ok=False)
        self.put('valid-evidence', self.record('evidence',id='v',source='fixture',date='2026-09-25',basis='original report',status='verified'))
        self.put('valid', self.record('research',version=2,status='decision_ready',**self.ready_fields('v')))
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
        self.put('discussion',self.record('decision',stage='suggestion',text='consider selling', research_id='x', research_version=1))
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
        self.put('primary', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'))
        self.put('ready', self.record('research', status='decision_ready', **self.ready_fields()))
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
        self.put('primary', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'))
        self.put('ready', self.record('research', status='decision_ready', **self.ready_fields()))
        self.put('downgrade', self.record('evidence', version=3, source='fixture', date='2026-09-25', basis='original', status='invalidated'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        self.put('restore', self.record('evidence', version=4, source_group='filing', evidence_type='original', source='fixture', date='2026-09-25', basis='original', status='verified'))
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
        self.put('review', self.record('research', version=2, status='decision_ready', reviewed_issues={'x':2}, review_source='fixture conclusion review', **self.ready_fields()))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'decision_ready')
        self.put('reopen', self.record('issue', version=3, status='open', impact='rating', next_action='new evidence'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')

    def test_material_risk_event_revokes_ready_like_financial_report(self):
        self.cli('init')
        self.put('primary', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'))
        self.put('ready', self.record('research', status='decision_ready', **self.ready_fields()))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'decision_ready')
        self.put('risk', self.record('event', event_type='material_risk', date='2026-09-26', source='fixture disclosure'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')
        stale_evidence = next(x for x in self.cli('audit')['records'] if x['kind']=='evidence')
        self.assertEqual(stale_evidence.get('effective_status'), 'invalidated')

    def test_verified_evidence_requires_excerpt_and_locator(self):
        self.cli('init')
        self.put('no-excerpt', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified', excerpt=None, locator='p.1'), ok=False)
        self.put('no-locator', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified', excerpt='text', locator=None), ok=False)

    def test_v2_readiness_requires_independent_original_contrarian_valuation_and_comparison(self):
        self.cli('init')
        self.put('partial', self.record('research', status='partial'))
        base = dict(source='fixture', date='2026-09-25', basis='original report', status='verified')
        for ident, group, role in [('original', 'filing', 'original'), ('second', 'broker', 'supporting'), ('against', 'critic', 'contrarian'), ('value', 'model', 'valuation'), ('compare', 'portfolio', 'portfolio_comparison')]:
            self.put('e-'+ident, self.record('evidence', id=ident, source_group=group, evidence_type=role, **base))
        checks = {'original':['original'], 'independent':['second'], 'contrarian':['against'], 'valuation':['value'], 'portfolio_comparison':['compare']}
        ready = self.record('research', version=2, status='decision_ready', protocol_version=2,
                            evidence_ids=['original','second','against','value','compare'], readiness=checks)
        for missing in checks:
            broken = dict(ready, readiness={k:v for k,v in checks.items() if k != missing})
            self.put('missing-'+missing, broken, ok=False)
        self.put('same-group', dict(ready, readiness=dict(checks, independent=['original'])), ok=False)
        self.put('ready', ready)
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'decision_ready')
        self.put('unsupported-version', dict(ready, version=3, protocol_version=3), ok=False)
        self.put('fake-role', self.record('evidence', id='fake', source='fixture', source_group='broker',
                                         evidence_type='made_up', date='2026-09-25', basis='original', status='verified'), ok=False)
        self.put('downgrade', self.record('evidence', id='against', version=2, source_group='critic',
                                          source='fixture', date='2026-09-25', basis='original report', status='invalidated'))
        self.assertEqual(self.cli('audit')['rows'][0]['status'], 'needs_review')

    def test_legacy_new_open_issue_cannot_bypass_accountability(self):
        self.cli('init')
        self.put('issue', dict(self.record('issue', status='open', impact='valuation', next_action='read filing'), owner=None), ok=False)

    def test_v2_open_issues_require_accountable_followup(self):
        self.cli('init')
        self.put('research', self.record('research', status='partial'))
        issue = self.record('issue', protocol_version=2, status='open', impact='valuation',
                            next_action='read filing', owner='analyst', due='2026-10-01',
                            next_event='quarterly results')
        for absent in ('owner', 'due', 'next_event'):
            self.put('missing-'+absent, {k:v for k,v in issue.items() if k != absent}, ok=False)
        self.put('issue', issue)
        gap = self.cli('audit')['rows'][0]['gaps'][0]
        self.assertEqual((gap['owner'], gap['due'], gap['next_event']), ('analyst','2026-10-01','quarterly results'))

    def test_legacy_new_suggestion_cannot_bypass_research_link(self):
        self.cli('init')
        self.put('research', self.record('research', status='partial'))
        self.put('unlinked', self.record('decision', stage='suggestion', text='consider'), ok=False)

    def test_v2_suggestion_binds_exact_research_version_without_execution(self):
        self.cli('init')
        self.put('research', self.record('research', status='partial'))
        suggestion = self.record('decision', id='d', protocol_version=2, stage='suggestion',
                                  text='continue research', research_id='x', research_version=1)
        self.put('missing-link', {k:v for k,v in suggestion.items() if k!='research_version'}, ok=False)
        self.put('wrong-version', dict(suggestion, research_version=2), ok=False)
        self.put('suggestion', suggestion)
        self.assertEqual(next(x for x in self.cli('audit')['records'] if x['kind']=='decision')['research_version'], 1)
        self.put('execution-without-confirmation', dict(suggestion, version=2, stage='executed'), ok=False)

    def test_v2_execution_is_recorded_even_without_research(self):
        self.cli('init')
        self.put('execution', self.record('decision', protocol_version=2, stage='executed',
            text='actual fill', confirmation_source='user confirmation',
            execution_source='broker fill'))
        self.assertEqual(next(x for x in self.cli('audit')['records'] if x['kind']=='decision')['stage'], 'executed')

    def test_v1_stored_ready_is_not_silently_recertified(self):
        self.cli('init')
        self.put('evidence', self.record('evidence', source='fixture', date='2026-09-25', basis='original', status='verified'))
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.db)) as db, db:
            old = self.record('research', status='decision_ready', evidence_ids=['x'])
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)',
                       ('research','x',1,'TSM',json.dumps(old)))
        report = self.cli('audit')
        self.assertEqual(report['rows'][0]['status'], 'needs_review')
        self.assertEqual(report['schema_version'], 1)

    def test_malformed_batches_fail_cleanly_without_writes(self):
        self.cli('init')
        before = self.db.read_bytes()
        for data in ([], {'key':' ', 'records':[]}, {'key':'x', 'records':[None]}, {'key':'x', 'records':{}}, {'key':'x', 'records':[self.record('event', source='fixture', event_type='typo', date='2026-09-25')]}):
            with self.subTest(data=data):
                self.cli('apply', data, ok=False)
                self.assertEqual(before, self.db.read_bytes())

if __name__ == '__main__':
    unittest.main()
