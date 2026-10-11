import io
import pytest
from PIL import Image
from whereru import create_app


def demo_app(tmp_path,**overrides):
    config=dict(TESTING=True,DATABASE=str(tmp_path/'whereru-demo.db'),UPLOAD_DIR=str(tmp_path/'demo-uploads'),
        SECRET_KEY='local-test-secret-123456789012345678901',DEMO_ENABLED=True,APP_ENV='development',
        AUTH_DELIVERY='console',AI_MODE='demo',COOKIE_SECURE=False,DEMO_LAN_ALLOWED=False)
    config.update(overrides)
    return create_app(config)


def test_demo_guards_and_csrf(tmp_path):
    app=demo_app(tmp_path);c=app.test_client()
    assert c.get('/api/demo/status',environ_overrides={'REMOTE_ADDR':'192.168.1.2'}).status_code==404
    r=c.post('/api/demo/start',json={});assert r.status_code==200
    assert not r.json['user']['email_verified']
    assert c.post('/api/demo/start',json={}).status_code==403
    assert c.post('/api/demo/switch',json={'role':'owner'}).status_code==403
    assert c.post('/api/demo/switch',json={'role':'admin'},headers={'X-CSRF-Token':r.json['csrf_token']}).status_code==400
    app.config['DEMO_ENABLED']=False
    assert c.get('/api/demo/status').status_code==404
    other=demo_app(tmp_path,DATABASE=str(tmp_path/'real.db'))
    assert other.test_client().get('/api/demo/status').status_code==404


@pytest.mark.parametrize('rehearsal',[1,2,3])
def test_full_demo_recovery(tmp_path,rehearsal):
    app=demo_app(tmp_path);c=app.test_client()
    def post(path,data,expected=200,headers=None):
        r=c.post('/api'+path,json=data,headers=headers or h)
        assert r.status_code==expected,(path,r.json)
        return r.json
    r=c.post('/api/demo/start',json={});assert r.status_code==200
    h={'X-CSRF-Token':r.json['csrf_token']}
    seed=c.get('/api/listings').json['listings'];lost=next(i for i in seed if i['category']=='bottle')
    assert 'private_description' not in lost and 'distinctive_features' not in lost['attributes']
    assert c.patch('/api/listings/'+str(lost['id']),json={'title':'Wrong owner'},headers=h).status_code==403
    found=post('/listings',dict(type='FOUND',title='Blue water bottle',description='Blue steel bottle left after class',category='bottle',attributes={'color':'blue','material':'steel'},campus='College Ave',location='Hardenbergh Hall',occurred_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),private_description='Small white cat sticker near the bottom'),201)
    raw=io.BytesIO();Image.new('RGB',(80,80),'blue').save(raw,'JPEG');raw.seek(0)
    uploaded=c.post(f"/api/listings/{found['id']}/images",data={'image':(raw,'bottle.jpg')},headers=h)
    assert uploaded.status_code==201
    owned=c.get(f"/api/listings/{found['id']}").json;image=owned['images'][0]['url']
    assert c.get(image).status_code==200
    r=post('/demo/switch',{'role':'owner'});h={'X-CSRF-Token':r['csrf_token']}
    assert c.get(image).status_code==404
    m=c.get('/api/matches').json['matches'];assert len(m)==1 and m[0]['found_id']==found['id']
    assert c.get('/api/notifications').json['unread_count']==1
    claim=post('/claims',{'found_id':found['id'],'lost_id':lost['id'],'evidence':'There is a small white cat sticker near the bottom.'},201)
    assert c.post(f"/api/claims/{claim['id']}/review",json={'decision':'ACCEPTED'},headers=h).status_code==403
    post(f"/claims/{claim['id']}/messages",{'body':'Meet at the student center?'},201)
    r=post('/demo/switch',{'role':'finder'});h={'X-CSRF-Token':r['csrf_token']}
    assert c.get(f"/api/claims/{claim['id']}/messages").json['messages'][0]['body']=='Meet at the student center?'
    post(f"/claims/{claim['id']}/review",{'decision':'ACCEPTED'})
    post(f"/claims/{claim['id']}/handoff",{'method':'MEETUP','place':'Busch Student Center lobby'},201)
    assert post(f"/claims/{claim['id']}/handoff/confirm",{})['status']=='PENDING'
    r=post('/demo/switch',{'role':'owner'});h={'X-CSRF-Token':r['csrf_token']}
    assert post(f"/claims/{claim['id']}/handoff/confirm",{})['status']=='COMPLETED'
    post(f"/claims/{claim['id']}/handoff/confirm",{})
    assert c.get('/api/auth/me').json['user']['reputation']==2
    assert next(i for i in c.get('/api/me/listings').json['listings'] if i['id']==lost['id'])['status']=='RETURNED'
    r=post('/demo/switch',{'role':'finder'});h={'X-CSRF-Token':r['csrf_token']}
    assert r['user']['reputation']==10
    assert c.get('/api/me/listings').json['listings'][0]['status']=='RETURNED'
    r=post('/demo/start',{});h={'X-CSRF-Token':r['csrf_token']}
    assert r['user']['reputation']==0 and c.get('/api/claims').json['claims']==[]
    assert len(c.get('/api/listings').json['listings'])==3


def test_private_registry_account_isolation_and_persistence(tmp_path):
    app=demo_app(tmp_path);c=app.test_client();r=c.post('/api/demo/start',json={});h={'X-CSRF-Token':r.json['csrf_token']}
    assert len(c.get('/api/me/registered-items').json['items'])==2
    created=c.post('/api/me/registered-items',json={'name':'Sample notebook','description':'Red elastic strap','serial':'DEMO-123','photoAdded':False},headers=h)
    assert created.status_code==201
    iid=created.json['id']
    switch=c.post('/api/demo/switch',json={'role':'owner'},headers=h);h={'X-CSRF-Token':switch.json['csrf_token']}
    assert c.get('/api/me/registered-items').json['items']==[]
    assert c.delete('/api/me/registered-items/'+iid,json={},headers=h).status_code==404
    switch=c.post('/api/demo/switch',json={'role':'finder'},headers=h);h={'X-CSRF-Token':switch.json['csrf_token']}
    assert any(i['serial']=='DEMO-123' for i in c.get('/api/me/registered-items').json['items'])
    assert c.delete('/api/me/registered-items/'+iid,json={},headers=h).status_code==200
    assert len(c.get('/api/me/registered-items').json['items'])==2


def test_demo_is_disabled_in_production(tmp_path):
    app=demo_app(tmp_path,APP_ENV='production',AUTH_DELIVERY='smtp',COOKIE_SECURE=True)
    c=app.test_client()
    assert c.get('/api/demo/status').status_code==404
    assert c.post('/api/demo/start',json={}).status_code==404
    assert c.post('/api/demo/switch',json={'role':'finder'}).status_code==404
