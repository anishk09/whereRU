import threading
import requests
from werkzeug.serving import make_server


def test_real_http_cookie_and_csrf(app):
    server=make_server('127.0.0.1',0,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with requests.Session() as c:
            assert c.get(base+'/api/health',timeout=5).json()['app']=='WhereRU?'
            assert c.get(base+'/api/listings',timeout=5).status_code==401
            assert c.post(base+'/api/auth/request-code',json={'email':'http@example.com'},timeout=5).status_code==200
            code=app.config['TEST_CODE_SINK']['http@example.com']
            response=c.post(base+'/api/auth/verify-code',json={'email':'http@example.com','code':code},timeout=5)
            assert response.status_code==200
            cookie=response.headers['Set-Cookie'];assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
            token=response.json()['csrf_token']
            body={'type':'LOST','title':'HTTP smoke test','occurred_at':'2026-10-10T14:00:00Z'}
            assert c.post(base+'/api/listings',json=body,timeout=5).status_code==403
            assert c.post(base+'/api/listings',json=body,headers={'X-CSRF-Token':token},timeout=5).status_code==201
            assert c.post(base+'/api/auth/logout',json={},headers={'X-CSRF-Token':token},timeout=5).status_code==200
            assert c.get(base+'/api/auth/me',timeout=5).status_code==401
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()
