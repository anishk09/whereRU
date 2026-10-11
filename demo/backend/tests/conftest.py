import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from whereru import create_app


@pytest.fixture
def app(tmp_path):
    catalog=tmp_path/'classrooms.json';catalog.write_text('{"rooms":[]}')
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'test.db'),'UPLOAD_DIR':str(tmp_path/'uploads'),
        'SECRET_KEY':'test-only-secret-not-for-deployment-123456789','TEST_CODE_SINK':{},'AUTH_DELIVERY':'console',
        'AI_MODE':'demo','GEMINI_API_KEY':'','CLASSROOM_CATALOG':str(catalog),'APP_ENV':'development','COOKIE_SECURE':False,'ALLOWED_ORIGINS':[]})
    return app


@pytest.fixture
def account(app):
    count=[0]
    def create():
        count[0]+=1;email=f'user{count[0]}@example.com';client=app.test_client()
        assert client.post('/api/auth/request-code',json={'email':email}).status_code==200
        code=app.config['TEST_CODE_SINK'][email]
        result=client.post('/api/auth/verify-code',json={'email':email,'code':code})
        assert result.status_code==200,result.json
        return client,{'X-CSRF-Token':result.json['csrf_token']},result.json['user']
    return create


@pytest.fixture
def report():
    def make(client,headers,**kwargs):
        data=dict(type='LOST',title='Blue metal bottle',category='bottle',description='Blue insulated water bottle',
             attributes={'color':'blue','material':'metal'},campus='College Ave',location='Library',
             occurred_at='2026-10-10T14:00:00-04:00',visibility='PUBLIC')
        data.update(kwargs)
        response=client.post('/api/listings',json=data,headers=headers)
        assert response.status_code==201,response.json
        return response.json
    return make
