"""Bounded HTTP stress test on isolated databases; never touches the presentation DB.
20 new authenticated users per round, actual HTTP cookies/CSRF, concurrent writes,
matching, nearby alerts, uploads, saved filters, claims, duplicate confirmations,
restart durability and mixed read load. No Gemini provider calls.
"""
import concurrent.futures as cf
import http.cookiejar
import io
import json
import logging
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from werkzeug.serving import make_server
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whereru import create_app
from whereru.db import atomic,get_db
from whereru.demo import seed_pool
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
logging.getLogger('werkzeug').setLevel(logging.ERROR)

class Client:
 def __init__(self,base,metrics,lock):
  self.base=base;self.metrics=metrics;self.lock=lock;self.csrf='';self.uid=None
  self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(self,path,data=None,method=None,expected=200,raw=False,content_type=None):
  headers={}
  if data is not None:
   if not isinstance(data,bytes):data=json.dumps(data).encode();content_type='application/json'
   headers={'Content-Type':content_type,'X-CSRF-Token':self.csrf}
  start=time.perf_counter()
  try:
   api_path=path if path.startswith('/api/') else '/api'+path
   with self.opener.open(urllib.request.Request(self.base+api_path,data=data,headers=headers,method=method),timeout=40) as r:status=r.status;body=r.read()
  except urllib.error.HTTPError as e:status=e.code;body=e.read()
  with self.lock:self.metrics.append({'path':path.split('?')[0],'status':status,'ms':round((time.perf_counter()-start)*1000,2)})
  if expected is None:return status,json.loads(body)
  allowed=expected if isinstance(expected,tuple) else (expected,)
  assert status in allowed,(path,status,body[:250].decode(errors='replace'))
  return body if raw else json.loads(body)


def multipart(raw):
 boundary='WhereRUStress'
 body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="unrelated-name.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
 return body,'multipart/form-data; boundary='+boundary


def run_round(round_number):
 with tempfile.TemporaryDirectory(prefix='whereru-stress-') as directory:
  config={'DATABASE':str(Path(directory)/'whereru-demo.db'),'UPLOAD_DIR':str(Path(directory)/'demo-uploads'),
   'TESTING':True,'TEST_CODE_SINK':{},'AUTH_DELIVERY':'console','AI_MODE':'demo','GEMINI_API_KEY':'','DEMO_ENABLED':True,
   'DEMO_LAN_ALLOWED':False,'APP_ENV':'development','SECRET_KEY':'isolated-stress-only-secret-12345678901234567890','COOKIE_SECURE':False}
  app=create_app(config)
  with app.app_context():
   with atomic() as db:seed_pool(db)
  server=make_server('127.0.0.1',0,app,threaded=True);port=server.server_port
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  metrics=[];lock=threading.Lock();clients=[Client(f'http://127.0.0.1:{port}',metrics,lock) for _ in range(20)]
  started=time.perf_counter()
  try:
   def signup(i):
    c=clients[i];email=f'stress{round_number}-{i}@demo.whereru.local'
    c.call('/auth/request-code',{'email':email})
    r=c.call('/auth/verify-code',{'email':email,'code':config['TEST_CODE_SINK'][email]});c.csrf=r['csrf_token'];c.uid=r['user']['id']
    c.call('/me',{'display_name':f'Stress Student {i}'},method='PATCH')
    return c.uid
   with cf.ThreadPoolExecutor(max_workers=20) as pool:ids=list(pool.map(signup,range(20)))
   assert len(set(ids))==20
   # Default limits stay active: the twenty-first code request from this IP is rejected.
   Client(clients[0].base,metrics,lock).call('/auth/request-code',{'email':'over-limit@demo.whereru.local'},expected=429)
   def subscribe(i):
    clients[i].call('/me/nearby-location',{'consent':True,'label':'Richard Weeks Hall','latitude':40.524464,'longitude':-74.459505,'radius_meters':350})
   with cf.ThreadPoolExecutor(max_workers=20) as pool:list(pool.map(subscribe,range(20)))
   now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
   def create_pair(i):
    owner,finder=clients[i*2:i*2+2]
    base={'title':f'Stress pair {i} gray tablet','category':'electronics','description':f'Tablet model pair{i} in folding case.',
      'attributes':{'color':f'pair{i}','brand':f'testbrand{i}','model':f'model{i}'},'campus':'Busch','location':'Richard Weeks Hall',
      'occurred_at':now,'visibility':'PUBLIC','private_location':'IDEA3 Lab','private_description':f'Private mark {i}'}
    lost=owner.call('/listings',{**base,'type':'LOST'},expected=201)
    owner.call(f"/listings/{lost['id']}/potential-locations",{'locations':[{'label':'Richard Weeks Hall','latitude':40.524464,'longitude':-74.459505,'priority':3,'share_public':True}]})
    found=finder.call('/listings',{**base,'type':'FOUND'},expected=201)
    assert any(m['lost_id']==lost['id'] and m['found_id']==found['id'] for m in owner.call('/matches?limit=100')['matches'])
    assert any(n['kind']=='MATCH' for n in owner.call('/notifications?limit=100')['notifications'])
    observer=clients[(i*2+2)%20]
    alert=observer.call(f"/nearby-alerts/{lost['id']}")
    assert 'IDEA3' not in json.dumps(alert) and 'Private mark' not in json.dumps(alert)
    observer.call(f"/listings/{found['id']}",{'title':'Unauthorized'},method='PATCH',expected=403)
    owner.call(f"/me/saved-listings/{lost['id']}",{});owner.call(f"/me/saved-listings/{lost['id']}",{})
    assert owner.call('/me/saved-listings')['ids']==[lost['id']]
    claim=owner.call('/claims',{'found_id':found['id'],'lost_id':lost['id'],'evidence':f'Private mark {i} on the case'},expected=201)
    observer.call(f"/claims/{claim['id']}",expected=404)
    finder.call(f"/claims/{claim['id']}/review",{'decision':'ACCEPTED'})
    finder.call(f"/claims/{claim['id']}/messages",{'body':f'Public meeting point for pair {i}'},expected=201)
    assert owner.call(f"/claims/{claim['id']}/messages")['messages']
    finder.call(f"/claims/{claim['id']}/handoff",{'method':'MEETUP','place':'Busch Student Center'},expected=201)
    return (lost['id'],found['id'],claim['id'])
   with cf.ThreadPoolExecutor(max_workers=10) as pool:pairs=list(pool.map(create_pair,range(10)))
   raw=(ROOT.parent/'public/examples/IMG_3990.jpg').read_bytes();image_body,image_type=multipart(raw)
   def analyze(i):
    result=clients[i].call('/vision/items',image_body,content_type=image_type)
    assert result['attributes']['color']=='red' and result['requires_review']
   with cf.ThreadPoolExecutor(max_workers=10) as pool:list(pool.map(analyze,range(20)))
   def private_upload(i):
    c=clients[i];row=c.call('/listings',{'type':'LOST','title':f'Private test {i}','category':'keys','visibility':'PRIVATE','occurred_at':now},expected=201)
    image=c.call(f"/listings/{row['id']}/images",image_body,content_type=image_type,expected=201)
    assert c.call(image['url'],raw=True)[:2]==b'\xff\xd8'
    other=clients[(i+1)%20];other.call(image['url'],expected=404);other.call(f"/listings/{row['id']}",expected=404)
    return image['id']
   with cf.ThreadPoolExecutor(max_workers=10) as pool:images=list(pool.map(private_upload,range(20)))
   confirmation_jobs=[(clients[i*2+role],pairs[i][2]) for i in range(10) for role in (0,1) for _ in range(3)]
   def confirm(job):job[0].call(f'/claims/{job[1]}/handoff/confirm',{})
   with cf.ThreadPoolExecutor(max_workers=20) as pool:list(pool.map(confirm,confirmation_jobs))
   for i,c in enumerate(clients):assert c.call('/auth/me')['user']['reputation']==(2 if i%2==0 else 10)
   # Two competing reviews must yield one winner, never two accepted claims.
   found=clients[1].call('/listings',{'type':'FOUND','title':'Concurrent claim contest','category':'bag','occurred_at':now},expected=201)
   claims=[clients[i].call('/claims',{'found_id':found['id'],'evidence':f'Private contender evidence {i}'},expected=201)['id'] for i in (0,2)]
   def race(cid):return clients[1].call(f'/claims/{cid}/review',{'decision':'ACCEPTED'},expected=None)[0]
   with cf.ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(race,claims))==[200,409]
   read_paths=['/auth/me','/me/listings','/listings?type=LOST&campus=Busch&sort=last_seen&limit=24',
    '/notifications?limit=100','/maps/density?campus=Busch','/me/saved-listings','/claims','/me/activity']
   read_start=len(metrics)
   def read_load(i):
    c=clients[i]
    for n in range(50):
     r=c.call(read_paths[n%len(read_paths)])
     if n%len(read_paths)==0:assert r['user']['id']==c.uid
   with cf.ThreadPoolExecutor(max_workers=20) as pool:list(pool.map(read_load,range(20)))
   reads=metrics[read_start:]
   assert len(reads)==1000 and all(m['status']==200 for m in reads)
   # Restart this isolated server with the same database and cookies.
   server.shutdown();server.server_close();thread.join(timeout=5)
   app=create_app(config);server=make_server('127.0.0.1',port,app,threaded=True)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   for i,c in enumerate(clients):
    assert c.call('/auth/me')['user']['id']==c.uid
    assert c.call('/auth/me')['user']['reputation']==(2 if i%2==0 else 10)
    assert c.call(f'/images/{images[i]}',raw=True)[:2]==b'\xff\xd8'
    assert len(c.call('/me/saved-listings')['ids'])==(1 if i%2==0 else 0)
   with app.app_context():
    db=get_db();assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert db.execute('SELECT COUNT(*) FROM reputation_events').fetchone()[0]==20
    assert db.execute('SELECT COUNT(*) FROM notifications').fetchone()[0]==db.execute('SELECT COUNT(DISTINCT event_key) FROM notifications').fetchone()[0]
    assert db.execute("SELECT COUNT(*) FROM handoffs WHERE status='COMPLETED'").fetchone()[0]==10
    assert db.execute("SELECT COUNT(*) FROM listings WHERE status='RETURNED'").fetchone()[0]==20
   ms=sorted(m['ms'] for m in reads)
   result={'round':round_number,'new_users':20,'concurrent_users':20,'requests':len(metrics),'mixed_read_requests':1000,
    'read_latency_ms':{'p50':round(statistics.median(ms),2),'p95':ms[int(len(ms)*.95)-1],'p99':ms[int(len(ms)*.99)-1],'max':ms[-1]},
    'seconds':round(time.perf_counter()-started,2),'completed_returns':10,'restart_sessions_and_private_images':'passed',
    'unexpected_errors':0,'intentional_errors':'403/404 permission denials, 409 losing claim, 429 rate limit', 'status':'passed'}
   print(json.dumps(result),flush=True);return result
  finally:
   server.shutdown();server.server_close();thread.join(timeout=5)

if __name__=='__main__':
 results=[run_round(i) for i in (1,2,3)]
 output=ROOT.parent/'verification/stress-report.json';output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(results,indent=2))
 print('STRESS TEST PASSED: 60 new accounts across 3 rounds, 20 simultaneous users per round, 30 returns, 3 isolated server restarts.',flush=True)
