import time
from whereru.db import get_db


def test_login_logout_and_replay(app,account):
    c,h,u=account()
    assert not u['email_verified']
    assert c.get('/api/auth/me').status_code==200
    assert app.test_client().get('/api/auth/me').status_code==401
    code=app.config['TEST_CODE_SINK'][u['email']]
    assert c.post('/api/auth/verify-code',json={'email':u['email'],'code':code}).status_code==400
    cookie=c.get_cookie('whereru_session').value
    assert c.post('/api/auth/logout',json={}).status_code==403
    assert c.post('/api/auth/logout',json={},headers=h).status_code==200
    c.set_cookie('whereru_session',cookie)
    assert c.get('/api/auth/me').status_code==401


def test_code_attempt_limit_and_expiry(app):
    c=app.test_client();email='attempts@example.com'
    assert c.post('/api/auth/request-code',json={'email':email}).status_code==200
    code=app.config['TEST_CODE_SINK'][email];bad='000000' if code!='000000' else '111111'
    for _ in range(5): assert c.post('/api/auth/verify-code',json={'email':email,'code':bad}).status_code==400
    assert c.post('/api/auth/verify-code',json={'email':email,'code':code}).status_code==400
    assert c.post('/api/auth/request-code',json={'email':email}).status_code==429
    email='expired@example.com'
    c.post('/api/auth/request-code',json={'email':email})
    with app.app_context():get_db().execute('UPDATE challenges SET expires=0 WHERE email=?',(email,))
    assert c.post('/api/auth/verify-code',json={'email':email,'code':app.config['TEST_CODE_SINK'][email]}).status_code==400


def test_origin_json_and_profile(app,account):
    c,h,u=account()
    assert c.patch('/api/me',json={'display_name':'Alex'},headers={**h,'Origin':'https://evil.example'}).status_code==403
    assert c.patch('/api/me',data='x',headers=h).status_code==415
    r=c.patch('/api/me',json={'display_name':'Alex','notifications_enabled':False},headers=h)
    assert r.status_code==200 and r.json['user']['display_name']=='Alex'
    assert not r.json['user']['notifications_enabled']


def test_session_expiry(app,account):
    c,h,u=account()
    with app.app_context():get_db().execute('UPDATE sessions SET expires=0')
    assert c.get('/api/auth/me').status_code==401
