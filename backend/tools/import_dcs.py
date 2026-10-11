"""Download Rutgers DCS 360-degree classroom panoramas for a few demo rooms and turn each
into ordinary camera-style views that the on-device room matcher can use.

Usage (from backend/):
    python tools/import_dcs.py                 # the 5 default CS lecture halls
    python tools/import_dcs.py ARC-103 RWH-105 # specific rooms already listed in ROOMS
    python tools/import_dcs.py --core          # only the 5 original demo rooms

Images are saved under data/rooms/<ROOM-ID>/ and are git-ignored: they belong to Rutgers
DCS and are used only locally for the demo. Room metadata (building, campus, capacity)
is added to data/classrooms.json with a link to the source page.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

DATA = Path(__file__).resolve().parent.parent / 'data'
PANO_URL = ('https://webapps.rutgers.edu/dcs/Data/public/DownloadFile'
            '?viewid=2068&groupid=0&id={code}&fieldPathSerialization=2022%2F2148')
PAGE_URL = 'https://webapps.rutgers.edu/dcs/classrooms/{code}'

# Verified from each room's DCS page on 2026-10-11.
ROOMS = {
    'ARC-103': dict(building='Allison Road Classroom', campus='Busch', room='103', capacity=500, room_type='Lecture Hall'),
    'LSH-A102': dict(building='Lucy Stone Hall', campus='Livingston', room='A102', capacity=400, room_type='Lecture Hall'),
    'PHY-001': dict(building='Physics Lecture Hall', campus='Busch', room='001', capacity=316, room_type='Lecture Hall'),
    'RWH-105': dict(building='Richard Weeks Hall of Engineering', campus='Busch', room='105', capacity=285, room_type='Auditorium'),
    'SEC-111': dict(building='Science & Engineering Research Center', campus='Busch', room='111', capacity=269, room_type='Auditorium'),
    # Added 2026-10-11 from the DCS classroom list (building, campus, student seating capacity).
    'ABE-2225': dict(building='Academic Building East Wing', campus='College Ave', room='2225', capacity=271),
    'ABE-2400': dict(building='Academic Building East Wing', campus='College Ave', room='2400', capacity=271),
    'ABE-4225': dict(building='Academic Building East Wing', campus='College Ave', room='4225', capacity=246),
    'ABW-2125': dict(building='Academic Building West Wing', campus='College Ave', room='2125', capacity=271),
    'ABW-2160': dict(building='Academic Building West Wing', campus='College Ave', room='2160', capacity=271),
    'MI-100': dict(building='Milledoler Hall', campus='College Ave', room='100', capacity=170),
    'BME-102': dict(building='Biomedical Engineering Building', campus='Busch', room='102', capacity=141),
    'CCB-1303': dict(building='Chemistry & Chemical Biology', campus='Busch', room='1303', capacity=117),
    'COR-101': dict(building='CoRE Building', campus='Busch', room='101', capacity=113),
    'EN-B120': dict(building='Engineering Building', campus='Busch', room='B120', capacity=165),
    'FBO-108': dict(building='Fiber Optic Materials Research Building', campus='Busch', room='108', capacity=173),
    'HLL-114': dict(building='Hill Center', campus='Busch', room='114', capacity=314),
    'HLL-116': dict(building='Hill Center', campus='Busch', room='116', capacity=105),
    'PH-111': dict(building='Pharmacy Building', campus='Busch', room='111', capacity=136),
    'BE-100': dict(building='Beck Hall', campus='Livingston', room='100', capacity=391),
    'LSH-A142': dict(building='Lucy Stone Hall', campus='Livingston', room='A142', capacity=112),
    'ARH-200': dict(building='Art History Hall', campus='Cook/Douglass', room='200', capacity=150),
    'CDL-102': dict(building='Cook/Douglass Lecture Hall', campus='Cook/Douglass', room='102', capacity=120),
    'FSW-105': dict(building='Food Science and Nutritional Sciences West', campus='Cook/Douglass', room='105', capacity=194),
    'HCK-101': dict(building='Hickman Hall', campus='Cook/Douglass', room='101', capacity=288),
    'HCK-138': dict(building='Hickman Hall', campus='Cook/Douglass', room='138', capacity=481),
    'KLG-010': dict(building='Ludwig Global Village Learning Center', campus='Cook/Douglass', room='010', capacity=198),
    'LOR-022': dict(building='Loree Classroom Building', campus='Cook/Douglass', room='022', capacity=295),
    'RAB-001': dict(building='Ruth Adams Building', campus='Cook/Douglass', room='001', capacity=144),
}

VIEW_YAWS = range(0, 360, 45)   # 8 directions
VIEW_PITCHES = (0, -12)         # eye level and slightly down toward the seats
VIEW_FOV = 75                   # degrees, close to a phone's main camera
VIEW_SIZE = (1000, 750)         # width, height


def perspective_view(pano, yaw_deg, pitch_deg, fov_deg=VIEW_FOV, size=VIEW_SIZE):
    """Render a pinhole-camera view from an equirectangular panorama."""
    out_w, out_h = size
    pano_h, pano_w = pano.shape[:2]
    focal = 0.5 * out_w / np.tan(np.radians(fov_deg) / 2)
    xs, ys = np.meshgrid(np.arange(out_w) - out_w / 2, np.arange(out_h) - out_h / 2)
    # Camera rays (x right, y down, z forward), rotated by pitch then yaw.
    rays = np.stack([xs, ys, np.full_like(xs, focal)], axis=-1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    pitch, yaw = np.radians(pitch_deg), np.radians(yaw_deg)
    rot_x = np.array([[1, 0, 0], [0, np.cos(pitch), np.sin(pitch)], [0, -np.sin(pitch), np.cos(pitch)]])
    rot_y = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    rays = rays @ rot_x.T @ rot_y.T
    lon = np.arctan2(rays[..., 0], rays[..., 2])            # -pi..pi
    lat = np.arcsin(np.clip(rays[..., 1], -1, 1))           # -pi/2..pi/2, down is positive
    map_x = ((lon / (2 * np.pi) + 0.5) * pano_w).astype(np.float32) % pano_w
    map_y = ((lat / np.pi + 0.5) * pano_h).astype(np.float32)
    return cv2.remap(pano, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def slice_panorama(pano, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for pitch in VIEW_PITCHES:
        for yaw in VIEW_YAWS:
            view = perspective_view(pano, yaw, pitch)
            name = f'view_y{yaw:03d}_p{abs(pitch):02d}.jpg'
            cv2.imwrite(str(out_dir / name), view, [cv2.IMWRITE_JPEG_QUALITY, 88])
            names.append(name)
    return names


def download(code):
    request = urllib.request.Request(PANO_URL.format(code=code), headers={'User-Agent': 'WhereRU-hackathon-demo/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    pano = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if pano is None:
        raise ValueError(f'{code}: the download is not an image (got {len(raw)} bytes)')
    if abs(pano.shape[1] / pano.shape[0] - 2) > 0.2:
        print(f'  warning: {code} is {pano.shape[1]}x{pano.shape[0]}, not a 2:1 panorama; views may look distorted')
    return pano


def update_catalog(entries):
    """Make sure each imported room is listed in classrooms.json (metadata only).

    The app finds the downloaded views in data/rooms/<id>/ on its own, so this file only
    changes when a new room is added, and git pull doesn't conflict with local imports.
    """
    path = DATA / 'classrooms.json'
    catalog = json.loads(path.read_text()) if path.exists() else {'rooms': []}
    by_id = {room['id']: room for room in catalog.get('rooms', [])}
    for entry in entries:
        existing = by_id.get(entry['id'], {})
        own = [img for img in existing.get('images', []) if '/view_' not in img]
        by_id[entry['id']] = {**existing, **entry, 'images': own}
    catalog['rooms'] = sorted(by_id.values(), key=lambda room: room['id'])
    text = json.dumps(catalog, indent=2) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def main(codes):
    unknown = [code for code in codes if code not in ROOMS]
    if unknown:
        sys.exit(f'Unknown room codes {unknown}. Add their verified details to ROOMS first.')
    entries = []
    for code in codes:
        print(f'{code}: downloading panorama...')
        try:
            pano = download(code)
        except Exception as error:  # keep going so one bad room doesn't stop the rest
            print(f'  failed: {error}')
            continue
        room_dir = DATA / 'rooms' / code
        room_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(room_dir / 'pano.jpg'), pano)
        names = slice_panorama(pano, room_dir)
        print(f'  saved {len(names)} views to data/rooms/{code}/')
        entries.append({'id': code, **ROOMS[code], 'source_url': PAGE_URL.format(code=code)})
        time.sleep(1)  # be polite to the DCS server
    if entries:
        update_catalog(entries)
        print(f'Updated data/classrooms.json with {len(entries)} room(s). Restart Flask to use them.')


CORE = ['ARC-103', 'LSH-A102', 'PHY-001', 'RWH-105', 'SEC-111']

if __name__ == '__main__':
    args = sys.argv[1:]
    main(CORE if args == ['--core'] else args or list(ROOMS))
