import sqlite3
import re
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db=sqlite3.connect(current_app.config['DATABASE'],timeout=15,isolation_level=None)
        g.db.row_factory=sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=15000')
    return g.db


@contextmanager
def atomic():
    db=get_db(); db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback(); raise


def init_db():
    path=Path(current_app.config['DATABASE']);path.parent.mkdir(parents=True,exist_ok=True)
    db=get_db()
    existing={r[1] for r in db.execute('PRAGMA table_info(listings)')}
    if existing and not {'creator_id','occurred_at','version'}.issubset(existing):
        raise RuntimeError('This appears to be a legacy database. Use a new WhereRU database and manage.py import-legacy; do not point DATABASE_PATH at CampusFind.')
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('BEGIN IMMEDIATE;\n'+Path(__file__).with_name('schema.sql').read_text()+
                     '\nINSERT OR IGNORE INTO schema_migrations(version) VALUES(1);\nCOMMIT;')
    # Deleted report/image/notification IDs must never refer to new objects later.
    # Upgrade existing local databases atomically, preserving rows and references.
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=2').fetchone():
        db.execute('PRAGMA foreign_keys=OFF')
        try:
            with atomic():
                tables=db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                for name,sql in tables:
                    if not re.search(r'\bid INTEGER PRIMARY KEY\b',sql) or 'AUTOINCREMENT' in sql:continue
                    temporary=name+'_id_upgrade'
                    definition=re.sub(r'^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?\S+\s*\(',f'CREATE TABLE {temporary}(',sql,count=1)
                    definition=definition.replace('id INTEGER PRIMARY KEY','id INTEGER PRIMARY KEY AUTOINCREMENT',1)
                    db.execute(definition)
                    db.execute(f'INSERT INTO {temporary} SELECT * FROM {name}')
                    db.execute(f'DROP TABLE {name}')
                    db.execute(f'ALTER TABLE {temporary} RENAME TO {name}')
                for statement in Path(__file__).with_name('schema.sql').read_text().split(';'):
                    if statement.strip():db.execute(statement)
                if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Database upgrade failed foreign-key validation')
                db.execute('INSERT INTO schema_migrations(version) VALUES(2)')
        finally:db.execute('PRAGMA foreign_keys=ON')


def close_db(error=None):
    db=g.pop('db',None)
    if db is not None: db.close()
