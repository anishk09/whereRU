import json
import subprocess
import sys
from pathlib import Path
import pytest
from whereru import demo_store

BACKEND = Path(__file__).resolve().parents[1]


def report(rid, updated, **extra):
    return {'id': rid, 'createdAt': updated, 'updatedAt': updated, 'status': 'active', **extra}


def test_merge_keeps_newest_record_and_unions_new_ones(tmp_path):
    path = tmp_path / 'catalog.json'
    state, ok = demo_store.push(path, None, {'reports': [report('a', '2026-10-11T01:00:00.000Z')]}, {})
    assert ok and state['version'] == 1
    gen = state['generation']
    # Phone 1 edits a; phone 2 (stale copy of a) adds b at the same time.
    demo_store.push(path, gen, {'reports': [report('a', '2026-10-11T02:00:00.000Z', status='returned')]}, {})
    state, ok = demo_store.push(path, gen, {'reports': [report('a', '2026-10-11T01:00:00.000Z'),
                                                         report('b', '2026-10-11T01:30:00.000Z')]}, {'c1': 'cat sticker'})
    assert ok
    by_id = {r['id']: r for r in state['catalog']['reports']}
    assert by_id['a']['status'] == 'returned' and 'b' in by_id
    assert state['claim_answers'] == {'c1': 'cat sticker'} and state['version'] == 3


def test_notifications_stay_read_and_unchanged_push_keeps_version(tmp_path):
    path = tmp_path / 'catalog.json'
    note = dict(id='n1', createdAt='2026-10-11T01:00:00.000Z', read=False)
    state, _ = demo_store.push(path, None, {'notifications': [note]}, {})
    gen = state['generation']
    state, _ = demo_store.push(path, gen, {'notifications': [{**note, 'read': True}]}, {})
    state, _ = demo_store.push(path, gen, {'notifications': [note]}, {})
    assert state['catalog']['notifications'][0]['read'] is True
    assert state['version'] == 2


def test_stale_generation_is_refused(tmp_path):
    path = tmp_path / 'catalog.json'
    demo_store.reset(path, {'reports': [report('fresh', '2026-10-11T01:00:00.000Z')]})
    state, ok = demo_store.push(path, 'old-generation', {'reports': [report('old', '2026-10-11T03:00:00.000Z')]}, {})
    assert not ok and [r['id'] for r in state['catalog']['reports']] == ['fresh']


def test_bad_records_rejected(tmp_path):
    with pytest.raises(ValueError):
        demo_store.push(tmp_path / 'c.json', None, {'reports': [{'title': 'no id'}]}, {})


def test_endpoints(app, tmp_path):
    app.config.update(DEMO_SYNC=True, DEMO_CATALOG=str(tmp_path / 'demo.json'))
    client = app.test_client()
    assert client.get('/api/demo/catalog').json['generation'] is None
    pushed = client.post('/api/demo/catalog', json={'generation': None, 'catalog': {'reports': [report('x', '2026-10-11T01:00:00.000Z')]}})
    assert pushed.status_code == 200 and pushed.json['accepted']
    got = client.get('/api/demo/catalog').json
    assert got['generation'] == pushed.json['generation'] and got['catalog']['reports'][0]['id'] == 'x'
    assert client.post('/api/demo/catalog', json={'catalog': []}).status_code == 400


def test_endpoints_hidden_unless_enabled(app):
    app.config.update(DEMO_SYNC=False)
    assert app.test_client().get('/api/demo/catalog').status_code == 404


def test_seed_script(tmp_path):
    out = tmp_path / 'seed.json'
    subprocess.run([sys.executable, str(BACKEND / 'tools/seed_demo.py'), '--out', str(out), '--reports', '30'], check=True,
                   capture_output=True)
    state = json.loads(out.read_text())
    reports = state['catalog']['reports']
    owners = {r['reporterId'] for r in reports}
    assert {'demo-jordan', 'demo-maya'} <= owners and len(owners) > 5
    assert len({r['id'] for r in reports}) == len(reports) == 30 + 5
    maya = next(r for r in reports if r['id'] == 'maya-lost')
    others = [r for r in reports if r['itemName'] == maya['itemName'] and r['id'] != 'maya-lost']
    assert not others
