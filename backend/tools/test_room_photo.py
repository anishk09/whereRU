"""Check how a photo scores against every classroom in data/classrooms.json.

Usage (from backend/, with the venv active):
    python tools/test_room_photo.py ~/Downloads/photo.jpg [more photos...]

For each room it prints:
  matches     verified feature matches (the room is reported at 18 or more)
  similarity  scene similarity from the DINOv2 model, if PyTorch is installed
and then which room(s) the app would suggest.
"""
import json
import sys
import time
from pathlib import Path

print('Loading OpenCV...', flush=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from whereru import vision  # noqa: E402
from whereru.ai import with_photos_on_disk  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / 'data'


def main(photos):
    rooms = [with_photos_on_disk(r, DATA) for r in json.loads((DATA / 'classrooms.json').read_text())['rooms']]
    rooms = [r for r in rooms if r['images']]
    print('Loading scene model (first run downloads about 90 MB)...', flush=True)
    if vision.scene_model() is None:
        print('  -> not available: install it with  pip install torch  (feature matching still works)')
    for photo in photos:
        raw = Path(photo).expanduser().read_bytes()
        print(f'\n{Path(photo).name} ({len(raw) / 1e6:.1f} MB)', flush=True)
        started = time.time()
        scores, _ = vision.score_rooms(raw, rooms, DATA)
        for room_id, value in sorted(scores.items(), key=lambda kv: -(kv[1]['similarity'] or 0)):
            if not value['views']:
                print(f'  {room_id:10s}  no reference images (run tools/import_dcs.py)')
                continue
            sim = f"{value['similarity']:.3f}" if value['similarity'] is not None else '  -  '
            print(f"  {room_id:10s}  matches {value['matches']:4d}   similarity {sim}")
        picked = vision.match_rooms(raw, rooms, DATA)
        print(f"  => app suggests: {', '.join(p['room_id'] for p in picked) or 'no match (placard / choose manually)'}"
              f"   ({time.time() - started:.1f}s, first photo includes loading reference photos)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Usage: python tools/test_room_photo.py <photo.jpg> [more photos...]')
    main(sys.argv[1:])
