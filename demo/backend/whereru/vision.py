"""No-key local image tools: verified example retrieval, native OCR/classification,
and geometrically checked retrieval from Rutgers classroom reference photos.
Every result is a draft; never infer ownership or silently confirm a room.
"""
import io
import base64
import json
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, NotFound
from .core import login_required, rate_limit
from .media import normalize_image

bp = Blueprint('vision', __name__)
FIVE_ROOMS=('ARC-103','LSH-A102','PHY-001','RWH-105','SEC-111')
cv2.setNumThreads(1)
ROOT = Path(__file__).resolve().parents[1]
ITEMS = [
    dict(id='red-bottle', files=['IMG_3989.jpg', 'IMG_3990.jpg'], title='Red translucent water bottle', category='bottle',
         attributes=dict(color='red', material='plastic', brand=None),
         public_description='Red translucent bottle with a red screw cap.',
         private_details='White Rutgers Computer Science printing on the bottle.'),
    dict(id='gray-bottle', files=['IMG_3991.jpg', 'IMG_3992.jpg'], title='Gray insulated water bottle', category='bottle',
         attributes=dict(color='gray', material='metal', brand='Hydro Flask'),
         public_description='Gray insulated bottle with a dark cap and loop handle.',
         private_details='Hydro Flask logo on the body; loop handle on the lid.'),
    dict(id='tablet', files=['IMG_3993.jpg', 'IMG_3994.jpg', 'IMG_3995.jpg'], title='Tablet in a gray folding case', category='electronics',
         attributes=dict(color='gray', material=None, brand=None),
         public_description='Tablet with a gray folding stand case.',
         private_details='Several illustrated stickers on the back of the folding case.'),
]


def photo_input():
    if 'image' not in request.files:
        raise BadRequest('Upload an image in multipart field image')
    return normalize_image(request.files['image'].stream)[0]


def pixels(raw):
    gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None: raise BadRequest('Invalid image')
    h, w = gray.shape
    if max(h, w) > 1000: gray = cv2.resize(gray, (round(w * 1000 / max(h, w)), round(h * 1000 / max(h, w))))
    return gray


def fingerprint(raw):
    gray = cv2.resize(pixels(raw), (32, 32)).astype(np.float32)
    block = cv2.dct(gray)[:8, :8].flatten()[1:]
    return block > np.median(block)


@lru_cache(maxsize=1)
def example_index():
    rows = []
    for item in ITEMS:
        for name in item['files']:
            path = ROOT.parent / 'public' / 'examples' / name
            if path.is_file(): rows.append((item, name, fingerprint(path.read_bytes())))
    return rows


def native_analysis(raw):
    executable = ROOT / '.tools' / 'local-vision'
    if not executable.is_file(): return dict(labels=[], text=[], engine='Local reference matching')
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg') as file:
            file.write(raw); file.flush()
            result = subprocess.run([str(executable), file.name], capture_output=True, timeout=15, check=True)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return dict(labels=[], text=[], engine='Local reference matching; native classifier unavailable')


def color_estimate(raw):
    image = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
    h, w = image.shape[:2]
    center = image[int(h*.2):int(h*.85), int(w*.3):int(w*.7)]
    hsv = cv2.cvtColor(center, cv2.COLOR_RGB2HSV)
    hue, saturation, value = [hsv[:, :, n].flatten() for n in range(3)]
    vivid = (saturation > 105) & (value > 45)
    if vivid.mean() < .13: return None
    hist, _ = np.histogram(hue[vivid], bins=18, range=(0, 180))
    top = int(hist.argmax()) * 10
    return 'red' if top < 10 or top >= 170 else 'orange' if top < 25 else 'yellow' if top < 40 else 'green' if top < 85 else 'blue' if top < 135 else 'purple'


def describe(raw):
    query = fingerprint(raw)
    ranked = sorted([(int(np.count_nonzero(query != fp)), item, name) for item, name, fp in example_index()], key=lambda r: r[0])
    if ranked and ranked[0][0] <= 7:
        distance, item, name = ranked[0]
        return dict(mode='local-reference', engine='Perceptual image comparison with reviewed example photos',
                    reference_id=item['id'], reference_photo=name, title=item['title'], category=item['category'],
                    attributes=item['attributes'], description=item['public_description'], private_details=item['private_details'],
                    evidence=[f'Visual fingerprint matched a reviewed {item["id"]} example ({distance} differing bits).'],
                    uncertainty='Limited to the reviewed example collection. Confirm every detail; this does not prove ownership.', requires_review=True)
    local = native_analysis(raw)
    labels = local.get('labels', [])
    selected = next((r for r in labels if float(r['score']) >= .12 and re.search(r'bottle|flask|tablet|laptop|computer|phone|bag|backpack|umbrella|headphone|shoe|clothing', r['label'], re.I)), None)
    label = selected['label'] if selected else ''
    category = 'bottle' if re.search('bottle|flask', label, re.I) else 'electronics' if re.search('tablet|laptop|computer|phone|headphone', label, re.I) else 'bag' if re.search('bag|backpack', label, re.I) else 'other'
    color = color_estimate(raw) if selected else None
    return dict(mode='local-vision', engine=local['engine'], title=(label.replace('_', ' ').capitalize() if selected else 'Unidentified item'),
                category=category, attributes=dict(color=color, material=None, brand=None),
                description=f'{color or ""} {label.replace("_", " ")}'.strip() if selected else '',
                private_details='', evidence=[f'Local classifier suggests {label}.'] if selected else [],
                uncertainty='On-device draft. Color samples can include the background; brands, material and hidden details are left unknown. Enter corrections before posting.',
                requires_review=True, labels=labels, visible_text=local.get('text', []))


@bp.post('/api/vision/items')
@login_required
def analyze_item():
    rate_limit('local-vision', 100)
    return jsonify(describe(photo_input()))


@bp.post('/api/vision/normalize')
@login_required
def normalize_upload():
    rate_limit('local-normalize',100)
    raw=photo_input()
    return jsonify(image='data:image/jpeg;base64,'+base64.b64encode(raw).decode('ascii'))


def room_manifest():
    path = Path(current_app.config['CLASSROOM_CATALOG'])
    return json.loads(path.read_text())['rooms'], path.parent / 'room-references'


def sift(gray):
    points, descriptors = cv2.SIFT_create(nfeatures=650).detectAndCompute(gray, None)
    return np.array([p.pt for p in points], np.float32), descriptors


@lru_cache(maxsize=2)
def room_index(catalog_path):
    rooms = json.loads(Path(catalog_path).read_text())['rooms']; base = Path(catalog_path).parent / 'room-references'
    rows = []
    for room in rooms:
        for name in room.get('images', []):
            path = (base / name).resolve()
            if not path.is_relative_to(base.resolve()): continue
            cache = path.with_suffix('.npz')
            if cache.is_file():
                stored = np.load(cache, allow_pickle=False); pts, desc = stored['points'], stored['descriptors']
            elif path.is_file(): pts, desc = sift(pixels(path.read_bytes()))
            else: continue
            if desc is not None and len(desc) >= 10: rows.append((room, name, pts, desc))
    return rows


def compare_room(raw, campus='', building='', scope='all'):
    rooms, _ = room_manifest()
    if scope=='five':rooms=[r for r in rooms if r['id'] in FIVE_ROOMS]
    allowed={r['id'] for r in rooms}
    query = fingerprint(raw)
    distances = [int(np.count_nonzero(query != fp)) for _,_,fp in example_index()]
    example_room = next((r for r in rooms if r['id']=='RWH-IDEA3'),None)
    if example_room and distances and min(distances)<=7 and (not campus or campus=='Busch') and (not building or building=='Richard Weeks Hall'):
        return [dict(**{k: example_room[k] for k in ('id','campus','building','code','room','source_url')},
            evidence=['Matches a supplied example photo. You identified this collection as IDEA3 Lab in Richard Weeks Hall.',
                      'Location comes from your confirmation, not an official Rutgers panorama. Confirm before saving.'],
            method='reviewed-example', needs_confirmation=True)],dict(engine='Reviewed local example lookup',text=[])
    local = native_analysis(raw)
    sign = ' '.join(local.get('text', [])).upper()
    # Require a full known code-and-room token, never a bare number in background text.
    sign_rooms = [r for r in rooms if (not campus or r['campus']==campus) and (not building or r['building']==building) and re.search(r'(?<![A-Z0-9])'+re.escape(r['code'])+r'[\s-]*'+re.escape(r['room'])+r'(?![A-Z0-9])', sign)]
    if len(sign_rooms) == 1:
        return [dict(**{k: sign_rooms[0][k] for k in ('id', 'campus', 'building', 'code', 'room', 'source_url')},
                     evidence=['Full room code and number read locally from the photo.'], method='local-ocr', needs_confirmation=True)], local
    gray=pixels(raw)
    h,w=gray.shape
    query_points, query_desc = sift(gray)
    if query_desc is None or len(query_desc) < 12: return [], local
    ranked = {}
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    for room, view, ref_points, ref_desc in room_index(current_app.config['CLASSROOM_CATALOG']):
        if room['id'] not in allowed:continue
        if campus and room['campus'] != campus: continue
        if building and room['building'] != building: continue
        pairs = matcher.knnMatch(query_desc, ref_desc, k=2)
        good = [a for pair in pairs if len(pair) == 2 for a, b in [pair] if a.distance < .70 * b.distance]
        if len(good) < 50: continue
        a = np.float32([query_points[m.queryIdx] for m in good]); b = np.float32([ref_points[m.trainIdx] for m in good])
        _, mask = cv2.findHomography(a, b, cv2.RANSAC, 5.0)
        if mask is None: continue
        inliers = int(mask.sum()); ratio = inliers / len(good)
        if inliers < 50 or ratio < .6: continue
        pts = a[mask.ravel().astype(bool)]
        spread = cv2.contourArea(cv2.convexHull(pts).astype(np.float32)) / (h * w)
        if spread < .12: continue
        score = inliers * ratio
        if room['id'] not in ranked or score > ranked[room['id']]['score']:
            ranked[room['id']] = dict(**{k: room[k] for k in ('id', 'campus', 'building', 'code', 'room', 'source_url')},
                score=round(score, 2), inliers=inliers, evidence=[f'{inliers} geometrically consistent visual features against a Rutgers reference view.'],
                method='local-reference', reference_view=view, needs_confirmation=True)
    for result in ranked.values():
        if result.get('reference_view')=='RWH-105-supplied.jpg':
            result['evidence'][0]=f'{result["inliers"]} geometrically consistent visual features against the supplied photo reference.'
            result['evidence'].append('This supplied Weeks Hall photo was visually labeled RWH-105 against the official panorama. Confirm the room.')
    candidates = sorted(ranked.values(), key=lambda r: r['score'], reverse=True)
    if len(candidates) > 1 and candidates[0]['score'] < candidates[1]['score'] * 1.5:
        # Similar rooms should not turn a weak ranking into a false identification.
        candidates=[]
    candidates=[r for r in candidates if r['score']>=candidates[0]['score']*.6][:5] if candidates else []
    # The uploaded five-room implementation handles viewpoint changes with DINOv2
    # and one-to-one feature matches checked using a fundamental camera matrix.
    if scope=='five' or not candidates:
        from . import scene_matcher
        selected=[{**r,'images':[name for name in r.get('images',[]) if 'supplied' not in name]}
            for r in rooms if r['id'] in FIVE_ROOMS and (not campus or r['campus']==campus) and (not building or r['building']==building)]
        if selected:
            _,base=room_manifest()
            result=scene_matcher.match_rooms(raw,selected,base,limit=5)
            by_id={r['id']:r for r in selected}
            suggestions=[dict(**{k:by_id[item['room_id']][k] for k in ('id','campus','building','code','room','source_url')},
                evidence=item['evidence']+['Compared with official Rutgers references. Review the room before saving; similarity is not a probability.'],
                method='local-scene' if item['similarity'] is not None else 'local-feature',similarity=item['similarity'],
                inliers=item['matches'],needs_confirmation=True) for item in result]
            candidates=suggestions+[r for r in candidates if r['id'] not in {s['id'] for s in suggestions}]
    return candidates[:5], local


@bp.post('/api/vision/rooms')
@login_required
def recognize_room():
    rate_limit('local-room', 50)
    raw = photo_input()
    scope=request.form.get('scope','all')
    if scope not in ('all','five'):raise BadRequest('scope must be all or five')
    candidates, local = compare_room(raw, request.form.get('campus', ''), request.form.get('building', ''),scope)
    return jsonify(mode='local', candidates=candidates, visible_sign_text=' '.join(local.get('text', [])), needs_confirmation=True,
        message='Possible room from local comparison; confirm before saving.' if candidates else 'No reliable reference match. Choose the building and room manually.',
        scope='Five lecture halls' if scope=='five' else 'Installed Rutgers room views and labeled examples',
        model='DINOv2-small and OpenCV' if scope=='five' else 'Local reference comparison',room_options=list(FIVE_ROOMS))


@bp.get('/api/classrooms/<room_id>/reference-photo')
@login_required
def reference_photo(room_id):
    rooms, base = room_manifest()
    room = next((r for r in rooms if r['id'] == room_id), None)
    if not room or not room.get('images'): raise NotFound('Reference photo not found')
    return send_file(base / room['images'][0], mimetype='image/jpeg')


@bp.get('/api/vision/room-examples')
@login_required
def room_examples():
    from .demo import guard
    guard()
    examples=[dict(id=name[:-4],title='IDEA3 Lab · user-confirmed',url='/examples/'+name) for item in ITEMS for name in item['files']]
    if (ROOT.parent/'public/examples/Weeks-lecture.jpg').is_file():
        examples.insert(0,dict(id='Weeks-lecture',title='Weeks Hall lecture room · RWH-105 reference',url='/examples/Weeks-lecture.jpg'))
    return jsonify(examples=examples)
