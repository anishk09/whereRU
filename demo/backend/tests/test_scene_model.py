"""Real local model evaluation; no Gemini, no supplied-photo leakage into references."""
import io
import json
import cv2
import pytest
from PIL import Image
from whereru import scene_matcher
from whereru.vision import ROOT,FIVE_ROOMS,compare_room
from tools.prepare_references import perspective


def configured(app):
    app.config['CLASSROOM_CATALOG']=str(ROOT/'data/classrooms.json')
    if scene_matcher.scene_model() is None:pytest.skip('Offline DINOv2 assets are not installed on this host')


@pytest.mark.parametrize('rid',FIVE_ROOMS)
def test_five_room_model_handles_unseen_viewpoint_lighting_and_jpeg(app,rid):
    configured(app)
    # Query angle and pitch are absent from the reference views (30-degree steps).
    pano=cv2.imread(str(ROOT/'data/room-references'/f'{rid}.jpg'))
    query=perspective(pano,17,0,size=640,fov=67)
    query=cv2.convertScaleAbs(query,alpha=.82,beta=9)
    success,raw=cv2.imencode('.jpg',query,[cv2.IMWRITE_JPEG_QUALITY,67]);assert success
    with app.app_context():
        candidates,_=compare_room(raw.tobytes(),scope='five')
    assert candidates and candidates[0]['id']==rid
    assert len(candidates)<=5 and all(c['needs_confirmation'] for c in candidates)


def test_actual_weeks_photo_matches_official_refs_without_supplied_photo(app):
    configured(app)
    rooms=json.loads((ROOT/'data/classrooms.json').read_text())['rooms']
    refs=[{**r,'images':[name for name in r['images'] if 'supplied' not in name]} for r in rooms if r['id'] in FIVE_ROOMS]
    result=scene_matcher.match_rooms((ROOT.parent/'public/examples/Weeks-lecture.jpg').read_bytes(),refs,ROOT/'data/room-references')
    assert result and result[0]['room_id']=='RWH-105'
    assert 'Overall look' in ' '.join(result[0]['evidence'])


@pytest.mark.parametrize('photo',['public/examples/IMG_3989.jpg','backend/data/room-references/ABW-1150A-still.jpg'])
def test_outside_five_room_catalogue_rejects_unrelated_photos(app,photo):
    configured(app)
    with app.app_context():
        candidates,_=compare_room((ROOT.parent/photo).read_bytes(),scope='five')
    assert candidates==[]


def test_room_scope_validation_and_confirmation(account,app):
    configured(app);c,h,_=account()
    raw=io.BytesIO();Image.new('RGB',(100,100),'black').save(raw,'JPEG')
    assert c.post('/api/vision/rooms',data={'image':(io.BytesIO(raw.getvalue()),'blank.jpg'),'scope':'invalid'},headers=h).status_code==400
    response=c.post('/api/vision/rooms',data={'image':(io.BytesIO(raw.getvalue()),'blank.jpg'),'scope':'five'},headers=h)
    assert response.status_code==200 and response.json['candidates']==[] and response.json['needs_confirmation']
    assert response.json['room_options']==list(FIVE_ROOMS)
