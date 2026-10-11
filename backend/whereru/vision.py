"""On-device computer vision used when AI_MODE=local.

No API key and no per-request cost. Two features:

1. match_rooms(): identifies which catalog classroom a photo was taken in, using two signals.
   a. Scene similarity (when PyTorch is installed): a pretrained DINOv2 model turns each photo
      into an embedding that captures the room's overall look (seating, walls, screens,
      windows). It tolerates different viewpoints and people in the shot. A room is reported
      only if it is clearly closer than every other room.
   b. Feature matching: SIFT keypoints matched against the reference photos, keeping only
      matches that agree on one camera geometry (RANSAC on the fundamental matrix). Strong
      evidence when the photo is taken from near a reference viewpoint.
2. dominant_color(): names the main color of the object in the center of an item photo.
"""
import os
import sys
import threading
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

MAX_SIDE = 1000
MIN_INLIERS = 18          # below this, feature matching does not report a room
# Feature matching must single out one room: every DCS reference panorama shows the same DCS
# slide on its projector, so a photo of that slide gets 30-70 matches in every room.
FEATURE_LEAD = 2.0        # best room needs at least this many times the next room's matches
RATIO = 0.75              # Lowe ratio test
# Scene similarity (cosine of DINOv2 embeddings, best reference view per room).
# Calibrated 2026-10-11: unrelated lecture halls score 0.57-0.70, a Weeks 105 photo scored 0.79
# for Weeks 105 with a 0.09 lead.
MIN_SIMILARITY = float(os.getenv('ROOM_MIN_SIMILARITY', '0.70'))
MIN_MARGIN = float(os.getenv('ROOM_MIN_MARGIN', '0.06'))      # below this lead: no match
CLEAR_MARGIN = float(os.getenv('ROOM_CLEAR_MARGIN', '0.10'))  # at or above: one confident match
# Between MIN_MARGIN and CLEAR_MARGIN the top two rooms are shown as possible matches.
# Stress test 2026-10-11 (236 photos, 5 rooms + 24 decoy rooms): look-alike rooms (Physics vs
# SEC, ARC vs Lucy Stone) lead by up to ~0.08, so a single confident pick needs 0.10. That cut
# confident wrong answers from 5-9% to about 1%.


def _prepare(gray):
    h, w = gray.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    # Even out lighting differences between the reference shot and the user's photo.
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def _features(gray):
    sift = cv2.SIFT_create(nfeatures=2500)
    keypoints, descriptors = sift.detectAndCompute(gray, None)
    points = np.float32([k.pt for k in keypoints]) if keypoints else np.empty((0, 2), np.float32)
    return points, descriptors


def features_from_bytes(raw):
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('Unreadable image')
    return _features(_prepare(image))


@lru_cache(maxsize=512)
def _reference_features(path_str, mtime):
    image = cv2.imread(path_str, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f'Unreadable reference image: {path_str}')
    return _features(_prepare(image))


_path_locks = defaultdict(threading.Lock)
_path_locks_guard = threading.Lock()


def reference_features(path):
    path = Path(path)
    # The startup warm-up thread and a scan request can ask for the same file at once.
    # The lock makes the second caller wait for the first result instead of redoing it.
    with _path_locks_guard:
        lock = _path_locks[str(path)]
    with lock:
        return _reference_features(str(path), path.stat().st_mtime)


class QueryIndex:
    """FLANN index over the user's photo, built once and reused for every reference view."""

    def __init__(self, query):
        self.points, descriptors = query
        self.ready = descriptors is not None and len(descriptors) >= 8
        if self.ready:
            self.matcher = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 48})
            self.matcher.add([descriptors])
            self.matcher.train()


def verified_matches(index, reference):
    r_points, r_desc = reference
    if not index.ready or r_desc is None or len(r_desc) < 8:
        return 0
    pairs = index.matcher.knnMatch(r_desc, k=2)
    good = [m for m, *rest in pairs if rest and m.distance < RATIO * rest[0].distance]
    # One-to-one: repetitive textures make many reference points land on the same photo
    # point. Keep only the closest match per photo feature.
    best_per_query = {}
    for m in good:
        if m.trainIdx not in best_per_query or m.distance < best_per_query[m.trainIdx].distance:
            best_per_query[m.trainIdx] = m
    good = list(best_per_query.values())
    if len(good) < 8:
        return 0
    src = index.points[[m.trainIdx for m in good]]
    dst = r_points[[m.queryIdx for m in good]]
    # Rooms are 3D scenes, so check consistency with one camera pose (fundamental matrix),
    # not a flat homography.
    fundamental, mask = cv2.findFundamentalMat(src, dst, cv2.FM_RANSAC, 3.0, 0.99)
    if fundamental is None or fundamental.shape != (3, 3) or mask is None:
        return 0
    return int(np.count_nonzero(mask.ravel() == 1))


# ---------------------------------------------------------------- scene similarity

_model = None
_model_state = 'unloaded'      # unloaded | ready | unavailable
_model_lock = threading.Lock()
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _log(message):
    print(f'[room scan] {message}', file=sys.stderr, flush=True)


def scene_model():
    """DINOv2-small via torch.hub, or None when PyTorch isn't installed or the download fails."""
    global _model, _model_state
    with _model_lock:
        if _model_state == 'unloaded':
            try:
                import warnings
                import torch
                warnings.filterwarnings('ignore', message='xFormers is not available')
                torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
                _model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14', verbose=False).eval()
                _model_state = 'ready'
                _log('scene model ready (DINOv2-small)')
            except Exception as error:  # ImportError, no network on first run, etc.
                _model_state = 'unavailable'
                _log(f'scene model unavailable, using feature matching only ({type(error).__name__}: {error})')
        return _model


def _embed_bgr(image):
    import torch
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    scale = 224 / min(h, w)
    # Keep the whole frame (no center crop) so wide shots keep their walls and windows.
    nh = max(14, round(h * scale / 14) * 14)
    nw = min(448, max(14, round(w * scale / 14) * 14))
    rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    tensor = torch.from_numpy(((rgb - _MEAN) / _STD).transpose(2, 0, 1)).unsqueeze(0)
    with _model_lock, torch.inference_mode():
        out = _model.forward_features(tensor)
    # Overall look = class token plus the average of the patch tokens.
    vector = torch.cat([out['x_norm_clstoken'], out['x_norm_patchtokens'].mean(1)], dim=1)[0].numpy()
    return vector / (np.linalg.norm(vector) + 1e-8)


def embed_bytes(raw):
    if scene_model() is None:
        return None
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Unreadable image')
    return _embed_bgr(image)


@lru_cache(maxsize=1024)
def _reference_embedding(path_str, mtime):
    image = cv2.imread(path_str, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'Unreadable reference image: {path_str}')
    return _embed_bgr(image)


def reference_embedding(path):
    if scene_model() is None:
        return None
    path = Path(path)
    with _path_locks_guard:
        lock = _path_locks['emb:' + str(path)]
    with lock:
        return _reference_embedding(str(path), path.stat().st_mtime)


def warm_cache(rooms, base):
    """Precompute reference features so the first scan isn't slow. Safe to run in a thread."""
    base = Path(base).resolve()
    warm_clip()
    if clip_model() is None:
        warm_items(base)
    for room in rooms:
        for name in room.get('images', []):
            path = (base / name).resolve()
            if path.is_relative_to(base) and path.is_file():
                try:
                    reference_features(path)
                    reference_embedding(path)
                except ValueError:
                    pass


def _room_paths(room, base):
    for name in room.get('images', []):
        path = (base / name).resolve()
        if path.is_relative_to(base) and path.is_file():
            yield path


SHORTLIST = 4   # with the scene model, detail matching only runs on the closest rooms


def score_rooms(query_raw, rooms, base):
    """Both signals per room: {room_id: {'matches': int, 'similarity': float|None, 'views': int}}.

    With the scene model, every room gets a similarity (fast: one dot product per view) and the
    slower detail matching runs only on the SHORTLIST most similar rooms, so scans stay quick as
    the catalog grows. Without the model, detail matching runs on every room.
    """
    base = Path(base).resolve()
    paths = {room['id']: list(_room_paths(room, base)) for room in rooms}
    query_vec = embed_bytes(query_raw)
    scores = {rid: {'matches': 0, 'similarity': None, 'views': len(p)} for rid, p in paths.items()}
    if query_vec is not None:
        for rid, room_paths in paths.items():
            if room_paths:
                scores[rid]['similarity'] = max(float(query_vec @ reference_embedding(p)) for p in room_paths)
        ranked = sorted((rid for rid in paths if scores[rid]['similarity'] is not None),
                        key=lambda rid: scores[rid]['similarity'], reverse=True)
        to_match = ranked[:SHORTLIST]
    else:
        to_match = [rid for rid, p in paths.items() if p]
    index = QueryIndex(features_from_bytes(query_raw))
    for rid in to_match:
        scores[rid]['matches'] = max(verified_matches(index, reference_features(p)) for p in paths[rid])
    return {rid: v for rid, v in scores.items() if v['views']}, len(index.points)


def match_rooms(query_raw, rooms, base, limit=3):
    """Rooms the photo was likely taken in, best first.

    Always compares against every room passed in, so a room only wins if it is clearly closer
    than all the others. Returns [{room_id, matches, similarity, evidence}]:
    - feature matching picks a room with >= MIN_INLIERS verified matches and FEATURE_LEAD times
      the next room's count;
    - scene similarity picks a room with similarity >= MIN_SIMILARITY that leads the next room
      by MIN_MARGIN.
    Usually both agree and one room is returned. An empty list means "couldn't match", and the
    finder scans the placard or picks the room.
    """
    started = time.time()
    scores, n_features = score_rooms(query_raw, rooms, base)
    accepted = {}

    sims = sorted(((v['similarity'], k) for k, v in scores.items() if v['similarity'] is not None), reverse=True)
    confident = False
    if sims:
        top_sim, top_id = sims[0]
        runner_up, runner_id = sims[1] if len(sims) > 1 else (-1.0, None)
        lead = top_sim - runner_up
        if top_sim >= MIN_SIMILARITY and lead >= CLEAR_MARGIN:
            confident = True
            accepted[top_id] = [f'Overall look of the room matches (similarity {top_sim:.2f}, '
                                f'next closest room {runner_up:.2f})']
        elif top_sim >= MIN_SIMILARITY and lead >= MIN_MARGIN and runner_id:
            # Close call: offer both and let the finder pick.
            accepted[top_id] = [f'Looks most like this room (similarity {top_sim:.2f})']
            accepted[runner_id] = [f'Also looks similar (similarity {runner_up:.2f})']

    feats = sorted(((v['matches'], k) for k, v in scores.items()), reverse=True)
    if feats:
        top_matches, top_id = feats[0]
        second = feats[1][0] if len(feats) > 1 else 0
        if top_matches >= MIN_INLIERS and top_matches >= FEATURE_LEAD * max(second, 1):
            accepted.setdefault(top_id, []).insert(0, f'{top_matches} visual details line up with the reference photos')
            confident = True
            # Detail matching is decisive (no false alarms in the stress test): drop close-call extras.
            accepted = {top_id: accepted[top_id]}

    ranked = sorted(accepted, key=lambda r: (len(accepted[r]), scores[r]['matches'], scores[r]['similarity'] or 0), reverse=True)
    report = ', '.join(
        f"{k}={v['matches']}" + (f"/{v['similarity']:.2f}" if v['similarity'] is not None else '')
        if v['views'] else f'{k}=no-photos' for k, v in scores.items())
    _log(f"{n_features} photo features; matches/similarity: {report}; picked {ranked or 'none'} "
         f"in {time.time() - started:.1f}s")
    return [{'room_id': r, 'matches': scores[r]['matches'], 'similarity': scores[r]['similarity'],
             'evidence': accepted[r], 'confident': confident} for r in ranked[:limit]]


# ---------------------------------------------------------------- item recognition

# Labeled examples: data/items (synthetic "campus_lost_items" set, 11 classes, RUID first).
ITEM_MIN_SIMILARITY = float(os.getenv('ITEM_MIN_SIMILARITY', '0.35'))
ITEM_MIN_MARGIN = float(os.getenv('ITEM_MIN_MARGIN', '0.02'))

# class -> (title shown to the finder, backend category, priority, always private)
ITEM_CLASSES = {
    'ruid': ('Rutgers ID card (RUID)', 'id_card', 'P1-critical', True),
    'wallet': ('Wallet', 'wallet', 'P1', True),
    'phone': ('Phone', 'electronics', 'P1', True),
    'keys': ('Keys', 'keys', 'P1', True),
    'laptop': ('Laptop', 'electronics', 'P1', True),
    'other_id_card': ('ID card', 'id_card', 'P2', True),
    'eyeglasses': ('Glasses', 'other', 'P2', False),
    'earbuds': ('Earbuds', 'electronics', 'P2', False),
    'headphones': ('Headphones', 'electronics', 'P2', False),
    'backpack': ('Backpack', 'bag', 'P2', False),
    'calculator': ('Calculator', 'electronics', 'P2', False),
    'charger': ('Charger', 'electronics', 'P3', False),
    'jacket': ('Jacket', 'clothing', 'P2', False),
    'hat': ('Hat', 'clothing', 'P3', False),
    'notebook': ('Notebook', 'other', 'P3', False),
    'water_bottle': ('Water bottle', 'bottle', 'P3', False),
    'umbrella': ('Umbrella', 'other', 'P3', False),
}

# Text descriptions for zero-shot recognition (CLIP). Several phrasings per class are averaged.
ITEM_PROMPTS = {
    'ruid': ['a Rutgers University student ID card', 'a college ID card with a red header and a photo of a person',
             'a red and white university ID badge on a lanyard'],
    'wallet': ['a wallet', 'a leather bifold wallet', 'a small card holder wallet', 'a zip-around clutch wallet',
               'a small coin purse', 'a wristlet wallet with a strap'],
    'phone': ['a smartphone', 'a mobile phone in a case', 'an iPhone lying on a table'],
    'keys': ['a set of keys', 'keys on a key ring', 'a car key fob with keys'],
    'laptop': ['a laptop computer', 'a closed laptop', 'a MacBook'],
    'other_id_card': ["a driver's license", 'a plastic ID card', 'an employee badge'],
    'eyeglasses': ['a pair of eyeglasses', 'sunglasses', 'reading glasses'],
    'earbuds': ['wireless earbuds in a charging case', 'AirPods case', 'a pair of earbuds'],
    'headphones': ['over-ear headphones', 'a headset', 'a pair of headphones'],
    'backpack': ['a backpack', 'a school bag', 'a tote bag', 'a drawstring gym bag', 'a crossbody sling bag'],
    'calculator': ['a calculator', 'a graphing calculator'],
    'charger': ['a phone charger with a cable', 'a laptop charger', 'a USB cable'],
    'jacket': ['a jacket', 'a hoodie', 'a sweatshirt'],
    'hat': ['a baseball cap', 'a beanie hat'],
    'notebook': ['a notebook', 'a textbook', 'a binder'],
    'water_bottle': ['a water bottle', 'an insulated metal water bottle', 'a plastic drink bottle', 'a tumbler cup',
                     'a sports squeeze bottle', 'a large water jug with a handle'],
    'umbrella': ['an umbrella', 'a folded umbrella'],
}
# Photos with no clear item (empty desk, classroom, blurry) should not get a guess.
BACKGROUND_PROMPTS = ['an empty table', 'a classroom', 'a room with chairs', 'a blurry photo', 'a floor']
ITEM_COLORS = ['black', 'white', 'gray', 'silver', 'red', 'pink', 'orange', 'yellow', 'gold', 'green',
               'blue', 'navy', 'purple', 'brown', 'beige', 'clear']
CLIP_MIN_PROBABILITY = float(os.getenv('CLIP_MIN_PROBABILITY', '0.45'))
CLIP_MIN_COLOR = float(os.getenv('CLIP_MIN_COLOR', '0.30'))


def _center_crop(image, keep=0.8):
    h, w = image.shape[:2]
    dh, dw = int(h * (1 - keep) / 2), int(w * (1 - keep) / 2)
    return image[dh:h - dh, dw:w - dw]


@lru_cache(maxsize=1)
def item_references(base):
    """[(class, path, (x0, y0, x1, y1))] from data/items/annotations.csv."""
    import csv
    root = Path(base) / 'items'
    refs = []
    try:
        with open(root / 'annotations.csv', newline='') as f:
            for row in csv.DictReader(f):
                if row['class_name'] in ITEM_CLASSES and (root / row['file']).is_file():
                    box = tuple(int(float(row[k])) for k in ('bbox_x0', 'bbox_y0', 'bbox_x1', 'bbox_y1'))
                    refs.append((row['class_name'], str(root / row['file']), box))
    except OSError:
        pass
    return tuple(refs)


@lru_cache(maxsize=256)
def _item_embedding(path_str, box):
    image = cv2.imread(path_str, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'Unreadable item image: {path_str}')
    x0, y0, x1, y1 = box
    pad = int(0.12 * max(x1 - x0, y1 - y0))   # keep a little of the surface, like a real photo
    h, w = image.shape[:2]
    crop = image[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]
    return _embed_bgr(crop if crop.size else image)


def warm_items(base):
    if scene_model() is None:
        return
    for _, path, box in item_references(str(base)):
        try:
            _item_embedding(path, box)
        except ValueError:
            pass


def _variant(path):
    """'ruid_v3_r2.jpg' -> 'v3'. RUID has 5 renders per variant, other classes 1."""
    return Path(path).stem.split('_v')[-1].split('_')[0]


def _variant_prototypes(refs):
    """{(class, variant): unit vector}: the average of a variant's renders, so every variant
    counts once whether it has 1 photo or 5 (RUID)."""
    groups = {}
    for cls, path, box in refs:
        groups.setdefault((cls, _variant(path)), []).append(_item_embedding(path, box))
    protos = {}
    for key, vectors in groups.items():
        mean = np.mean(vectors, axis=0)
        protos[key] = mean / (np.linalg.norm(mean) + 1e-8)
    return protos


def _score_classes(query, refs, skip=None):
    """[(score, class)] best first: a class scores the mean of its 3 most similar variants."""
    by_class = {}
    for (cls, variant), proto in _variant_prototypes(refs).items():
        if (cls, variant) != skip:
            by_class.setdefault(cls, []).append(float(query @ proto))
    return sorted(((float(np.mean(sorted(v, reverse=True)[:3])), c) for c, v in by_class.items()), reverse=True)


def classify_item_dataset(raw, base):
    """Fallback: nearest classes in the campus lost-items set (DINOv2). None if unavailable.

    Each class scores the mean of its 3 most similar variants. Returns
    {class, title, category, priority, sensitive, similarity, lead, confident, runner_up}.
    """
    if scene_model() is None:
        return None
    refs = item_references(str(base))
    if not refs:
        return None
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Unreadable image')
    query = _embed_bgr(_center_crop(image))
    scored = _score_classes(query, refs)
    (top, cls), (second, runner) = scored[0], scored[1]
    title, category, priority, sensitive = ITEM_CLASSES[cls]
    result = {'class': cls, 'title': title, 'category': category, 'priority': priority,
              'sensitive': sensitive, 'similarity': top, 'lead': top - second,
              'runner_up': runner, 'confident': top >= ITEM_MIN_SIMILARITY and top - second >= ITEM_MIN_MARGIN}
    _log(f"item: {cls} {top:.2f} (next {runner} {second:.2f}) -> {'suggested' if result['confident'] else 'not sure'}")
    return result


_clip = None
_clip_state = 'unloaded'
_clip_lock = threading.Lock()
_clip_text = {}


def clip_model():
    """(model, preprocess, tokenizer) for OpenAI CLIP ViT-B/32 via open_clip, or None."""
    global _clip, _clip_state
    with _clip_lock:
        if _clip_state == 'unloaded':
            try:
                import open_clip
                import torch  # noqa: F401
                model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32-quickgelu', pretrained='openai')
                _clip = (model.eval(), preprocess, open_clip.get_tokenizer('ViT-B-32-quickgelu'))
                _clip_state = 'ready'
                _log('item model ready (CLIP ViT-B/32)')
            except Exception as error:
                _clip_state = 'unavailable'
                _log(f'item model unavailable, using the lost-items set instead ({type(error).__name__}: {error})')
        return _clip


def _clip_text_features(key, prompts):
    """Unit text embeddings, cached; one row per prompt."""
    if key not in _clip_text:
        import torch
        model, _, tokenizer = _clip
        with _clip_lock, torch.inference_mode():
            feats = model.encode_text(tokenizer(prompts)).float()
        _clip_text[key] = (feats / feats.norm(dim=-1, keepdim=True)).numpy()
    return _clip_text[key]


def _class_matrix():
    names = list(ITEM_PROMPTS) + ['_background']
    rows = []
    for name in names:
        prompts = BACKGROUND_PROMPTS if name == '_background' else ITEM_PROMPTS[name]
        mean = _clip_text_features('cls:' + name, [f'a photo of {p}' if not p.startswith('a photo') else p for p in prompts]).mean(0)
        rows.append(mean / np.linalg.norm(mean))
    return names, np.stack(rows)


def warm_clip():
    if clip_model() is not None:
        _class_matrix()


def _softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()


def classify_item(raw, base):
    """What the found item is, and its color.

    Uses CLIP zero-shot (text descriptions of each class; works on real photos without training).
    Falls back to the campus lost-items set (DINOv2) when CLIP isn't installed. Returns
    {class, title, category, priority, sensitive, similarity, lead, runner_up, confident, color?}
    or None when no model is available.
    """
    if clip_model() is None:
        return classify_item_dataset(raw, base)
    import torch
    from PIL import Image
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Unreadable image')
    model, preprocess, _ = _clip
    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    with _clip_lock, torch.inference_mode():
        feat = model.encode_image(preprocess(pil).unsqueeze(0)).float()[0].numpy()
    feat /= np.linalg.norm(feat)
    names, matrix = _class_matrix()
    probs = _softmax(100.0 * matrix @ feat)
    order = np.argsort(-probs)
    top, second = names[order[0]], names[order[1]]
    p_top, p_second = float(probs[order[0]]), float(probs[order[1]])
    if top == '_background':
        _log(f'item: no clear item (background {p_top:.2f}, next {second} {p_second:.2f})')
        return {'class': None, 'confident': False, 'similarity': p_top, 'lead': p_top - p_second,
                'runner_up': second, 'title': '', 'category': 'other', 'priority': 'P3', 'sensitive': False}
    # Color of the item itself: "a black water bottle" vs "a red water bottle", not the background.
    noun = ITEM_PROMPTS[top][0].removeprefix('a ').removeprefix('an ')
    color_feats = _clip_text_features('color:' + top, [f'a photo of a {c} {noun}' for c in ITEM_COLORS])
    color_probs = _softmax(100.0 * color_feats @ feat)
    color = ITEM_COLORS[int(color_probs.argmax())] if color_probs.max() >= CLIP_MIN_COLOR else None
    title, category, priority, sensitive = ITEM_CLASSES[top]
    confident = p_top >= CLIP_MIN_PROBABILITY
    _log(f"item: {top} {p_top:.2f} (next {second} {p_second:.2f}), color {color or '?'} "
         f"{color_probs.max():.2f} -> {'suggested' if confident else 'not sure'}")
    return {'class': top, 'title': title, 'category': category, 'priority': priority, 'sensitive': sensitive,
            'similarity': p_top, 'lead': p_top - p_second, 'runner_up': second, 'confident': confident,
            'color': color}


# ---------------------------------------------------------------- reading ID cards

# Words printed on every card; never part of a name.
CARD_WORDS = {'RUTGERS', 'STUDENT', 'FACULTY', 'STAFF', 'UNIVERSITY', 'STATE', 'NEW', 'JERSEY', 'THE', 'OF',
              'ID', 'CARD', 'NJ', 'AFFILIATE', 'EMPLOYEE', 'VISITOR', 'LICENSE', 'DRIVER', 'CLASS', 'EXP'}


def _ocr_apple(raw):
    """macOS Vision framework text recognition (pip install pyobjc-framework-Vision)."""
    import Vision
    from Foundation import NSData
    data = NSData.dataWithBytes_length_(raw, len(raw))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)
    ok, _ = handler.performRequests_error_([request], None)
    if not ok:
        return []
    return [str(obs.topCandidates_(1)[0].string()) for obs in (request.results() or [])]


def _ocr_tesseract(raw):
    """Tesseract CLI, trying a few rotations because cards are often photographed tilted."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which('tesseract'):
        raise RuntimeError('tesseract not installed')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    scale = 1500 / max(image.shape)
    image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    image = cv2.createCLAHE(2.0, (8, 8)).apply(image)
    best, best_score = [], -1
    h, w = image.shape
    for angle in (0, -15, 15, -30, 30):
        rotated = cv2.warpAffine(image, cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0), (w, h),
                                 borderMode=cv2.BORDER_REPLICATE)
        with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
            cv2.imwrite(tmp.name, rotated)
            out = subprocess.run(['tesseract', tmp.name, '-', '--psm', '11'], capture_output=True,
                                 text=True, timeout=20).stdout
        lines = [line for line in out.splitlines() if line.strip()]
        # Rotated attempts tend to produce letter fragments; count only solid words.
        score = sum(len(word) >= 3 for word in card_words(lines))
        if score > best_score:
            best, best_score = lines, score
        if score >= 2:
            break   # first angle that reads a plausible name wins
    return best


def read_card_text(raw):
    """Text lines on an ID card photo, or None if no OCR engine is available."""
    for engine in (_ocr_apple, _ocr_tesseract):
        try:
            return engine(raw)
        except Exception:
            continue
    return None


def card_words(lines):
    """Upper-case name-like words: letters only (hyphen/apostrophe allowed), 2+ letters, not card text.
    ID numbers and anything with digits are dropped and never stored."""
    import re
    words = []
    for line in lines or []:
        for token in re.findall(r"[A-Za-z][A-Za-z'\-]+", line):
            word = token.upper().strip("'-")
            near_card_word = len(word) >= 5 and any(_close(word, c) for c in CARD_WORDS if len(c) >= 5)
            if len(word) >= 2 and word not in CARD_WORDS and not near_card_word and word not in words:
                words.append(word)
    return words[:20]


def name_on_card(words):
    """Best guess at the printed name: the first two solid name-like words (cards print FIRST then LAST)."""
    solid = [w for w in words if len(w) >= 3]
    return ' '.join(w.capitalize() for w in solid[:2]) if len(solid) >= 2 else None


def _close(a, b):
    """Exact match, or one letter off for longer names (OCR slips like OSEI/OSFI)."""
    if a == b:
        return True
    if len(a) < 5 or abs(len(a) - len(b)) > 1:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 1


def name_matches(words, full_name):
    """True if both the first and the last name of full_name appear among the card words."""
    parts = [p.upper() for p in str(full_name).replace('-', ' ').split() if len(p) >= 2]
    if len(parts) < 2:
        return False
    first, last = parts[0], parts[-1]
    return any(_close(first, w) for w in words) and any(_close(last, w) for w in words)


# Named colors in HSV terms. Hue in OpenCV is 0-179.
_HUES = [(0, 'red'), (10, 'orange'), (22, 'yellow'), (35, 'green'), (85, 'teal'),
         (100, 'blue'), (125, 'purple'), (150, 'pink'), (170, 'red')]


def _color_name(h, s, v):
    # Dark pixels pick up a tint from lighting; call them black unless clearly colored.
    if v < 60 or (v < 100 and s < 110):
        return 'black'
    if s < 40:
        return 'white' if v > 200 else 'gray'
    name = 'red'
    for start, label in _HUES:
        if h >= start:
            name = label
    if name in ('orange', 'red') and v < 160 and s < 210 and h < 25:
        return 'brown'
    if name == 'blue' and v < 110:
        return 'navy'
    return name


def dominant_color(raw):
    """Main color of the object in the middle of a photo (fallback when CLIP isn't installed).

    Clusters the colors, then picks the cluster that is common in the center but rare along the
    edges, so a table or chairs behind a narrow item don't win.
    """
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    small = cv2.resize(image, (96, 96), interpolation=cv2.INTER_AREA)
    pixels = np.float32(small.reshape(-1, 3))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 5, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(96, 96)
    yy, xx = np.mgrid[0:96, 0:96]
    dist = np.hypot(yy - 47.5, xx - 47.5) / 47.5
    center = labels[dist < 0.35]
    border = labels[dist > 0.85]
    scores = [np.mean(center == k) - 0.7 * np.mean(border == k) for k in range(5)]
    bgr = np.uint8([[centers[int(np.argmax(scores))]]])
    hue, sat, val = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
    return _color_name(int(hue), int(sat), int(val))
