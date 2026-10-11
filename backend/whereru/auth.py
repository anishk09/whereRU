import hmac
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from flask import Blueprint,current_app,g,jsonify
from werkzeug.exceptions import BadRequest,Unauthorized,TooManyRequests,ServiceUnavailable
from .core import payload,text,boolean,digest,login_required,rate_limit
from .db import get_db,atomic
bp=Blueprint('auth',__name__)


def email_input(value):
    value=text(value,'email',254,True).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): raise BadRequest('Valid email required')
    return value


def deliver(email,code):
    if current_app.testing and current_app.config.get('TEST_CODE_SINK') is not None:
        current_app.config['TEST_CODE_SINK'][email]=code;return
    mode=current_app.config['AUTH_DELIVERY']
    if mode=='console' and current_app.config['APP_ENV']!='production':
        print(f'[WhereRU? LOCAL CODE] {email}: {code} (10 minutes; no email sent)',flush=True);return
    if mode!='smtp': raise ServiceUnavailable('Email delivery is not configured')
    host=os.getenv('SMTP_HOST','');sender=os.getenv('SMTP_FROM','');port=int(os.getenv('SMTP_PORT','587'))
    if not host or not sender: raise ServiceUnavailable('SMTP_HOST and SMTP_FROM are required')
    msg=EmailMessage();msg['Subject']='Your WhereRU? sign-in code';msg['From']=sender;msg['To']=email
    msg.set_content(f'Your WhereRU? code is {code}. It expires in 10 minutes. Ignore this message if you did not request it.')
    try:
        factory=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
        with factory(host,port,timeout=15) as smtp:
            if port!=465: smtp.starttls(context=ssl.create_default_context())
            if os.getenv('SMTP_USERNAME'): smtp.login(os.environ['SMTP_USERNAME'],os.environ['SMTP_PASSWORD'])
            smtp.send_message(msg)
    except (OSError,smtplib.SMTPException,KeyError): raise ServiceUnavailable('Email delivery failed; please retry later')


@bp.post('/api/auth/request-code')
def request_code():
    email=email_input(payload().get('email'))
    rate_limit('code-ip',20,3600)
    rate_limit('code-email',1,60,email)
    code=f'{secrets.randbelow(1000000):06d}';now=time.time()
    code_hash=digest(email+':'+code)
    with atomic() as db:
        db.execute('INSERT OR REPLACE INTO challenges(email,code_hash,expires,attempts,requested) VALUES(?,?,?,0,?)',
                   (email,code_hash,now+600,now))
    try: deliver(email,code)
    except ServiceUnavailable:
        with atomic() as db: db.execute('DELETE FROM challenges WHERE email=? AND code_hash=?',(email,code_hash))
        raise
    return jsonify(message='Code requested',delivery=current_app.config['AUTH_DELIVERY'],expires_in=600)


@bp.post('/api/auth/verify-code')
def verify_code():
    p=payload();email=email_input(p.get('email'));code=text(p.get('code'),'code',6,True)
    if not re.fullmatch(r'[0-9]{6}',code): raise BadRequest('Six-digit code required')
    rate_limit('verify-ip',60,600)
    now=time.time();invalid=False
    with atomic() as db:
        row=db.execute('SELECT * FROM challenges WHERE email=?',(email,)).fetchone()
        if not row or row['expires']<=now or row['attempts']>=5: invalid=True
        elif not hmac.compare_digest(row['code_hash'],digest(email+':'+code)):
            db.execute('UPDATE challenges SET attempts=attempts+1 WHERE email=?',(email,));invalid=True
        else:
            db.execute('DELETE FROM challenges WHERE email=?',(email,))
            # Console codes are local development credentials, not proof of email control.
            verified=current_app.config['AUTH_DELIVERY']=='smtp'
            db.execute('INSERT OR IGNORE INTO users(email) VALUES(?)',(email,))
            if verified: db.execute('UPDATE users SET verified_at=CURRENT_TIMESTAMP WHERE email=?',(email,))
            user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if g.auth_session: db.execute('DELETE FROM sessions WHERE token_hash=?',(g.auth_session['token_hash'],))
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user['id'],csrf,now+86400))
    if invalid: raise BadRequest('Invalid, expired, used, or exhausted code')
    response=jsonify(user=user_json(user),csrf_token=csrf)
    response.set_cookie('whereru_session',token,max_age=86400,httponly=True,secure=current_app.config['COOKIE_SECURE'],samesite='Lax',path='/')
    return response


@bp.post('/api/auth/demo-login')
def demo_login():
    """Development-only shortcut for live demos: signs in without an email code.

    Disabled unless DEMO_LOGIN=true and APP_ENV is not production.
    """
    if current_app.config['APP_ENV']=='production' or os.getenv('DEMO_LOGIN','').lower()!='true':
        from werkzeug.exceptions import NotFound
        raise NotFound('Not found')
    p=payload()
    email=email_input(p.get('email') or 'demo@scarletmail.rutgers.edu')
    name=text(p.get('display_name') or '','display_name',80)
    rate_limit('demo-login',60,600)
    now=time.time()
    with atomic() as db:
        db.execute('INSERT OR IGNORE INTO users(email) VALUES(?)',(email,))
        if name: db.execute('UPDATE users SET display_name=? WHERE email=? AND (display_name IS NULL OR display_name=\'\')',(name,email))
        user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if g.auth_session: db.execute('DELETE FROM sessions WHERE token_hash=?',(g.auth_session['token_hash'],))
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user['id'],csrf,now+86400))
    response=jsonify(user=user_json(user),csrf_token=csrf,demo=True)
    response.set_cookie('whereru_session',token,max_age=86400,httponly=True,secure=current_app.config['COOKIE_SECURE'],samesite='Lax',path='/')
    return response


def user_json(row):
    points=get_db().execute('SELECT COALESCE(SUM(points),0) FROM reputation_events WHERE user_id=?',(row['id'],)).fetchone()[0]
    return dict(id=row['id'],email=row['email'],display_name=row['display_name'],email_verified=bool(row['verified_at']),
                notifications_enabled=bool(row['notifications_enabled']),reputation=points)


@bp.get('/api/auth/me')
@login_required
def me(): return jsonify(user=user_json(g.user),csrf_token=g.auth_session['csrf'])


@bp.patch('/api/me')
@login_required
def edit_profile():
    p=payload()
    if not p or set(p)-{'display_name','notifications_enabled'}: raise BadRequest('Allowed: display_name, notifications_enabled')
    name=text(p.get('display_name',g.user['display_name']),'display_name',80)
    enabled=boolean(p.get('notifications_enabled',bool(g.user['notifications_enabled'])),'notifications_enabled')
    with atomic() as db:
        db.execute('UPDATE users SET display_name=?,notifications_enabled=? WHERE id=?',(name,int(enabled),g.user['id']))
    return jsonify(user=user_json(get_db().execute('SELECT * FROM users WHERE id=?',(g.user['id'],)).fetchone()))


@bp.post('/api/auth/logout')
@login_required
def logout():
    payload()
    with atomic() as db: db.execute('DELETE FROM sessions WHERE token_hash=?',(g.auth_session['token_hash'],))
    response=jsonify(message='Signed out');response.delete_cookie('whereru_session',path='/');return response


@bp.get('/api/me/activity')
@login_required
def activity():
    db=get_db();uid=g.user['id']
    return jsonify(reports=db.execute('SELECT COUNT(*) FROM listings WHERE creator_id=?',(uid,)).fetchone()[0],
        claims=db.execute('SELECT COUNT(*) FROM claims WHERE claimant_id=?',(uid,)).fetchone()[0],
        confirmed_returns=db.execute('SELECT COUNT(*) FROM reputation_events WHERE user_id=?',(uid,)).fetchone()[0],
        reputation=user_json(g.user)['reputation'])
