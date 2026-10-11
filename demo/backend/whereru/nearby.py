"""Opt-in helpers receive coarse alerts about deliberately shared search areas."""
import math
import time
from flask import Blueprint, g, jsonify
from werkzeug.exceptions import NotFound, BadRequest
from .core import payload, text, number, login_required, notify, rate_limit
from .db import atomic, get_db

bp = Blueprint('nearby', __name__)


def distance_meters(a, b, c, d):
    x, y = math.radians(c-a), math.radians(d-b)
    k = math.sin(x/2)**2 + math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(y/2)**2
    return 6371000 * 2 * math.atan2(math.sqrt(k), math.sqrt(max(0, 1-k)))


def refresh(listing_id=None, helper_id=None):
    with atomic() as db:
        helpers = db.execute('SELECT * FROM nearby_subscriptions WHERE expires_at>?'+(' AND user_id=?' if helper_id else ''),
                             [time.time()]+([helper_id] if helper_id else [])).fetchall()
        rows = db.execute("""SELECT l.id,l.creator_id,l.category,p.label,p.latitude,p.longitude FROM listings l
            JOIN potential_locations p ON p.listing_id=l.id
            WHERE l.type='LOST' AND l.status='OPEN' AND l.visibility='PUBLIC' AND p.share_public=1"""+
            (' AND l.id=?' if listing_id else ''), [listing_id] if listing_id else []).fetchall()
        for helper in helpers:
            for row in rows:
                if row['creator_id'] == helper['user_id']: continue
                if distance_meters(helper['latitude'], helper['longitude'], row['latitude'], row['longitude']) <= helper['radius_meters']:
                    category = row['category'].replace('_', ' ')
                    notify(db, helper['user_id'], 'NEARBY', row['id'],
                        f'A {category} may be lost near {row["label"]}. Can you check?', f'nearby:{row["id"]}')


@bp.get('/api/me/nearby-location')
@login_required
def location():
    row = get_db().execute('SELECT * FROM nearby_subscriptions WHERE user_id=? AND expires_at>?', (g.user['id'], time.time())).fetchone()
    return jsonify(location=dict(row) if row else None)


@bp.post('/api/me/nearby-location')
@login_required
def subscribe():
    p = payload(); rate_limit('nearby-settings', 100)
    if p.get('consent') is not True: raise BadRequest('Explicit consent is required to receive nearby alerts')
    label = text(p.get('label'), 'label', 120, True)
    lat = number(p.get('latitude'), 'latitude', -90, 90); lon = number(p.get('longitude'), 'longitude', -180, 180)
    radius = number(p.get('radius_meters', 350), 'radius_meters', 100, 1000)
    with atomic() as db:
        db.execute('INSERT OR REPLACE INTO nearby_subscriptions VALUES(?,?,?,?,?,?)', (g.user['id'], label, lat, lon, radius, time.time()+86400))
    refresh(helper_id=g.user['id'])
    return jsonify(message='Nearby alerts enabled for 24 hours. Only deliberately shared public search areas are considered.')


@bp.delete('/api/me/nearby-location')
@login_required
def unsubscribe():
    payload()
    with atomic() as db: db.execute('DELETE FROM nearby_subscriptions WHERE user_id=?', (g.user['id'],))
    return jsonify(message='Nearby alerts stopped; your selected location was removed')


@bp.get('/api/nearby-alerts/<int:listing_id>')
@login_required
def detail(listing_id):
    db = get_db()
    notification = db.execute("SELECT 1 FROM notifications WHERE user_id=? AND kind='NEARBY' AND resource_id=?", (g.user['id'], listing_id)).fetchone()
    listing = db.execute("SELECT * FROM listings WHERE id=? AND visibility='PUBLIC' AND status='OPEN'", (listing_id,)).fetchone()
    if not notification or not listing: raise NotFound('This nearby request is no longer available')
    areas = db.execute('SELECT label FROM potential_locations WHERE listing_id=? AND share_public=1', (listing_id,)).fetchall()
    return jsonify(id=listing['id'], title=listing['title'], category=listing['category'], campus=listing['campus'],
        description=listing['description'], areas=[r['label'] for r in areas],
        message='These are possible search areas selected by the reporter, not a confirmed item location.')
