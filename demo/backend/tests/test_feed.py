from datetime import datetime,timezone,timedelta
import io
from pathlib import Path
from PIL import Image
from whereru.vision import compare_room,ROOT,room_index


def test_missing_feed_filters_total_search_sort_and_pagination(account,report):
 c,h,_=account();now=datetime.now(timezone.utc)
 one=report(c,h,title='First red bottle',campus='Busch',location='Richard Weeks Hall',occurred_at=now.isoformat())
 two=report(c,h,title='Old bag',category='bag',campus='Livingston',location='Beck Hall',occurred_at=(now-timedelta(days=5)).isoformat())
 report(c,h,title='Private secret',visibility='PRIVATE');report(c,h,type='FOUND')
 assert c.get('/api/listings?type=LOST').json['total']==2
 r=c.get('/api/listings?type=LOST&campus=Busch&category=bottle&q=Weeks').json
 assert r['total']==1 and r['listings'][0]['id']==one['id']
 assert c.get('/api/listings?type=LOST&campus=Busch&category=bag').json['total']==0
 assert c.get('/api/listings?type=LOST&q=%25').json['total']==0
 assert c.get('/api/listings?type=LOST&sort=oldest&limit=1').json['listings'][0]['id']==one['id']
 assert c.get('/api/listings?type=LOST&sort=newest&limit=1').json['listings'][0]['id']==two['id']
 assert c.get('/api/listings?type=LOST&sort=oldest&offset=1&limit=1').json['listings'][0]['id']==two['id']
 cutoff=(now-timedelta(days=1)).isoformat()
 assert c.get('/api/listings',query_string={'type':'LOST','from':cutoff}).json['total']==1
 for query in ['sort=bad','status=CLOSED','status=PRIVATE','sort=id;DROP TABLE users']:
  assert c.get('/api/listings?'+query).status_code==400


def test_saved_shortlist_is_private_idempotent_and_hides_private_reports(account,report):
 owner,oh,_=account();helper,hh,_=account()
 r=report(owner,oh);secret=report(owner,oh,visibility='PRIVATE')
 route=f"/api/me/saved-listings/{r['id']}"
 assert helper.post(route,json={}).status_code==403
 assert helper.post(route,json={},headers=hh).status_code==200
 assert helper.post(route,json={},headers=hh).status_code==200
 assert helper.get('/api/me/saved-listings').json['ids']==[r['id']]
 assert owner.get('/api/me/saved-listings').json['ids']==[]
 assert helper.get('/api/listings?type=LOST&saved=true').json['total']==1
 assert owner.get('/api/listings?type=LOST&saved=true').json['total']==0
 assert helper.post(f"/api/me/saved-listings/{secret['id']}",json={},headers=hh).status_code==404
 assert owner.patch(f"/api/listings/{r['id']}",json={'visibility':'PRIVATE'},headers=oh).status_code==200
 assert helper.get('/api/me/saved-listings').json['ids']==[]
 assert helper.get('/api/listings?type=LOST&saved=true').json['total']==0
 assert helper.delete(route,json={},headers=hh).status_code==200
 assert helper.delete(route,json={},headers=hh).status_code==200


def test_status_filter_does_not_leak_private_fields(app,account,report):
 c,h,_=account();r=report(c,h,private_description='Hidden printing',private_location='IDEA3 Lab')
 with app.app_context():
  from whereru.db import get_db
  get_db().execute("UPDATE listings SET status='RETURNED' WHERE id=?",(r['id'],))
 assert c.get('/api/listings?type=LOST').json['total']==0
 row=c.get('/api/listings?type=LOST&status=RETURNED').json['listings'][0]
 assert row['status']=='RETURNED' and 'private_location' not in row and 'private_description' not in row


def test_supplied_weeks_lecture_photo_with_crop_resize_and_recompression(app):
 app.config['CLASSROOM_CATALOG']=str(ROOT/'data/classrooms.json');room_index.cache_clear()
 with Image.open(ROOT.parent/'public/examples/Weeks-lecture.jpg') as image:
  w,h=image.size;image=image.crop((25,20,w-25,h-20));image.thumbnail((900,900));raw=io.BytesIO();image.save(raw,'JPEG',quality=65)
 with app.app_context():
  result,_=compare_room(raw.getvalue())
  assert result[0]['id']=='RWH-105' and result[0]['needs_confirmation']
  assert 'supplied Weeks Hall photo' in ' '.join(result[0]['evidence'])
