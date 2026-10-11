"""Install the pinned official DINOv2 model once, then cache five rooms offline."""
import json
import subprocess
import sys
import tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

ROOT=Path(__file__).resolve().parents[1]
REVISION='7764ea0f912e53c92e82eb78a2a1631e92725fc8'
FIVE_ROOMS=('ARC-103','LSH-A102','PHY-001','RWH-105','SEC-111')


def download(url,path):
    subprocess.run(['/usr/bin/curl','--fail','--location','--silent','--show-error','--max-time','120',url,'--output',str(path)],check=True)


def main():
    assets=ROOT/'.tools';assets.mkdir(exist_ok=True)
    source=assets/'dinov2';weights=assets/'dinov2_vits14_pretrain.pth'
    if not (source/'hubconf.py').is_file():
        archive=assets/'dinov2.tar.gz'
        download(f'https://codeload.github.com/facebookresearch/dinov2/tar.gz/{REVISION}',archive)
        with tarfile.open(archive) as tar:tar.extractall(assets,filter='data')
        (assets/('dinov2-'+REVISION)).rename(source)
        archive.unlink()
    if not weights.is_file():
        temporary=weights.with_suffix('.download')
        download('https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth',temporary)
        temporary.replace(weights)
    from whereru import scene_matcher
    if scene_matcher.scene_model() is None:raise SystemExit('The scene model could not be loaded')
    rooms=json.loads((ROOT/'data/classrooms.json').read_text())['rooms']
    for room in rooms:
        if room['id'] not in FIVE_ROOMS:continue
        # Keep the supplied Weeks image out of this model's evaluation/reference set.
        refs={**room,'images':[x for x in room['images'] if 'supplied' not in x]}
        scene_matcher.warm_cache([refs],ROOT/'data/room-references')
        print('Cached scene and feature references:',room['id'],flush=True)
    print('DINOv2-small ready offline. No API key is needed.',flush=True)
    (assets/'room-model-ready.json').write_text(json.dumps({'revision':REVISION,'rooms':FIVE_ROOMS,'model':'dinov2_vits14'}))


if __name__=='__main__':main()
