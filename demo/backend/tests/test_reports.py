import io
import pytest
from PIL import Image
from whereru.db import get_db


def png():
    b=io.BytesIO();Image.new('RGB',(100,80),'blue').save(b,'PNG');b.seek(0);return b


def test_report_privacy_and_ownership(app,account,report):
    a,ah,au=account();b,bh,bu=account()
    r=report(a,ah,private_description='Secret sticker',private_location='Room 9',attributes={'color':'blue','distinctive_features':['Secret sticker']})
    assert r['creator_id']==au['id']
    public=b.get(f"/api/listings/{r['id']}").json
    assert 'private_description' not in public and 'distinctive_features' not in public['attributes']
    assert 'creator_id' not in public
    assert b.patch(f"/api/listings/{r['id']}",json={'title':'Hijack'},headers=bh).status_code==403
    assert app.test_client().get('/api/listings').status_code==401
    assert a.patch(f"/api/listings/{r['id']}",json={'visibility':'PRIVATE'},headers=ah).status_code==200
    assert b.get(f"/api/listings/{r['id']}").status_code==404
    assert not b.get('/api/listings').json['listings']
    assert a.get('/api/me/listings').json['listings'][0]['private_description']=='Secret sticker'
    assert not b.get('/api/me/listings').json['listings']


@pytest.mark.parametrize('change',[{'creator_id':99},{'status':'RETURNED'},{'reward':True},{'reward':float('inf')},{'title':123},{'occurred_at':'2026-10-10'},{'attributes':{'weird':'x'}}])
def test_validation(account,change):
    c,h,u=account()
    data=dict(type='LOST',title='Bottle',occurred_at='2026-10-10T14:00:00Z');data.update(change)
    assert c.post('/api/listings',json=data,headers=h).status_code==400


def test_sensitive_and_close(account,report):
    c,h,u=account()
    data=dict(type='FOUND',title='ID card',category='id_card',occurred_at='2026-10-10T14:00:00Z')
    assert c.post('/api/listings',json=data,headers=h).status_code==400
    r=report(c,h,category='id_card',visibility='PRIVATE')
    assert c.post(f"/api/listings/{r['id']}/close",json={'reason':'SELF_RECOVERED'},headers=h).status_code==200
    assert c.get('/api/auth/me').json['user']['reputation']==0
    assert c.patch(f"/api/listings/{r['id']}",json={'title':'No'},headers=h).status_code==409


def test_search_and_filters(account,report):
    c,h,u=account();report(c,h)
    assert len(c.get('/api/listings?q=blue&category=bottle&type=LOST').json['listings'])==1
    assert not c.get('/api/listings?q=umbrella').json['listings']
    assert c.get('/api/listings?limit=999').status_code==400
    assert c.get('/api/listings?from=bad').status_code==400


def test_images_private_by_default(account,report,app):
    a,ah,u=account();b,bh,bu=account();r=report(a,ah)
    upload=a.post(f"/api/listings/{r['id']}/images",data={'image':(png(),'../photo.png')},headers=ah)
    assert upload.status_code==201,upload.json
    image_id=upload.json['id']
    assert b.get(f'/api/images/{image_id}').status_code==404
    image=a.get(f'/api/images/{image_id}')
    assert image.status_code==200 and image.mimetype=='image/jpeg'
    assert not Image.open(io.BytesIO(image.data)).getexif()
    assert a.patch(f'/api/images/{image_id}',json={'is_public':True},headers=ah).status_code==200
    assert b.get(f'/api/images/{image_id}').status_code==200
    a.patch(f"/api/listings/{r['id']}",json={'visibility':'PRIVATE'},headers=ah)
    assert b.get(f'/api/images/{image_id}').status_code==404
    assert a.post(f"/api/listings/{r['id']}/images",data={'image':(io.BytesIO(b'<script>bad</script>'),'a.jpg')},headers=ah).status_code==400
    assert a.delete(f'/api/images/{image_id}',json={},headers=ah).status_code==200
    assert a.get(f'/api/images/{image_id}').status_code==404
