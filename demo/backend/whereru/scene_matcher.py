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
MIN_INLIERS = 30          # below this, feature matching does not report a room
RATIO = 0.75              # Lowe ratio test
# Scene similarity (cosine of DINOv2 embeddings, best reference view per room).
# Calibrated 2026-10-11: unrelated lecture halls score 0.57-0.70, a Weeks 105 photo scored 0.79
# for Weeks 105 with a 0.09 lead.
MIN_SIMILARITY = float(os.getenv('ROOM_MIN_SIMILARITY', '0.70'))
MIN_MARGIN = float(os.getenv('ROOM_MIN_MARGIN', '0.06'))   # lead over the next-best room


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
    path=Path(path_str);cache=path.with_suffix('.geometry.npz')
    if cache.is_file():
        with np.load(cache,allow_pickle=False) as saved:
            if float(saved['mtime'])==mtime:return saved['points'],saved['descriptors']
    image = cv2.imread(path_str, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f'Unreadable reference image: {path_str}')
    points,descriptors=_features(_prepare(image))
    if descriptors is not None:
        temporary=cache.with_suffix('.tmp')
        with temporary.open('wb') as file:np.savez_compressed(file,points=points,descriptors=descriptors,mtime=mtime)
        temporary.replace(cache)
    return points,descriptors


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
    valid=mask.ravel()==1
    if valid.sum()<MIN_INLIERS:return 0
    # Reject feature clusters on a logo/slide/tiny repeated patch.
    pts=src[valid]
    extent=np.ptp(index.points,axis=0)
    if cv2.contourArea(cv2.convexHull(pts).astype(np.float32))/max(float(extent[0]*extent[1]),1)<.12:return 0
    return int(np.count_nonzero(valid))


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
                torch.set_num_threads(min(4, max(1, (os.cpu_count() or 2) - 1)))
                assets = Path(__file__).resolve().parents[1] / '.tools'
                source, weights = assets / 'dinov2', assets / 'dinov2_vits14_pretrain.pth'
                if not (source / 'hubconf.py').is_file() or not weights.is_file():
                    raise FileNotFoundError('Run tools/prepare_scene_model.py once before using the scene model')
                # Inference only reads installed files. No Hub/network downloads during scans.
                _model = torch.hub.load(str(source), 'dinov2_vits14', source='local', pretrained=False).eval()
                _model.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True))
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
    path = Path(path_str)
    cache = path.with_suffix('.scene.npz')
    if cache.is_file():
        with np.load(cache, allow_pickle=False) as saved:
            if float(saved['mtime']) == mtime:
                return saved['vector']
    image = cv2.imread(path_str, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'Unreadable reference image: {path_str}')
    vector = _embed_bgr(image)
    temporary = cache.with_suffix('.tmp')
    with temporary.open('wb') as file:
        np.savez_compressed(file, vector=vector, mtime=mtime)
    temporary.replace(cache)
    return vector


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


def score_rooms(query_raw, rooms, base):
    """Both signals for every room: {room_id: {'matches': int, 'similarity': float|None, 'views': int}}."""
    base = Path(base).resolve()
    index = QueryIndex(features_from_bytes(query_raw))
    query_vec = embed_bytes(query_raw)
    scores = {}
    for room in rooms:
        best_matches, best_sim, views = 0, None, 0
        for path in _room_paths(room, base):
            views += 1
            best_matches = max(best_matches, verified_matches(index, reference_features(path)))
            if query_vec is not None:
                sim = float(query_vec @ reference_embedding(path))
                best_sim = sim if best_sim is None else max(best_sim, sim)
        scores[room['id']] = {'matches': best_matches, 'similarity': best_sim, 'views': views}
    return scores, len(index.points)


def match_rooms(query_raw, rooms, base, limit=5):
    """Rooms the photo was likely taken in, best first.

    Returns [{room_id, matches, similarity, evidence}]. A room is reported when feature matching
    verifies it (>= MIN_INLIERS) or when its scene similarity is at least MIN_SIMILARITY and
    leads the next-best room by MIN_MARGIN. Otherwise the list is empty and the finder uses
    the placard or picks the room.
    """
    started = time.time()
    scores, n_features = score_rooms(query_raw, rooms, base)
    sims = sorted(((v['similarity'], k) for k, v in scores.items() if v['similarity'] is not None), reverse=True)
    accepted = {}
    if sims:
        top_sim, top_id = sims[0]
        runner_up = sims[1][0] if len(sims) > 1 else -1.0
        if top_sim >= MIN_SIMILARITY and top_sim - runner_up >= MIN_MARGIN:
            accepted[top_id] = [f'Overall look of the room matches (similarity {top_sim:.2f}, '
                                f'next closest room {runner_up:.2f})']
    for room_id, value in scores.items():
        if value['matches'] >= MIN_INLIERS:
            accepted.setdefault(room_id, []).insert(0, f"{value['matches']} visual details line up with the reference photos")
    ranked = sorted(accepted, key=lambda r: (scores[r]['matches'] >= MIN_INLIERS, scores[r]['matches'],
                                            scores[r]['similarity'] or 0), reverse=True)
    report = ', '.join(
        f"{k}={v['matches']}" + (f"/{v['similarity']:.2f}" if v['similarity'] is not None else '')
        if v['views'] else f'{k}=no-photos' for k, v in scores.items())
    _log(f"{n_features} photo features; matches/similarity: {report} "
         f"(need {MIN_INLIERS} matches, or similarity {MIN_SIMILARITY} with lead {MIN_MARGIN}); "
         f"picked {ranked or 'none'} in {time.time() - started:.1f}s")
    return [{'room_id': r, 'matches': scores[r]['matches'], 'similarity': scores[r]['similarity'],
             'evidence': accepted[r]} for r in ranked[:limit]]


# Named colors in HSV terms. Hue in OpenCV is 0-179.
_HUES = [(0, 'red'), (10, 'orange'), (22, 'yellow'), (35, 'green'), (85, 'teal'),
         (100, 'blue'), (125, 'purple'), (150, 'pink'), (170, 'red')]


def _color_name(h, s, v):
    if v < 50:
        return 'black'
    if s < 35:
        return 'white' if v > 200 else 'gray'
    name = 'red'
    for start, label in _HUES:
        if h >= start:
            name = label
    if name == 'blue' and v < 110:
        return 'navy'
    return name


def dominant_color(raw):
    """Most common color in the central area of a photo, where the item usually is."""
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    h, w = image.shape[:2]
    center = image[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    small = cv2.resize(center, (64, 64), interpolation=cv2.INTER_AREA)
    pixels = np.float32(small.reshape(-1, 3))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 4, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=4)
    bgr = np.uint8([[centers[int(counts.argmax())]]])
    hue, sat, val = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
    return _color_name(int(hue), int(sat), int(val))
