from whereru.db import get_db


def setup_pair(account,report,private=False):
    owner,oh,ou=account();finder,fh,fu=account()
    lost=report(owner,oh,visibility='PRIVATE' if private else 'PUBLIC',private_description='SECRET LOST DETAIL')
    found=report(finder,fh,type='FOUND',campus='Busch',visibility='PRIVATE' if private else 'PUBLIC',private_description='SECRET FOUND DETAIL')
    return owner,oh,finder,fh,lost,found


def test_complete_recovery_and_idempotent_credit(account,report):
    a,ah,b,bh,lost,found=setup_pair(account,report)
    matches=a.get('/api/matches').json['matches'];assert len(matches)==1
    assert matches[0]['score']>=35
    assert not b.get('/api/matches').json['matches']
    assert a.get('/api/notifications').json['unread_count']==1
    b.patch(f"/api/listings/{found['id']}",json={'title':'Blue bottle'},headers=bh)
    assert a.get('/api/notifications').json['unread_count']==1
    r=a.post('/api/claims',json={'found_id':found['id'],'lost_id':lost['id'],'evidence':'Private sticker evidence'},headers=ah)
    assert r.status_code==201,r.json
    cid=r.json['id']
    assert a.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=ah).status_code==403
    assert b.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=bh).status_code==200
    assert a.get(f"/api/listings/{lost['id']}").json['status']=='CLAIMED'
    assert not a.get('/api/listings').json['listings']
    assert b.post(f'/api/claims/{cid}/messages',json={'body':'Meet at the front desk?'},headers=bh).status_code==201
    assert a.get(f'/api/claims/{cid}/messages').json['messages'][0]['body']=='Meet at the front desk?'
    assert a.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Student center'},headers=ah).status_code==201
    assert b.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=bh).json['status']=='PENDING'
    assert a.get('/api/auth/me').json['user']['reputation']==0
    assert a.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=ah).json['status']=='COMPLETED'
    for _ in range(2):assert b.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=bh).status_code==200
    assert b.get('/api/auth/me').json['user']['reputation']==10
    assert a.get('/api/auth/me').json['user']['reputation']==2
    assert a.get(f"/api/listings/{lost['id']}").json['status']=='RETURNED'
    assert b.get(f"/api/listings/{found['id']}").json['status']=='RETURNED'


def test_private_match_disclosure_and_third_party(account,report):
    a,ah,b,bh,lost,found=setup_pair(account,report,True);outsider,ch,cu=account()
    match=a.get('/api/matches').json['matches'][0]
    assert match['score'] is None and match['candidate']=={'restricted':True}
    assert 'SECRET' not in str(match)
    assert a.get(f"/api/listings/{found['id']}").status_code==404
    assert outsider.post('/api/claims',json={'found_id':found['id'],'evidence':'Some evidence'},headers=ch).status_code==404
    r=a.post('/api/claims',json={'found_id':found['id'],'lost_id':lost['id'],'evidence':'Private claim detail'},headers=ah)
    assert r.status_code==201;cid=r.json['id']
    for endpoint in (f'/api/claims/{cid}',f'/api/claims/{cid}/messages',f'/api/claims/{cid}/handoff'):
        assert outsider.get(endpoint).status_code==404
    assert outsider.get(f"/api/matches/{match['id']}").status_code==404
    nid=a.get('/api/notifications').json['notifications'][0]['id']
    assert outsider.post(f'/api/notifications/{nid}/read',json={},headers=ch).status_code==404
    assert a.post(f'/api/notifications/{nid}/read',json={},headers=ah).status_code==200


def test_competing_claims_and_cancellation(account,report):
    a,ah,b,bh,lost,found=setup_pair(account,report);c,ch,cu=account()
    first=a.post('/api/claims',json={'found_id':found['id'],'lost_id':lost['id'],'evidence':'My evidence'},headers=ah).json['id']
    second=c.post('/api/claims',json={'found_id':found['id'],'evidence':'Other evidence'},headers=ch).json['id']
    assert b.post(f'/api/claims/{first}/review',json={'decision':'ACCEPTED'},headers=bh).status_code==200
    assert b.post(f'/api/claims/{second}/review',json={'decision':'ACCEPTED'},headers=bh).status_code==409
    assert c.get(f'/api/claims/{second}').json['status']=='REJECTED'
    assert a.post(f'/api/claims/{first}/cancel',json={},headers=ah).status_code==200
    assert b.get(f"/api/listings/{found['id']}").json['status']=='OPEN'
    assert a.get(f"/api/listings/{lost['id']}").json['status']=='OPEN'


def test_dropoff_is_not_a_return(account,report):
    c,h,u=account();r=report(c,h,type='FOUND')
    assert c.post(f"/api/listings/{r['id']}/drop-off",json={'place':'Information desk'},headers=h).status_code==200
    row=c.get(f"/api/listings/{r['id']}").json
    assert row['custody']=='DROP_OFF_REPORTED' and row['status']=='OPEN'
    assert c.get('/api/auth/me').json['user']['reputation']==0


def test_concurrent_acceptance_has_one_winner(app,account,report):
    from concurrent.futures import ThreadPoolExecutor
    owner,oh,u=account();other,ch,cu=account();finder,fh,fu=account()
    found=report(finder,fh,type='FOUND')
    ids=[]
    for c,h in ((owner,oh),(other,ch)):
        ids.append(c.post('/api/claims',json={'found_id':found['id'],'evidence':'Ownership evidence'},headers=h).json['id'])
    cookie=finder.get_cookie('whereru_session').value
    def accept(cid):
        c=app.test_client();c.set_cookie('whereru_session',cookie)
        return c.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=fh).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(accept,ids))
    assert sorted(results)==[200,409]
    with app.app_context():assert get_db().execute("SELECT COUNT(*) FROM claims WHERE status='ACCEPTED'").fetchone()[0]==1


def test_cannot_cancel_after_transfer_confirmation(account,report):
    a,ah,b,bh,lost,found=setup_pair(account,report)
    cid=a.post('/api/claims',json={'found_id':found['id'],'evidence':'My evidence'},headers=ah).json['id']
    b.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=bh)
    a.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Front desk'},headers=ah)
    b.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=bh)
    assert a.post(f'/api/claims/{cid}/cancel',json={},headers=ah).status_code==409
    assert a.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'New place'},headers=ah).status_code==409
