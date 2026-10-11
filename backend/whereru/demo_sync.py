"""Demo-only endpoints: one shared catalog that every phone in a live demo syncs to.

Enabled only when DEMO_LOGIN=true and APP_ENV is not production (same switch as the demo login).
Seed or reset it with: python tools/seed_demo.py
"""
import os
import re
import secrets
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, NotFound
from .core import payload, login_required, rate_limit
from .media import normalize_image
from . import demo_store

bp = Blueprint('demo_sync', __name__)


def catalog_path():
    return current_app.config.get('DEMO_CATALOG') or str(Path(current_app.instance_path) / 'demo_catalog.json')


def require_enabled():
    enabled = current_app.config.get('DEMO_SYNC')
    if enabled is None:
        enabled = os.getenv('DEMO_LOGIN', '').lower() == 'true'
    if not enabled or current_app.config['APP_ENV'] == 'production':
        raise NotFound('Not found')


def public_state(state):
    if state is None:
        return dict(generation=None, version=0, catalog=None, claim_answers={}, personas=[])
    return dict(generation=state['generation'], version=state['version'], catalog=state['catalog'],
                claim_answers=state.get('claim_answers', {}), personas=state.get('personas', []))


@bp.get('/api/demo/catalog')
def get_catalog():
    require_enabled()
    state = demo_store.read(catalog_path())
    # Phones poll every few seconds; when they already have this version, skip resending the catalog.
    if (state and request.args.get('generation') == state['generation']
            and request.args.get('version') == str(state['version'])):
        return jsonify(generation=state['generation'], version=state['version'], unchanged=True,
                       catalog=None, claim_answers={}, personas=[])
    return jsonify(public_state(state))


@bp.post('/api/demo/catalog')
def push_catalog():
    require_enabled()
    p = payload()
    generation = p.get('generation')
    if generation is not None and not isinstance(generation, str):
        raise BadRequest('generation must be text or null')
    try:
        state, accepted = demo_store.push(catalog_path(), generation, p.get('catalog'), p.get('claim_answers'))
    except ValueError as error:
        raise BadRequest(str(error))
    return jsonify(accepted=accepted, **public_state(state))


# Report photos for the shared demo, so the other phone can see them. Re-encoded without EXIF
# (normalize_image) and kept under instance/demo_photos with an unguessable 128-bit name; viewing
# needs only that name, like the shared catalog itself.
PHOTO_NAME = re.compile(r'^[0-9a-f]{32}\.jpg$')


def photo_dir():
    path = Path(current_app.instance_path) / 'demo_photos'
    path.mkdir(parents=True, exist_ok=True)
    return path


@bp.post('/api/demo/photos')
@login_required
def upload_photo():
    require_enabled()
    rate_limit('demo_photo', 120)
    if 'image' not in request.files:
        raise BadRequest('multipart/form-data field image is required')
    raw, _, _ = normalize_image(request.files['image'].stream)
    name = secrets.token_hex(16) + '.jpg'
    (photo_dir() / name).write_bytes(raw)
    return jsonify(url=f'/api/demo/photos/{name}'), 201


@bp.get('/api/demo/photos/<name>')
def view_photo(name):
    require_enabled()
    path = photo_dir() / name
    if not PHOTO_NAME.match(name) or not path.is_file():
        raise NotFound('Photo not found')
    response = send_file(path, mimetype='image/jpeg', conditional=False)
    response.headers['Cache-Control'] = 'private, max-age=86400'
    return response
