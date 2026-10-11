"""Exercise the running local demo over HTTP, with three independent cookie jars.
Run against the dedicated demo only. --pause-for-restart keeps cookies in memory
so a server restart can be verified without signing in again.
"""
import argparse
import concurrent.futures
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

class Client:
    def __init__(self, base):
        self.base=base.rstrip('/');self.csrf=''
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,data=None,method=None,expected=200,raw=False,content_type=None):
        headers={}
        if data is not None:
            if not isinstance(data,bytes):data=json.dumps(data).encode();content_type='application/json'
            headers={'Content-Type':content_type,'X-CSRF-Token':self.csrf}
        req=urllib.request.Request(self.base+'/api'+path,data=data,headers=headers,method=method)
        try:
            with self.opener.open(req,timeout=25) as r:status=r.status;body=r.read()
        except urllib.error.HTTPError as e:status=e.code;body=e.read()
        assert status==expected,(path,status,body[:300].decode(errors='replace'))
        return body if raw else json.loads(body)
    def login(self,role):
        r=self.call('/demo/session',{'role':role});self.csrf=r['csrf_token'];self.uid=r['user']['id'];return r['user']


def main():
    p=argparse.ArgumentParser();p.add_argument('--lan',required=True);p.add_argument('--pause-for-restart',action='store_true');a=p.parse_args()
    start=time.monotonic();owner=Client('http://localhost:5003');finder=Client('http://127.0.0.1:5003');helper=Client(a.lan)
    assert owner.call('/health')['ai_mode']=='demo'
    assert owner.call('/demo/status')['enabled']
    before_owner=owner.login('owner')['reputation'];before_finder=finder.login('finder')['reputation'];helper.login('helper')
    assert len({owner.uid,finder.uid,helper.uid})==3
    print('PASS: three live HTTP accounts, loopback and LAN, no login reset',flush=True)
    helper.call('/me/nearby-location',{'consent':True,'label':'Richard Weeks Hall','latitude':40.524464,'longitude':-74.459505,'radius_meters':350})
    now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    base={'title':'Red translucent water bottle — live HTTP check','category':'bottle','description':'Red translucent bottle with a red screw cap.',
        'attributes':{'color':'red','material':'plastic'},'campus':'Busch','location':'Richard Weeks Hall','private_location':'IDEA3 Lab',
        'private_description':'White Rutgers Computer Science printing.','visibility':'PUBLIC','occurred_at':now}
    lost=owner.call('/listings',{**base,'type':'LOST'},expected=201)
    owner.call(f"/listings/{lost['id']}/potential-locations",{'locations':[{'label':'Richard Weeks Hall','latitude':40.524464,'longitude':-74.459505,'priority':3,'share_public':True}]})
    alerts=helper.call('/notifications?limit=100')['notifications']
    assert any(n['kind']=='NEARBY' and n['resource_id']==lost['id'] for n in alerts)
    details=helper.call(f"/nearby-alerts/{lost['id']}")
    assert 'IDEA3' not in json.dumps(details) and 'Computer Science' not in json.dumps(details)
    found=finder.call('/listings',{**base,'type':'FOUND'},expected=201)
    matches=owner.call('/matches?limit=100')['matches']
    assert any(m['found_id']==found['id'] and m['lost_id']==lost['id'] for m in matches)
    assert any(n['kind']=='MATCH' for n in owner.call('/notifications?limit=100')['notifications'])
    print('PASS: live nearby and match notifications, private lab/evidence excluded',flush=True)
    raw=(Path(__file__).resolve().parents[2]/'public/examples/IMG_3990.jpg').read_bytes();boundary='WhereRULiveCheck'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
    image=finder.call(f"/listings/{found['id']}/images",body,expected=201,content_type='multipart/form-data; boundary='+boundary)
    assert finder.call(f"/images/{image['id']}",raw=True)[:2]==b'\xff\xd8'
    helper.call(f"/images/{image['id']}",expected=404)
    public=helper.call(f"/listings/{found['id']}")
    assert 'private_description' not in public and 'private_location' not in public
    helper.call(f"/listings/{found['id']}",{'title':'Unauthorized change'},method='PATCH',expected=403)
    registered=owner.call('/me/registered-items',{'name':'Live durability check','description':'Private test evidence','serial':'DEMO-HTTP','photoAdded':False},expected=201)
    assert not any(x['id']==registered['id'] for x in helper.call('/me/registered-items')['items'])
    claim=owner.call('/claims',{'found_id':found['id'],'lost_id':lost['id'],'evidence':'White Rutgers Computer Science printing.'},expected=201)
    helper.call(f"/claims/{claim['id']}",expected=404)
    finder.call(f"/claims/{claim['id']}/review",{'decision':'ACCEPTED'})
    finder.call(f"/claims/{claim['id']}/messages",{'body':'Meet at a public student center desk.'},expected=201)
    assert owner.call(f"/claims/{claim['id']}/messages")['messages']
    finder.call(f"/claims/{claim['id']}/handoff",{'method':'MEETUP','place':'Busch Student Center'},expected=201)
    first=finder.call(f"/claims/{claim['id']}/handoff/confirm",{})
    assert first['status']=='PENDING' and owner.call('/auth/me')['user']['reputation']==before_owner
    assert owner.call(f"/claims/{claim['id']}/handoff/confirm",{})['status']=='COMPLETED'
    assert finder.call('/auth/me')['user']['reputation']==before_finder+10
    assert owner.call('/auth/me')['user']['reputation']==before_owner+2
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _: owner.call('/maps/density?campus=Busch'),range(30)))
    assert all(r['contributing_reports']>0 for r in results)
    print('PASS: actual media, permission boundaries, claims, conversation, two-party return, 30 concurrent reads',flush=True)
    if a.pause_for_restart:
        print('READY: restart the demo server; press Enter here when it is healthy',flush=True)
        input()
    for client in (owner,finder,helper):assert client.call('/auth/me')['user']['id']==client.uid
    assert finder.call(f"/images/{image['id']}",raw=True)[:2]==b'\xff\xd8'
    helper.call(f"/images/{image['id']}",expected=404)
    assert any(n['resource_id']==lost['id'] and n['kind']=='NEARBY' for n in helper.call('/notifications?limit=100')['notifications'])
    assert owner.call(f"/listings/{lost['id']}")['status']=='RETURNED'
    assert finder.call(f"/listings/{found['id']}")['status']=='RETURNED'
    assert finder.call(f"/claims/{claim['id']}/handoff/confirm",{})['status']=='COMPLETED'
    assert finder.call('/auth/me')['user']['reputation']==before_finder+10
    assert owner.call('/auth/me')['user']['reputation']==before_owner+2
    assert any(i['id']==registered['id'] for i in owner.call('/me/registered-items')['items'])
    owner.call(f"/me/registered-items/{registered['id']}",{},method='DELETE')
    print('PASS: sessions, reports, images, private registration and idempotent reputation survive restart',flush=True)
    print(f'LIVE HTTP CHECK PASSED in {time.monotonic()-start:.1f}s (restart wait included)',flush=True)

if __name__=='__main__':main()
