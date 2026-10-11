"""Stress test room recognition: how often it picks the right room, and how often it is fooled.

Usage (from backend/, venv active, after tools/import_dcs.py):
    python tools/stress_rooms.py --fetch     # first time: download decoy rooms (~25 panoramas)
    python tools/stress_rooms.py             # full run (about 25 minutes with 29 rooms)
    python tools/stress_rooms.py --quick     # smaller run (about 8 minutes)

Test photos are rendered from DCS 360° panoramas at angles, zooms and tilts the reference views
don't use, then roughened up: people in the way, dim or warm lighting, blur, low resolution,
tilted phone, portrait framing.

- Known rooms: photos of the 5 catalog rooms. The app should name the right room.
- Unknown rooms: photos of other Rutgers lecture halls (decoys). The app should say no match.
- Leave-one-out: photos of a catalog room scanned as if that room were missing from the app.
  This is the "a random classroom the app doesn't know" case, tested for every room.
- Hard viewpoint: known-room photos compared without the reference views facing the same way,
  closer to a finder standing somewhere other than where the panorama was shot.

Caveat: test photos come from the same spot as the panorama, so "known rooms" is optimistic. Real
photos from other seats behave more like "hard viewpoint".

Writes data/stress/results.json (raw scores) and prints a summary with a threshold sweep.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from whereru import vision  # noqa: E402
from whereru.ai import with_photos_on_disk  # noqa: E402
from import_dcs import download, perspective_view  # noqa: E402

DATA = ROOT / 'data'
STRESS = DATA / 'stress'
# Large DCS rooms that are not in the catalog (from the DCS classroom list, 2026-10-11).
DECOYS = ['ABE-2225', 'ABE-2400', 'ABE-4225', 'ABW-2125', 'ABW-2160', 'ARH-200', 'BE-100', 'BME-102',
          'CCB-1303', 'CDL-102', 'COR-101', 'EN-B120', 'FBO-108', 'FSW-105', 'HCK-101', 'HCK-138',
          'HLL-114', 'HLL-116', 'KLG-010', 'LOR-022', 'LSH-A142', 'MI-100', 'PH-111', 'RAB-001']
VARIANTS = ['clean', 'crowd', 'dim', 'warm', 'blur_lowres', 'tilt', 'portrait']


def fetch():
    for code in DECOYS:
        target = STRESS / code / 'pano.jpg'
        if target.exists():
            continue
        try:
            pano = download(code)
        except Exception as error:
            print(f'  {code}: skipped ({error})')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(target), pano, [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(f'  {code}: saved')
        time.sleep(1)


def roughen(view, variant, rng):
    img = view.copy()
    h, w = img.shape[:2]
    if variant == 'crowd':     # heads and shoulders in the lower two thirds
        for _ in range(rng.randint(6, 14)):
            cx, cy = rng.randint(0, w), rng.randint(h // 3, h)
            r = rng.randint(w // 30, w // 12)
            color = [rng.randint(10, 230) for _ in range(3)]
            cv2.ellipse(img, (cx, cy), (r, int(r * 1.2)), 0, 0, 360, color, -1)
            cv2.rectangle(img, (cx - 2 * r, cy + r), (cx + 2 * r, h), [rng.randint(10, 230) for _ in range(3)], -1)
    elif variant == 'dim':
        img = (255 * (img / 255.0) ** 1.8).astype(np.uint8)
        img = np.clip(img + np.random.default_rng(rng.randint(0, 9999)).normal(0, 6, img.shape), 0, 255).astype(np.uint8)
    elif variant == 'warm':
        img = np.clip(img * np.array([0.8, 0.95, 1.2]), 0, 255).astype(np.uint8)
    elif variant == 'blur_lowres':
        img = cv2.GaussianBlur(cv2.resize(img, (w // 3, h // 3), interpolation=cv2.INTER_AREA), (3, 3), 0)
    elif variant == 'tilt':
        m = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-9, 9), 1.12)
        img = cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
    elif variant == 'portrait':
        img = img[:, w // 2 - h * 3 // 8: w // 2 + h * 3 // 8]
    return img


def make_queries(pano, n_views, variants, rng, per_view=None):
    out = []
    for i in range(n_views):
        yaw = 22.5 + 45 * i + rng.uniform(-12, 12)
        pitch = rng.uniform(-20, 5)
        fov = rng.choice([55, 65, 75, 90])
        view = perspective_view(pano, yaw, pitch, fov, (1000, 750))
        chosen = rng.sample(variants, per_view) if per_view and per_view < len(variants) else variants
        for variant in chosen:
            ok, buf = cv2.imencode('.jpg', roughen(view, variant, rng), [cv2.IMWRITE_JPEG_QUALITY, 85])
            out.append({'yaw': yaw % 360, 'variant': variant, 'raw': buf.tobytes()})
    return out


def view_yaw(name):
    return float(name.split('view_y')[1][:3]) if 'view_y' in name else None


def score_query(raw, rooms):
    """Per reference view: (yaw, verified matches, similarity). Mirrors the app: detail matching
    runs only on the rooms closest in similarity (one extra so leave-one-out stays accurate)."""
    q = vision.embed_bytes(raw)
    paths = {r['id']: [(n, DATA / n) for n in r['images'] if (DATA / n).is_file()] for r in rooms}
    sims = {rid: [float(q @ vision.reference_embedding(p)) if q is not None else None for _, p in ps]
            for rid, ps in paths.items()}
    if q is not None:
        order = sorted((rid for rid in paths if sims[rid]), key=lambda rid: max(sims[rid]), reverse=True)
        to_match = set(order[:vision.SHORTLIST + 1])
    else:
        to_match = set(paths)
    index = vision.QueryIndex(vision.features_from_bytes(raw))
    per_room = {}
    for rid, ps in paths.items():
        per_room[rid] = [(view_yaw(n), vision.verified_matches(index, vision.reference_features(p)) if rid in to_match else 0, s)
                         for (n, p), s in zip(ps, sims[rid])]
    return per_room


def room_scores(per_room, drop_room=None, hide_yaw_of=None, query_yaw=None):
    out = {}
    for room_id, views in per_room.items():
        if room_id == drop_room:
            continue
        if room_id == hide_yaw_of and query_yaw is not None:
            views = [v for v in views if v[0] is None or min(abs(v[0] - query_yaw), 360 - abs(v[0] - query_yaw)) > 50]
        if not views:
            continue
        sims = [v[2] for v in views if v[2] is not None]
        out[room_id] = (max(v[1] for v in views), max(sims) if sims else None)
    return out


def decide(scores, min_sim, min_margin, clear=None):
    """Same rules as vision.match_rooms. Returns (rooms suggested, confident?)."""
    clear = vision.CLEAR_MARGIN if clear is None else clear
    picked, confident = set(), False
    sims = sorted(((s, r) for r, (_, s) in scores.items() if s is not None), reverse=True)
    if sims:
        runner, runner_id = sims[1] if len(sims) > 1 else (-1.0, None)
        lead = sims[0][0] - runner
        if sims[0][0] >= min_sim and lead >= clear:
            picked, confident = {sims[0][1]}, True
        elif sims[0][0] >= min_sim and lead >= min_margin and runner_id:
            picked = {sims[0][1], runner_id}
    feats = sorted(((m, r) for r, (m, _) in scores.items()), reverse=True)
    if feats:
        second = feats[1][0] if len(feats) > 1 else 0
        if feats[0][0] >= vision.MIN_INLIERS and feats[0][0] >= vision.FEATURE_LEAD * max(second, 1):
            picked, confident = {feats[0][1]}, True
    return picked, confident


def evaluate(records, min_sim, min_margin):
    """right: one confident pick, correct. offered: correct room among two possible matches.
    wrong: confident pick of the wrong room. fooled (unknown rooms): confident pick of any room.
    maybe: unknown room shown as two possible matches (the finder can still tap None of these)."""
    keys = ('n', 'right', 'offered', 'wrong', 'none', 'maybe')
    stats = {k: dict.fromkeys(keys, 0) for k in ('known', 'hard', 'unknown', 'leave_one_out')}
    for rec in records:
        if rec['truth'] in rec['catalog_ids']:
            cases = (('known', room_scores(rec['per_room'])),
                     ('hard', room_scores(rec['per_room'], hide_yaw_of=rec['truth'], query_yaw=rec['yaw'])),
                     ('leave_one_out', room_scores(rec['per_room'], drop_room=rec['truth'])))
        else:
            cases = (('unknown', room_scores(rec['per_room'])),)
        for kind, scores in cases:
            picked, confident = decide(scores, min_sim, min_margin)
            st = stats[kind]
            st['n'] += 1
            if kind in ('unknown', 'leave_one_out'):
                st['wrong' if confident else 'maybe' if picked else 'none'] += 1
            elif not picked:
                st['none'] += 1
            elif rec['truth'] in picked:
                st['right' if confident else 'offered'] += 1
            else:
                st['wrong'] += 1
    return stats


def pct(a, b):
    return f'{100 * a / b:5.1f}%' if b else '   - '


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--report', action='store_true', help='re-score data/stress/results.json without scanning')
    args = parser.parse_args()
    if args.fetch:
        print('Downloading decoy rooms...')
        fetch()
        return
    if args.report:
        report(json.loads((STRESS / 'results.json').read_text()), [])
        return
    rng = random.Random(args.seed)
    rooms = [with_photos_on_disk(r, DATA) for r in json.loads((DATA / 'classrooms.json').read_text())['rooms']]
    rooms = [r for r in rooms if r['images']]
    catalog_ids = [r['id'] for r in rooms]
    if vision.scene_model() is None:
        print('Scene model not available (pip install torch); testing feature matching only.')
    print('Preparing reference views...', flush=True)
    vision.warm_cache(rooms, DATA)

    n_views, per_view = (3, 3) if args.quick else (6, 4)
    sources = [(r['id'], DATA / 'rooms' / r['id'] / 'pano.jpg', VARIANTS) for r in rooms]
    decoys = sorted(p.parent.name for p in STRESS.glob('*/pano.jpg') if p.parent.name not in catalog_ids)
    if args.quick:
        decoys = decoys[:12]
    sources += [(code, STRESS / code / 'pano.jpg', ['clean', 'crowd']) for code in decoys]
    if not decoys:
        print('No extra decoy rooms (all of them are in the app now); the look-alike test covers unknown rooms.')

    records, times = [], []
    for code, pano_path, variants in sources:
        pano = cv2.imread(str(pano_path))
        if pano is None:
            print(f'  {code}: no panorama at {pano_path}, skipped')
            continue
        queries = make_queries(pano, n_views, variants, rng, per_view)
        print(f'  {code:10s} {len(queries):3d} photos', end='', flush=True)
        for q in queries:
            t = time.time()
            per_room = score_query(q['raw'], rooms)
            times.append(time.time() - t)
            records.append({'truth': code, 'catalog_ids': catalog_ids, 'yaw': q['yaw'],
                            'variant': q['variant'], 'per_room': per_room})
        print(f'  ({np.mean(times[-len(queries):]):.2f}s each)', flush=True)

    STRESS.mkdir(parents=True, exist_ok=True)
    (STRESS / 'results.json').write_text(json.dumps(records))

    report(records, times)


def report(records, times):
    catalog_ids = records[0]['catalog_ids'] if records else []
    cur = (vision.MIN_SIMILARITY, vision.MIN_MARGIN)
    print(f'\n=== Current settings: similarity >= {cur[0]}, lead >= {cur[1]} ===')
    stats = evaluate(records, *cur)
    print('(right = one confident correct pick; offered = correct room among 2 possible matches)')
    for kind, label in (('known', 'Known rooms'), ('hard', 'Known rooms, hard viewpoint')):
        st = stats[kind]
        print(f"{label:30s} right {pct(st['right'], st['n'])}  offered {pct(st['offered'], st['n'])}  "
              f"wrong {pct(st['wrong'], st['n'])}  no match {pct(st['none'], st['n'])}   (n={st['n']})")
    print('(fooled = confident wrong pick; 2 options = shown as possible matches, finder can say none)')
    for kind, label in (('unknown', 'Unknown rooms (decoys)'), ('leave_one_out', 'Look-alike (leave-one-out)')):
        st = stats[kind]
        print(f"{label:30s} fooled {pct(st['wrong'], st['n'])}  2 options {pct(st['maybe'], st['n'])}  "
              f"no match {pct(st['none'], st['n'])}   (n={st['n']})")

    print('\nKnown rooms by condition (right or offered / wrong):')
    for variant in VARIANTS:
        sub = [r for r in records if r['variant'] == variant and r['truth'] in catalog_ids]
        st = evaluate(sub, *cur)['known']
        print(f"  {variant:12s} {pct(st['right'] + st['offered'], st['n'])} / {pct(st['wrong'], st['n'])}  (n={st['n']})")

    print('\nSweep of the confident-match lead (hard right+offered | decoys fooled | look-alike fooled):')
    for clear in (0.06, 0.08, 0.10, 0.12):
        saved = vision.CLEAR_MARGIN
        vision.CLEAR_MARGIN = clear
        st = evaluate(records, *cur)
        vision.CLEAR_MARGIN = saved
        h, u, lo = st['hard'], st['unknown'], st['leave_one_out']
        mark = '  <- current' if clear == saved else ''
        print(f"  clear lead {clear:.2f}:  {pct(h['right'] + h['offered'], h['n'])} | {pct(u['wrong'], u['n'])} | "
              f"{pct(lo['wrong'], lo['n'])}{mark}")

    print('\nWorst confident false alarms (decoy photo -> room picked, similarity):')
    alarms = []
    for rec in records:
        if rec['truth'] in catalog_ids:
            continue
        scores = room_scores(rec['per_room'])
        picked, confident = decide(scores, *cur)
        for room in (picked if confident else []):
            alarms.append((scores[room][1] or 0, rec['truth'], room, rec['variant']))
    for sim, truth, room, variant in sorted(alarms, reverse=True)[:8]:
        print(f'  {truth:10s} -> {room:10s} sim {sim:.2f} ({variant})')
    if not alarms:
        print('  none')
    if len(times):
        times = np.array(times)
        print(f'\nTime per scan: median {np.median(times):.2f}s, slowest 5% {np.percentile(times, 95):.2f}s')
    print(f'Raw scores in {STRESS / "results.json"}')


if __name__ == '__main__':
    main()
