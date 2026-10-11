import os
import secrets
import sqlite3
from pathlib import Path
from flask import Flask,g,jsonify,request
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException,Forbidden,UnsupportedMediaType
from .db import init_db,close_db
from .core import authenticate


def create_app(test_config=None):
    root=Path(__file__).resolve().parent.parent
    load_dotenv(root/'.env')
    app=Flask(__name__,instance_path=str(root/'instance'))
    app.config.update(DATABASE=os.getenv('DATABASE_PATH',str(root/'instance/whereru.db')),
        UPLOAD_DIR=os.getenv('UPLOAD_DIR',str(root/'instance/uploads')),
        SECRET_KEY=os.getenv('SECRET_KEY',''),APP_ENV=os.getenv('APP_ENV','development'),
        AUTH_DELIVERY=os.getenv('AUTH_DELIVERY','console'),
        AI_MODE=os.getenv('AI_MODE','demo'),GEMINI_API_KEY=os.getenv('GEMINI_API_KEY',''),
        GEMINI_MODEL=os.getenv('GEMINI_MODEL','gemini-2.5-flash'),
        GEMINI_EMBEDDING_MODEL=os.getenv('GEMINI_EMBEDDING_MODEL','gemini-embedding-2'),
        CLASSROOM_CATALOG=str(root/'data/classrooms.json'),
        MAX_CONTENT_LENGTH=10*1024*1024,MAX_FORM_MEMORY_SIZE=128*1024,
        ALLOWED_ORIGINS=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','').split(',') if x.strip()],
        COOKIE_SECURE=os.getenv('APP_ENV','development')=='production',TESTING=False)
    if test_config: app.config.update(test_config)
    if app.config['AI_MODE'] not in ('demo','local','gemini'): raise RuntimeError('AI_MODE must be demo, local, or gemini')
    if app.config['APP_ENV']=='production':
        if len(app.config['SECRET_KEY'])<32: raise RuntimeError('Production requires SECRET_KEY of at least 32 characters')
        if app.config['AUTH_DELIVERY']!='smtp': raise RuntimeError('Production requires SMTP authentication delivery')
        if not app.config['COOKIE_SECURE']: raise RuntimeError('Production requires secure cookies')
    if not app.config['SECRET_KEY']:
        secret_path=Path(app.config['DATABASE']).parent/'secret.key'
        secret_path.parent.mkdir(parents=True,exist_ok=True)
        try: fd=os.open(secret_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError: pass
        else:
            with os.fdopen(fd,'w') as f: f.write(secrets.token_hex(32))
        app.config['SECRET_KEY']=secret_path.read_text().strip()
    Path(app.config['UPLOAD_DIR']).mkdir(parents=True,exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context(): init_db()
    if app.config['AI_MODE']=='local' and not app.config.get('TESTING'):
        # Load classroom reference features in the background so the first room scan is fast.
        import threading
        def warm():
            try:
                from .vision import warm_cache
                with app.app_context():
                    from .ai import catalog
                    rooms,base=catalog()
                warm_cache(rooms,base)
                app.logger.info('Room recognition ready: %d rooms',len(rooms))
            except Exception as error:
                app.logger.warning('Room cache warm-up skipped: %s',error)
        threading.Thread(target=warm,daemon=True).start()

    @app.before_request
    def guards():
        if request.method=='OPTIONS': return '',204
        authenticate()
        if request.method in ('POST','PATCH','PUT','DELETE'):
            origin=request.headers.get('Origin')
            allowed=[request.host_url.rstrip('/')]+app.config['ALLOWED_ORIGINS']
            if origin and origin not in allowed: raise Forbidden('Origin is not permitted')
            if request.headers.get('Sec-Fetch-Site')=='cross-site' and not (origin and origin in allowed):
                raise Forbidden('Cross-site request denied')
            if request.endpoint not in ('media.upload','ai.recognize_room_photo','ai.analyze_item_photo') and not request.is_json:
                raise UnsupportedMediaType('Use Content-Type: application/json')
            if g.user and request.endpoint not in ('auth.request_code','auth.verify_code','auth.demo_login'):
                import hmac
                if not hmac.compare_digest(request.headers.get('X-CSRF-Token','').encode(),g.auth_session['csrf'].encode()):
                    raise Forbidden('Valid X-CSRF-Token required')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        origin=request.headers.get('Origin')
        if origin and origin in app.config['ALLOWED_ORIGINS']:
            response.headers['Access-Control-Allow-Origin']=origin
            response.headers['Access-Control-Allow-Credentials']='true'
            response.headers['Access-Control-Allow-Headers']='Content-Type, X-CSRF-Token'
            response.headers['Access-Control-Allow-Methods']='GET, POST, PATCH, DELETE, OPTIONS'
            response.vary.add('Origin')
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name,message=error.description),error.code

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error): return jsonify(error='Conflict',message='This operation conflicts with an existing record'),409

    @app.errorhandler(Exception)
    def unexpected(error):
        if app.testing: raise error
        app.logger.error('Unhandled error type=%s endpoint=%s',type(error).__name__,request.endpoint)
        return jsonify(error='Server error',message='The request could not be completed'),500

    @app.get('/api/health')
    def health(): return jsonify(status='ok',app='WhereRU?',ai_mode=app.config['AI_MODE'],auth_delivery=app.config['AUTH_DELIVERY'])

    from . import auth,listings,media,matching,recovery,maps,ai,demo_sync
    for module in (auth,listings,media,matching,recovery,maps,ai,demo_sync): app.register_blueprint(module.bp)
    return app
