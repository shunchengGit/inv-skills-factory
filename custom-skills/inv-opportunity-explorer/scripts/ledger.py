#!/usr/bin/env python3
"""Append-only company review ledger. JSON output; SQLite serializes writers."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlparse

DEFAULT_DB = str(Path.home() / '.hermes/memories/opportunity-explorer/ledger.sqlite3')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def connect(path):
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(Path(path).expanduser()), timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS companies (company_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS aliases (
            alias TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id));
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
            reviewed_at TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL,
            UNIQUE(company_id, reviewed_at, stage));
    ''')
    return db


def resolve(db, identifier):
    row = db.execute('SELECT company_id FROM aliases WHERE alias=?', (identifier,)).fetchone()
    return row['company_id'] if row else identifier


def latest(db, company):
    row = db.execute('SELECT id, payload FROM reviews WHERE company_id=? ORDER BY reviewed_at DESC, id DESC LIMIT 1', (company,)).fetchone()
    if not row:
        return None
    result = json.loads(row['payload'])
    result['review_id'] = row['id']
    result['aliases'] = [r[0] for r in db.execute('SELECT alias FROM aliases WHERE company_id=? ORDER BY alias', (company,))]
    return result


def validate_record(data):
    if not isinstance(data, dict):
        raise ValueError('record must be a JSON object')
    for field in ('company_id', 'name', 'industry', 'stage', 'reviewed_at', 'reason'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(field + ' must be a nonempty string')
    for field in ('aliases', 'sources'):
        if not isinstance(data.get(field), list) or any(not isinstance(v, str) or not v.strip() for v in data[field]):
            raise ValueError(field + ' must be a list of nonempty strings')
    if data['company_id'] != data['company_id'].strip() or any(a != a.strip() for a in data['aliases']):
        raise ValueError('identifiers must not have surrounding whitespace')
    if data['stage'] not in set(COOLDOWNS) | {'candidate'}:
        raise ValueError('invalid stage')
    if iso_date(data['reviewed_at']) > dt.date.today():
        raise ValueError('reviewed_at cannot be in the future')
    if 'report_path' in data and data['report_path'] is not None and not isinstance(data['report_path'], str):
        raise ValueError('report_path must be a string or null')


def record(db, data):
    validate_record(data)
    db.execute('BEGIN IMMEDIATE')
    try:
        company = resolve(db, data['company_id'])
        db.execute('INSERT OR IGNORE INTO companies VALUES (?)', (company,))
        for alias in set([data['company_id'], company] + data['aliases']):
            owner = db.execute('SELECT company_id FROM aliases WHERE alias=?', (alias,)).fetchone()
            if owner and owner['company_id'] != company:
                raise ValueError('alias collision: ' + alias)
            db.execute('INSERT OR IGNORE INTO aliases VALUES (?, ?)', (alias, company))
        data = dict(data, company_id=company)
        cur = db.execute('INSERT OR IGNORE INTO reviews(company_id,reviewed_at,stage,payload) VALUES (?,?,?,?)', (company, data['reviewed_at'], data['stage'], json.dumps(data, ensure_ascii=False)))
        inserted = bool(cur.rowcount)
        row = db.execute('SELECT id FROM reviews WHERE company_id=? AND reviewed_at=? AND stage=?', (company, data['reviewed_at'], data['stage'])).fetchone()
        db.execute('COMMIT')
        return {'inserted': inserted, 'review_id': row['id'], 'company_id': company}
    except Exception:
        db.execute('ROLLBACK')
        raise


COOLDOWNS = {'screen_reject': 30, 'deep_done': 60, 'hard_reject': 180,
             'historical_review': 60, 'partial': 7}


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError('date must be YYYY-MM-DD')
    parsed = dt.date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('date must be YYYY-MM-DD')
    return parsed


def check(db, args):
    if not args.company.strip() or args.company != args.company.strip():
        raise ValueError('company must be a nonempty identifier without surrounding whitespace')
    as_of = iso_date(args.as_of)
    event_date = None
    if args.event:
        if not args.event_date or not args.evidence or not args.evidence.strip():
            raise ValueError('event requires event-date and evidence URL')
        url = urlparse(args.evidence)
        if url.scheme not in ('https', 'http') or not url.netloc or any(ch.isspace() for ch in args.evidence):
            raise ValueError('evidence must be an HTTP(S) URL')
        event_date = iso_date(args.event_date)
        if event_date > min(as_of, dt.date.today()):
            raise ValueError('event-date cannot be in the future or after as-of')
    elif args.event_date or args.evidence is not None or args.resolves_hard_risk:
        raise ValueError('event options require --event')
    db.execute('BEGIN')
    company = resolve(db, args.company)
    review = latest(db, company)
    result = {'company_id': company, 'allowed': True, 'auto_selected': False,
              'reason': 'unknown_company'}
    if not review:
        return result
    reviewed = iso_date(review['reviewed_at'])
    if as_of < reviewed:
        raise ValueError('as-of precedes latest review')
    if event_date and event_date <= reviewed:
        raise ValueError('event-date must be strictly after reviewed_at')
    stage = review['stage']
    result.update(stage=stage, reviewed_at=review['reviewed_at'])
    if stage == 'candidate' or (stage == 'partial' and args.mode == 'weekly'):
        result.update(allowed=args.mode == 'weekly', reason='weekly_deep_review' if args.mode == 'weekly' else 'candidate_daily_skip')
    else:
        days = COOLDOWNS[stage]
        elapsed = (as_of - reviewed).days
        result.update(allowed=elapsed >= days, reason='cooldown_expired' if elapsed >= days else 'cooldown',
                      cooldown_days=days, remaining_days=max(0, days - elapsed),
                      next_eligible_at=(reviewed + dt.timedelta(days=days)).isoformat())
    if args.event and not result['allowed']:
        if stage == 'hard_reject' and (args.event == 'price' or not args.resolves_hard_risk):
            result['reason'] = 'hard_risk_not_resolved'
        else:
            result.update(allowed=True, reason='event_exception', event=args.event,
                          event_date=args.event_date, evidence=args.evidence)
    return result


def main():
    p = Parser(description=__doc__)
    p.add_argument('--db', default=DEFAULT_DB)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('status')
    r = sub.add_parser('record')
    r.add_argument('--file', required=True)
    c = sub.add_parser('check')
    c.add_argument('--company', required=True)
    c.add_argument('--mode', choices=['daily', 'weekly'], required=True)
    c.add_argument('--as-of', default=dt.date.today().isoformat())
    c.add_argument('--event', choices=['earnings', 'material', 'price'])
    c.add_argument('--event-date')
    c.add_argument('--evidence')
    c.add_argument('--resolves-hard-risk', action='store_true')
    args = p.parse_args()
    db = connect(args.db)
    try:
        if args.command == 'init':
            return {'status': 'initialized'}
        if args.command == 'record':
            return record(db, json.loads(Path(args.file).read_text(encoding='utf-8')))
        if args.command == 'status':
            db.execute('BEGIN')
            return {'companies': [latest(db, r[0]) for r in db.execute('SELECT company_id FROM companies ORDER BY company_id').fetchall()]}
        return check(db, args)
    finally:
        db.close()


if __name__ == '__main__':
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        sys.exit(1)
