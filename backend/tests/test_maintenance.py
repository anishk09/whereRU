import sqlite3
from manage import import_legacy,seed_demo
from whereru.db import get_db


def test_legacy_import_preserves_source_and_is_idempotent(app,tmp_path):
    source=tmp_path/'old.db'
    db=sqlite3.connect(source)
    db.executescript("CREATE TABLE listings(id INTEGER PRIMARY KEY,type TEXT,title TEXT,description TEXT,category TEXT,location TEXT,time TEXT,visibility TEXT,reward REAL,created_at TEXT); INSERT INTO listings VALUES(1,'LOST','Old bottle','Original','Accessories','Library','2026-10-10T14:00:00-04:00','PUBLIC',0,'2026-10-10 20:00:00');")
    db.close();before=source.read_bytes()
    with app.app_context():
        assert import_legacy(source)==1
        assert import_legacy(source)==0
        row=get_db().execute('SELECT * FROM listings').fetchone()
        assert row['title']=='Old bottle' and row['creator_id'] is None
    assert source.read_bytes()==before


def test_demo_is_idempotent(app):
    with app.app_context():
        assert seed_demo()==4
        assert seed_demo()==0
        assert get_db().execute('SELECT COUNT(*) FROM matches WHERE active=1').fetchone()[0]>=1


def test_legacy_database_cannot_be_used_as_runtime(tmp_path):
    import pytest
    from whereru import create_app
    path=tmp_path/'campusfind.db'
    db=sqlite3.connect(path);db.execute('CREATE TABLE listings(id INTEGER PRIMARY KEY,title TEXT)');db.close()
    before=path.read_bytes()
    with pytest.raises(RuntimeError,match='legacy database'):
        create_app({'TESTING':True,'DATABASE':str(path),'UPLOAD_DIR':str(tmp_path/'uploads'),
          'SECRET_KEY':'test-only-secret-not-for-production','APP_ENV':'development','AI_MODE':'demo'})
    assert path.read_bytes()==before
