"""Check what the item recognizer says about photos of found items.

Usage (from backend/, venv active, PyTorch installed):
    python tools/test_item_photo.py ~/Downloads/keys.jpg [more photos...]
    python tools/test_item_photo.py --eval      # leave-one-variant-out check on data/items

--eval hides each variant of each class in turn and classifies its images using only the
other variants, so the reported accuracy is on unseen variants (still synthetic images; check
real phone photos too).
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

print('Loading the vision model...', flush=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from whereru import vision  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / 'data'


def classify_file(path):
    result = vision.classify_item(Path(path).expanduser().read_bytes(), DATA)
    if result is None:
        sys.exit('Scene model not available: pip install torch')
    return result


def evaluate():
    import numpy as np
    refs = vision.item_references(str(DATA))
    # query embeddings use the same center crop the app uses on uploads
    import cv2
    queries = [vision._embed_bgr(vision._center_crop(cv2.imread(p))) for _, p, _ in refs]
    correct, confident_right, confident_wrong, confusion = 0, 0, 0, Counter()
    per_class = defaultdict(lambda: [0, 0])
    for i, (cls, path, _) in enumerate(refs):
        scored = vision._score_classes(queries[i], refs, skip=(cls, vision._variant(path)))
        (top, guess), (second, _) = scored[0], scored[1]
        sure = top >= vision.ITEM_MIN_SIMILARITY and top - second >= vision.ITEM_MIN_MARGIN
        correct += guess == cls
        per_class[cls][0] += guess == cls
        per_class[cls][1] += 1
        if sure:
            confident_right += guess == cls
            confident_wrong += guess != cls
        if guess != cls:
            confusion[(cls, guess)] += 1
    n = len(refs)
    print(f'\nUnseen-variant accuracy: {correct}/{n} = {100 * correct / n:.0f}%')
    print(f'Suggested to the finder: {confident_right + confident_wrong}/{n}, of which wrong: {confident_wrong}')
    for cls, (ok, total) in sorted(per_class.items()):
        print(f'  {cls:14s} {ok}/{total}')
    if confusion:
        print('Most common mix-ups:', ', '.join(f'{a}->{b} x{k}' for (a, b), k in confusion.most_common(6)))


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args == ['--eval']:
        evaluate()
    else:
        for photo in args:
            r = classify_file(photo)
            verdict = 'SUGGEST' if r['confident'] else 'not sure (finder fills it in)'
            print(f"{Path(photo).name}: {r['title']} [{r['priority']}{', private' if r['sensitive'] else ''}] "
                  f"similarity {r['similarity']:.2f}, lead {r['lead']:.2f} over {r['runner_up']} -> {verdict}")
