import io
import json
import time
from pathlib import Path
from PIL import Image
from whereru.db import get_db


def upload(c,h,lid):
    data=io.BytesIO();Image.new('RGB',(50,50),'blue').save(data,'PNG');data.seek(0)
    return c.post(f'/api/listings/{lid}/images',data={'image':(data,'x.png')},headers=h).json['id']


def test_selected_places_and_density_no_route_leak(account,report):
    a,ah,u=account();b,bh,bu=account();r=report(a,ah)
    places=[{'label':'Library','latitude':40.50,'longitude':-74.45,'share_public':True,'priority':3},
            {'label':'Private stop','latitude':40.51,'longitude':-74.46,'share_public':False,'priority':2}]
    assert a.post(f"/api/listings/{r['id']}/potential-locations",json={'locations':places},headers=ah).status_code==200
    own=a.get(f"/api/listings/{r['id']}/search-areas").json
    other=b.get(f"/api/listings/{r['id']}/search-areas").json
    assert len(own['features'])==2 and len(other['features'])==1
    assert 'Private stop' not in str(other)
    density=b.get('/api/maps/density').json
    assert density['contributing_reports']==1 and len(density['features'])==1
    assert sum(f['properties']['weight'] for f in density['features'])==1
    a.patch(f"/api/listings/{r['id']}",json={'visibility':'PRIVATE'},headers=ah)
    assert b.get('/api/maps/density').json['contributing_reports']==0
    assert b.get(f"/api/listings/{r['id']}/search-areas").status_code==404


def test_recording_consent_ownership_stop_expiry(app,account):
    a,ah,u=account();b,bh,bu=account()
    assert a.post('/api/location-sessions',json={},headers=ah).status_code==400
    sid=a.post('/api/location-sessions',json={'consent':True},headers=ah).json['id']
    point={'latitude':40.5,'longitude':-74.4,'accuracy':15,'recorded_at':time.time()}
    assert a.post(f'/api/location-sessions/{sid}/points',json={'points':[point]},headers=ah).status_code==200
    assert b.get(f'/api/location-sessions/{sid}').status_code==404
    assert a.post(f'/api/location-sessions/{sid}/points',json={'points':[{**point,'recorded_at':0}]},headers=ah).status_code==400
    assert len(a.get(f'/api/location-sessions/{sid}').json['points'])==1
    a.post(f'/api/location-sessions/{sid}/stop',json={},headers=ah)
    assert a.post(f'/api/location-sessions/{sid}/points',json={'points':[point]},headers=ah).status_code==409
    with app.app_context():get_db().execute('UPDATE recording_sessions SET expires=0 WHERE id=?',(sid,))
    assert a.get(f'/api/location-sessions/{sid}').status_code==404
    assert a.delete(f'/api/location-sessions/{sid}',json={},headers=ah).status_code==200


def test_demo_ai_consent_and_stale_apply(account,report):
    a,ah,u=account();r=report(a,ah)
    path=f"/api/listings/{r['id']}/analyze"
    assert a.post(path,json={},headers=ah).status_code==400
    result=a.post(path,json={'consent_to_ai':True},headers=ah)
    assert result.status_code==200 and result.json['mode']=='demo'
    assert 'No photograph recognition' in result.json['suggestion']['uncertainty']
    aid=result.json['id']
    applied=a.post(f'/api/analyses/{aid}/apply',json={'confirm':True},headers=ah)
    assert applied.status_code==200,applied.json
    assert a.post(f'/api/analyses/{aid}/apply',json={'confirm':True},headers=ah).status_code==409


def test_live_ai_failure_fallback_and_unowned_images(app,account,report,monkeypatch):
    from whereru import ai
    a,ah,u=account();b,bh,bu=account();r=report(a,ah);other=report(b,bh)
    image_id=upload(b,bh,other['id'])
    assert a.post(f"/api/listings/{r['id']}/analyze",json={'consent_to_ai':True,'image_ids':[image_id]},headers=ah).status_code==404
    app.config['AI_MODE']='gemini'
    def fail(*args):raise RuntimeError('secret-key-must-not-appear')
    monkeypatch.setattr(ai,'generate',fail)
    response=a.post(f"/api/listings/{r['id']}/analyze",json={'consent_to_ai':True},headers=ah)
    assert response.status_code==200 and response.json['mode']=='fallback'
    assert 'secret-key' not in response.get_data(as_text=True)


def test_room_catalog_and_grounding(app,account,report,monkeypatch,tmp_path):
    from whereru import ai
    a,ah,u=account();r=report(a,ah);image_id=upload(a,ah,r['id'])
    path=f"/api/listings/{r['id']}/recognize-room";data={'consent_to_ai':True,'image_id':image_id}
    assert a.post(path,json=data,headers=ah).json['candidates']==[]
    ref=tmp_path/'reference.jpg';Image.new('RGB',(40,40),'white').save(ref)
    Path(app.config['CLASSROOM_CATALOG']).write_text(json.dumps({'rooms':[{'id':'room-a','campus':'Campus','building':'Building','room':'101','source_url':'example','images':['reference.jpg']}]}))
    app.config['AI_MODE']='gemini'
    def result(*args):return {'candidates':[{'room_id':'invented','evidence':[],'conflicts':[]},{'room_id':'room-a','evidence':['similar windows'],'conflicts':[]}],
                             'visible_sign_text':'','needs_confirmation':False,'uncertainty':'Uncertain'}
    monkeypatch.setattr(ai,'generate',result)
    response=a.post(path,json=data,headers=ah)
    assert response.status_code==200,response.json
    assert len(response.json['candidates'])==1
    assert response.json['candidates'][0]['room_id']=='room-a' and response.json['needs_confirmation'] is True


def test_semantic_index_rechecks_matches_and_invalidates_on_edit(app,account,report,monkeypatch):
    from whereru import ai
    a,ah,u=account();b,bh,bu=account()
    lost=report(a,ah,title='Insulated drink container',description='',attributes={},location='',category='other')
    found=report(b,bh,type='FOUND',title='Metal flask',description='',attributes={},location='',category='other',campus='Busch')
    assert not a.get('/api/matches').json['matches']
    app.config['AI_MODE']='gemini';monkeypatch.setattr(ai,'embed',lambda content:[1.0,0.1,0.5])
    for client,headers,row in ((a,ah,lost),(b,bh,found)):
        assert client.post(f"/api/listings/{row['id']}/semantic-index",json={'consent_to_ai':True},headers=headers).status_code==200
    assert len(a.get('/api/matches').json['matches'])==1
    assert 'AI-indexed' in str(a.get('/api/matches').json)
    b.patch(f"/api/listings/{found['id']}",json={'title':'Something different'},headers=bh)
    assert not a.get('/api/matches').json['matches']
