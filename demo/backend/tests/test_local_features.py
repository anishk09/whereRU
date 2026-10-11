import io
import json
from pathlib import Path
import pytest
from PIL import Image
from whereru import create_app
from whereru.demo import seed_pool
from whereru.nearby import distance_meters
from whereru.vision import describe, ROOT, compare_room, native_analysis


@pytest.mark.parametrize('name,category,color',[('IMG_3989','bottle','red'),('IMG_3990','bottle','red'),
 ('IMG_3991','bottle','gray'),('IMG_3992','bottle','gray'),('IMG_3993','electronics','gray'),('IMG_3994','electronics','gray'),('IMG_3995','electronics','gray')])
def test_reviewed_photo_retrieval_after_resizing_and_reencoding(name,category,color):
    # Query differs from reference bytes; filename is never used to identify it.
    with Image.open(ROOT.parent/'public/examples'/f'{name}.jpg') as image:
        image.thumbnail((900,900)); raw=io.BytesIO();image.save(raw,'JPEG',quality=70)
    result=describe(raw.getvalue())
    assert result['category']==category and result['attributes']['color']==color
    assert result['mode']=='local-reference' and result['requires_review']
    assert result['private_details'] not in result['description']


def test_unknown_photo_does_not_invent_item_or_brand(monkeypatch):
    monkeypatch.setattr('whereru.vision.native_analysis',lambda raw:dict(labels=[],text=[],engine='local-test'))
    raw=io.BytesIO();Image.new('RGB',(300,300),'black').save(raw,'JPEG')
    result=describe(raw.getvalue())
    assert result['category']=='other' and result['title']=='Unidentified item'
    assert result['attributes']['brand'] is None and result['private_details']==''


def test_geographic_distance_handles_identical_and_separate_campuses():
    assert distance_meters(40.5021,-74.4480,40.5021,-74.4480)==0
    assert distance_meters(40.5021,-74.4480,40.5230,-74.4588)>2000


def test_native_ocr_is_real_and_local():
    if not (ROOT/'.tools/local-vision').exists():pytest.skip('Native macOS Vision not installed on this host')
    result=native_analysis((ROOT.parent/'public/examples/IMG_3990.jpg').read_bytes())
    assert result['engine']=='Apple Vision (on-device)'
    assert any('RUTGERS' in word.upper() for word in result['text'])


def test_room_reference_geometry_and_blank_rejection(app):
    app.config['CLASSROOM_CATALOG']=str(ROOT/'data/classrooms.json')
    with app.app_context():
        candidates,_=compare_room((ROOT/'data/room-references/ABW-1150A-still.jpg').read_bytes())
        assert candidates[0]['id']=='ABW-1150A' and candidates[0]['inliers']>100
        assert candidates[0]['needs_confirmation']
        blank=io.BytesIO();Image.new('RGB',(640,640),'black').save(blank,'JPEG')
        candidates,_=compare_room(blank.getvalue());assert candidates==[]


def test_local_photo_endpoint_needs_auth_csrf_and_valid_image(account,app):
    client,h,_=account()
    raw=(ROOT.parent/'public/examples/IMG_3989.jpg').read_bytes()
    assert app.test_client().post('/api/vision/items',data={'image':(io.BytesIO(raw),'photo.jpg')}).status_code==401
    assert client.post('/api/vision/items',data={'image':(io.BytesIO(raw),'photo.jpg')}).status_code==403
    r=client.post('/api/vision/items',data={'image':(io.BytesIO(raw),'unrelated-name.jpg')},headers=h)
    assert r.status_code==200 and r.json['attributes']['color']=='red'
    assert client.post('/api/vision/items',data={'image':(io.BytesIO(b'bad'),'fake.jpg')},headers=h).status_code==400


def test_heic_normalizes_without_exif(account):
    # The supplied HEIC is a real 24 MP file, not a mocked format marker.
    source=Path('/Users/sujai/Downloads/IMG_3989.HEIC')
    if not source.exists():pytest.skip('Original HEIC fixture is unavailable')
    c,h,_=account()
    r=c.post('/api/vision/normalize',data={'image':(io.BytesIO(source.read_bytes()),'photo.HEIC')},headers=h)
    assert r.status_code==200
    import base64
    image=Image.open(io.BytesIO(base64.b64decode(r.json['image'].split(',')[1])))
    assert image.format=='JPEG' and not image.getexif() and max(image.size)<=2000


def demo(tmp_path):
    return create_app({'DATABASE':str(tmp_path/'whereru-demo.db'),'UPLOAD_DIR':str(tmp_path/'demo-uploads'),
        'TESTING':True,'DEMO_ENABLED':True,'DEMO_LAN_ALLOWED':True,'APP_ENV':'development','SECRET_KEY':'test-secret-123456789012345678901234','AI_MODE':'demo','GEMINI_API_KEY':''})


def test_three_lan_sessions_and_login_do_not_reset_data(tmp_path):
    app=demo(tmp_path);clients=[]
    for role,ip in [('owner','192.168.1.20'),('finder','192.168.1.21'),('helper','192.168.1.22')]:
        c=app.test_client();r=c.post('/api/demo/session',json={'role':role},environ_overrides={'REMOTE_ADDR':ip})
        assert r.status_code==200;clients.append((c,{'X-CSRF-Token':r.json['csrf_token']},r.json['user']['id']))
    assert len({uid for _,_,uid in clients})==3
    owner,h,_=clients[0]
    assert owner.get('/api/auth/me').json['user']['email'].startswith('owner@')
    assert clients[1][0].get('/api/auth/me').json['user']['email'].startswith('finder@')
    assert owner.post('/api/demo/reset',json={},headers=h,environ_overrides={'REMOTE_ADDR':'192.168.1.20'}).status_code==404
    assert app.test_client().post('/api/demo/session',json={'role':'finder'},environ_overrides={'REMOTE_ADDR':'8.8.8.8'}).status_code==404
    with app.app_context():
        from whereru.db import get_db
        assert get_db().execute('SELECT COUNT(*) FROM listings').fetchone()[0]==140
    density=owner.get('/api/maps/density').json
    assert density['contributing_reports']==105 and len(density['features'])>=14
    assert abs(sum(f['properties']['weight'] for f in density['features'])-105)<.01
    for campus in ['College Ave','Busch','Livingston','Cook/Douglass']:
        assert owner.get('/api/maps/density?campus='+campus).json['contributing_reports']>0


def test_nearby_opt_in_dedup_exact_details_and_other_user_location_stay_private(account,report):
    owner,oh,_=account();helper,hh,_=account();outsider,xh,_=account()
    data=dict(consent=True,label='Academic Building West',latitude=40.5021,longitude=-74.4480,radius_meters=350)
    assert helper.post('/api/me/nearby-location',json={**data,'consent':False},headers=hh).status_code==400
    assert helper.post('/api/me/nearby-location',json=data,headers=hh).status_code==200
    item=report(owner,oh,private_description='Private serial SECRET',private_location='Exact room 1150A',location='Academic Building West')
    points=dict(locations=[dict(label='Academic Building West',latitude=40.5021,longitude=-74.4480,priority=3,share_public=True)])
    for _ in range(3):assert owner.post(f"/api/listings/{item['id']}/potential-locations",json=points,headers=oh).status_code==200
    alerts=helper.get('/api/notifications').json['notifications'];assert len(alerts)==1 and alerts[0]['kind']=='NEARBY'
    detail=helper.get(f"/api/nearby-alerts/{item['id']}")
    assert detail.status_code==200 and 'SECRET' not in detail.text and '1150A' not in detail.text
    assert outsider.get(f"/api/nearby-alerts/{item['id']}").status_code==404
    assert outsider.get('/api/me/nearby-location').json['location'] is None
    assert helper.delete('/api/me/nearby-location',json={},headers=hh).status_code==200
    assert helper.get('/api/me/nearby-location').json['location'] is None


@pytest.mark.parametrize('private,shared,far',[(True,True,False),(False,False,False),(False,True,True)])
def test_private_unshared_or_distant_reports_do_not_alert_helpers(account,report,private,shared,far):
    owner,oh,_=account();helper,hh,_=account()
    assert helper.post('/api/me/nearby-location',json=dict(consent=True,label='West',latitude=40.5021,longitude=-74.4480),headers=hh).status_code==200
    item=report(owner,oh,visibility='PRIVATE' if private else 'PUBLIC')
    point=dict(label='A selected place',latitude=40.5230 if far else 40.5021,longitude=-74.4480,priority=1,share_public=shared)
    assert owner.post(f"/api/listings/{item['id']}/potential-locations",json={'locations':[point]},headers=oh).status_code==200
    assert helper.get('/api/notifications').json['notifications']==[]


def test_two_accounts_matching_notification_then_claim_confirmation(account,report):
    owner,oh,ou=account();finder,fh,fu=account()
    lost=report(owner,oh)
    found=report(finder,fh,type='FOUND',private_description='Distinctive sticker')
    notification=owner.get('/api/notifications').json['notifications'][0]
    assert notification['kind']=='MATCH'
    m=owner.get(f"/api/matches/{notification['resource_id']}").json
    assert m['lost_id']==lost['id'] and m['found_id']==found['id']
    assert finder.get(f"/api/matches/{m['id']}").status_code==404
    claim=owner.post('/api/claims',json=dict(found_id=found['id'],lost_id=lost['id'],evidence='I know the distinctive sticker'),headers=oh).json
    assert finder.get('/api/notifications').json['notifications'][0]['kind']=='CLAIM'
    assert finder.post(f"/api/claims/{claim['id']}/review",json={'decision':'ACCEPTED'},headers=fh).status_code==200
    assert finder.post(f"/api/claims/{claim['id']}/handoff",json={'method':'MEETUP','place':'Public student center'},headers=fh).status_code==201
    assert finder.post(f"/api/claims/{claim['id']}/handoff/confirm",json={},headers=fh).json['status']=='PENDING'
    assert owner.post(f"/api/claims/{claim['id']}/handoff/confirm",json={},headers=oh).json['status']=='COMPLETED'
    for c,h,pts in [(owner,oh,2),(finder,fh,10)]:
        c.post(f"/api/claims/{claim['id']}/handoff/confirm",json={},headers=h)
        assert c.get('/api/auth/me').json['user']['reputation']==pts


@pytest.mark.parametrize('name',[f'IMG_{n}' for n in range(3989,3996)])
def test_user_confirmed_idea3_examples_are_labeled_honestly(name,app):
    app.config['CLASSROOM_CATALOG']=str(ROOT/'data/classrooms.json')
    with Image.open(ROOT.parent/'public/examples'/f'{name}.jpg') as image:
        image.thumbnail((900,900));raw=io.BytesIO();image.save(raw,'JPEG',quality=70)
    with app.app_context():
        result,_=compare_room(raw.getvalue())
        assert result[0]['id']=='RWH-IDEA3' and result[0]['method']=='reviewed-example'
        assert result[0]['needs_confirmation'] and 'not an official Rutgers panorama' in ' '.join(result[0]['evidence'])

def test_official_reference_with_crop_and_recompression(app):
    app.config['CLASSROOM_CATALOG']=str(ROOT/'data/classrooms.json')
    with Image.open(ROOT/'data/room-references/ABW-1150A-still.jpg') as image:
        w,h=image.size;image=image.crop((50,50,w-50,h-50));raw=io.BytesIO();image.save(raw,'JPEG',quality=70)
    with app.app_context():
        result,_=compare_room(raw.getvalue())
        assert result[0]['id']=='ABW-1150A' and result[0]['method']=='local-reference'
