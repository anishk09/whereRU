"""Runs the complete recovery demo in a temporary database; no server or keys needed."""
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from whereru import create_app


def main():
    with tempfile.TemporaryDirectory() as tmp:
        app=create_app({'TESTING':True,'SECRET_KEY':'isolated-demo-secret-12345678901234567890',
            'DATABASE':str(Path(tmp)/'demo.db'),'UPLOAD_DIR':str(Path(tmp)/'uploads'),'APP_ENV':'development',
            'AUTH_DELIVERY':'console','AI_MODE':'demo','COOKIE_SECURE':False,'TEST_CODE_SINK':{}})
        def login(email):
            c=app.test_client();r=c.post('/api/auth/request-code',json={'email':email});assert r.status_code==200,r.json
            r=c.post('/api/auth/verify-code',json={'email':email,'code':app.config['TEST_CODE_SINK'][email]});assert r.status_code==200,r.json
            return c,{'X-CSRF-Token':r.json['csrf_token']}
        owner,oh=login('owner@example.com');finder,fh=login('finder@example.com')
        print('1. Two separate accounts signed in.')
        base={'title':'Blue bottle','description':'Insulated water bottle','category':'bottle','attributes':{'color':'blue'},
              'occurred_at':datetime.now(timezone.utc).isoformat(),'visibility':'PRIVATE','campus':'College Ave'}
        r=owner.post('/api/listings',json={**base,'type':'LOST'},headers=oh);assert r.status_code==201,r.json;lost=r.json['id']
        r=finder.post('/api/listings',json={**base,'type':'FOUND'},headers=fh);assert r.status_code==201,r.json;found=r.json['id']
        print('2. Private lost and found reports saved.')
        assert len(owner.get('/api/matches').json['matches'])==1
        assert owner.get(f'/api/listings/{found}').status_code==404
        print('3. Match notification delivered without revealing the private report.')
        r=owner.post('/api/claims',json={'found_id':found,'lost_id':lost,'evidence':'Small dent below the cap'},headers=oh);assert r.status_code==201,r.json;cid=r.json['id']
        assert finder.post(f'/api/claims/{cid}/review',json={'decision':'ACCEPTED'},headers=fh).status_code==200
        print('4. Finder reviewed and accepted the ownership claim.')
        assert owner.post(f'/api/claims/{cid}/messages',json={'body':'Meet at the student center?'},headers=oh).status_code==201
        assert finder.post(f'/api/claims/{cid}/handoff',json={'method':'MEETUP','place':'Student center'},headers=fh).status_code==201
        print('5. Private message and handoff arranged.')
        assert finder.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=fh).json['status']=='PENDING'
        assert owner.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=oh).json['status']=='COMPLETED'
        assert finder.post(f'/api/claims/{cid}/handoff/confirm',json={},headers=fh).status_code==200
        assert finder.get('/api/auth/me').json['user']['reputation']==10
        print('6. Both parties confirmed; reports returned; credits awarded exactly once.')
        print('PASS. Temporary demo data removed on exit. No Gemini calls or emails were sent.')


if __name__=='__main__':main()
