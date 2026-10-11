import hashlib
import hmac
import math
import re
import time
from datetime import datetime, timezone
from functools import wraps
from flask import current_app,g,request
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden, TooManyRequests
from .db import get_db,atomic


def payload():
    value=request.get_json(silent=True)
    if not isinstance(value,dict): raise BadRequest('A JSON object is required')
    return value


def text(value,name,maximum=200,required=False):
    if not isinstance(value,str) or len(value)>maximum: raise BadRequest(f'{name} must be text of at most {maximum} characters')
    value=value.strip()
    if required and not value: raise BadRequest(f'{name} is required')
    return value


def number(value,name,low,high):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
        raise BadRequest(f'{name} must be a number between {low} and {high}')
    return value


def boolean(value,name):
    if not isinstance(value,bool): raise BadRequest(f'{name} must be true or false')
    return value


def choice(value,name,options):
    if not isinstance(value,str) or value not in options: raise BadRequest(f'{name} must be one of: {", ".join(options)}')
    return value


def identifier(value,name):
    if isinstance(value,bool) or not isinstance(value,int) or value<1: raise BadRequest(f'{name} must be a positive integer')
    return value


def iso(value,name='occurred_at'):
    value=text(value,name,64,True)
    try: d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: raise BadRequest(f'{name} must be an ISO date/time')
    if d.tzinfo is None: raise BadRequest(f'{name} must include a timezone, for example -04:00')
    try: return d.astimezone(timezone.utc).isoformat()
    except (OverflowError, ValueError): raise BadRequest(f'{name} is outside the supported date range')


def digest(value):
    return hmac.new(current_app.config['SECRET_KEY'].encode(),value.encode(),hashlib.sha256).hexdigest()


def authenticate():
    g.user=None;g.auth_session=None
    token=request.cookies.get('whereru_session','')
    if token:
        row=get_db().execute('''SELECT s.token_hash,s.csrf,s.expires,u.* FROM sessions s
          JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?''',(digest(token),time.time())).fetchone()
        if row: g.user=row;g.auth_session=row


def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if g.user is None: raise Unauthorized('Sign in required')
        return fn(*args,**kwargs)
    return wrapped


def rate_limit(name,limit=30,seconds=3600,identity=None):
    identity=identity or str(g.user['id'] if g.user else request.remote_addr or 'unknown')
    bucket=digest(name+':'+identity);now=time.time()
    with atomic() as db:
        row=db.execute('SELECT * FROM rate_limits WHERE bucket=?',(bucket,)).fetchone()
        if row and now-row['started']<seconds:
            if row['count']>=limit:
                raise TooManyRequests('Too many requests; try again later')
            db.execute('UPDATE rate_limits SET count=count+1 WHERE bucket=?',(bucket,))
        else: db.execute('INSERT OR REPLACE INTO rate_limits VALUES(?,?,1)',(bucket,now))


def page_args():
    try:
        limit=int(request.args.get('limit',30));offset=int(request.args.get('offset',0))
    except ValueError: raise BadRequest('limit and offset must be integers')
    if not 1<=limit<=100 or not 0<=offset<=100000: raise BadRequest('Invalid pagination')
    return limit,offset


def notify(db,user_id,kind,resource_id,message,event_key):
    if user_id is None: return
    user=db.execute('SELECT notifications_enabled FROM users WHERE id=?',(user_id,)).fetchone()
    if user and user['notifications_enabled']:
        db.execute('INSERT OR IGNORE INTO notifications(user_id,kind,resource_id,message,event_key) VALUES(?,?,?,?,?)',
                   (user_id,kind,resource_id,message,f'{user_id}:{event_key}'))


def event(db,listing_id,kind):
    db.execute('INSERT INTO events(listing_id,actor_id,kind) VALUES(?,?,?)',(listing_id,g.user['id'] if g.user else None,kind))
