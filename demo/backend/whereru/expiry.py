"""Delete reports and dependent private data seven days after posting.

Requests enforce expiry as endpoints are used. The local server also sweeps every
minute, and startup cleans up time spent offline. Earned reputation survives.
"""
import threading
from pathlib import Path
from flask import current_app
from .db import atomic,get_db

EXPIRY_SQL="julianday(created_at)<=julianday('now','-7 days')"


def _remove_uploads():
    db=get_db();base=Path(current_app.config['UPLOAD_DIR']).resolve()
    for row in db.execute('SELECT storage_name FROM upload_deletions').fetchall():
        path=(base/row['storage_name']).resolve()
        if path.parent!=base:
            current_app.logger.error('Rejected invalid expired upload path')
            continue
        try:path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning('Expired upload deletion will be retried')
            continue
        db.execute('DELETE FROM upload_deletions WHERE storage_name=?',(row['storage_name'],))


def expire_listings():
    db=get_db();count=0
    # Avoid a write transaction on the ordinary polling/read path.
    if db.execute('SELECT 1 FROM listings WHERE '+EXPIRY_SQL+' LIMIT 1').fetchone():
        with atomic() as db:
            db.execute('CREATE TEMP TABLE IF NOT EXISTS expiring_listings(id INTEGER PRIMARY KEY)')
            db.execute('DELETE FROM expiring_listings')
            db.execute('INSERT INTO expiring_listings SELECT id FROM listings WHERE '+EXPIRY_SQL)
            count=db.execute('SELECT COUNT(*) FROM expiring_listings').fetchone()[0]
            expired='SELECT id FROM expiring_listings'
            claims=f'SELECT id FROM claims WHERE found_id IN ({expired}) OR lost_id IN ({expired})'
            handoffs=f'SELECT id FROM handoffs WHERE claim_id IN ({claims})'
            matches=f'SELECT id FROM matches WHERE lost_id IN ({expired}) OR found_id IN ({expired})'
            earned=db.execute(f'SELECT user_id,SUM(points),COUNT(*) FROM reputation_events WHERE handoff_id IN ({handoffs}) GROUP BY user_id').fetchall()
            for uid,points,returns in earned:
                db.execute('''INSERT INTO retained_reputation VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                    points=points+excluded.points,confirmed_returns=confirmed_returns+excluded.confirmed_returns''',(uid,points,returns))
            # A newer counterpart must not remain reserved by a deleted claim.
            db.execute(f'''UPDATE listings SET status='OPEN',updated_at=CURRENT_TIMESTAMP,version=version+1
                WHERE status='CLAIMED' AND id NOT IN ({expired}) AND id IN
                (SELECT found_id FROM claims WHERE status='ACCEPTED' AND id IN ({claims})
                 UNION SELECT lost_id FROM claims WHERE status='ACCEPTED' AND id IN ({claims}))''')
            db.execute(f"DELETE FROM notifications WHERE (kind='MATCH' AND resource_id IN ({matches})) OR (kind='NEARBY' AND resource_id IN ({expired})) OR (kind IN ('CLAIM','MESSAGE','HANDOFF') AND resource_id IN ({claims}))")
            db.execute(f'INSERT OR IGNORE INTO upload_deletions SELECT storage_name FROM images WHERE listing_id IN ({expired})')
            db.execute(f'DELETE FROM reputation_events WHERE handoff_id IN ({handoffs})')
            db.execute(f'DELETE FROM handoffs WHERE claim_id IN ({claims})')
            db.execute(f'DELETE FROM messages WHERE claim_id IN ({claims})')
            db.execute(f'DELETE FROM claims WHERE id IN ({claims})')
            db.execute(f'DELETE FROM match_feedback WHERE match_id IN ({matches})')
            db.execute(f'DELETE FROM matches WHERE id IN ({matches})')
            for table in ('images','ai_analyses','events','listing_vectors'):
                db.execute(f'DELETE FROM {table} WHERE listing_id IN ({expired})')
            db.execute(f'DELETE FROM listings WHERE id IN ({expired})')
            # potential_locations and saved_listings cascade through foreign keys.
    _remove_uploads()
    return count


def start_expiry_worker(app):
    """Daemon stops with Flask and never resets demo data."""
    if app.extensions.get('expiry_worker'):return
    stop=threading.Event()
    def sweep():
        while not stop.wait(60):
            try:
                with app.app_context():expire_listings()
            except Exception:app.logger.exception('Listing expiry sweep failed; it will retry')
    app.extensions['expiry_worker']=stop
    threading.Thread(target=sweep,name='listing-expiry',daemon=True).start()
