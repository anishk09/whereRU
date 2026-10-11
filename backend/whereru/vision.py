"""On-device computer vision used when AI_MODE=local.

No API key, no network, no cost. Two features:

1. match_rooms(): identifies which catalog classroom a photo was taken in by matching
   SIFT keypoints against labeled reference photos, then keeping only matches that agree
   on one camera geometry (RANSAC on the fundamental matrix). The score is the number of
   geometrically verified feature matches, so it reflects real visual evidence rather than
   an invented confidence value.
2. dominant_color(): names the main color of the object in the center of an item photo.
"""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

MAX_SIDE = 1000
MIN_INLIERS = 18          # below this, a room is not reported as a match
RATIO = 0.75              # Lowe ratio test


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


def reference_features(path):
    path = Path(path)
    return _reference_features(str(path), path.stat().st_mtime)


def verified_matches(query, reference):
    q_points, q_desc = query
    r_points, r_desc = reference
    if q_desc is None or r_desc is None or len(q_desc) < 8 or len(r_desc) < 8:
        return 0
    matcher = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 64})
    pairs = matcher.knnMatch(q_desc, r_desc, k=2)
    good = [m for m, *rest in pairs if rest and m.distance < RATIO * rest[0].distance]
    # One-to-one: repetitive textures make many query points land on the same reference
    # point. Keep only the closest match per reference feature.
    best_per_train = {}
    for m in good:
        if m.trainIdx not in best_per_train or m.distance < best_per_train[m.trainIdx].distance:
            best_per_train[m.trainIdx] = m
    good = list(best_per_train.values())
    if len(good) < 8:
        return 0
    src = q_points[[m.queryIdx for m in good]]
    dst = r_points[[m.trainIdx for m in good]]
    # Rooms are 3D scenes, so check consistency with one camera pose (fundamental matrix),
    # not a flat homography.
    fundamental, mask = cv2.findFundamentalMat(src, dst, cv2.FM_RANSAC, 3.0, 0.99)
    if fundamental is None or fundamental.shape != (3, 3) or mask is None:
        return 0
    return int(np.count_nonzero(mask.ravel() == 1))


def match_rooms(query_raw, rooms, base, limit=3):
    """Rank catalog rooms by verified feature matches against their reference photos.

    rooms: catalog entries with an `images` list of paths relative to `base`.
    Returns [{room_id, matches}] for rooms at or above MIN_INLIERS, best first.
    """
    query = features_from_bytes(query_raw)
    base = Path(base).resolve()
    scored = []
    for room in rooms:
        best = 0
        for name in room.get('images', []):
            path = (base / name).resolve()
            if not path.is_relative_to(base) or not path.is_file():
                continue
            best = max(best, verified_matches(query, reference_features(path)))
        if best >= MIN_INLIERS:
            scored.append({'room_id': room['id'], 'matches': best})
    scored.sort(key=lambda item: item['matches'], reverse=True)
    return scored[:limit]


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
