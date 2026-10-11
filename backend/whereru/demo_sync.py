"""Demo-only endpoints: one shared catalog that every phone in a live demo syncs to.

Enabled only when DEMO_LOGIN=true and APP_ENV is not production (same switch as the demo login).
Seed or reset it with: python tools/seed_demo.py
"""
import os
from pathlib import Path
from flask import Blueprint, current_app, jsonify
from werkzeug.exceptions import BadRequest, NotFound
from .core import payload
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
    return jsonify(public_state(demo_store.read(catalog_path())))


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
