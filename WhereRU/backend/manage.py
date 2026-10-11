"""Local maintenance commands. Run --help before importing an existing database."""
import argparse
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from whereru import create_app
from whereru.db import get_db,atomic


def import_legacy(source,owner_id=None):
    source=Path(source).resolve()
    if not source.is_file(): raise ValueError('Source database does not exist')
    from flask import current_app
    if source==Path(current_app.config['DATABASE']).resolve(): raise ValueError('Source and destination must be different databases')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as old:
        old.row_factory=sqlite3.Row
        rows=[dict(r) for r in old.execute('SELECT * FROM listings ORDER BY id')]
    fingerprint=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    with atomic() as db:
        if db.execute('SELECT 1 FROM import_runs WHERE source_hash=?',(fingerprint,)).fetchone(): return 0
        if owner_id is not None and not db.execute('SELECT 1 FROM users WHERE id=?',(owner_id,)).fetchone(): raise ValueError('Requested owner does not exist in the new database')
        for row in rows:
            when=datetime.fromisoformat(row['time'].replace('Z','+00:00'))
            if when.tzinfo is None: when=when.replace(tzinfo=timezone.utc)
            category=str(row.get('category','')).lower()
            category={'accessories':'other','water bottle':'bottle','bags':'bag'}.get(category,category)
            from whereru.listings import CATEGORIES,SENSITIVE
            if category not in CATEGORIES: category='other'
            status=row.get('status','OPEN')
            if status not in ('OPEN','RETURNED','CLOSED'): status='CLOSED'
            visibility=row.get('visibility','PRIVATE')
            if visibility not in ('PUBLIC','PRIVATE') or category in SENSITIVE: visibility='PRIVATE'
            # Never import old sessions, keys or accounts. Assignment requires an explicit local CLI option.
            db.execute('''INSERT INTO listings(creator_id,type,title,description,private_description,category,location,private_location,
                occurred_at,visibility,status,resolution,reward,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (owner_id,row['type'],row['title'],row.get('description') or '',row.get('private_description') or '',category,
                 row.get('location') or '',row.get('private_location') or '',when.astimezone(timezone.utc).isoformat(),visibility,status,
                 f"LEGACY_IMPORT:{row['id']}",row.get('reward') or 0,row.get('created_at') or datetime.now(timezone.utc).isoformat()))
        db.execute('INSERT INTO import_runs(source_hash,imported_count) VALUES(?,?)',(fingerprint,len(rows)))
    return len(rows)


def seed_demo():
    db=get_db()
    if db.execute("SELECT 1 FROM import_runs WHERE source_hash='demo-v1'").fetchone():return 0
    now=datetime.now(timezone.utc).isoformat()
    with atomic() as db:
        for email,name in [('owner@example.com','Demo owner'),('finder@example.com','Demo finder')]:
            db.execute('INSERT OR IGNORE INTO users(email,display_name) VALUES(?,?)',(email,name))
        owner=db.execute("SELECT id FROM users WHERE email='owner@example.com'").fetchone()[0]
        finder=db.execute("SELECT id FROM users WHERE email='finder@example.com'").fetchone()[0]
        ids=[]
        for uid,kind,title,category,color,location,lat,lon in [
            (owner,'LOST','DEMO Blue metal bottle','bottle','blue','Library',40.503,-74.452),
            (finder,'FOUND','DEMO Navy water flask','bottle','blue','Library',40.503,-74.452),
            (owner,'LOST','DEMO Red backpack','bag','red','Student center',40.502,-74.450),
            (finder,'FOUND','DEMO Black umbrella','other','black','Bus stop',40.520,-74.461)]:
            lid=db.execute('''INSERT INTO listings(creator_id,type,title,category,description,attributes,campus,location,occurred_at,custody)
              VALUES(?,?,?,?,?,?,?,?,?,?)''',(uid,kind,title,category,title,json.dumps({'color':color}),'Demo campus',location,now,'FINDER' if kind=='FOUND' else 'UNKNOWN')).lastrowid
            db.execute('INSERT INTO potential_locations(listing_id,label,latitude,longitude,share_public) VALUES(?,?,?,?,1)',(lid,'DEMO '+location,lat,lon));ids.append(lid)
        db.execute("INSERT INTO import_runs VALUES('demo-v1',4,CURRENT_TIMESTAMP)")
    from whereru.matching import refresh
    for lid in ids:refresh(lid)
    return len(ids)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init');sub.add_parser('seed-demo');sub.add_parser('cleanup');sub.add_parser('backup')
    imp=sub.add_parser('import-legacy');imp.add_argument('source');imp.add_argument('--owner-id',type=int,help='Explicitly assign ALL imported reports to this existing local user; omit to retain ownerless reports')
    args=parser.parse_args();app=create_app()
    with app.app_context():
        if args.command=='init':print('WhereRU? database ready:',app.config['DATABASE'])
        elif args.command=='seed-demo':
            if app.config['APP_ENV']=='production':raise SystemExit('Demo seeding is disabled in production')
            print('Added',seed_demo(),'clearly labeled demo reports. Use owner@example.com or finder@example.com with console codes.')
        elif args.command=='import-legacy':print('Imported',import_legacy(args.source,args.owner_id),'reports. Original database unchanged. Old accounts and sessions are not imported.')
        elif args.command=='backup':
            path=Path(app.config['DATABASE']);backup=path.parent/f'whereru-backup-{time.time_ns()}.db'
            with closing(sqlite3.connect(backup)) as dest:get_db().backup(dest)
            print(backup)
        elif args.command=='cleanup':
            with atomic() as db:
                cur=db.execute('DELETE FROM recording_sessions WHERE expires<=?',(time.time(),));count=cur.rowcount
                db.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),))
                db.execute('DELETE FROM challenges WHERE expires<=?',(time.time(),))
                db.execute('DELETE FROM rate_limits WHERE started<?',(time.time()-86400,))
            print('Deleted',count,'expired location sessions and expired authentication data.')


if __name__=='__main__':main()
