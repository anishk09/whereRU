import sqlite3
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


def close_db(error=None):
    db=g.pop('db',None)
    if db is not None: db.close()
