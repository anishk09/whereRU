import pytest
from whereru.db import atomic


@pytest.mark.parametrize('category', ['bottle', 'clothing', 'bag', 'other'])
def test_everyday_return_needs_no_secret_answer(account, report, category):
    owner, oh, _ = account(); finder, fh, _ = account()
    found = report(finder, fh, type='FOUND', category=category)
    assert found['requires_ownership_evidence'] is False
    claim = owner.post('/api/claims', json={'found_id': found['id']}, headers=oh)
    assert claim.status_code == 201, claim.json
    assert claim.json['evidence'] == '' and claim.json['requires_ownership_evidence'] is False
    cid = claim.json['id']
    assert owner.post(f'/api/claims/{cid}/review', json={'decision': 'ACCEPTED'}, headers=oh).status_code == 403
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'ACCEPTED'}, headers=fh).status_code == 200
    assert owner.post(f'/api/claims/{cid}/handoff', json={'method': 'MEETUP', 'place': 'Student center'}, headers=oh).status_code == 201
    assert finder.post(f'/api/claims/{cid}/handoff/confirm', json={}, headers=fh).json['status'] == 'PENDING'
    assert owner.post(f'/api/claims/{cid}/handoff/confirm', json={}, headers=oh).json['status'] == 'COMPLETED'


@pytest.mark.parametrize('category,visibility', [
    ('electronics', 'PUBLIC'), ('keys', 'PRIVATE'), ('wallet', 'PRIVATE'),
    ('id_card', 'PRIVATE'), ('other', 'PRIVATE'),
])
def test_valuable_and_sensitive_answers_are_enforced(account, report, category, visibility):
    owner, oh, _ = account(); finder, fh, _ = account()
    lost = report(owner, oh, category=category, visibility=visibility)
    found = report(finder, fh, type='FOUND', category=category, visibility=visibility)
    assert found['requires_ownership_evidence'] is True
    match = owner.get('/api/matches').json['matches'][0]
    assert match['requires_ownership_evidence'] is True
    for answer in ('', 'short'):
        r = owner.post('/api/claims', json={'found_id': found['id'], 'lost_id': lost['id'],
            'evidence': answer, 'requires_ownership_evidence': False}, headers=oh)
        assert r.status_code == 400, r.json
    r = owner.post('/api/claims', json={'found_id': found['id'], 'lost_id': lost['id'],
        'evidence': 'Distinctive mark behind the hinge'}, headers=oh)
    assert r.status_code == 201 and r.json['requires_ownership_evidence'] is True
    cid = r.json['id']
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'NEEDS_INFO'}, headers=fh).status_code == 200
    assert owner.post(f'/api/claims/{cid}/evidence', json={'evidence': 'short'}, headers=oh).status_code == 400
    assert owner.post(f'/api/claims/{cid}/evidence', json={'evidence': 'Additional distinctive hidden mark'}, headers=oh).status_code == 200
    assert finder.get(f'/api/claims/{cid}').json['requires_ownership_evidence'] is True
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'ACCEPTED'}, headers=fh).status_code == 200


def test_owner_marked_valuable_is_honored_with_public_found_report(account, report):
    owner, oh, _ = account(); finder, fh, _ = account()
    lost = report(owner, oh, visibility='PRIVATE')
    found = report(finder, fh, type='FOUND')
    assert found['requires_ownership_evidence'] is False
    assert owner.get('/api/matches').json['matches'][0]['requires_ownership_evidence'] is True
    r = owner.post('/api/claims', json={'found_id': found['id'], 'lost_id': lost['id']}, headers=oh)
    assert r.status_code == 400
    r = owner.post('/api/claims', json={'found_id': found['id'], 'lost_id': lost['id'], 'evidence': 'The hidden inscription on the base'}, headers=oh)
    assert r.status_code == 201 and r.json['requires_ownership_evidence'] is True


def test_ordinary_message_can_be_short_and_updated(account, report):
    owner, oh, _ = account(); finder, fh, _ = account()
    found = report(finder, fh, type='FOUND')
    r = owner.post('/api/claims', json={'found_id': found['id'], 'evidence': 'Hi'}, headers=oh)
    assert r.status_code == 201 and r.json['evidence'] == 'Hi'
    cid = r.json['id']
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'NEEDS_INFO'}, headers=fh).status_code == 200
    r = owner.post(f'/api/claims/{cid}/evidence', json={'evidence': 'At 2'}, headers=oh)
    assert r.status_code == 200 and r.json['status'] == 'PENDING'


def test_reclassified_valuable_claim_cannot_approve_a_missing_answer(app, account, report):
    owner, oh, _ = account(); finder, fh, _ = account()
    found = report(finder, fh, type='FOUND')
    cid = owner.post('/api/claims', json={'found_id': found['id']}, headers=oh).json['id']
    assert finder.patch(f"/api/listings/{found['id']}", json={'category': 'electronics'}, headers=fh).status_code == 200
    assert owner.get(f'/api/claims/{cid}').json['requires_ownership_evidence'] is True
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'ACCEPTED'}, headers=fh).status_code == 400
    with app.app_context():
        with atomic() as db:
            assert db.execute('SELECT status FROM claims WHERE id=?', (cid,)).fetchone()[0] == 'PENDING'
    assert owner.post(f'/api/claims/{cid}/evidence', json={'evidence': 'The distinctive engraving on the underside'}, headers=oh).status_code == 200
    assert finder.post(f'/api/claims/{cid}/review', json={'decision': 'ACCEPTED'}, headers=fh).status_code == 200
