#!/usr/bin/env python3
"""Local append-only decision records. Structure validation is not investment advice."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

KINDS = {'research', 'evidence', 'assumption', 'decision', 'condition', 'issue', 'event', 'quote'}
SCHEMA = '''
CREATE TABLE records(kind TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL,
 symbol TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(kind,id,version));
CREATE TABLE events(key TEXT PRIMARY KEY,payload TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
PRAGMA user_version=1;
'''

def latest(db):
    return [json.loads(r[0]) for r in db.execute('SELECT a.payload FROM records a WHERE version=(SELECT max(version) FROM records b WHERE a.kind=b.kind AND a.id=b.id) ORDER BY symbol,kind,id')]

def validate(db, r):
    from datetime import date
    kind = r['kind']
    for field in ('id', 'symbol', 'source', 'basis', 'metric', 'impact', 'next_action', 'text', 'confirmation_source', 'execution_source'):
        if field in r and (not isinstance(r[field], str) or not r[field].strip()):
            raise ValueError('nonblank string required: '+field)
    for field in ('evidence_ids', 'closure_evidence_ids'):
        if field in r and (not isinstance(r[field], list) or any(not isinstance(x, str) or not x.strip() for x in r[field])):
            raise ValueError('list of evidence IDs required')
    if 'reviewed_issues' in r and (not isinstance(r['reviewed_issues'], dict) or any(not isinstance(k, str) or type(v) is not int or v < 1 for k,v in r['reviewed_issues'].items())):
        raise ValueError('reviewed_issues must map issue IDs to positive versions')
    if 'review_source' in r and (not isinstance(r['review_source'], str) or not r['review_source'].strip()):
        raise ValueError('review_source must be a nonblank string')
    if 'anomalous' in r and type(r['anomalous']) is not bool:
        raise ValueError('anomalous must be boolean')
    identity = db.execute('SELECT symbol FROM records WHERE kind=? AND id=? LIMIT 1', (kind, r['id'])).fetchone()
    if identity and identity[0] != r['symbol']:
        raise ValueError('record symbol is immutable')
    if kind == 'research' and any(x['kind']=='research' and x['symbol']==r['symbol'] and x['id']!=r['id'] for x in latest(db)):
        raise ValueError('one research identity per symbol')
    for field in ('date', 'reviewed_through', 'last_research_date', 'next_report_date'):
        if r.get(field) is not None and date.fromisoformat(r[field]).isoformat()!=r[field]:
            raise ValueError('invalid date')
    if any(k in r for k in ('shares','cash','quantity','holdings')):
        raise ValueError('holdings belong only in PORTFOLIO.md')
    prev = db.execute('SELECT max(version) FROM records WHERE kind=? AND id=?',(kind,r['id'])).fetchone()[0]
    if r['version'] != (prev or 0)+1:
        raise ValueError('nonsequential version')
    records = latest(db)
    same = [x for x in records if x['symbol']==r['symbol']]
    def verified(ids):
        evidence = {x['id']:x for x in same if x['kind']=='evidence'}
        events = [x['date'] for x in same if x['kind']=='event' and x.get('event_type')=='financial_report']
        return bool(ids) and all(i in evidence and evidence[i].get('status')=='verified'
            and evidence[i].get('basis') not in {'earningsGrowth','price_position','52w_position'}
            and not evidence[i].get('anomalous',False)
            and (not events or (evidence[i].get('date') or '')>=max(events)) for i in ids)
    if kind in {'evidence','quote','event'}:
        if not r.get('source') or not r.get('status',kind=='event'):
            raise ValueError('source/status required')
    if kind=='evidence':
        if not r.get('basis') or r.get('status') not in {'verified','historical','unknown','anomalous','upstream_failed','invalidated'}:
            raise ValueError('evidence basis/status required')
        if r['status']=='verified' and (not r.get('date') or r.get('anomalous') or r['basis'] in {'earningsGrowth','price_position','52w_position'}):
            raise ValueError('cannot certify abnormal growth or price position')
    if kind=='event' and r.get('event_type') not in {'financial_report','material_risk'}:
        raise ValueError('event_type must be financial_report or material_risk')
    if kind=='event' and not r.get('date'):
        raise ValueError('actual report date required; never invent dates')
    if kind=='condition':
        if not r.get('metric') or not isinstance(r.get('line'), str) or not r['line'].strip():
            raise ValueError('condition metric/line required')
        if r.get('purpose')!='reminder' or r.get('metric') in {'price_position','52w_position'}:
            raise ValueError('condition must be reminder, not valuation/price-position trigger')
        if r.get('status') not in {'active','suspended','historical','superseded'} or not r.get('source'):
            raise ValueError('condition source/status required')
    if kind=='research':
        if r.get('status') not in {'unknown','partial','needs_review','decision_ready'}:
            raise ValueError('invalid research status')
        if r['status']=='decision_ready':
            closed = [x for x in same if x['kind']=='issue' and x.get('status')=='closed']
            if any(r.get('reviewed_issues', {}).get(x['id']) != x['version'] for x in closed) or (closed and not r.get('review_source')):
                raise ValueError('closed issue impact requires explicit versioned conclusion review')
            events = [x['date'] for x in same if x['kind']=='event' and x.get('event_type')=='financial_report']
            if events and (r.get('reviewed_through') or '') < max(events):
                raise ValueError('financial event requires explicit research review')
            if not verified(r.get('evidence_ids')) or any(x['kind']=='issue' and x.get('status')!='closed' for x in same):
                raise ValueError('missing verified evidence/open issues')
            if any(x['status']=='suspended' for x in audit(db)['conditions'] if x['symbol']==r['symbol']):
                raise ValueError('conflicting or suspended conditions')
    if kind=='issue':
        if not r.get('impact') or not r.get('next_action') or r.get('status') not in {'open','closed'}:
            raise ValueError('issue requires impact/next action/status')
        if r['status']=='closed' and not verified(r.get('closure_evidence_ids')):
            raise ValueError('issue closure requires verified evidence')
    if kind=='decision':
        if r.get('stage') not in {'suggestion','user_confirmed','executed'}:
            raise ValueError('invalid decision stage')
        if r['stage']!='suggestion' and not r.get('confirmation_source'):
            raise ValueError('explicit user confirmation source required')
        if r['stage']=='executed' and not r.get('execution_source'):
            raise ValueError('actual execution source required, never inferred from discussion')
    if kind=='assumption' and (not r.get('text') or not r.get('source')):
        raise ValueError('assumption text/source required')

def apply(db, data):
    if not isinstance(data, dict) or not isinstance(data.get('key'), str) or not data['key'].strip() or not isinstance(data.get('records'), list) or not data['records'] or any(not isinstance(r, dict) for r in data['records']):
        raise ValueError('batch requires nonblank key and nonempty record objects')
    key = data['key']
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    db.execute('BEGIN IMMEDIATE')
    try:
        old = db.execute('SELECT payload FROM events WHERE key=?', (key,)).fetchone()
        if old:
            if old[0] != payload:
                raise ValueError('idempotency key payload conflict')
            db.rollback()
            return {'duplicate': True}
        for r in data['records']:
            if r.get('kind') not in KINDS or not r.get('id') or not r.get('symbol') or type(r.get('version')) is not int or r['version'] < 1:
                raise ValueError('invalid record')
            validate(db, r)
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)', (r['kind'],r['id'],r['version'],r['symbol'],json.dumps(r,ensure_ascii=False,sort_keys=True)))
        db.execute('INSERT INTO events(key,payload) VALUES(?,?)',(key,payload))
        db.commit()
        return {'duplicate': False}
    except Exception:
        db.rollback()
        raise

def audit(db):
    records = latest(db)
    rows = [r for r in records if r['kind']=='research']
    conditions = [r for r in records if r['kind']=='condition']
    for c in conditions:
        peers = [x for x in conditions if x['symbol']==c['symbol'] and x.get('metric')==c.get('metric') and x.get('status') in {'active','suspended'}]
        if c.get('status') in {'active','suspended'} and len({x.get('line') for x in peers}) > 1:
            c['status']='suspended'
            c['conflict']='multiple unresolved condition lines'
    for c in conditions:
        if c['version']>1 and c.get('supersedes')!=c['version']-1:
            c['status']='suspended'
            c['conflict']='unresolved version conflict'
        c['evaluation']='unknown'
    for r in rows:
        same=[x for x in records if x['symbol']==r['symbol']]
        events=[x['date'] for x in same if x['kind']=='event' and x.get('event_type')=='financial_report']
        closed=[x for x in same if x['kind']=='issue' and x.get('status')=='closed' and x.get('impact')]
        r['gaps']=[{'id':x['id'],'impact':x['impact'],'next_action':x['next_action']} for x in same if x['kind']=='issue' and x.get('status')=='open']
        pending_closed = any(r.get('reviewed_issues', {}).get(x['id']) != x['version'] for x in closed) or (closed and not r.get('review_source'))
        if (events and (r.get('reviewed_through') or '')<max(events)) or pending_closed or r['gaps']:
            r['status']='needs_review'
        if r['status']=='decision_ready':
            evidence = {x['id']:x for x in same if x['kind']=='evidence'}
            ids = r.get('evidence_ids')
            if (not isinstance(ids, list) or not ids or
                    any(i not in evidence or evidence[i].get('status')!='verified' or evidence[i].get('anomalous') or evidence[i].get('basis') in {'earningsGrowth','price_position','52w_position'} or (events and (evidence[i].get('date') or '')<max(events)) for i in ids) or
                    any(c['symbol']==r['symbol'] and c['status']=='suspended' for c in conditions)):
                r['status']='needs_review'
        r['quote_refresh_is_research']=False
    for e in records:
        if e['kind']=='evidence':
            dates=[x['date'] for x in records if x['symbol']==e['symbol'] and x['kind']=='event' and x.get('event_type')=='financial_report']
            if dates and (e.get('date') or '')<max(dates):
                e['effective_status']='invalidated'
    return {'schema_version':1, 'coverage':len(rows), 'rows':rows, 'records':records, 'conditions':conditions,
            'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=str(Path.home()/'.hermes/memories/investment-decisions/ledger.sqlite3'))
    parser.add_argument('command', choices=['init','apply','audit','render'])
    parser.add_argument('--json')
    args = parser.parse_args()
    try:
        path = Path(args.db).expanduser().resolve()
        if args.command == 'init':
            path.parent.mkdir(parents=True,exist_ok=True)
        readonly = args.command in {'audit','render'}
        db = sqlite3.connect(path.as_uri()+'?mode='+('ro' if readonly else 'rwc'),uri=True)
        try:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if args.command=='init' and version==0:
                db.executescript(SCHEMA)
                version=1
            if version!=1:
                raise ValueError('unsupported schema version')
            if args.command=='init':
                result={'schema_version':1}
            elif args.command=='apply':
                result=apply(db,json.loads(args.json))
            else:
                db.execute('BEGIN')
                result=audit(db)
                db.rollback()
            if args.command=='render':
                print('# 投资决策当前视图（生成文件，不手改）\n\n持仓/现金仅以 PORTFOLIO.md 为准；提醒不是下单。\n')
                for r in result['rows']:
                    print('## '+r['symbol']+' — '+r['status'])
                    for item in result['records']:
                        if item['symbol']==r['symbol']:
                            print('- '+json.dumps(item,ensure_ascii=False,sort_keys=True))
            else:
                print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        finally:
            db.close()
        return 0
    except (ValueError,KeyError,TypeError,sqlite3.Error,OSError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False))
        return 1

if __name__=='__main__':
    sys.exit(main())
