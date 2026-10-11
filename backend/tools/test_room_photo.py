"""Check how a photo scores against every classroom in data/classrooms.json.

Usage (from backend/, with the venv active):
    python tools/test_room_photo.py ~/Downloads/hill114.jpg

Prints each room's best number of verified feature matches (a room is reported
by the app at 18 or more) and how long matching took.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from whereru import vision  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / 'data'


def main(photo):
    rooms = json.loads((DATA / 'classrooms.json').read_text())['rooms']
    raw = Path(photo).expanduser().read_bytes()
    query = vision.QueryIndex(vision.features_from_bytes(raw))
    print(f'Photo features: {len(query.points)}')
    started = time.time()
    for room in rooms:
        images = room.get('images', [])
        if not images:
            print(f'{room["id"]:10s}  no reference images (run tools/import_dcs.py)')
            continue
        scores = []
        for name in images:
            path = DATA / name
            if path.is_file():
                scores.append((vision.verified_matches(query, vision.reference_features(path)), name))
        missing = len(images) - len(scores)
        best, best_name = max(scores) if scores else (0, '-')
        verdict = 'MATCH' if best >= vision.MIN_INLIERS else 'no match'
        print(f'{room["id"]:10s}  best {best:4d}  {verdict:8s}  ({Path(best_name).name}){"  missing files: " + str(missing) if missing else ""}')
    print(f'Matching took {time.time() - started:.1f}s (includes loading reference features the first time)')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python tools/test_room_photo.py <photo.jpg>')
    main(sys.argv[1])
