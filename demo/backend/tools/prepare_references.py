"""Build the offline room reference index from official Rutgers panorama JPEGs.
Run with --download to refresh the public references. Nothing is fetched at runtime.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data' / 'room-references'
USER_CONFIRMED_ROOM = dict(id='RWH-IDEA3',campus='Busch',building='Richard Weeks Hall',code='RWH',room='IDEA3 Lab',
    source_url='https://webapps.rutgers.edu/dcs/classrooms/RWH-206',images=[],
    reference_kind='user-confirmed examples',metadata_source='User confirmed on 2026-10-11; lab room number not verified')
ROOMS = [
    ('RWH-102','Busch','Richard Weeks Hall','RWH','102'),
    ('RWH-105','Busch','Richard Weeks Hall','RWH','105'),
    ('RWH-206','Busch','Richard Weeks Hall','RWH','206'),
    ('RWH-208','Busch','Richard Weeks Hall','RWH','208'),
    ('HH-A2', 'College Ave', 'Hardenbergh Hall', 'HH', 'A2'),
    ('ABE-4400', 'College Ave', 'Academic Building East', 'ABE', '4400'),
    ('ARC-103', 'Busch', 'Allison Road Classroom', 'ARC', '103'),
    ('LSH-A102', 'Livingston', 'Lucy Stone Hall', 'LSH', 'A102'),
    ('PHY-001', 'Busch', 'Physics Lecture Hall', 'PHY', '001'),
    ('SEC-111', 'Busch', 'Science and Engineering Resource Center', 'SEC', '111'),
    ('BE-100', 'Livingston', 'Beck Hall', 'BE', '100'),
    ('CDL-102', 'Cook/Douglass', 'Cook/Douglass Lecture Hall', 'CDL', '102'),
    ('WL-128', 'Busch', 'Wright Labs', 'WL', '128'),
    ('ABW-1150A', 'College Ave', 'Academic Building West', 'ABW', '1150A'),
    ('ABW-1150B', 'College Ave', 'Academic Building West', 'ABW', '1150B'),
    ('ABW-1100', 'College Ave', 'Academic Building West', 'ABW', '1100'),
    ('ABW-2150', 'College Ave', 'Academic Building West', 'ABW', '2150'),
    ('ABW-2100', 'College Ave', 'Academic Building West', 'ABW', '2100'),
    ('ABE-2200', 'College Ave', 'Academic Building East', 'ABE', '2200'),
    ('ABE-3200', 'College Ave', 'Academic Building East', 'ABE', '3200'),
    ('TIL-204', 'Livingston', 'Tillett Hall', 'TIL', '204'),
    ('ABE-1180', 'College Ave', 'Academic Building East', 'ABE', '1180'),
    ('ABE-2225', 'College Ave', 'Academic Building East', 'ABE', '2225'),
    ('ABE-2250', 'College Ave', 'Academic Building East', 'ABE', '2250'),
    ('ABE-2400', 'College Ave', 'Academic Building East', 'ABE', '2400'),
    ('ABE-3450', 'College Ave', 'Academic Building East', 'ABE', '3450'),
    ('ABE-4225', 'College Ave', 'Academic Building East', 'ABE', '4225'),
    ('ABE-4450', 'College Ave', 'Academic Building East', 'ABE', '4450'),
    ('ABW-1125', 'College Ave', 'Academic Building West', 'ABW', '1125'),
    ('ABW-1170', 'College Ave', 'Academic Building West', 'ABW', '1170'),
    ('ABW-2125', 'College Ave', 'Academic Building West', 'ABW', '2125'),
    ('ABW-2160', 'College Ave', 'Academic Building West', 'ABW', '2160'),
    ('ABW-3100', 'College Ave', 'Academic Building West', 'ABW', '3100'),
]


def download(url, destination):
    # Use macOS's configured certificate trust; never disable TLS verification.
    subprocess.run(['/usr/bin/curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '40',
                    url, '--output', str(destination)], check=True)
    with Image.open(destination) as image: image.verify()


def perspective(pano, yaw, pitch, size=640, fov=80):
    h, w = pano.shape[:2]
    focal = (size / 2) / np.tan(np.radians(fov / 2))
    xx, yy = np.meshgrid((np.arange(size) - size/2) / focal, -(np.arange(size) - size/2) / focal)
    rays = np.stack([xx, yy, np.ones_like(xx)], axis=-1)
    a, b = np.radians(yaw), np.radians(pitch)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    rays = rays @ rx.T @ ry.T
    length = np.linalg.norm(rays, axis=-1)
    u = (np.arctan2(rays[..., 0], rays[..., 2]) / (2*np.pi) + .5) * w
    v = (.5 - np.arcsin(rays[..., 1] / length) / np.pi) * h
    return cv2.remap(pano, u.astype(np.float32), v.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def index_image(path):
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    points, desc = cv2.SIFT_create(nfeatures=650).detectAndCompute(gray, None)
    if desc is not None:
        np.savez_compressed(path.with_suffix('.npz'), points=np.array([p.pt for p in points], np.float32), descriptors=desc)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--download', action='store_true'); args = parser.parse_args()
    BASE.mkdir(parents=True, exist_ok=True); cv2.setNumThreads(1)
    manifest = []
    for rid, campus, building, code, room in ROOMS:
        url = 'https://webapps.rutgers.edu/dcs/Data/public/DownloadFile?viewid=2068&groupid=0&id='+rid+'&fieldPathSerialization=2022%2F2148'
        path = BASE/(rid+'.jpg')
        if args.download or not path.exists(): download(url, path)
        pano = cv2.imread(str(path))
        if pano is None: raise RuntimeError('Invalid panorama '+rid)
        if pano.shape[1]>4096:pano=cv2.resize(pano,(4096,round(pano.shape[0]*4096/pano.shape[1])))
        views = []
        for yaw in range(0, 360, 30):
            for pitch in (-15, 10):
                name = f'{rid}-y{yaw}-p{pitch}.jpg'; target = BASE/name

                if args.download or not target.is_file():
                    cv2.imwrite(str(target), perspective(pano, yaw, pitch), [cv2.IMWRITE_JPEG_QUALITY, 88]); index_image(target)
                views.append(name)
        if rid in ('ABW-1150A', 'ABW-1150B'):
            suffix = 'ca_collab-room-1150a.jpg' if rid.endswith('A') else 'ca_collab-room-1150b_0.jpg'
            still_url = 'https://learningcenters.rutgers.edu/sites/default/files/2023-03/'+suffix
            still = BASE/(rid+'-still.jpg')
            if args.download or not still.exists(): download(still_url, still)
            with Image.open(still) as image:
                image = image.convert('RGB'); image.thumbnail((1000, 1000)); image.save(still, quality=88)
            index_image(still); views.insert(0, still.name)
        if rid=='RWH-105' and (ROOT.parent/'public/examples/Weeks-lecture.jpg').is_file():
            supplied=BASE/'RWH-105-supplied.jpg'
            with Image.open(ROOT.parent/'public/examples/Weeks-lecture.jpg') as image:
                image=image.convert('RGB');image.thumbnail((1000,1000));image.save(supplied,quality=88)
            index_image(supplied);views.append(supplied.name)
        manifest.append(dict(id=rid, campus=campus, building=building, code=code, room=room,
            source_url='https://webapps.rutgers.edu/dcs/classrooms/'+rid, image_url=url,
            downloaded_at='2026-10-11', panorama=path.name, images=views))
        if rid=='RWH-105' and 'RWH-105-supplied.jpg' in views:
            manifest[-1]['additional_source']='https://torcon.com/project/richard-weeks-hall-of-engineering-2/'
            manifest[-1]['additional_label_basis']='Visual inference against the official RWH-105 panorama; supplied sample requires confirmation.'
        print('Prepared', rid, len(views), 'views', flush=True)
    (ROOT/'data'/'classrooms.json').write_text(json.dumps({'rooms': manifest+[USER_CONFIRMED_ROOM]}, indent=2))

if __name__ == '__main__': main()
