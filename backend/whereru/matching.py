import json
import math
import re
from datetime import datetime
from flask import Blueprint,g,jsonify
from werkzeug.exceptions import NotFound
from .core import login_required,payload,choice,page_args,notify
from .db import get_db,atomic
bp=Blueprint('matching',__name__)
SYNONYMS={'flask':'bottle','drinkware':'bottle','navy':'blue','grey':'gray','rucksack':'backpack','backpack':'bag','headphones':'earphones','earbuds':'earphones'}


def tokens(value):
    return {SYNONYMS.get(w,w) for w in re.findall(r'[a-z0-9]+',(value or '').lower())}-{ 'a','the','my','lost','found','at','in','with','and','near' }


def compare(lost,found):
    if lost['type']!='LOST' or found['type']!='FOUND': return 0,[]
    if lost['category']!='other' and found['category']!='other' and lost['category']!=found['category']: return 0,['Different categories']
    a=datetime.fromisoformat(lost['occurred_at']);b=datetime.fromisoformat(found['occurred_at'])
    # Allow two hours of uncertainty around the reported last-seen time.
    if (a-b).total_seconds()>7200: return 0,['Found before the plausible loss window']
    score=0;reasons=[]
    if lost['category']==found['category'] and lost['category']!='other': score+=25;reasons.append('Same item category')
    ta=tokens(lost['title']+' '+lost['description']);tb=tokens(found['title']+' '+found['description'])
    similarity=len(ta&tb)/max(1,len(ta|tb));score+=30*similarity
    if similarity: reasons.append('Descriptions share normalized terms')
    aa=json.loads(lost['attributes']);ab=json.loads(found['attributes'])
    for attr,weight in [('color',12),('brand',12),('model',12),('material',5)]:
        if aa.get(attr) and ab.get(attr):
            if tokens(aa[attr])&tokens(ab[attr]): score+=weight;reasons.append(f'Compatible {attr}')
            else: score-=weight;reasons.append(f'Conflicting {attr}')
    if lost['campus'] and lost['campus'].casefold()==found['campus'].casefold(): score+=5;reasons.append('Same campus')
    if lost['location'] and tokens(lost['location'])&tokens(found['location']): score+=8;reasons.append('Compatible reported area')
    if abs((b-a).total_seconds())<=86400: score+=5;reasons.append('Reported event times are close')
    # Verification secrets are excluded from scoring to avoid a score-based guessing oracle.
    return round(max(0,min(100,score)),1),reasons


def semantic_score(db,lost,found,score,reasons):
    if reasons in (['Different categories'],['Found before the plausible loss window']): return score,reasons
    a=db.execute('SELECT * FROM listing_vectors WHERE listing_id=? AND listing_version=?',(lost['id'],lost['version'])).fetchone()
    b=db.execute('SELECT * FROM listing_vectors WHERE listing_id=? AND listing_version=?',(found['id'],found['version'])).fetchone()
    if not a or not b or a['model']!=b['model']: return score,reasons
    va=json.loads(a['vector']);vb=json.loads(b['vector'])
    if len(va)!=len(vb):return score,reasons
    denom=math.sqrt(sum(x*x for x in va)*sum(x*x for x in vb))
    cosine=sum(x*y for x,y in zip(va,vb))/denom if denom else 0
    # Prototype weighting, not calibrated probability. Validate using your own examples.
    boost=30*max(0,min(1,(cosine-0.3)/0.7))
    if boost: reasons=reasons+['AI-indexed descriptions are semantically similar']
    return round(min(100,score+boost),1),reasons


def refresh(listing_id):
    with atomic() as db:
        row=db.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
        db.execute('UPDATE matches SET active=0 WHERE lost_id=? OR found_id=?',(listing_id,listing_id))
        if not row or row['status']!='OPEN' or row['creator_id'] is None: return
        candidates=db.execute("SELECT * FROM listings WHERE status='OPEN' AND type!=? AND creator_id IS NOT NULL AND creator_id!=?",(row['type'],row['creator_id'])).fetchall()
        for other in candidates:
            lost,found=(row,other) if row['type']=='LOST' else (other,row)
            score,reasons=compare(lost,found)
            score,reasons=semantic_score(db,lost,found,score,reasons)
            if score<35: continue
            db.execute('''INSERT INTO matches(lost_id,found_id,score,reasons) VALUES(?,?,?,?)
                ON CONFLICT(lost_id,found_id) DO UPDATE SET score=excluded.score,reasons=excluded.reasons,active=1,updated_at=CURRENT_TIMESTAMP''',
                (lost['id'],found['id'],score,json.dumps(reasons)))
            match_id=db.execute('SELECT id FROM matches WHERE lost_id=? AND found_id=?',(lost['id'],found['id'])).fetchone()[0]
            # Notify the lost reporter only: finder does not learn all potential owners.
            rejected=db.execute("SELECT 1 FROM match_feedback WHERE match_id=? AND user_id=? AND decision='NOT_MINE'",(match_id,lost['creator_id'])).fetchone()
            if not rejected: notify(db,lost['creator_id'],'MATCH',match_id,'A found report may match your lost item.',f'match:{match_id}')


def match_for_owner(match_id):
    row=get_db().execute('''SELECT m.*,l.creator_id FROM matches m JOIN listings l ON l.id=m.lost_id
        WHERE m.id=? AND l.creator_id=?''',(match_id,g.user['id'])).fetchone()
    if not row: raise NotFound('Match not found')
    return row


def match_json(row):
    found=get_db().execute('SELECT * FROM listings WHERE id=?',(row['found_id'],)).fetchone()
    lost=get_db().execute('SELECT status FROM listings WHERE id=?',(row['lost_id'],)).fetchone()
    active=bool(row['active']) and found['status']=='OPEN' and lost['status']=='OPEN'
    result=dict(id=row['id'],lost_id=row['lost_id'],found_id=row['found_id'],active=active)
    if not active: return {**result,'message':'This candidate is no longer active'}
    if found['visibility']=='PRIVATE':
        result.update(score=None,reasons=['A restricted found report may match; submit private evidence for review.'],candidate={'restricted':True})
    else:
        result.update(score=row['score'],score_label='ranking score, not ownership probability',reasons=json.loads(row['reasons']),
                      candidate={k:found[k] for k in ('id','title','category','location','campus')})
    return result


@bp.get('/api/matches')
@login_required
def matches():
    limit,offset=page_args()
    rows=get_db().execute('''SELECT m.* FROM matches m JOIN listings l ON l.id=m.lost_id
      WHERE l.creator_id=? AND m.active=1 AND NOT EXISTS(SELECT 1 FROM match_feedback f WHERE f.match_id=m.id AND f.user_id=? AND f.decision='NOT_MINE')
      ORDER BY m.score DESC,m.id DESC LIMIT ? OFFSET ?''',(g.user['id'],g.user['id'],limit,offset)).fetchall()
    return jsonify(matches=[match_json(r) for r in rows])


@bp.get('/api/matches/<int:match_id>')
@login_required
def detail(match_id): return jsonify(match_json(match_for_owner(match_id)))


@bp.post('/api/matches/<int:match_id>/feedback')
@login_required
def feedback(match_id):
    match_for_owner(match_id);decision=choice(payload().get('decision'),'decision',('NOT_MINE','POSSIBLE'))
    with atomic() as db: db.execute('INSERT OR REPLACE INTO match_feedback VALUES(?,?,?)',(match_id,g.user['id'],decision))
    return jsonify(message='Feedback saved')


@bp.get('/api/notifications')
@login_required
def notifications():
    limit,offset=page_args();db=get_db()
    rows=db.execute('SELECT id,kind,resource_id,message,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?',
                    (g.user['id'],limit,offset)).fetchall()
    count=db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0',(g.user['id'],)).fetchone()[0]
    return jsonify(notifications=[dict(r) for r in rows],unread_count=count)


@bp.post('/api/notifications/<int:notification_id>/read')
@login_required
def read(notification_id):
    payload()
    with atomic() as db:
        cur=db.execute('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?',(notification_id,g.user['id']))
        if not cur.rowcount: raise NotFound('Notification not found')
    return jsonify(message='Marked read')
