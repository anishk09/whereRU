import json
from flask import Blueprint,g,jsonify,request
from werkzeug.exceptions import BadRequest,NotFound,Forbidden,Conflict
from .db import get_db,atomic
from .core import payload,text,number,boolean,choice,iso,login_required,rate_limit,page_args,event
bp=Blueprint('listings',__name__)
CATEGORIES=('bottle','electronics','clothing','bag','keys','wallet','id_card','financial_card','cash','other')
SENSITIVE={'keys','wallet','id_card','financial_card','cash'}
FIELDS={'type','title','description','private_description','category','attributes','campus','location','private_location','occurred_at','visibility','reward'}


def requires_ownership_evidence(row):
    # The valuable/sensitive choice is saved as PRIVATE by the lost-report flow.
    return row['category'] in SENSITIVE | {'electronics'} or row['visibility']=='PRIVATE'


def fetch_listing(listing_id,owner=False):
    row=get_db().execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not row: raise NotFound('Listing not found')
    mine=row['creator_id']==g.user['id']
    if row['visibility']=='PRIVATE' and not mine: raise NotFound('Listing not found')
    if owner and not mine: raise Forbidden('Only the report creator may perform this action')
    return row


def listing_json(row,owner=None):
    owner=(row['creator_id']==g.user['id']) if owner is None else owner
    keys=['id','type','title','description','category','campus','location','occurred_at','visibility','status','reward','created_at','updated_at','version']
    result={key:row[key] for key in keys}
    result['requires_ownership_evidence']=requires_ownership_evidence(row)
    from datetime import datetime,timedelta,timezone
    posted=datetime.fromisoformat(row['created_at'].replace('Z','+00:00'))
    if posted.tzinfo is None:posted=posted.replace(tzinfo=timezone.utc)
    result['expires_at']=(posted+timedelta(days=7)).isoformat()
    if owner:
        result.update({key:row[key] for key in ('creator_id','private_description','private_location','custody','custody_note','resolution')})
    attrs=json.loads(row['attributes'])
    # Distinctive features remain creator-only; they can be used internally for matching.
    result['attributes']=attrs if owner else {k:v for k,v in attrs.items() if k!='distinctive_features'}
    images=get_db().execute('SELECT id,is_public,width,height FROM images WHERE listing_id=?',(row['id'],)).fetchall()
    result['images']=[dict(id=i['id'],url=f"/api/images/{i['id']}",is_public=bool(i['is_public']),width=i['width'],height=i['height'])
                      for i in images if owner or (row['visibility']=='PUBLIC' and i['is_public'])]
    return result


def validate(p,old=None):
    if not p or set(p)-FIELDS: raise BadRequest('Unsupported or empty listing fields; creator and status are server-controlled')
    defaults=dict(description='',private_description='',category='other',attributes={},campus='',location='',private_location='',visibility='PUBLIC',reward=0)
    if old:
        defaults={k:old[k] for k in FIELDS};defaults['attributes']=json.loads(defaults['attributes'])
    defaults.update(p);v=defaults
    choice(v.get('type'),'type',('LOST','FOUND'))
    choice(v['category'],'category',CATEGORIES)
    choice(v['visibility'],'visibility',('PUBLIC','PRIVATE'))
    for name,limit in [('title',160),('description',4000),('private_description',4000),('campus',100),('location',200),('private_location',300)]:
        v[name]=text(v.get(name),name,limit,name=='title')
    v['occurred_at']=iso(v.get('occurred_at'))
    v['reward']=number(v['reward'],'reward',0,100000)
    attrs=v['attributes']
    if not isinstance(attrs,dict) or set(attrs)-{'color','brand','material','model','distinctive_features'}: raise BadRequest('Invalid attributes')
    for k,value in attrs.items():
        if k=='distinctive_features':
            if not isinstance(value,list) or len(value)>10: raise BadRequest('At most 10 distinctive features')
            attrs[k]=[text(x,'feature',150,True) for x in value]
        elif value is not None: attrs[k]=text(value,k,100)
    v['attributes']=json.dumps(attrs)
    if v['category'] in SENSITIVE and v['visibility']!='PRIVATE':
        raise BadRequest('Sensitive items must use PRIVATE visibility. Use official lost-property procedures for hand-in.')
    return v


@bp.get('/api/listings')
@login_required
def feed():
    status=choice(request.args.get('status','OPEN'),'status',('ALL','OPEN','CLAIMED','RETURNED'))
    clauses=["visibility='PUBLIC'"];params=[]
    if status=='ALL':clauses.append("status IN ('OPEN','CLAIMED')")
    else:clauses.append('status=?');params.append(status)
    if request.args.get('saved')=='true':
        clauses.append('EXISTS(SELECT 1 FROM saved_listings s WHERE s.listing_id=listings.id AND s.user_id=?)');params.append(g.user['id'])
    for field in ('type','category','campus'):
        value=request.args.get(field)
        if value and field=='type':choice(value,'type',('LOST','FOUND'))
        if value: clauses.append(field+'=?');params.append(text(value,field,100))
    q=request.args.get('q','').strip()
    if q:
        q=text(q,'q',160).replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        clauses.append("(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR location LIKE ? ESCAPE '\\' OR campus LIKE ? ESCAPE '\\')");params.extend(['%'+q+'%']*4)
    for query,op in [('from','>='),('to','<=')]:
        if request.args.get(query): clauses.append('occurred_at'+op+'?');params.append(iso(request.args[query],query))
    limit,offset=page_args()
    sort=choice(request.args.get('sort','newest'),'sort',('newest','oldest','last_seen'))
    order={'newest':'id DESC','oldest':'id ASC','last_seen':'occurred_at DESC,id DESC'}[sort]
    where=' AND '.join(clauses)
    total=get_db().execute('SELECT COUNT(*) FROM listings WHERE '+where,params).fetchone()[0]
    rows=get_db().execute('SELECT * FROM listings WHERE '+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',params+[limit,offset]).fetchall()
    return jsonify(listings=[listing_json(r,False) for r in rows],limit=limit,offset=offset,total=total)


@bp.get('/api/me/listings')
@login_required
def mine():
    limit,offset=page_args()
    rows=get_db().execute('SELECT * FROM listings WHERE creator_id=? ORDER BY id DESC LIMIT ? OFFSET ?',(g.user['id'],limit,offset)).fetchall()
    return jsonify(listings=[listing_json(r,True) for r in rows])


@bp.get('/api/listings/<int:listing_id>')
@login_required
def detail(listing_id): return jsonify(listing_json(fetch_listing(listing_id)))


@bp.post('/api/listings')
@login_required
def create():
    rate_limit('create-report',40)
    values=validate(payload());fields=sorted(values)
    with atomic() as db:
        cur=db.execute('INSERT INTO listings('+','.join(fields)+',creator_id,custody) VALUES('+','.join('?' for _ in fields)+',?,?)',
            [values[k] for k in fields]+[g.user['id'],'FINDER' if values['type']=='FOUND' else 'UNKNOWN'])
        listing_id=cur.lastrowid;event(db,listing_id,'CREATED')
    from .matching import refresh
    refresh(listing_id)
    return jsonify(listing_json(fetch_listing(listing_id))),201


@bp.patch('/api/listings/<int:listing_id>')
@login_required
def edit(listing_id):
    p=payload()
    with atomic() as db:
        old=fetch_listing(listing_id,True)
        if old['status']!='OPEN': raise Conflict('Only OPEN reports may be edited')
        if 'type' in p and p['type']!=old['type']: raise BadRequest('Report type cannot be changed; close this report and create another')
        values=validate(p,old);fields=sorted(values)
        db.execute('UPDATE listings SET '+','.join(k+'=?' for k in fields)+',version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   [values[k] for k in fields]+[listing_id])
        event(db,listing_id,'EDITED')
    from .matching import refresh
    refresh(listing_id)
    return jsonify(listing_json(fetch_listing(listing_id)))


@bp.post('/api/listings/<int:listing_id>/close')
@login_required
def close(listing_id):
    reason=choice(payload().get('reason'),'reason',('WITHDRAWN','SELF_RECOVERED'))
    with atomic() as db:
        row=fetch_listing(listing_id,True)
        if row['status']!='OPEN': raise Conflict('Only OPEN reports may be closed; cancel an active handoff first')
        if reason=='SELF_RECOVERED' and row['type']!='LOST': raise BadRequest('SELF_RECOVERED applies to lost reports')
        db.execute("UPDATE listings SET status='CLOSED',resolution=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(reason,listing_id))
        db.execute('UPDATE matches SET active=0 WHERE lost_id=? OR found_id=?',(listing_id,listing_id))
        db.execute("UPDATE claims SET status='CANCELLED',updated_at=CURRENT_TIMESTAMP WHERE (found_id=? OR lost_id=?) AND status IN ('PENDING','NEEDS_INFO')",(listing_id,listing_id))
        event(db,listing_id,'CLOSED:'+reason)
    return jsonify(listing_json(fetch_listing(listing_id)))


@bp.get('/api/listings/<int:listing_id>/history')
@login_required
def history(listing_id):
    fetch_listing(listing_id,True)
    return jsonify(events=[dict(r) for r in get_db().execute('SELECT id,kind,created_at FROM events WHERE listing_id=? ORDER BY id',(listing_id,))])


@bp.post('/api/listings/<int:listing_id>/drop-off')
@login_required
def drop_off(listing_id):
    p=payload();note=text(p.get('place'),'place',300,True)
    with atomic() as db:
        row=fetch_listing(listing_id,True)
        if row['type']!='FOUND' or row['status'] not in ('OPEN','CLAIMED'): raise Conflict('Only active found reports can record a drop-off')
        db.execute("UPDATE listings SET custody='DROP_OFF_REPORTED',custody_note=? WHERE id=?",(note,listing_id))
        event(db,listing_id,'DROP_OFF_REPORTED_NOT_STAFF_VERIFIED')
    return jsonify(message='Drop-off recorded as user-reported, not institutionally verified')


@bp.get('/api/me/saved-listings')
@login_required
def saved_listings():
    rows=get_db().execute("SELECT s.listing_id FROM saved_listings s JOIN listings l ON l.id=s.listing_id WHERE s.user_id=? AND l.visibility='PUBLIC' AND l.status!='CLOSED'",(g.user['id'],)).fetchall()
    return jsonify(ids=[r['listing_id'] for r in rows])

@bp.post('/api/me/saved-listings/<int:listing_id>')
@login_required
def save_listing(listing_id):
    payload()
    with atomic() as db:
        row=db.execute("SELECT id FROM listings WHERE id=? AND visibility='PUBLIC' AND status!='CLOSED'",(listing_id,)).fetchone()
        if not row:raise NotFound('Public report not available')
        db.execute('INSERT OR IGNORE INTO saved_listings(user_id,listing_id) VALUES(?,?)',(g.user['id'],listing_id))
    return jsonify(message='Report saved')

@bp.delete('/api/me/saved-listings/<int:listing_id>')
@login_required
def unsave_listing(listing_id):
    payload()
    with atomic() as db:db.execute('DELETE FROM saved_listings WHERE user_id=? AND listing_id=?',(g.user['id'],listing_id))
    return jsonify(message='Report removed from your shortlist')
