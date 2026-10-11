import math
import time
from flask import Blueprint,g,jsonify,request
from werkzeug.exceptions import BadRequest,NotFound,Conflict
from .core import payload,text,number,boolean,login_required,rate_limit,iso
from .db import get_db,atomic
from .listings import fetch_listing
bp=Blueprint('maps',__name__)


def coords(p):
    return number(p.get('latitude'),'latitude',-90,90),number(p.get('longitude'),'longitude',-180,180)


@bp.post('/api/listings/<int:listing_id>/potential-locations')
@login_required
def locations(listing_id):
    p=payload();points=p.get('locations')
    if not isinstance(points,list) or len(points)>20: raise BadRequest('locations must be a list of at most 20 selected places')
    validated=[]
    for point in points:
        if not isinstance(point,dict): raise BadRequest('Invalid location')
        lat,lon=coords(point)
        label=text(point.get('label'),'label',120,True)
        priority=number(point.get('priority',1),'priority',1,3)
        public=boolean(point.get('share_public',False),'share_public')
        validated.append((listing_id,label,lat,lon,priority,int(public)))
    with atomic() as db:
        row=fetch_listing(listing_id,True)
        if row['status']!='OPEN': raise Conflict('Only OPEN reports may change potential locations')
        db.execute('DELETE FROM potential_locations WHERE listing_id=?',(listing_id,))
        db.executemany('INSERT INTO potential_locations(listing_id,label,latitude,longitude,priority,share_public) VALUES(?,?,?,?,?,?)',validated)
    from .nearby import refresh
    refresh(listing_id=listing_id)
    return jsonify(message='Selected potential locations saved; no movement trail was published',count=len(validated))


@bp.get('/api/listings/<int:listing_id>/search-areas')
@login_required
def cloud(listing_id):
    listing=fetch_listing(listing_id)
    mine=listing['creator_id']==g.user['id']
    clause='' if mine else ' AND share_public=1'
    rows=get_db().execute('SELECT * FROM potential_locations WHERE listing_id=?'+clause+' ORDER BY priority DESC,label',(listing_id,)).fetchall()
    maximum=max([r['priority'] for r in rows],default=1)
    return jsonify(type='FeatureCollection',features=[{
        'type':'Feature','geometry':{'type':'Point','coordinates':[r['longitude'],r['latitude']]},
        'properties':{'label':r['label'],'intensity':round(r['priority']/maximum,3),'radius_meters':150,
          'reason':'Reporter-selected potential location','shared':bool(r['share_public'])}}
        for r in rows],meaning='Relative search priority, not an item position or probability',
        evidence='Selected places only; no inferred walking route',empty_reason=None if rows else 'No potential locations shared for this audience')


@bp.get('/api/maps/density')
@login_required
def density():
    clauses=["l.visibility='PUBLIC'","l.status='OPEN'","l.type='LOST'","p.share_public=1"]
    params=[]
    for field in ('category','campus'):
        if request.args.get(field): clauses.append('l.'+field+'=?');params.append(text(request.args[field],field,100))
    for key,op in [('from','>='),('to','<=')]:
        if request.args.get(key): clauses.append('l.occurred_at'+op+'?');params.append(iso(request.args[key],key))
    rows=get_db().execute('''SELECT p.listing_id,p.latitude,p.longitude FROM potential_locations p
       JOIN listings l ON l.id=p.listing_id WHERE '''+' AND '.join(clauses),params).fetchall()
    # Only deliberately shared candidate locations enter the public density map.
    # One report contributes one unit total, regardless of how many places it names.
    by_report={}
    for row in rows:
        cell=(math.floor(row['latitude']/0.002),math.floor(row['longitude']/0.002))
        by_report.setdefault(row['listing_id'],set()).add(cell)
    cells={}
    for group in by_report.values():
        for cell in group: cells[cell]=cells.get(cell,0)+1/len(group)
    return jsonify(type='FeatureCollection',features=[{'type':'Feature','geometry':{'type':'Point','coordinates':[(lon+0.5)*0.002,(lat+0.5)*0.002]},
        'properties':{'weight':round(weight,3)}} for (lat,lon),weight in cells.items()],
        meaning='Density of active public lost reports with explicitly shared locations; not loss probability',
        contributing_reports=len(by_report),cell_size_degrees=0.002)


@bp.post('/api/location-sessions')
@login_required
def start():
    if payload().get('consent') is not True: raise BadRequest('Explicit consent:true is required')
    rate_limit('recording-start',20)
    now=time.time()
    with atomic() as db:
        db.execute('DELETE FROM recording_sessions WHERE expires<=?',(now,))
        db.execute('UPDATE recording_sessions SET active=0 WHERE user_id=?',(g.user['id'],))
        sid=db.execute('INSERT INTO recording_sessions(user_id,consented_at,expires) VALUES(?,?,?)',(g.user['id'],now,now+86400)).lastrowid
    return jsonify(id=sid,expires_at=now+86400,mode='optional client recording',message='Only locations collected after consent may be submitted. Backend does not collect phone GPS.'),201


def session_row(sid):
    row=get_db().execute('SELECT * FROM recording_sessions WHERE id=? AND user_id=? AND expires>?',(sid,g.user['id'],time.time())).fetchone()
    if not row: raise NotFound('Recording session not found or expired')
    return row


@bp.post('/api/location-sessions/<int:sid>/points')
@login_required
def points(sid):
    rate_limit('recording-upload',120)
    p=payload().get('points')
    if not isinstance(p,list) or not 1<=len(p)<=200: raise BadRequest('Submit 1–200 points')
    now=time.time()
    with atomic() as db:
        session=session_row(sid)
        if not session['active']: raise Conflict('Recording is stopped')
        if db.execute('SELECT COUNT(*) FROM location_points WHERE session_id=?',(sid,)).fetchone()[0]+len(p)>5000: raise BadRequest('Session point limit reached')
        for point in p:
            if not isinstance(point,dict): raise BadRequest('Invalid point')
            lat,lon=coords(point);accuracy=number(point.get('accuracy'),'accuracy',0,10000)
            recorded=number(point.get('recorded_at'),'recorded_at',session['consented_at'],min(session['expires'],now+30))
            db.execute('INSERT OR IGNORE INTO location_points(session_id,latitude,longitude,accuracy,recorded_at) VALUES(?,?,?,?,?)',(sid,lat,lon,accuracy,recorded))
    return jsonify(message='Private points stored')


@bp.get('/api/location-sessions/<int:sid>')
@login_required
def trail(sid):
    session=session_row(sid)
    rows=get_db().execute('SELECT latitude,longitude,accuracy,recorded_at FROM location_points WHERE session_id=? ORDER BY recorded_at',(sid,)).fetchall()
    return jsonify(id=sid,active=bool(session['active']),expires_at=session['expires'],points=[dict(r) for r in rows],
                   warning='Sparse points do not establish the exact route. Select potential places separately to share them.')


@bp.post('/api/location-sessions/<int:sid>/stop')
@login_required
def stop(sid):
    payload()
    with atomic() as db:
        session_row(sid);db.execute('UPDATE recording_sessions SET active=0 WHERE id=?',(sid,))
    return jsonify(message='Recording stopped')


@bp.delete('/api/location-sessions/<int:sid>')
@login_required
def delete(sid):
    payload()
    with atomic() as db:
        cur=db.execute('DELETE FROM recording_sessions WHERE id=? AND user_id=?',(sid,g.user['id']))
        if not cur.rowcount: raise NotFound('Recording session not found')
    return jsonify(message='Recording and points deleted')
