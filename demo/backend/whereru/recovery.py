from flask import Blueprint,g,jsonify
from werkzeug.exceptions import BadRequest,NotFound,Forbidden,Conflict
from .core import payload,text,choice,identifier,iso,login_required,rate_limit,page_args,notify,event
from .db import get_db,atomic
from .listings import requires_ownership_evidence
bp=Blueprint('recovery',__name__)


def claim_row(claim_id):
    row=get_db().execute('''SELECT c.*,f.creator_id AS finder_id FROM claims c JOIN listings f ON f.id=c.found_id WHERE c.id=?''',(claim_id,)).fetchone()
    if not row or g.user['id'] not in (row['finder_id'],row['claimant_id']): raise NotFound('Claim not found')
    return row


def claim_json(row):
    keys=('id','found_id','lost_id','evidence','status','review_note','created_at','updated_at')
    result={**{k:row[k] for k in keys},'your_role':'finder' if g.user['id']==row['finder_id'] else 'claimant'}
    result['requires_ownership_evidence']=claim_requires_evidence(get_db(),row)
    if row['status'] in ('ACCEPTED','COMPLETED'):
        for role,uid in (('finder',row['finder_id']),('owner',row['claimant_id'])):
            name=get_db().execute('SELECT display_name FROM users WHERE id=?',(uid,)).fetchone()[0]
            result[role+'_first_name']=name.split()[0] if name.strip() else ('Finder' if role=='finder' else 'Owner')
    return result


def claim_requires_evidence(db,row):
    reports=db.execute('SELECT category,visibility FROM listings WHERE id IN (?,?)',(row['found_id'],row['lost_id'])).fetchall()
    return any(requires_ownership_evidence(report) for report in reports)


def validate_evidence(value,required):
    value=text(value,'evidence',3000)
    if required and len(value)<8:
        raise BadRequest('Valuable or sensitive items require at least eight characters of private evidence')
    return value


def tell(db,row,kind,message,key):
    for uid in (row['finder_id'],row['claimant_id']):
        if uid!=g.user['id']: notify(db,uid,kind,row['id'],message,key)


@bp.post('/api/claims')
@login_required
def create_claim():
    rate_limit('claim',15)
    p=payload();found_id=identifier(p.get('found_id'),'found_id');lost_id=p.get('lost_id')
    if lost_id is not None: identifier(lost_id,'lost_id')
    with atomic() as db:
        found=db.execute('SELECT * FROM listings WHERE id=?',(found_id,)).fetchone()
        if not found or found['type']!='FOUND' or found['creator_id'] is None: raise NotFound('Eligible found report not found')
        if found['creator_id']==g.user['id']: raise BadRequest('You cannot claim your own found report')
        if found['visibility']=='PRIVATE':
            allowed=db.execute('''SELECT 1 FROM matches m JOIN listings l ON l.id=m.lost_id
                WHERE m.found_id=? AND m.active=1 AND l.creator_id=? AND l.status='OPEN' ''',(found_id,g.user['id'])).fetchone()
            if not allowed: raise NotFound('Eligible found report not found')
        if found['status']!='OPEN': raise Conflict('This item is not open for claims')
        lost=None
        if lost_id:
            lost=db.execute('SELECT * FROM listings WHERE id=? AND creator_id=?',(lost_id,g.user['id'])).fetchone()
            if not lost or lost['type']!='LOST': raise NotFound('Your lost report was not found')
            if lost['status']!='OPEN': raise Conflict('Your lost report is not OPEN')
        required=requires_ownership_evidence(found) or (lost is not None and requires_ownership_evidence(lost))
        evidence=validate_evidence(p.get('evidence',''),required)
        recent=db.execute('SELECT COUNT(*) FROM claims WHERE found_id=? AND claimant_id=?',(found_id,g.user['id'])).fetchone()[0]
        if recent>=3: raise Conflict('Maximum three claims per person for this report')
        cid=db.execute('INSERT INTO claims(found_id,lost_id,claimant_id,evidence) VALUES(?,?,?,?)',(found_id,lost_id,g.user['id'],evidence)).lastrowid
        notify(db,found['creator_id'],'CLAIM',cid,'Someone submitted a private ownership claim.',f'claim:{cid}')
        event(db,found_id,'CLAIM_SUBMITTED')
    return jsonify(claim_json(claim_row(cid))),201


@bp.get('/api/claims')
@login_required
def claims():
    limit,offset=page_args()
    rows=get_db().execute('''SELECT c.*,l.creator_id AS finder_id FROM claims c JOIN listings l ON l.id=c.found_id
      WHERE c.claimant_id=? OR l.creator_id=? ORDER BY c.id DESC LIMIT ? OFFSET ?''',(g.user['id'],g.user['id'],limit,offset)).fetchall()
    return jsonify(claims=[claim_json(r) for r in rows])


@bp.get('/api/claims/<int:claim_id>')
@login_required
def detail(claim_id): return jsonify(claim_json(claim_row(claim_id)))


@bp.post('/api/claims/<int:claim_id>/evidence')
@login_required
def evidence(claim_id):
    p=payload()
    with atomic() as db:
        row=claim_row(claim_id)
        if g.user['id']!=row['claimant_id']: raise Forbidden('Only the claimant can update evidence')
        if row['status'] not in ('PENDING','NEEDS_INFO'): raise Conflict('Evidence cannot be changed after review is complete')
        value=validate_evidence(p.get('evidence',''),claim_requires_evidence(db,row))
        db.execute("UPDATE claims SET evidence=?,status='PENDING',updated_at=CURRENT_TIMESTAMP WHERE id=?",(value,claim_id))
        event(db,row['found_id'],'CLAIM_EVIDENCE_UPDATED')
    return jsonify(claim_json(claim_row(claim_id)))


@bp.post('/api/claims/<int:claim_id>/review')
@login_required
def review(claim_id):
    p=payload();decision=choice(p.get('decision'),'decision',('ACCEPTED','REJECTED','NEEDS_INFO'))
    note=text(p.get('note',''),'note',1000)
    with atomic() as db:
        row=claim_row(claim_id)
        if row['finder_id']!=g.user['id']: raise Forbidden('Only the finder can review this claim')
        if row['status']==decision: return jsonify(claim_json(row))
        if row['status'] not in ('PENDING','NEEDS_INFO'): raise Conflict('This claim has already been decided')
        found=db.execute('SELECT * FROM listings WHERE id=?',(row['found_id'],)).fetchone()
        if found['status']!='OPEN': raise Conflict('Item is no longer OPEN')
        if decision=='ACCEPTED':
            validate_evidence(row['evidence'],claim_requires_evidence(db,row))
            if row['lost_id']:
                lost=db.execute('SELECT * FROM listings WHERE id=?',(row['lost_id'],)).fetchone()
                if lost['status']!='OPEN': raise Conflict('Linked lost report is not OPEN')
                db.execute("UPDATE listings SET status='CLAIMED',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['lost_id'],))
                event(db,row['lost_id'],'CLAIM_ACCEPTED')
            db.execute("UPDATE listings SET status='CLAIMED',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['found_id'],))
            affected=[row['found_id']]+([row['lost_id']] if row['lost_id'] else [])
            for lid in affected: db.execute('UPDATE matches SET active=0 WHERE lost_id=? OR found_id=?',(lid,lid))
            others=db.execute("SELECT id,claimant_id FROM claims WHERE id!=? AND (found_id=? OR (lost_id IS NOT NULL AND lost_id=?)) AND status IN ('PENDING','NEEDS_INFO')",(claim_id,row['found_id'],row['lost_id'])).fetchall()
            for other in others:
                db.execute("UPDATE claims SET status='REJECTED',review_note='Item reserved through another claim',updated_at=CURRENT_TIMESTAMP WHERE id=?",(other['id'],))
                notify(db,other['claimant_id'],'CLAIM',other['id'],'A claim is no longer available.',f"claim:{other['id']}:reserved")
        db.execute('UPDATE claims SET status=?,review_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(decision,note,claim_id))
        event(db,row['found_id'],'CLAIM_'+decision)
        tell(db,row,'CLAIM','Your claim has an update.',f'claim:{claim_id}:{decision}')
    return jsonify(claim_json(claim_row(claim_id)))


@bp.post('/api/claims/<int:claim_id>/cancel')
@login_required
def cancel(claim_id):
    payload();affected=[]
    with atomic() as db:
        row=claim_row(claim_id)
        if row['status']=='CANCELLED': return jsonify(message='Already cancelled')
        if row['status']=='COMPLETED': raise Conflict('A completed return cannot be cancelled')
        handoff=db.execute('SELECT * FROM handoffs WHERE claim_id=?',(claim_id,)).fetchone()
        if handoff and (handoff['finder_confirmed'] or handoff['owner_confirmed']):
            raise Conflict('A participant has confirmed transfer; resolve the handoff before cancellation')
        if row['status']=='ACCEPTED':
            affected=[row['found_id']]+([row['lost_id']] if row['lost_id'] else [])
            for lid in affected:
                db.execute("UPDATE listings SET status='OPEN',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='CLAIMED'",(lid,))
                event(db,lid,'CLAIM_CANCELLED')
        db.execute("UPDATE claims SET status='CANCELLED',updated_at=CURRENT_TIMESTAMP WHERE id=?",(claim_id,))
        db.execute("UPDATE handoffs SET status='CANCELLED' WHERE claim_id=?",(claim_id,))
        tell(db,row,'CLAIM','A claim was cancelled.',f'claim:{claim_id}:cancelled')
    from .matching import refresh
    for lid in affected: refresh(lid)
    return jsonify(message='Claim cancelled')


@bp.get('/api/claims/<int:claim_id>/messages')
@login_required
def messages(claim_id):
    row=claim_row(claim_id);limit,offset=page_args()
    rows=get_db().execute('SELECT id,sender_id,body,created_at FROM messages WHERE claim_id=? ORDER BY id LIMIT ? OFFSET ?',(claim_id,limit,offset)).fetchall()
    return jsonify(messages=[dict(id=r['id'],body=r['body'],created_at=r['created_at'],sender_role='finder' if r['sender_id']==row['finder_id'] else 'claimant',is_mine=r['sender_id']==g.user['id']) for r in rows])


@bp.post('/api/claims/<int:claim_id>/messages')
@login_required
def send_message(claim_id):
    rate_limit('message',120)
    body=text(payload().get('body'),'body',2000,True)
    with atomic() as db:
        row=claim_row(claim_id)
        if row['status'] in ('CANCELLED','REJECTED','COMPLETED'): raise Conflict('This conversation is closed')
        mid=db.execute('INSERT INTO messages(claim_id,sender_id,body) VALUES(?,?,?)',(claim_id,g.user['id'],body)).lastrowid
        tell(db,row,'MESSAGE','You have a new private message.',f'message:{mid}')
    return jsonify(id=mid),201


@bp.post('/api/claims/<int:claim_id>/handoff')
@login_required
def arrange(claim_id):
    p=payload();method=choice(p.get('method'),'method',('MEETUP','STAFFED_DROP_OFF'))
    place=text(p.get('place'),'place',300,True);when=iso(p['arranged_at'],'arranged_at') if p.get('arranged_at') else None
    with atomic() as db:
        row=claim_row(claim_id)
        if row['status']!='ACCEPTED': raise Conflict('Accept a claim before arranging a return')
        from .listings import SENSITIVE
        category=db.execute('SELECT category FROM listings WHERE id=?',(row['found_id'],)).fetchone()[0]
        if category in SENSITIVE and method!='STAFFED_DROP_OFF': raise BadRequest('Use appropriate staffed handling for this sensitive item; see /api/return-guidance')
        existing=db.execute('SELECT * FROM handoffs WHERE claim_id=?',(claim_id,)).fetchone()
        if existing and (existing['finder_confirmed'] or existing['owner_confirmed']): raise Conflict('Cannot change arrangements after a confirmation')
        db.execute('''INSERT INTO handoffs(claim_id,method,place,arranged_at) VALUES(?,?,?,?)
          ON CONFLICT(claim_id) DO UPDATE SET method=excluded.method,place=excluded.place,arranged_at=excluded.arranged_at''',(claim_id,method,place,when))
        event(db,row['found_id'],'HANDOFF_ARRANGED')
        hid=db.execute('SELECT id FROM handoffs WHERE claim_id=?',(claim_id,)).fetchone()[0]
        tell(db,row,'HANDOFF','Return arrangements were updated.',f'handoff:{hid}:arranged')
    return jsonify(dict(get_db().execute('SELECT * FROM handoffs WHERE id=?',(hid,)).fetchone())),201


@bp.get('/api/claims/<int:claim_id>/handoff')
@login_required
def handoff(claim_id):
    claim_row(claim_id)
    row=get_db().execute('SELECT * FROM handoffs WHERE claim_id=?',(claim_id,)).fetchone()
    if not row: raise NotFound('Handoff not arranged')
    return jsonify(dict(row))


@bp.post('/api/claims/<int:claim_id>/handoff/confirm')
@login_required
def confirm(claim_id):
    payload()
    with atomic() as db:
        row=claim_row(claim_id)
        h=db.execute('SELECT * FROM handoffs WHERE claim_id=?',(claim_id,)).fetchone()
        if not h: raise NotFound('Handoff not arranged')
        if h['status']=='COMPLETED': return jsonify(message='Return already completed',status='COMPLETED')
        if row['status']!='ACCEPTED' or h['status']!='PENDING': raise Conflict('Handoff is not awaiting confirmation')
        role='finder_confirmed' if g.user['id']==row['finder_id'] else 'owner_confirmed'
        db.execute(f'UPDATE handoffs SET {role}=1 WHERE id=?',(h['id'],))
        h=db.execute('SELECT * FROM handoffs WHERE id=?',(h['id'],)).fetchone()
        complete=bool(h['finder_confirmed'] and h['owner_confirmed'])
        if complete:
            db.execute("UPDATE handoffs SET status='COMPLETED' WHERE id=?",(h['id'],))
            db.execute("UPDATE claims SET status='COMPLETED',updated_at=CURRENT_TIMESTAMP WHERE id=?",(claim_id,))
            for lid in [row['found_id']]+([row['lost_id']] if row['lost_id'] else []):
                db.execute("UPDATE listings SET status='RETURNED',custody='RETURNED',resolution='CONFIRMED_HANDOFF',updated_at=CURRENT_TIMESTAMP WHERE id=?",(lid,))
                db.execute('UPDATE matches SET active=0 WHERE lost_id=? OR found_id=?',(lid,lid));event(db,lid,'RETURN_CONFIRMED')
            # Credits are a contribution log, not proof of identity or ownership.
            for uid in (row['finder_id'],row['claimant_id']):
                db.execute('INSERT OR IGNORE INTO reputation_events(user_id,handoff_id,points,reason) VALUES(?,?,?,?)',(uid,h['id'],10 if uid==row['finder_id'] else 2,'Two-party confirmed return'))
                notify(db,uid,'HANDOFF',claim_id,'Return completed. Thank you!',f"handoff:{h['id']}:completed")
        else: tell(db,row,'HANDOFF','The other participant confirmed the return. Please confirm receipt or transfer.',f"handoff:{h['id']}:{role}")
    return jsonify(status='COMPLETED' if complete else 'PENDING',finder_confirmed=bool(h['finder_confirmed']),owner_confirmed=bool(h['owner_confirmed']))


@bp.get('/api/return-guidance')
@login_required
def guidance():
    return jsonify(message='Use the relevant institution’s current lost-property rules. Listed sources are guidance, not a partnership or custody verification.',
        sources=[{'title':'Rutgers lost-property guidance','url':'https://ipo.rutgers.edu/publicsafety/lost-found-nb'},
                 {'title':'Rutgers student-center lost and found','url':'https://sca.rutgers.edu/services/lost-and-found'},
                 {'title':'Lost and found RU ID cards','url':'https://ipo.rutgers.edu/publicsafety/iam/lost-found-ruid'}],
        sensitive_items='For IDs, keys, cards, or cash, contact the appropriate staffed campus office before arranging a direct exchange.',
        verified_dropoff_supported=False)
