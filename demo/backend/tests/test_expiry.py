"""Time-boundary, dependent-data and concurrent expiry regression checks."""
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from whereru.db import get_db
from whereru.expiry import expire_listings


def age(app,lid,modifier='-7 days'):
    with app.app_context():
        get_db().execute("UPDATE listings SET created_at=datetime('now',?) WHERE id=?",(modifier,lid))


def test_seven_day_boundary_uses_posted_time_and_deletes_all_statuses(app,account,report):
    c,h,_=account();fresh=report(c,h,occurred_at='2020-01-01T00:00:00Z')
    almost=report(c,h)
    # SQLite applies individual modifiers, so use an unambiguous just-before boundary.
    with app.app_context():get_db().execute("UPDATE listings SET created_at=datetime('now','-7 days','+15 seconds') WHERE id=?",(almost['id'],))
    expired=[]
    for status in ('OPEN','CLAIMED','RETURNED','CLOSED'):
        r=report(c,h,visibility='PRIVATE' if status=='CLOSED' else 'PUBLIC');expired.append(r['id'])
        with app.app_context():get_db().execute("UPDATE listings SET status=?,created_at=datetime('now','-7 days') WHERE id=?",(status,r['id']))
    assert c.get('/api/listings?status=ALL').status_code==200
    assert {r['id'] for r in c.get('/api/me/listings').json['listings']}=={fresh['id'],almost['id']}
    for lid in expired:assert c.get(f'/api/listings/{lid}').status_code==404
    with app.app_context():assert not get_db().execute('PRAGMA foreign_key_check').fetchall()


def test_expiry_removes_photos_matches_alerts_evidence_and_saved_entries(app,account,report):
    owner,oh,_=account();finder,fh,_=account()
    lost=report(owner,oh);found=report(finder,fh,type='FOUND')
    raw=io.BytesIO();Image.new('RGB',(32,32),'blue').save(raw,'JPEG')
    image=finder.post(f"/api/listings/{found['id']}/images",data={'image':(io.BytesIO(raw.getvalue()),'photo.jpg')},headers=fh).json
    assert owner.post(f"/api/me/saved-listings/{found['id']}",json={},headers=oh).status_code==200
    claim=owner.post('/api/claims',json={'found_id':found['id'],'lost_id':lost['id'],'evidence':'private bottle evidence'},headers=oh).json
    cid=claim['id'];finder.post(f'/api/claims/{cid}/messages',json={'body':'private conversation'},headers=fh)
    with app.app_context():
        db=get_db();name=db.execute('SELECT storage_name FROM images WHERE id=?',(image['id'],)).fetchone()[0]
        db.execute("INSERT INTO ai_analyses(listing_id,user_id,kind,mode,listing_version,result) VALUES(?,?,'ITEM','local',1,'{}')",(found['id'],claim['id']))
    file=Path(app.config['UPLOAD_DIR'])/name;assert file.is_file()
    age(app,found['id'])
    assert finder.get(image['url']).status_code==404 and not file.exists()
    assert owner.get('/api/me/saved-listings').json['ids']==[]
    assert owner.get('/api/matches').json['matches']==[]
    assert owner.get(f'/api/claims/{cid}').status_code==404
    assert owner.get('/api/notifications').json['notifications']==[]
    assert finder.get('/api/notifications').json['notifications']==[]
    with app.app_context():
        db=get_db()
        for table in ('images','claims','messages','matches','saved_listings','ai_analyses','upload_deletions'):
            assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def recovery(account,report,complete=False):
    owner,oh,_=account();finder,fh,_=account()
    lost=report(owner,oh);found=report(finder,fh,type='FOUND')
    cid=owner.post('/api/claims',json={'found_id':found['id'],'lost_id':lost['id'],'evidence':'private distinctive sticker'},headers=oh).json['id']
    assert finder.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=fh).status_code==200
    assert finder.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Public student centre'},headers=fh).status_code==201
    if complete:
        finder.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=fh)
        owner.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=oh)
    return owner,finder,lost,found,cid


def test_expired_claim_releases_newer_report_without_awarding_points(app,account,report):
    owner,finder,lost,found,cid=recovery(account,report)
    age(app,lost['id'])
    assert finder.get(f"/api/listings/{found['id']}").json['status']=='OPEN'
    assert owner.get(f'/api/claims/{cid}').status_code==404
    assert finder.get('/api/auth/me').json['user']['reputation']==0


def test_earned_reputation_survives_repeated_and_concurrent_deletion(app,account,report):
    owner,finder,lost,found,_=recovery(account,report,True)
    age(app,lost['id']);age(app,found['id'])
    def cleanup(_):
        with app.app_context():return expire_listings()
    with ThreadPoolExecutor(max_workers=20) as pool:counts=list(pool.map(cleanup,range(40)))
    assert sum(counts)==2
    for client,points in ((owner,2),(finder,10)):
        assert client.get('/api/auth/me').json['user']['reputation']==points
        assert client.get('/api/me/activity').json['confirmed_returns']==1
    with app.app_context():
        db=get_db()
        assert db.execute('SELECT COUNT(*) FROM claims').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_all_active_feed_includes_both_types_and_reserved_reports(app,account,report):
    c,h,_=account();lost=report(c,h);found=report(c,h,type='FOUND');returned=report(c,h)
    with app.app_context():
        db=get_db();db.execute("UPDATE listings SET status='CLAIMED' WHERE id=?",(found['id'],));db.execute("UPDATE listings SET status='RETURNED' WHERE id=?",(returned['id'],))
    assert {x['id'] for x in c.get('/api/listings?status=ALL').json['listings']}=={lost['id'],found['id']}
    assert c.get('/api/listings?status=ALL&type=FOUND').json['total']==1
    assert c.get('/api/listings?type=bad').status_code==400


def test_deleted_report_id_is_not_reused(app,account,report):
    c,h,_=account();old=report(c,h);age(app,old['id'])
    new=report(c,h)
    assert new['id']>old['id'] and c.get(f"/api/listings/{old['id']}").status_code==404


def test_startup_removes_reports_that_expired_while_server_was_offline(app,account,report):
    from whereru import create_app
    c,h,_=account();old=report(c,h);age(app,old['id'],'-8 days')
    restarted=create_app(dict(app.config))
    with restarted.app_context():assert get_db().execute('SELECT COUNT(*) FROM listings').fetchone()[0]==0
