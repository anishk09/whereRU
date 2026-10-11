"""Additional demo-readiness checks; all data and API providers are isolated."""
import io
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from PIL import Image
from whereru import create_app
from whereru.db import get_db


def picture(fmt='PNG'):
    stream=io.BytesIO(); Image.new('RGB',(40,30),'blue').save(stream,fmt);stream.seek(0);return stream


def test_all_protected_get_routes_deny_guests(app):
    guest=app.test_client()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/api/') or 'GET' not in rule.methods or rule.rule in ('/api/health','/api/demo/status'):continue
        path=rule.rule
        for name in rule.arguments:
            path=path.replace('<int:'+name+'>','1').replace('<'+name+'>','missing')
        response=guest.get(path)
        assert response.status_code==401,(path,response.status_code)


@pytest.mark.parametrize('body',[None,[],True,42,'text'])
def test_non_object_request_bodies(account,body):
    c,h,_=account()
    response=c.post('/api/listings',data=json.dumps(body),content_type='application/json',headers=h)
    assert response.status_code==400


@pytest.mark.parametrize('date',['0001-01-01T00:00:00+14:00','9999-12-31T23:59:59-14:00'])
def test_date_normalization_overflow_returns_400(account,date):
    c,h,_=account()
    assert c.post('/api/listings',json={'type':'LOST','title':'Test','occurred_at':date},headers=h).status_code==400


def test_notifications_preferences_feedback_and_history(account,report):
    owner,oh,_=account();finder,fh,_=account()
    owner.patch('/api/me',json={'notifications_enabled':False},headers=oh)
    lost=report(owner,oh);found=report(finder,fh,type='FOUND')
    assert owner.get('/api/notifications').json['unread_count']==0
    match=owner.get('/api/matches').json['matches'][0]
    assert owner.post(f"/api/matches/{match['id']}/feedback",json={'decision':'NOT_MINE'},headers=oh).status_code==200
    assert owner.get('/api/matches').json['matches']==[]
    finder.patch(f"/api/listings/{found['id']}",json={'title':'Blue bottle update'},headers=fh)
    assert owner.get('/api/matches').json['matches']==[]
    assert owner.post(f"/api/matches/{match['id']}/feedback",json={'decision':'POSSIBLE'},headers=oh).status_code==200
    assert len(owner.get('/api/matches').json['matches'])==1
    assert finder.get(f"/api/listings/{lost['id']}/history").status_code==403
    assert owner.get(f"/api/listings/{lost['id']}/history").json['events'][0]['kind']=='CREATED'


@pytest.mark.parametrize('fmt',['JPEG','PNG','WEBP'])
def test_image_formats_and_metadata(account,report,fmt):
    c,h,_=account();row=report(c,h)
    result=c.post(f"/api/listings/{row['id']}/images",data={'image':(picture(fmt),'photo')},headers=h)
    assert result.status_code==201
    response=c.get(result.json['url']);assert response.mimetype=='image/jpeg'
    image=Image.open(io.BytesIO(response.data));assert image.size==(40,30);assert not image.getexif()


def test_image_limit_and_sensitive_access(account,report,app):
    a,ah,_=account();b,bh,_=account();r=report(a,ah,category='keys',visibility='PRIVATE')
    ids=[]
    for _ in range(5):
        upload=a.post(f"/api/listings/{r['id']}/images",data={'image':(picture(),'a.png')},headers=ah)
        assert upload.status_code==201;ids.append(upload.json['id'])
    assert a.post(f"/api/listings/{r['id']}/images",data={'image':(picture(),'a.png')},headers=ah).status_code==400
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir()))==5
    assert a.patch(f'/api/images/{ids[0]}',json={'is_public':True},headers=ah).status_code==400
    assert b.delete(f'/api/images/{ids[0]}',json={},headers=bh).status_code==404
    assert a.post(f"/api/listings/{r['id']}/images",data={'image':(io.BytesIO(b'x'*(8*1024*1024+1)),'huge.png')},headers=ah).status_code==400


def accepted_pair(account,report):
    a,ah,_=account();b,bh,_=account()
    lost=report(a,ah);found=report(b,bh,type='FOUND')
    cid=a.post('/api/claims',json={'lost_id':lost['id'],'found_id':found['id'],'evidence':'Secret original evidence'},headers=ah).json['id']
    return a,ah,b,bh,lost,found,cid


def test_claim_revision_reject_closed_messages(account,report):
    a,ah,b,bh,lost,found,cid=accepted_pair(account,report)
    assert a.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Library'},headers=ah).status_code==409
    assert b.post(f'/api/claims/{cid}/review',json={'decision':'NEEDS_INFO'},headers=bh).json['status']=='NEEDS_INFO'
    assert b.post(f'/api/claims/{cid}/evidence',json={'evidence':'Some evidence'},headers=bh).status_code==403
    assert a.post(f'/api/claims/{cid}/evidence',json={'evidence':'Additional unique evidence'},headers=ah).json['status']=='PENDING'
    assert b.post(f'/api/claims/{cid}/review',json={'decision':'REJECTED'},headers=bh).status_code==200
    assert a.post(f'/api/claims/{cid}/messages',json={'body':'Should fail'},headers=ah).status_code==409


def test_repeated_concurrent_return_confirmation(app,account,report):
    a,ah,b,bh,lost,found,cid=accepted_pair(account,report)
    b.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=bh)
    a.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Library'},headers=ah)
    args=[(a.get_cookie('whereru_session').value,ah),(b.get_cookie('whereru_session').value,bh)]*3
    def confirm(arg):
        cookie,headers=arg;c=app.test_client();c.set_cookie('whereru_session',cookie)
        return c.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=headers).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:assert list(pool.map(confirm,args))==[200]*6
    assert a.get('/api/auth/me').json['user']['reputation']==2
    assert b.get('/api/auth/me').json['user']['reputation']==10
    with app.app_context():assert get_db().execute('SELECT COUNT(*) FROM reputation_events').fetchone()[0]==2


def test_close_cancels_pending_claims(account,report):
    a,ah,b,bh,lost,found,cid=accepted_pair(account,report)
    assert b.post(f"/api/listings/{found['id']}/close",json={'reason':'WITHDRAWN'},headers=bh).status_code==200
    assert a.get(f'/api/claims/{cid}').json['status']=='CANCELLED'
    assert a.get('/api/matches').json['matches']==[]


def test_classroom_catalog_search_errors(app,account):
    c,_,_=account();path=Path(app.config['CLASSROOM_CATALOG'])
    rooms=[{'id':f'RWH-{n}','campus':'Busch','building':'Richard Weeks Hall','room':str(n),'source_url':'https://example.com','images':[]} for n in (206,208)]
    path.write_text(json.dumps({'rooms':rooms}))
    assert c.get('/api/classrooms').json['count']==2
    assert c.get('/api/classrooms?q=206').json['count']==1
    assert c.get('/api/classrooms?campus=busch').json['count']==2
    assert c.get('/api/classrooms?q=missing').json['rooms']==[]
    assert c.get('/api/classrooms/rwh-208').json['room']=='208'
    assert c.get('/api/classrooms/missing').status_code==404
    for bad in ('bad-json',json.dumps({'classrooms':[]}),json.dumps({'rooms':[rooms[0],rooms[0]]})):
        path.write_text(bad);assert c.get('/api/classrooms').status_code==503


def test_location_batch_rolls_back_and_deletes(account,app):
    c,h,_=account();sid=c.post('/api/location-sessions',json={'consent':True},headers=h).json['id']
    point={'latitude':40.5,'longitude':-74.5,'accuracy':10,'recorded_at':time.time()}
    result=c.post(f'/api/location-sessions/{sid}/points',json={'points':[point,{**point,'latitude':200}]},headers=h)
    assert result.status_code==400
    assert c.get(f'/api/location-sessions/{sid}').json['points']==[]
    assert c.post(f'/api/location-sessions/{sid}/points',json={'points':[point,point]},headers=h).status_code==200
    assert len(c.get(f'/api/location-sessions/{sid}').json['points'])==1
    assert c.delete(f'/api/location-sessions/{sid}',json={},headers=h).status_code==200
    with app.app_context():assert get_db().execute('SELECT COUNT(*) FROM location_points').fetchone()[0]==0


def test_database_survives_app_restart(app,account,report):
    c,h,u=account();row=report(c,h)
    second=create_app(dict(app.config))
    client=second.test_client();client.set_cookie('whereru_session',c.get_cookie('whereru_session').value)
    assert client.get(f"/api/listings/{row['id']}").json['title']==row['title']
    assert client.get('/api/auth/me').json['user']['id']==u['id']


def test_cors_contract(app):
    app.config['ALLOWED_ORIGINS']=['http://localhost:8443']
    c=app.test_client()
    response=c.options('/api/listings',headers={'Origin':'http://localhost:8443','Access-Control-Request-Method':'POST'})
    assert response.status_code==204
    assert response.headers['Access-Control-Allow-Credentials']=='true'
    assert 'X-CSRF-Token' in response.headers['Access-Control-Allow-Headers']
    assert 'Access-Control-Allow-Origin' not in c.options('/api/listings',headers={'Origin':'https://evil.example'}).headers


def test_full_recovery_over_real_http(app):
    import threading
    import requests
    from werkzeug.serving import make_server
    server=make_server('127.0.0.1',0,app,threaded=True)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    owner=requests.Session();finder=requests.Session()
    try:
        def call(client,method,path,expected=200,**kwargs):
            response=client.request(method,base+path,timeout=10,**kwargs)
            assert response.status_code==expected,(path,response.status_code,response.text)
            return response.json()
        for client,email in ((owner,'network-owner@example.com'),(finder,'network-finder@example.com')):
            call(client,'POST','/api/auth/request-code',json={'email':email})
            result=call(client,'POST','/api/auth/verify-code',json={'email':email,'code':app.config['TEST_CODE_SINK'][email]})
            client.headers['X-CSRF-Token']=result['csrf_token']
        data={'title':'Blue bottle','description':'Blue steel bottle','category':'bottle','attributes':{'color':'blue'},
              'occurred_at':'2026-10-11T12:00:00Z','visibility':'PRIVATE','campus':'Busch'}
        lost=call(owner,'POST','/api/listings',201,json={**data,'type':'LOST'})
        found=call(finder,'POST','/api/listings',201,json={**data,'type':'FOUND'})
        image=call(finder,'POST',f"/api/listings/{found['id']}/images",201,files={'image':('bottle.png',picture(),'image/png')})
        assert owner.get(base+image['url'],timeout=10).status_code==404
        analysis=call(finder,'POST',f"/api/listings/{found['id']}/analyze",json={'consent_to_ai':True,'image_ids':[image['id']]})
        assert analysis['mode']=='demo'
        call(finder,'POST',f"/api/analyses/{analysis['id']}/apply",json={'confirm':True})
        assert call(owner,'GET','/api/matches')['matches']
        assert call(owner,'GET','/api/notifications')['unread_count']>=1
        claim=call(owner,'POST','/api/claims',201,json={'lost_id':lost['id'],'found_id':found['id'],'evidence':'Dent underneath cap'})
        cid=claim['id']
        call(finder,'POST',f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'})
        call(owner,'POST',f'/api/claims/{cid}/messages',201,json={'body':'Meet at the library'})
        assert call(finder,'GET',f'/api/claims/{cid}/messages')['messages'][0]['body']=='Meet at the library'
        call(finder,'POST',f'/api/claims/{cid}/handoff',201,json={'method':'MEETUP','place':'Library'})
        assert call(owner,'POST',f'/api/claims/{cid}/handoff/confirm',json={})['status']=='PENDING'
        assert call(finder,'POST',f'/api/claims/{cid}/handoff/confirm',json={})['status']=='COMPLETED'
        assert call(owner,'GET',f"/api/listings/{lost['id']}")['status']=='RETURNED'
        assert call(finder,'GET','/api/auth/me')['user']['reputation']==10
        for client in (owner,finder):
            call(client,'POST','/api/auth/logout',json={})
            call(client,'GET','/api/auth/me',401)
    finally:
        owner.close();finder.close();server.shutdown();worker.join(timeout=5);server.server_close()


def test_maintenance_commands_on_isolated_database(app,tmp_path):
    import subprocess
    import sys
    import os
    backend=Path(__file__).resolve().parents[1]
    env={**os.environ,'DATABASE_PATH':app.config['DATABASE'],'UPLOAD_DIR':app.config['UPLOAD_DIR'],
         'SECRET_KEY':app.config['SECRET_KEY'],'AI_MODE':'demo','AUTH_DELIVERY':'console','APP_ENV':'development',
         'GEMINI_API_KEY':''}
    for command in ('init','seed-demo','seed-demo','backup','cleanup'):
        result=subprocess.run([sys.executable,str(backend/'manage.py'),command],cwd=backend,env=env,capture_output=True,text=True)
        assert result.returncode==0,(command,result.stdout,result.stderr)
    backups=list(Path(app.config['DATABASE']).parent.glob('whereru-backup-*.db'))
    assert len(backups)==1
    conn=sqlite3.connect(backups[0])
    try:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert conn.execute('SELECT COUNT(*) FROM listings').fetchone()[0]==4
    finally: conn.close()
