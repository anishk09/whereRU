"""Shared catalog for live demos (no Flask imports, so tools and tests can use it directly).

The app keeps reports, claims and notifications in each browser. For a two-phone demo the
backend holds one copy that every phone syncs to. Phones send their whole catalog; the server
merges it record by record (newest updatedAt wins) so two phones acting at once don't erase
each other. A new seed starts a new "generation": phones holding an older generation drop
their local copy and take the server's.
"""
import json
import os
import secrets
import tempfile
import threading
from pathlib import Path

_lock = threading.Lock()
LIST_LIMIT = 5000


def new_generation():
    return secrets.token_hex(6)


def read(path):
    path = Path(path)
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def write(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.demo_catalog.', suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f)
    os.replace(tmp, path)


def _records(value, name):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > LIST_LIMIT:
        raise ValueError(f'{name} must be a list of at most {LIST_LIMIT} records')
    out = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            raise ValueError(f'Every item in {name} needs a text id')
        out.append(item)
    return out


def clean_catalog(catalog):
    if not isinstance(catalog, dict):
        raise ValueError('catalog must be an object')
    return {name: _records(catalog.get(name), name) for name in ('reports', 'claims', 'notifications')}


def clean_answers(answers):
    if answers is None:
        return {}
    if not isinstance(answers, dict):
        raise ValueError('claim_answers must be an object')
    return {k: v for k, v in answers.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}


def _stamp(record):
    value = record.get('updatedAt') or record.get('createdAt') or ''
    return value if isinstance(value, str) else ''


def _merge_list(current, incoming, notification=False):
    merged = {r['id']: r for r in current}
    for record in incoming:
        existing = merged.get(record['id'])
        if existing is None:
            merged[record['id']] = record
        elif notification:
            # Notifications only ever change by being read.
            merged[record['id']] = {**existing, 'read': bool(existing.get('read')) or bool(record.get('read'))}
        elif _stamp(record) > _stamp(existing):
            merged[record['id']] = record
    return sorted(merged.values(), key=lambda r: r.get('createdAt') or '', reverse=True)


def merge(state, catalog, answers):
    """Returns (new_state, changed)."""
    current = state['catalog']
    merged = {
        'reports': _merge_list(current['reports'], catalog['reports']),
        'claims': _merge_list(current['claims'], catalog['claims']),
        'notifications': _merge_list(current['notifications'], catalog['notifications'], notification=True),
    }
    merged_answers = {**state.get('claim_answers', {}), **answers}
    changed = merged != current or merged_answers != state.get('claim_answers', {})
    new_state = {**state, 'catalog': merged, 'claim_answers': merged_answers}
    if changed:
        new_state['version'] = int(state.get('version', 0)) + 1
    return new_state, changed


def push(path, generation, catalog, answers):
    """Merges a phone's catalog into the shared one. Returns (state, accepted).

    accepted is False when the phone is on an older generation; it should adopt the returned state.
    """
    catalog = clean_catalog(catalog)
    answers = clean_answers(answers)
    with _lock:
        state = read(path)
        if state is None:
            state = {'generation': new_generation(), 'version': 1, 'catalog': catalog,
                     'claim_answers': answers, 'personas': []}
            write(path, state)
            return state, True
        if generation != state['generation']:
            return state, False
        state, changed = merge(state, catalog, answers)
        if changed:
            write(path, state)
        return state, True


def reset(path, catalog, answers=None, personas=None):
    state = {'generation': new_generation(), 'version': 1, 'catalog': clean_catalog(catalog),
             'claim_answers': clean_answers(answers), 'personas': personas or []}
    with _lock:
        write(path, state)
    return state
