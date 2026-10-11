#!/usr/bin/env python3
"""
Campus Lost & Found — synthetic image dataset generator.

10 of the most commonly lost items on college campuses, 8 variants each
(different size, shape, style and color), rendered on realistic campus
surfaces with soft shadows and random rotation.

Outputs (in OUTDIR):
  images/<class>/<class>_v<N>.png       512x512 RGB images
  labels/<class>/<class>_v<N>.txt       YOLO-format bounding boxes
  annotations.csv                       one row per image with variant metadata + bbox
  classes.txt                           YOLO class index list
  contact_sheet.png                     overview grid

Usage:  python3 generate_dataset.py OUTDIR [--seed 7] [--renders 1]
  --renders N  renders each variant N times on different backgrounds/angles
               (useful for training; default 1 = exactly 8 images per class)
"""
import argparse, csv, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024          # working canvas (rendered at 2x, downsampled for anti-aliasing)
OUT = 512         # output size
X = Y = 512       # canvas centre


# ───────────────────────── helpers ─────────────────────────
def C(h, a=255):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def sh(c, f):
    """lighten (f>1) or darken (f<1) an RGBA colour"""
    r, g, b, a = c
    if f >= 1:
        k = f - 1
        return (int(r + (255 - r) * k), int(g + (255 - g) * k), int(b + (255 - b) * k), a)
    return (int(r * f), int(g * f), int(b * f), a)


def layer(size=S):
    return Image.new('RGBA', (size, size), (0, 0, 0, 0))


def over(L, img, x=0, y=0):
    """alpha-composite img onto L with its top-left at (x, y), clipping safely"""
    t = layer(L.size[0])
    t.paste(img, (int(round(x)), int(round(y))))
    L.alpha_composite(t)


def bez(p0, p1, p2, p3, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def dashed_rect(d, box, color, width=3, dash=14, gap=9, radius=0):
    x0, y0, x1, y1 = box
    segs = [((x0 + radius, y0), (x1 - radius, y0)), ((x1, y0 + radius), (x1, y1 - radius)),
            ((x1 - radius, y1), (x0 + radius, y1)), ((x0, y1 - radius), (x0, y0 + radius))]
    for (ax, ay), (bx, by) in segs:
        L = math.hypot(bx - ax, by - ay)
        n = int(L // (dash + gap))
        for i in range(n + 1):
            t0 = i * (dash + gap) / L
            t1 = min(1, t0 + dash / L)
            if t0 >= 1:
                break
            d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                   fill=color, width=width)


def fill_pattern(L, mask_fn, pattern):
    """draw a mask with mask_fn(draw) and fill it with the pattern image"""
    m = Image.new('L', (S, S), 0)
    mask_fn(ImageDraw.Draw(m))
    t = layer()
    t.paste(pattern, (0, 0), m)
    L.alpha_composite(t)


def pattern(kind, c1, c2, rng, scale=1.0):
    P = Image.new('RGBA', (S, S), C(c1))
    d = ImageDraw.Draw(P)
    if kind == 'dots':
        step = int(70 * scale)
        for yy in range(0, S, step):
            off = step // 2 if (yy // step) % 2 else 0
            for xx in range(-step, S, step):
                r = 13 * scale
                d.ellipse([xx + off - r, yy - r, xx + off + r, yy + r], fill=C(c2))
    elif kind == 'gores':     # vertical panels, like umbrella segments
        w = int(90 * scale)
        for i, xx in enumerate(range(0, S, w)):
            if i % 2:
                d.rectangle([xx, 0, xx + w, S], fill=C(c2))
    elif kind == 'plaid':
        for xx in range(0, S, 80):
            d.rectangle([xx, 0, xx + 26, S], fill=sh(C(c2), 1.0)[:3] + (150,))
        for yy in range(0, S, 80):
            d.rectangle([0, yy, S, yy + 26], fill=C(c2)[:3] + (150,))
        P = P.convert('RGB').convert('RGBA')
        d = ImageDraw.Draw(P)
        for xx in range(40, S, 80):
            d.line([(xx, 0), (xx, S)], fill=(250, 240, 210, 255), width=3)
    elif kind == 'stripes':
        cols = [C(c) for c in c2.split(',')]
        w = 70
        for i, yy in enumerate(range(-S, 2 * S, w)):
            d.polygon([(0, yy), (S, yy - S * 0.4), (S, yy - S * 0.4 + w), (0, yy + w)], fill=cols[i % len(cols)])
    elif kind == 'tortoise':
        for _ in range(140):
            x, y = rng.uniform(0, S), rng.uniform(0, S)
            r = rng.uniform(8, 30)
            d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=C(c2, rng.randint(120, 230)))
    return P


def light(L, strength=0.18, band=0.0, band_pos=0.3, band_w=0.05):
    """cylindrical-ish shading: lighter on the left, optional specular band"""
    arr = np.asarray(L).astype(np.float32)
    a = arr[..., 3]
    xs = np.nonzero(a.max(0) > 0)[0]
    if len(xs) == 0:
        return L
    x0, x1 = xs[0], xs[-1]
    t = (np.arange(S) - x0) / max(1, x1 - x0)
    f = 1 + strength * (0.5 - t)
    add = band * np.exp(-((t - band_pos) / band_w) ** 2)
    arr[..., :3] = np.clip(arr[..., :3] * f[None, :, None] + add[None, :, None], 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


# ───────────────────────── backgrounds ─────────────────────────
BACKGROUNDS = ['wood desk', 'gray carpet', 'concrete', 'white laminate', 'dark lab bench', 'lawn',
               'library table', 'tile floor', 'gray laminate']


def lowfreq(rng, n, amp):
    a = rng.normal(0, 1, (n, n)).astype(np.float32)
    a = (a - a.min()) / (np.ptp(a) + 1e-6)
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)
    return (np.asarray(im, dtype=np.float32) / 255 - 0.5) * amp


def background(kind, rng):
    y = np.arange(S, dtype=np.float32)[:, None]
    x = np.arange(S, dtype=np.float32)[None, :]
    if kind in ('wood desk', 'library table'):
        base = np.array([156, 110, 72] if kind == 'wood desk' else [196, 160, 112], np.float32)
        g = np.sin((y + np.sin(x / 120) * 25) / 6.0) * 9 + np.sin(y / 31.0 + x / 400) * 9
        img = base + g[..., None] + lowfreq(rng, 6, 30)[..., None] + rng.normal(0, 3, (S, S, 1))
    elif kind == 'gray carpet':
        img = np.array([98, 101, 110], np.float32) + rng.normal(0, 12, (S, S, 1)) + lowfreq(rng, 10, 14)[..., None]
    elif kind == 'concrete':
        img = (np.array([172, 170, 164], np.float32) + rng.normal(0, 7, (S, S, 1))
               + lowfreq(rng, 12, 26)[..., None] + lowfreq(rng, 40, 10)[..., None])
    elif kind == 'white laminate':
        img = np.array([229, 227, 221], np.float32) + rng.normal(0, 2.5, (S, S, 1)) + lowfreq(rng, 4, 10)[..., None]
    elif kind == 'dark lab bench':
        img = np.array([50, 54, 58], np.float32) + rng.normal(0, 4, (S, S, 1)) + lowfreq(rng, 5, 12)[..., None]
    elif kind == 'lawn':
        img = (np.array([78, 118, 58], np.float32) + rng.normal(0, 16, (S, S, 3)) * np.array([0.8, 1, 0.6])
               + lowfreq(rng, 14, 30)[..., None])
    elif kind == 'gray laminate':
        a = rng.normal(0, 1, (S // 3, 20)).astype(np.float32)
        a = (a - a.min()) / (np.ptp(a) + 1e-6)
        st = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC), np.float32) / 255
        img = np.array([150, 150, 147], np.float32) + (st[..., None] - 0.5) * 95 + rng.normal(0, 4, (S, S, 1))
    else:  # tile floor
        img = np.array([205, 200, 190], np.float32) + rng.normal(0, 4, (S, S, 1)) + lowfreq(rng, 8, 14)[..., None]
        grout = ((np.mod(x, 256) < 6) | (np.mod(y, 256) < 6)).astype(np.float32)
        img = img - grout[..., None] * 60
    img = np.broadcast_to(img, (S, S, 3)).copy()
    r2 = ((x - S / 2) ** 2 + (y - S / 2) ** 2) / (S / 2) ** 2
    img *= (1 - 0.16 * r2)[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB')


def _coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float))


def compose(bg, obj, ang, zoom=1.0, persp=0.0, rr=None):
    if zoom != 1.0:
        c = S / 2
        obj = obj.transform((S, S), Image.AFFINE, (1 / zoom, 0, c - c / zoom, 0, 1 / zoom, c - c / zoom), Image.BICUBIC)
    if persp and rr is not None:
        src = [(0, 0), (S, 0), (S, S), (0, S)]
        dst = [(x + rr.uniform(-persp, persp) * S, y + rr.uniform(-persp, persp) * S) for x, y in src]
        obj = obj.transform((S, S), Image.PERSPECTIVE, tuple(_coeffs(dst, src)), Image.BICUBIC)
    obj = obj.rotate(ang, resample=Image.BICUBIC, center=(S / 2, S / 2))
    a = obj.getchannel('A')
    sa = a.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.5))
    sl = Image.new('RGBA', (S, S), (12, 10, 18, 0))
    sl.putalpha(sa)
    shadow = layer()
    shadow.paste(sl, (16, 22))
    out = bg.convert('RGBA')
    out.alpha_composite(shadow)
    out.alpha_composite(obj)
    bb = a.point(lambda v: 255 if v > 60 else 0).getbbox()
    bb = tuple(int(round(b * OUT / S)) for b in bb)
    return out.convert('RGB').resize((OUT, OUT), Image.LANCZOS), bb


# ───────────────────────── 1. water bottle ─────────────────────────
def water_bottle(v, rng):
    L = layer(); d = ImageDraw.Draw(L)
    s = v['s']; col = C(v['c'], v.get('alpha', 255)); cap = C(v.get('cap', '#232323'))
    H = 620 * s; W = v['w'] * s; nw = v['nw'] * s; ch = v.get('ch', 90) * s; shh = v.get('shh', 60) * s
    top = Y - H / 2; bot = Y + H / 2; by = top + ch + shh
    r = min(W * 0.22, 46 * s)
    d.rounded_rectangle([X - W / 2, by, X + W / 2, bot], radius=r, fill=col, corners=(False, False, True, True))
    pts_l, pts_r = [], []
    for i in range(21):
        t = i / 20
        half = nw / 2 + (W - nw) / 2 * (0.5 - 0.5 * math.cos(math.pi * t))
        yy = top + ch - 2 + (shh + 4) * t
        pts_l.append((X - half, yy)); pts_r.append((X + half, yy))
    d.polygon(pts_l + pts_r[::-1], fill=col)
    if v.get('label'):
        lc = C(v['label'])
        y0 = by + (bot - by) * 0.28; y1 = by + (bot - by) * 0.62
        d.rectangle([X - W / 2, y0, X + W / 2, y1], fill=lc)
        if v.get('label2'):
            d.rectangle([X - W / 2, y0 + (y1 - y0) * 0.35, X + W / 2, y0 + (y1 - y0) * 0.6], fill=C(v['label2']))
    if v.get('sleeve'):
        sc = C(v['sleeve'])
        d.rounded_rectangle([X - W / 2 - 6 * s, by + (bot - by) * 0.35, X + W / 2 + 6 * s, bot - (bot - by) * 0.12],
                            radius=18 * s, fill=sc)
        for k in range(5):
            yy = by + (bot - by) * (0.42 + k * 0.08)
            d.line([(X - W / 2, yy), (X + W / 2, yy)], fill=sh(sc, 0.8), width=int(6 * s))
    if v.get('marks'):
        for k in range(6):
            yy = by + (bot - by) * (0.15 + k * 0.13)
            d.line([(X + W / 2 - 50 * s, yy), (X + W / 2 - 14 * s, yy)], fill=C('#bbbbbb'), width=int(6 * s))
    if v.get('handle'):
        d.arc([X + W / 2 - 50 * s, by + 10 * s, X + W / 2 + 90 * s, by + (bot - by) * 0.55], 270, 90,
              fill=sh(cap, 1.1), width=int(26 * s))
    capstyle = v.get('capstyle', 'screw')
    cw = nw + 16 * s
    if capstyle == 'sport':
        d.rounded_rectangle([X - cw / 2, top + ch * 0.45, X + cw / 2, top + ch], radius=10 * s, fill=cap)
        d.polygon([(X - cw * 0.28, top + ch * 0.47), (X + cw * 0.28, top + ch * 0.47),
                   (X + cw * 0.14, top), (X - cw * 0.14, top)], fill=sh(cap, 1.25))
    else:
        d.rounded_rectangle([X - cw / 2, top + (ch * 0.3 if capstyle == 'loop' else 0), X + cw / 2, top + ch],
                            radius=14 * s, fill=cap)
        for k in range(1, 8):
            xx = X - cw / 2 + cw * k / 8
            d.line([(xx, top + ch * 0.45), (xx, top + ch - 8 * s)], fill=sh(cap, 0.75), width=max(2, int(4 * s)))
    if capstyle == 'loop':
        d.ellipse([X - cw * 0.32, top - ch * 0.45, X + cw * 0.32, top + ch * 0.55], outline=cap, width=int(20 * s))
    if capstyle == 'straw':
        d.line([(X + cw * 0.1, top + 10 * s), (X + cw * 0.38, top - ch * 1.1)], fill=sh(cap, 1.15), width=int(22 * s))
    if capstyle == 'flip':
        d.rounded_rectangle([X + cw / 2 - 10 * s, top + ch * 0.1, X + cw / 2 + 34 * s, top + ch * 0.75],
                            radius=10 * s, fill=sh(cap, 1.2))
    return light(L, 0.32, 55, 0.25, 0.06)


BOTTLE_VARIANTS = [
    dict(name='insulated steel, carry loop', size='L', shape='straight cylinder', color='steel blue',
         s=0.98, c='#3b6ea8', w=190, nw=150, cap='#2b2b2b', capstyle='loop', shh=40),
    dict(name='slim flip-top', size='M', shape='slim cylinder', color='mint', s=1.0, c='#7fc8a9', w=140, nw=122,
         cap='#1f1f1f', capstyle='flip', shh=30),
    dict(name='wide-mouth chunky', size='M', shape='wide cylinder', color='coral', s=0.78, c='#e4572e', w=250,
         nw=205, cap='#f2f2f2', capstyle='loop', shh=36),
    dict(name='disposable plastic', size='S', shape='tapered neck', color='clear/blue label', s=0.8, c='#cfe6f5',
         alpha=215, w=150, nw=58, ch=60, shh=120, cap='#2a6fdb', label='#2a6fdb', label2='#ffffff'),
    dict(name='straw-lid tumbler', size='M', shape='wide cylinder', color='lavender', s=0.86, c='#a99ad8', w=210,
         nw=196, cap='#ffffff', capstyle='straw', shh=20),
    dict(name='sport squeeze bottle', size='S', shape='tapered neck', color='yellow', s=0.74, c='#f2c230', w=170,
         nw=96, cap='#1d3c78', capstyle='sport', shh=70),
    dict(name='glass with silicone sleeve', size='M', shape='straight cylinder', color='clear/green sleeve',
         s=0.84, c='#d9e4e1', alpha=225, w=160, nw=112, cap='#3a3a3a', sleeve='#4c9a6a', shh=50),
    dict(name='64 oz jug with handle', size='XL', shape='wide cylinder + handle', color='matte black', s=1.12,
         c='#2b2b2b', w=255, nw=160, cap='#555555', capstyle='screw', shh=70, marks=True, handle=True),
]


# ───────────────────────── 2. keys ─────────────────────────
def key_img(length, metal, rr, cap=None, head='round'):
    Ls = int(length * 2.3); Cc = Ls // 2
    K = Image.new('RGBA', (Ls, Ls), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    r = length * 0.2; bl = length * 0.78; bh = r * 0.62
    m = C(metal); dk = sh(m, 0.68); lt = sh(m, 1.35)
    x0 = Cc + r * 0.55; x1 = Cc + r + bl
    d.rectangle([x0, Cc - bh / 2, x1 - bh * 0.5, Cc + bh / 2], fill=m)
    d.polygon([(x1 - bh * 0.5, Cc - bh / 2), (x1, Cc - bh * 0.05), (x1, Cc + bh * 0.1), (x1 - bh * 0.5, Cc + bh / 2)],
              fill=m)
    tx0 = x0 + bl * 0.2; n = 6; tw = (x1 - bh * 0.6 - tx0) / n
    pts = [(tx0, Cc - bh / 2)]
    for i in range(n):
        pts.append((tx0 + i * tw + tw * 0.5, Cc - bh / 2 - bh * rr.uniform(0.15, 0.55)))
        pts.append((tx0 + (i + 1) * tw, Cc - bh / 2))
    d.polygon(pts, fill=m)
    d.rectangle([x0, Cc - bh * 0.75, x0 + bh * 0.35, Cc + bh * 0.75], fill=m)
    d.line([(x0 + bh * 0.5, Cc + bh * 0.08), (x1 - bh * 0.6, Cc + bh * 0.08)], fill=dk, width=max(2, int(bh * 0.12)))
    d.line([(x0 + bh * 0.5, Cc - bh * 0.25), (x1 - bh * 0.7, Cc - bh * 0.25)], fill=lt, width=max(2, int(bh * 0.08)))
    hx = Cc - r * 0.48
    if cap:
        cc = C(cap)
        d.rounded_rectangle([Cc - r * 1.25, Cc - r * 1.05, Cc + r * 0.95, Cc + r * 1.05], radius=r * 0.6, fill=cc)
        d.ellipse([Cc - r * 0.2, Cc - r * 0.55, Cc + r * 0.6, Cc + r * 0.55], fill=sh(cc, 0.8))
    elif head == 'square':
        d.rounded_rectangle([Cc - r * 1.05, Cc - r * 0.95, Cc + r * 0.8, Cc + r * 0.95], radius=r * 0.3, fill=m)
    elif head == 'bow':
        d.ellipse([Cc - r * 1.15, Cc - r * 0.9, Cc + r * 0.85, Cc + r * 0.9], fill=m)
    else:
        d.ellipse([Cc - r, Cc - r, Cc + r, Cc + r], fill=m)
        d.arc([Cc - r * 0.85, Cc - r * 0.85, Cc + r * 0.85, Cc + r * 0.85], 200, 290, fill=lt, width=max(2, int(r * 0.1)))
    hr = r * 0.22
    d.ellipse([hx - hr, Cc - hr, hx + hr, Cc + hr], fill=(0, 0, 0, 0))
    return K, (hx, Cc)


def fob_img(w, h, color, buttons=3, kind='car'):
    Ls = int(max(w, h) * 2.4); Cc = Ls // 2
    K = Image.new('RGBA', (Ls, Ls), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    c = C(color)
    x0 = Cc + 10
    if kind == 'car':
        d.rounded_rectangle([x0, Cc - h / 2, x0 + w, Cc + h / 2], radius=h * 0.45, fill=c)
        for i in range(buttons):
            bx = x0 + w * (0.32 + i * 0.22)
            d.ellipse([bx - h * 0.15, Cc - h * 0.15, bx + h * 0.15, Cc + h * 0.15], fill=sh(c, 1.6))
        d.rounded_rectangle([Cc - 30, Cc - h * 0.22, x0 + 18, Cc + h * 0.22], radius=10, fill=C('#9a9a9a'))
    else:  # teardrop dorm fob
        d.ellipse([x0 + w * 0.25, Cc - h / 2, x0 + w, Cc + h / 2], fill=c)
        d.polygon([(Cc - 20, Cc), (x0 + w * 0.55, Cc - h / 2), (x0 + w * 0.55, Cc + h / 2)], fill=c)
        d.ellipse([x0 + w * 0.45, Cc - h * 0.2, x0 + w * 0.85, Cc + h * 0.2], outline=sh(c, 0.7), width=6)
    hr = 12
    d.ellipse([Cc - 12 - hr, Cc - hr, Cc - 12 + hr, Cc + hr], fill=(0, 0, 0, 0))
    return K, (Cc - 12, Cc)


def place(L, img_anchor, x, y, ang):
    img, (ax, ay) = img_anchor
    img = img.rotate(ang, resample=Image.BICUBIC, center=(ax, ay))
    over(L, img, x - ax, y - ay)


def keys(v, rng):
    L = layer(); d = ImageDraw.Draw(L)
    rr = random.Random(v['seed'])
    s = v['s']; R = v.get('ring', 70) * s
    rx, ry = X - 120 * s, Y - 60 * s
    if v.get('lanyard'):
        lc = C(v['lanyard'])
        d.line(bez((rx, ry), (rx - 260, ry - 300), (rx + 200, ry - 420), (rx + 330, ry - 260)), fill=lc,
               width=int(46 * s), joint='curve')
        d.line(bez((rx, ry), (rx - 230, ry - 260), (rx + 180, ry - 380), (rx + 330, ry - 260)), fill=sh(lc, 0.75),
               width=int(4 * s), joint='curve')
        d.rounded_rectangle([rx - 22 * s, ry - 70 * s, rx + 22 * s, ry - 20 * s], radius=8, fill=C('#8a8a8a'))
    items = v['items']
    n = len(items)
    for i, it in enumerate(items):
        th = math.radians(v.get('spread_start', -40) + i * v.get('spread', 38))
        hx, hy = rx + R * math.cos(th), ry - R * math.sin(th)
        deg = math.degrees(th) + rr.uniform(-6, 6)
        if it[0] == 'key':
            place(L, key_img(it[1] * s, it[2], rr, cap=it[3] if len(it) > 3 else None,
                             head=it[4] if len(it) > 4 else 'round'), hx, hy, deg)
        elif it[0] in ('car', 'dorm'):
            place(L, fob_img(it[1] * s, it[2] * s, it[3], kind=it[0]), hx, hy, deg)
        elif it[0] == 'charm':
            cx, cy = hx + 70 * s * math.cos(th), hy - 70 * s * math.sin(th)
            d.line([(hx, hy), (cx, cy)], fill=C('#aaaaaa'), width=int(6 * s))
            rc = it[1] * s
            if it[3] == 'star':
                pts = []
                for k in range(10):
                    a = math.pi / 2 + k * math.pi / 5
                    rad = rc if k % 2 == 0 else rc * 0.45
                    pts.append((cx + rad * math.cos(a), cy - rad * math.sin(a)))
                d.polygon(pts, fill=C(it[2]))
            else:
                d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=C(it[2]))
                d.ellipse([cx - rc * 0.55, cy - rc * 0.55, cx + rc * 0.55, cy + rc * 0.55], fill=sh(C(it[2]), 1.4))
    if n > 1 or v.get('ring_single'):
        d.ellipse([rx - R, ry - R, rx + R, ry + R], outline=C('#c9c9c9'), width=max(4, int(10 * s)))
        d.arc([rx - R, ry - R, rx + R, ry + R], 120, 200, fill=C('#f2f2f2'), width=max(2, int(4 * s)))
    return light(L, 0.12)


KEY_VARIANTS = [
    dict(name='single brass house key', size='S', shape='round-head key', color='brass', s=1.6, ring=0, seed=1,
         items=[('key', 230, '#c8a046')], spread_start=-20),
    dict(name='two keys on split ring', size='M', shape='ring + 2 keys', color='silver/brass', s=1.15, seed=2,
         items=[('key', 230, '#bfc3c7'), ('key', 200, '#c8a046', None, 'square')]),
    dict(name='car fob + key', size='M', shape='fob + key', color='black/silver', s=1.1, seed=3,
         items=[('car', 190, 90, '#232323'), ('key', 210, '#bfc3c7')]),
    dict(name='three keys with color caps', size='M', shape='ring + 3 capped keys', color='multi', s=1.05, seed=4,
         items=[('key', 220, '#bfc3c7', '#d6336c'), ('key', 220, '#bfc3c7', '#1c7ed6'),
                ('key', 210, '#c8a046', '#37b24d')], spread_start=-60),
    dict(name='keys on campus lanyard', size='L', shape='lanyard + ring', color='red lanyard', s=1.0, seed=5,
         lanyard='#c92a2a', items=[('key', 220, '#bfc3c7'), ('key', 200, '#c8a046')], spread_start=-70),
    dict(name='tiny mailbox key', size='XS', shape='small bow key', color='silver', s=1.15, ring=40, seed=6,
         ring_single=True, items=[('key', 200, '#d0d4d8', None, 'bow')], spread_start=-30),
    dict(name='keys with charm', size='M', shape='ring + keys + charm', color='silver/yellow charm', s=1.0, seed=7,
         items=[('key', 220, '#bfc3c7'), ('charm', 52, '#fcc419', 'star'), ('key', 200, '#bfc3c7', None, 'square')],
         spread_start=-50, spread=55),
    dict(name='dorm access fob + key', size='M', shape='teardrop fob + key', color='blue fob', s=1.1, seed=8,
         items=[('dorm', 150, 100, '#1864ab'), ('key', 210, '#c8a046')]),
]


# ───────────────────────── 3. student ID card ─────────────────────────
def id_card_img(w, h, header, vertical=False, back=False, rr=None, faded=0.0, hologram=False):
    pad = 20
    K = Image.new('RGBA', (int(w + 2 * pad), int(h + 2 * pad)), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    base = C('#f6f5f1'); hc = C(header)
    d.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=base)
    gray = C('#9aa0a6'); dgray = C('#5f6368')
    if back:
        d.rectangle([x0, y0 + h * 0.12, x1, y0 + h * 0.3], fill=C('#1e1e1e'))
        d.rectangle([x0 + w * 0.06, y0 + h * 0.4, x0 + w * 0.65, y0 + h * 0.55], fill=C('#ffffff'),
                    outline=gray, width=2)
        for k in range(6):
            d.line([(x0 + w * 0.08, y0 + h * 0.42 + k * 9), (x0 + w * 0.63, y0 + h * 0.42 + k * 9)],
                   fill=C('#dde3ea'), width=2)
        for k in range(3):
            d.rounded_rectangle([x0 + w * 0.06, y0 + h * (0.62 + k * 0.07), x0 + w * (0.5 - k * 0.08),
                                 y0 + h * (0.62 + k * 0.07) + 9], radius=4, fill=gray)
        bx0 = x0 + w * 0.55
        for k in range(36):
            ww = rr.choice([2, 3, 5])
            d.rectangle([bx0 + k * 6.5, y0 + h * 0.66, bx0 + k * 6.5 + ww, y0 + h * 0.9], fill=C('#111111'))
    else:
        hh = h * (0.17 if vertical else 0.24)
        d.rounded_rectangle([x0, y0, x1, y0 + hh], radius=24, fill=hc, corners=(True, True, False, False))
        d.ellipse([x0 + 18, y0 + hh * 0.18, x0 + 18 + hh * 0.64, y0 + hh * 0.82], fill=C('#ffffff', 230))
        d.rounded_rectangle([x0 + 30 + hh * 0.64, y0 + hh * 0.35, x0 + w * 0.75, y0 + hh * 0.6], radius=6,
                            fill=C('#ffffff', 235))
        if vertical:
            pw, ph = w * 0.5, h * 0.36
            px0, py0 = x0 + (w - pw) / 2, y0 + hh + h * 0.05
        else:
            pw, ph = w * 0.27, h * 0.52
            px0, py0 = x0 + w * 0.05, y0 + hh + h * 0.08
        d.rectangle([px0, py0, px0 + pw, py0 + ph], fill=C('#b9cbe0'))
        hr = pw * 0.2
        d.chord([px0 + pw * 0.12, py0 + ph * 0.62, px0 + pw * 0.88, py0 + ph * 1.35], 180, 360, fill=C('#55657a'))
        d.ellipse([px0 + pw / 2 - hr, py0 + ph * 0.2, px0 + pw / 2 + hr, py0 + ph * 0.2 + 2 * hr], fill=C('#55657a'))
        if vertical:
            tx0, ty0, tw = x0 + w * 0.12, py0 + ph + h * 0.05, w * 0.76
        else:
            tx0, ty0, tw = px0 + pw + w * 0.05, py0 + 6, w * 0.55
        for k, frac in enumerate([0.9, 0.65, 0.75, 0.45]):
            d.rounded_rectangle([tx0, ty0 + k * h * 0.075, tx0 + tw * frac, ty0 + k * h * 0.075 + h * 0.035],
                                radius=5, fill=dgray if k == 0 else gray)
        by0 = y1 - h * 0.14
        bx0 = (x0 + w * 0.12) if vertical else (tx0)
        for k in range(30):
            ww = rr.choice([2, 3, 5])
            d.rectangle([bx0 + k * 7, by0, bx0 + k * 7 + ww, y1 - h * 0.05], fill=C('#111111'))
        if hologram:
            for k, col in enumerate(['#ff8787', '#ffd43b', '#69db7c', '#74c0fc', '#b197fc']):
                d.arc([x1 - w * 0.2, y1 - h * 0.35, x1 - w * 0.05, y1 - h * 0.12], 30 + k * 60, 90 + k * 60,
                      fill=C(col, 200), width=8)
        if vertical:
            d.rounded_rectangle([x0 + w / 2 - 34, y0 + hh + 8, x0 + w / 2 + 34, y0 + hh + 24], radius=8,
                                fill=(0, 0, 0, 0))
    if faded:
        arr = np.asarray(K).astype(np.float32)
        arr[..., :3] = arr[..., :3] * (1 - faded) + np.array([235, 228, 210]) * faded
        K = Image.fromarray(arr.astype(np.uint8), 'RGBA')
        d = ImageDraw.Draw(K)
        d.line([(x0 + w * 0.62, y0), (x0 + w * 0.58, y1)], fill=C('#d8d2c4'), width=4)
    return K


def id_card(v, rng):
    L = layer(); d = ImageDraw.Draw(L)
    rr = random.Random(v['seed']); s = v['s']
    vert = v.get('vertical', False)
    w, h = (350 * s, 555 * s) if vert else (560 * s, 352 * s)
    K = id_card_img(w, h, v['c'], vert, v.get('back', False), rr, v.get('faded', 0), v.get('holo', False))
    return card_scene(v, K, w, h)


def card_scene(v, K, w, h):
    L = layer(); d = ImageDraw.Draw(L)
    cx, cy = X, Y + (70 if (v.get('lanyard') or v.get('reel')) else 0)
    if v.get('lanyard'):
        lc = C(v['lanyard'])
        top = cy - h / 2
        d.line([(cx - 40, top - 10), (cx - 200, top - 330)], fill=lc, width=40)
        d.line([(cx + 40, top - 10), (cx + 200, top - 330)], fill=lc, width=40)
        d.rounded_rectangle([cx - 26, top - 60, cx + 26, top + 6], radius=8, fill=C('#9a9a9a'))
    if v.get('reel'):
        top = cy - h / 2
        d.line([(cx, top - 150), (cx, top + 10)], fill=C('#333333'), width=4)
        d.ellipse([cx - 70, top - 290, cx + 70, top - 150], fill=C(v['reel']))
        d.ellipse([cx - 40, top - 260, cx + 40, top - 180], fill=sh(C(v['reel']), 1.3))
        d.rounded_rectangle([cx - 25, top - 30, cx + 25, top + 18], radius=6, fill=C('#cfcfcf'))
    over(L, K, cx - K.size[0] / 2, cy - K.size[1] / 2)
    if v.get('sleeve'):
        sl = layer(); sd = ImageDraw.Draw(sl)
        sd.rounded_rectangle([cx - w / 2 - 22, cy - h / 2 - 50, cx + w / 2 + 22, cy + h / 2 + 22], radius=26,
                             fill=(225, 238, 248, 70), outline=(200, 215, 230, 200), width=5)
        sd.rounded_rectangle([cx - 60, cy - h / 2 - 38, cx + 60, cy - h / 2 - 20], radius=8, fill=(90, 90, 90, 160))
        L.alpha_composite(sl)
    if v.get('keyring'):
        d = ImageDraw.Draw(L)
        top = cy - h / 2
        d.ellipse([cx - 75, top - 120, cx + 75, top + 50], outline=C('#c9c9c9'), width=12)
        d.arc([cx - 75, top - 120, cx + 75, top + 50], 130, 220, fill=C('#f2f2f2'), width=4)
        kimg = key_img(220, '#bfc3c7', random.Random(5))
        place(L, kimg, cx - 70, top - 70, 160)
    return light(L, 0.08)


ID_VARIANTS = [
    dict(name='other-school student ID', size='M', shape='CR80 landscape', color='navy header', s=1.0, c='#1c3d7a', seed=1),
    dict(name='portrait ID on lanyard', size='M', shape='portrait + lanyard', color='blue header', s=0.95,
         c='#1864ab', vertical=True, lanyard='#1864ab', seed=2),
    dict(name='ID in clear badge sleeve', size='M', shape='landscape in sleeve', color='green header', s=0.95,
         c='#2b8a3e', sleeve=True, seed=3),
    dict(name='ID on retractable badge reel', size='M', shape='portrait + reel', color='purple header', s=0.85,
         c='#5f3dc4', vertical=True, reel='#5f3dc4', seed=4),
    dict(name='ID card back (mag stripe)', size='M', shape='landscape, back side', color='white/black stripe',
         s=1.0, c='#000000', back=True, seed=5),
    dict(name='large temp visitor badge', size='L', shape='oversized landscape', color='orange header', s=1.25,
         c='#e8590c', seed=6),
    dict(name='state driver license', size='M', shape='landscape + hologram', color='teal header', s=1.0,
         c='#0b7285', holo=True, seed=7),
    dict(name='worn, bent ID', size='M', shape='landscape, faded/creased', color='maroon header', s=1.0,
         c='#862e43', faded=0.35, seed=8),
]


# ───────────────────────── 4. earbuds ─────────────────────────
def stem_bud(scale, color, flip=False):
    Ls = int(400 * scale); K = Image.new('RGBA', (Ls, Ls), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    c = C(color); cx = Ls / 2
    d.rounded_rectangle([cx - 18 * scale, Ls * 0.38, cx + 18 * scale, Ls * 0.92], radius=18 * scale, fill=c)
    d.ellipse([cx - 62 * scale, Ls * 0.12, cx + 62 * scale, Ls * 0.46], fill=c)
    d.ellipse([cx - 30 * scale, Ls * 0.16, cx + 18 * scale, Ls * 0.27], fill=C('#4a4a4a'))
    d.ellipse([cx - 9 * scale, Ls * 0.86, cx + 9 * scale, Ls * 0.9], fill=C('#9a9a9a'))
    if flip:
        K = K.transpose(Image.FLIP_LEFT_RIGHT)
    return K


def round_bud(scale, color, tip):
    Ls = int(260 * scale); K = Image.new('RGBA', (Ls, Ls), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    c = C(color); cx = cy = Ls / 2
    d.ellipse([cx - 80 * scale, cy - 70 * scale, cx + 80 * scale, cy + 70 * scale], fill=c)
    d.ellipse([cx - 40 * scale, cy - 35 * scale, cx + 40 * scale, cy + 35 * scale], fill=sh(c, 1.35))
    d.ellipse([cx + 40 * scale, cy - 45 * scale, cx + 115 * scale, cy + 45 * scale], fill=C(tip))
    return K


def earbuds(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']; c = C(v['c'])
    kind = v['kind']
    if kind in ('pill', 'square', 'puck', 'egg'):
        W, H = {'pill': (300, 230), 'square': (270, 260), 'puck': (280, 280), 'egg': (330, 250)}[kind]
        W *= s; H *= s
        if kind in ('puck', 'egg'):
            d.ellipse([X - W / 2, Y - H / 2, X + W / 2, Y + H / 2], fill=c)
            d.arc([X - W / 2, Y - H / 2 - H * 0.25, X + W / 2, Y + H / 2 - H * 0.25], 20, 160, fill=sh(c, 0.7),
                  width=max(3, int(5 * s)))
        else:
            rad = H * (0.42 if kind == 'pill' else 0.28)
            d.rounded_rectangle([X - W / 2, Y - H / 2, X + W / 2, Y + H / 2], radius=rad, fill=c)
            d.line([(X - W / 2 + 6, Y - H * 0.12), (X + W / 2 - 6, Y - H * 0.12)], fill=sh(c, 0.75),
                   width=max(3, int(5 * s)))
        d.ellipse([X - 7 * s, Y + H * 0.08, X + 7 * s, Y + H * 0.08 + 14 * s], fill=C('#40c057'))
        if v.get('cover'):
            cc = C(v['cover'])
            Lc = layer(); dc = ImageDraw.Draw(Lc)
            rad = H * 0.42
            dc.rounded_rectangle([X - W / 2 - 14, Y - H / 2 - 14, X + W / 2 + 14, Y + H / 2 + 14], radius=rad + 10,
                                 fill=cc)
            dc.line([(X - W / 2, Y - H * 0.12), (X + W / 2, Y - H * 0.12)], fill=sh(cc, 0.75), width=6)
            dc.ellipse([X - 10, Y + H * 0.06, X + 10, Y + H * 0.06 + 20], fill=sh(cc, 1.2))
            dc.ellipse([X - W / 2 - 120, Y - H / 2 - 120, X - W / 2 + 10, Y - H / 2 + 20], outline=C('#adb5bd'),
                       width=16)
            L = Lc
    elif kind == 'stems':
        over(L, stem_bud(1.2 * s, v['c']).rotate(18, resample=Image.BICUBIC), X - 260 * s, Y - 240 * s)
        over(L, stem_bud(1.2 * s, v['c'], flip=True).rotate(-28, resample=Image.BICUBIC), X - 20 * s, Y - 210 * s)
    elif kind == 'round':
        over(L, round_bud(1.25 * s, v['c'], '#3d3d3d').rotate(30, resample=Image.BICUBIC), X - 250 * s, Y - 180 * s)
        over(L, round_bud(1.25 * s, v['c'], '#3d3d3d').rotate(200, resample=Image.BICUBIC), X - 20 * s, Y - 80 * s)
    elif kind == 'wired':
        wc = C(v['c'])
        pA, pB, pJ, pP = (X - 170, Y - 220), (X + 130, Y - 240), (X - 10, Y + 20), (X + 180, Y + 290)
        d.line(bez(pA, (X - 250, Y - 60), (X - 120, Y + 40), pJ), fill=wc, width=8, joint='curve')
        d.line(bez(pB, (X + 260, Y - 120), (X + 90, Y - 40), pJ), fill=wc, width=8, joint='curve')
        d.line(bez(pJ, (X + 40, Y + 260), (X - 220, Y + 200), (X - 120, Y + 110)), fill=wc, width=9, joint='curve')
        d.line(bez((X - 120, Y + 110), (X - 20, Y + 30), (X + 300, Y + 120), pP), fill=wc, width=9, joint='curve')
        d.rounded_rectangle([pP[0] - 18, pP[1] - 10, pP[0] + 18, pP[1] + 60], radius=8, fill=wc)
        d.rectangle([pP[0] - 6, pP[1] + 60, pP[0] + 6, pP[1] + 110], fill=C('#c0c0c0'))
        d.rounded_rectangle([pJ[0] - 14, pJ[1] - 30, pJ[0] + 14, pJ[1] + 22], radius=8, fill=wc)
        for p in (pA, pB):
            d.ellipse([p[0] - 52, p[1] - 52, p[0] + 52, p[1] + 52], fill=wc)
            d.ellipse([p[0] - 28, p[1] - 28, p[0] + 28, p[1] + 28], fill=C('#5c5c5c'))
    return light(L, 0.25, 35, 0.3, 0.08)


EARBUD_VARIANTS = [
    dict(name='pill-shaped charging case', size='S', shape='rounded rectangle', color='white', s=1.2, c='#f4f4f2',
         kind='pill'),
    dict(name='square charging case', size='S', shape='squircle', color='black', s=1.15, c='#272727', kind='square'),
    dict(name='round puck case', size='S', shape='circle', color='charcoal', s=1.1, c='#3e4247', kind='puck'),
    dict(name='case in silicone cover + carabiner', size='M', shape='rounded rect + clip', color='pink cover',
         s=1.15, c='#f4f4f2', kind='pill', cover='#f783ac'),
    dict(name='loose stem earbuds (pair)', size='XS', shape='stem buds', color='white', s=1.0, c='#f4f4f2',
         kind='stems'),
    dict(name='loose round earbuds (pair)', size='XS', shape='round buds', color='black', s=1.0, c='#2a2a2a',
         kind='round'),
    dict(name='wired earbuds, tangled', size='S', shape='buds + cable + 3.5mm plug', color='white', s=1.0,
         c='#f1f1ef', kind='wired'),
    dict(name='large egg clamshell case', size='M', shape='oval', color='navy', s=1.25, c='#1f3a68', kind='egg'),
]


# ───────────────────────── 5. headphones ─────────────────────────
def headphones(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']
    c = C(v['c']); cush = C(v.get('cush', '#222222')); acc = C(v.get('acc', v['c']))
    R = 250 * s; cy = Y + 20 * s
    if v.get('kind') == 'neckband':
        d.arc([X - R, cy - R * 0.9, X + R, cy + R * 0.9], 10, 170, fill=c, width=int(48 * s))
        for sgn in (-1, 1):
            ex, ey = X + sgn * R * 0.98, cy + R * 0.15
            d.line(bez((ex, ey), (ex + sgn * 20, ey - 200), (ex - sgn * 80, ey - 250), (ex - sgn * 60, ey - 330)),
                   fill=C('#333333'), width=6)
            bx, by = ex - sgn * 60, ey - 345
            d.ellipse([bx - 40, by - 34, bx + 40, by + 34], fill=acc)
        return light(L, 0.2)
    folded = v.get('folded', False)
    cupw, cuph = v.get('cup', (150, 200))
    cupw *= s; cuph *= s
    bw = int(v.get('bw', 36) * s)
    d.arc([X - R, cy - R, X + R, cy + R], 190, 350, fill=c, width=bw)
    if v.get('pad'):
        d.arc([X - R + bw, cy - R + bw, X + R - bw, cy + R - bw], 230, 310, fill=C(v['pad']), width=int(30 * s))
        for k in range(7):
            a = math.radians(232 + k * 11)
            rr_ = R - bw - 15 * s
            d.ellipse([X + rr_ * math.cos(a) - 4, cy + rr_ * math.sin(a) - 4, X + rr_ * math.cos(a) + 4,
                       cy + rr_ * math.sin(a) + 4], fill=sh(C(v['pad']), 0.75))
    for sgn in (-1, 1):
        if folded:
            ex, ey = X + sgn * R * 0.42, cy + R * 0.38
        else:
            ex, ey = X + sgn * (R - bw * 0.2), cy + R * 0.2
        ax, ay = X + sgn * (R - bw / 2) * math.cos(math.radians(10)), cy - (R - bw / 2) * math.sin(math.radians(10))
        d.line([(ax, ay), (ex, ey - cuph * 0.35)], fill=sh(c, 0.85), width=int(18 * s))
        d.ellipse([ex - cupw / 2, ey - cuph / 2, ex + cupw / 2, ey + cuph / 2], fill=acc)
        d.ellipse([ex - cupw * 0.32, ey - cuph * 0.34, ex + cupw * 0.32, ey + cuph * 0.34], fill=sh(acc, 1.18))
        inner = ex - sgn * cupw * 0.5
        d.ellipse([inner - cupw * 0.16, ey - cuph * 0.47, inner + cupw * 0.16, ey + cuph * 0.47], fill=cush)
    if v.get('mic'):
        ex, ey = X - (R - bw * 0.2), cy + R * 0.2
        d.line(bez((ex, ey + 40), (ex + 10, ey + 180), (ex + 120, ey + 230), (ex + 210, ey + 200)),
               fill=C('#2b2b2b'), width=int(14 * s), joint='curve')
        d.ellipse([ex + 190, ey + 180, ex + 240, ey + 220], fill=C(v['mic']))
    return light(L, 0.2, 30, 0.35, 0.07)


HEADPHONE_VARIANTS = [
    dict(name='over-ear, large', size='L', shape='over-ear', color='black', s=1.1, c='#1f1f1f', acc='#2b2b2b',
         cush='#3a3a3a'),
    dict(name='over-ear, white', size='L', shape='over-ear', color='white', s=1.05, c='#ecebe7', acc='#f4f3ef',
         cush='#b9b6ae'),
    dict(name='on-ear, compact', size='M', shape='on-ear (small round cups)', color='rose gold', s=0.85,
         c='#d9a38e', acc='#e8b8a6', cush='#7a5b50', cup=(130, 150)),
    dict(name="kids' headphones", size='S', shape='on-ear, thick band', color='sky blue', s=0.72, c='#4dabf7',
         acc='#ffd43b', cush='#1971c2', cup=(150, 165), bw=56),
    dict(name='over-ear, folded', size='M', shape='folded / collapsed', color='navy', s=0.95, c='#22356b',
         acc='#2c4485', cush='#121c3a', folded=True),
    dict(name='neckband wireless', size='S', shape='U-shaped neckband', color='graphite', s=0.95, c='#3d4148',
         acc='#3d4148', kind='neckband'),
    dict(name='gaming headset with boom mic', size='L', shape='over-ear + mic boom', color='black/red', s=1.05,
         c='#1b1b1b', acc='#c92a2a', cush='#2b2b2b', mic='#c92a2a', cup=(170, 215), bw=48),
    dict(name='padded-band over-ear', size='L', shape='over-ear + padded band', color='beige', s=1.05,
         c='#cbb89a', acc='#d8c7aa', cush='#6b5a44', pad='#8f7a5a'),
]


# ───────────────────────── 6. phone ─────────────────────────
def phone(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']; c = C(v['c'])
    kind = v.get('kind', 'front')
    W, H = v.get('wh', (300, 620))
    W *= s; H *= s
    x0, y0, x1, y1 = X - W / 2, Y - H / 2, X + W / 2, Y + H / 2
    rad = W * 0.16
    if v.get('case'):
        cc = C(v['case'], v.get('case_alpha', 255))
        e = v.get('case_e', 16) * s
        d.rounded_rectangle([x0 - e, y0 - e, x1 + e, y1 + e], radius=rad + e, fill=cc)
        if v.get('rugged'):
            for (cx_, cy_) in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
                d.ellipse([cx_ - 46 * s, cy_ - 46 * s, cx_ + 46 * s, cy_ + 46 * s], fill=sh(cc, 0.6))
    if kind == 'flip':
        d.rounded_rectangle([x0, y0, x1, y1], radius=W * 0.2, fill=c)
        d.rounded_rectangle([x0 - 4, Y - 18 * s, x1 + 4, Y + 18 * s], radius=10, fill=sh(c, 0.7))
        d.rounded_rectangle([X - W * 0.32, y0 + H * 0.1, X + W * 0.32, y0 + H * 0.4], radius=18 * s,
                            fill=C('#0e0e10'))
        d.ellipse([X + W * 0.2, y0 + H * 0.04, X + W * 0.33, y0 + H * 0.04 + W * 0.13], fill=C('#1b1b1b'))
        return light(L, 0.18, 30)
    d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=c)
    if kind == 'front':
        b = 12 * s
        d.rounded_rectangle([x0 + b, y0 + b, x1 - b, y1 - b], radius=rad - b, fill=C('#0d0f14'))
        g = layer(); gd = ImageDraw.Draw(g)
        gd.polygon([(x0 + b, y0 + H * 0.15), (x1 - b, y0 + b + 4), (x1 - b, y0 + H * 0.35), (x0 + b, y0 + H * 0.6)],
                   fill=(255, 255, 255, 18))
        L.alpha_composite(g)
        d.ellipse([X - 11 * s, y0 + 28 * s, X + 11 * s, y0 + 50 * s], fill=C('#000000'))
        if v.get('cracked'):
            ox, oy = X + W * 0.15, y0 + H * 0.66
            rr = random.Random(3)
            for k in range(11):
                a = rr.uniform(0, 2 * math.pi); ln = rr.uniform(80, 260) * s
                px, py = ox, oy
                for _ in range(4):
                    nx = px + ln / 4 * math.cos(a) + rr.uniform(-12, 12)
                    ny = py + ln / 4 * math.sin(a) + rr.uniform(-12, 12)
                    nx = min(max(nx, x0 + b), x1 - b); ny = min(max(ny, y0 + b), y1 - b)
                    d.line([(px, py), (nx, ny)], fill=C('#d0d4da', 220), width=3)
                    px, py = nx, ny
            d.ellipse([ox - 14, oy - 14, ox + 14, oy + 14], fill=C('#e9ecef', 200))
    else:  # back
        m = W * 0.06
        n = v.get('lenses', 3)
        mw = W * 0.46
        d.rounded_rectangle([x0 + m, y0 + m, x0 + m + mw, y0 + m + mw * (1.0 if n == 3 else 0.62)], radius=mw * 0.22,
                            fill=sh(c, 0.85))
        lr = mw * 0.17
        spots = [(0.3, 0.28), (0.3, 0.72), (0.72, 0.5)] if n == 3 else [(0.3, 0.5), (0.7, 0.5)]
        for (fx, fy) in spots:
            cx_, cy_ = x0 + m + mw * fx, y0 + m + mw * (1.0 if n == 3 else 0.62) * fy
            d.ellipse([cx_ - lr, cy_ - lr, cx_ + lr, cy_ + lr], fill=C('#1a1a1e'))
            d.ellipse([cx_ - lr * 0.55, cy_ - lr * 0.55, cx_ + lr * 0.55, cy_ + lr * 0.55], fill=C('#2f3a4a'))
        if v.get('wallet'):
            wc = C(v['wallet'])
            d.rounded_rectangle([x0 + W * 0.12, y0 + H * 0.5, x1 - W * 0.12, y1 - H * 0.08], radius=14 * s, fill=wc)
            d.rectangle([x0 + W * 0.12, y0 + H * 0.56, x1 - W * 0.12, y0 + H * 0.58], fill=sh(wc, 0.7))
            d.rectangle([x0 + W * 0.2, y0 + H * 0.47, x1 - W * 0.2, y0 + H * 0.52], fill=C('#2f6fbf'))
            dashed_rect(d, [x0 + W * 0.15, y0 + H * 0.52, x1 - W * 0.15, y1 - H * 0.1], sh(wc, 1.4), width=3, dash=10,
                        gap=8)
    return light(L, 0.16, 25, 0.25, 0.06)


PHONE_VARIANTS = [
    dict(name='large smartphone, screen up', size='L', shape='tall slab', color='black', s=1.12, c='#2b2d31'),
    dict(name='compact smartphone', size='S', shape='short slab', color='silver', s=0.78, c='#c9ced6',
         wh=(300, 560)),
    dict(name='phone in clear case', size='M', shape='slab + bumper', color='blue', s=1.0, c='#4a76c9',
         case='#e7f1ff', case_alpha=150, kind='back', lenses=2),
    dict(name='phone in rugged case', size='L', shape='slab + thick corners', color='orange/black', s=1.0,
         c='#2b2b2b', case='#f08c00', case_e=34, rugged=True),
    dict(name='cracked screen', size='M', shape='slab, damaged', color='black', s=1.0, c='#34363b', cracked=True),
    dict(name='phone back, triple camera', size='M', shape='slab, back side', color='lavender', s=1.0,
         c='#b7a8d9', kind='back', lenses=3),
    dict(name='folded flip phone', size='S', shape='square folded', color='mint', s=1.0, c='#9fd8c3',
         wh=(330, 380), kind='flip'),
    dict(name='phone with wallet case', size='M', shape='slab + card pocket', color='tan', s=1.0, c='#3a3a3a',
         case='#a8774a', kind='back', lenses=2, wallet='#8a5d34'),
]


# ───────────────────────── 7. umbrella ─────────────────────────
def umbrella(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']
    pat = pattern(v.get('pattern', 'solid'), v['c'], v.get('c2', v['c']), rng) if v.get('pattern') else \
        Image.new('RGBA', (S, S), C(v['c']))
    hc = C(v.get('handle', '#1e1e1e'))
    if v['kind'] == 'compact':
        Hf = 430 * s; Wf = v.get('w', 130) * s
        top = Y - (Hf + 150 * s) / 2; bot = top + Hf
        pts_l, pts_r = [], []
        for i in range(25):
            t = i / 24
            half = Wf / 2 * (0.75 + 0.35 * math.sin(math.pi * t ** 0.8)) + 6 * math.sin(t * 19)
            yy = top + Hf * t
            pts_l.append((X - half, yy)); pts_r.append((X + half + 4 * math.cos(t * 13), yy))
        fill_pattern(L, lambda m: m.polygon(pts_l + pts_r[::-1], fill=255), pat)
        for k in range(4):
            xx = X - Wf * 0.3 + k * Wf * 0.2
            d.line(bez((xx, top + 20), (xx + 12, top + Hf * 0.3), (xx - 14, top + Hf * 0.6), (xx + 5, bot - 10)),
                   fill=C('#000000', 70), width=3)
        L2 = light(L, 0.0); d = ImageDraw.Draw(L)
        d.rounded_rectangle([X - 18 * s, top - 30 * s, X + 18 * s, top + 10 * s], radius=8 * s, fill=C('#444444'))
        d.rounded_rectangle([X - Wf * 0.42, bot - 8, X + Wf * 0.42, bot + 150 * s], radius=26 * s, fill=hc)
        d.rectangle([X - Wf * 0.55, top + Hf * 0.45, X + Wf * 0.6, top + Hf * 0.53],
                    fill=sh(C(v.get('strap', v['c'])), 0.8))
        d.ellipse([X + Wf * 0.38, top + Hf * 0.45, X + Wf * 0.58, top + Hf * 0.53], fill=C('#c0c0c0'))
        if v.get('sleeve'):
            sc = C(v['sleeve'])
            d.rounded_rectangle([X + Wf * 0.9, top + Hf * 0.05, X + Wf * 0.9 + Wf * 1.05, top + Hf * 0.95],
                                radius=Wf * 0.4, fill=sc)
            d.line([(X + Wf * 1.0, top + Hf * 0.1), (X + Wf * 1.0, top + Hf * 0.9)], fill=sh(sc, 0.7), width=6)
    else:  # long stick
        Ht = 760 * s; top = Y - Ht / 2; bot = Y + Ht / 2
        Wf = v.get('w', 120) * s; fab_end = top + Ht * 0.68
        d.line([(X, top), (X, bot - 90 * s)], fill=C('#555555'), width=int(14 * s))
        pts_l, pts_r = [], []
        for i in range(31):
            t = i / 30
            half = Wf / 2 * (math.sin(math.pi * t ** 1.35 * 0.92)) ** 0.9 + 3
            yy = top + 40 * s + (fab_end - top - 40 * s) * t
            pts_l.append((X - half, yy)); pts_r.append((X + half, yy))
        fill_pattern(L, lambda m: m.polygon(pts_l + pts_r[::-1], fill=255), pat)
        d = ImageDraw.Draw(L)
        d.rounded_rectangle([X - 9 * s, top - 6 * s, X + 9 * s, top + 46 * s], radius=6, fill=C('#bbbbbb'))
        ys = top + (fab_end - top) * 0.55
        d.rectangle([X - Wf * 0.48, ys - 14 * s, X + Wf * 0.48, ys + 14 * s], fill=sh(C(v['c']), 0.7))
        hb = bot - 120 * s
        d.rounded_rectangle([X - 20 * s, hb - 40 * s, X + 20 * s, hb + 100 * s], radius=12, fill=hc)
        d.arc([X - 150 * s, hb + 20 * s, X + 20 * s, hb + 190 * s], 0, 190, fill=hc, width=int(40 * s))
    return light(L, 0.22, 25, 0.3, 0.08)


UMBRELLA_VARIANTS = [
    dict(name='compact folding, black', size='M', shape='folded compact', color='black', s=1.0, c='#202124',
         kind='compact'),
    dict(name='compact folding, polka dot', size='M', shape='folded compact', color='navy w/ white dots', s=1.0,
         c='#1f3a68', c2='#f8f9fa', pattern='dots', kind='compact'),
    dict(name='compact with sleeve beside it', size='M', shape='folded + cover', color='red', s=0.95, c='#c92a2a',
         kind='compact', sleeve='#c92a2a'),
    dict(name='long stick, J-hook', size='XL', shape='closed stick + J handle', color='black', s=1.0, c='#232323',
         kind='stick', handle='#6b4226'),
    dict(name='long stick, plaid', size='XL', shape='closed stick + J handle', color='beige plaid', s=0.95,
         c='#c8b48f', c2='#7a2e2e', pattern='plaid', kind='stick', handle='#2b2b2b'),
    dict(name='mini compact, yellow', size='S', shape='short folded compact', color='yellow', s=0.75, c='#fab005',
         kind='compact', w=120),
    dict(name='golf umbrella, two-tone', size='XL', shape='oversized stick', color='green/white panels', s=1.08,
         c='#2f9e44', c2='#f8f9fa', pattern='gores', kind='stick', w=170),
    dict(name='compact, rainbow stripes', size='M', shape='folded compact', color='rainbow', s=1.0, c='#e03131',
         c2='#e03131,#f08c00,#fab005,#40c057,#1c7ed6,#7048e8', pattern='stripes', kind='compact', strap='#555555'),
]


# ───────────────────────── 8. wallet ─────────────────────────
def wallet(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']; c = C(v['c'])
    W, H = v['wh']; W *= s; H *= s
    x0, y0, x1, y1 = X - W / 2, Y - H / 2, X + W / 2, Y + H / 2
    kind = v['kind']; st = sh(c, 1.45) if sum(c[:3]) < 400 else sh(c, 0.6)
    if kind == 'cardholder':
        d.rounded_rectangle([x0 + W * 0.08, y0 - H * 0.28, x1 - W * 0.08, y0 + H * 0.4], radius=14,
                            fill=C('#1971c2'))
        d.rectangle([x0 + W * 0.08, y0 - H * 0.2, x1 - W * 0.08, y0 - H * 0.12], fill=C('#dbe4ff'))
    if kind == 'coin':
        d.ellipse([x0, y0, x1, y1 + H * 0.15], fill=c)
        d.rectangle([x0, y0 - 2, x1, y0 + H * 0.15], fill=(0, 0, 0, 0))
        d.rounded_rectangle([x0 + 6, y0 - 4, x1 - 6, y0 + 22 * s], radius=10, fill=C('#c9a646'))
        for sgn in (-1, 1):
            d.ellipse([X + sgn * 20 * s - 18 * s, y0 - 30 * s, X + sgn * 20 * s + 18 * s, y0 + 6 * s],
                      fill=C('#d9b44a'))
        return light(L, 0.2, 20)
    d.rounded_rectangle([x0, y0, x1, y1], radius=v.get('r', 22) * s, fill=c)
    if kind in ('bifold', 'trifold', 'cardholder', 'long', 'velcro'):
        dashed_rect(d, [x0 + 14 * s, y0 + 14 * s, x1 - 14 * s, y1 - 14 * s], st, width=max(2, int(4 * s)))
    if kind == 'bifold':
        d.line([(x0 + 4, Y + H * 0.38), (x1 - 4, Y + H * 0.38)], fill=sh(c, 0.75), width=4)
    if kind == 'trifold':
        d.line([(x0 + W / 3, y0 + 4), (x0 + W / 3, y1 - 4)], fill=sh(c, 0.6), width=6)
        d.rectangle([x0 + W / 3 + 3, y0, x0 + W / 3 + 14, y1], fill=sh(c, 1.15))
    if kind == 'cardholder':
        d.arc([X - W * 0.22, y0 - H * 0.12, X + W * 0.22, y0 + H * 0.2], 20, 160, fill=sh(c, 0.6), width=6)
    if kind in ('zip', 'wristlet'):
        zc = C('#b8a46a') if kind == 'zip' else C('#c0c0c0')
        if kind == 'zip':
            d.rounded_rectangle([x0 + 10, y0 + 10, x1 - 10, y1 - 10], radius=v.get('r', 22) * s - 6, outline=zc,
                                width=int(9 * s))
            px, py = x1 - 8, y0 + H * 0.25
        else:
            d.line([(x0 + 18, y0 + H * 0.16), (x1 - 18, y0 + H * 0.16)], fill=zc, width=int(9 * s))
            px, py = x1 - 30, y0 + H * 0.16
            d.arc([x0 - W * 0.35, y0 - H * 0.55, x0 + W * 0.25, y0 + H * 0.5], 120, 330, fill=sh(c, 0.85),
                  width=int(22 * s))
        d.rounded_rectangle([px - 12 * s, py - 10 * s, px + 36 * s, py + 14 * s], radius=6, fill=zc)
    if kind == 'long':
        d.polygon([(x0, y0), (x1, y0), (x1, y0 + H * 0.45), (X + W * 0.1, y0 + H * 0.62), (x0, y0 + H * 0.45)],
                  fill=sh(c, 1.12))
        d.ellipse([X + W * 0.1 - 20 * s, y0 + H * 0.5, X + W * 0.1 + 20 * s, y0 + H * 0.5 + 40 * s],
                  fill=C('#c0c0c0'))
    if kind == 'velcro':
        tc = C(v['trim'])
        d.rectangle([x0, y0 + H * 0.12, x1, y0 + H * 0.22], fill=tc)
        d.rectangle([x0, y1 - H * 0.22, x1, y1 - H * 0.12], fill=tc)
        d.rounded_rectangle([X - W * 0.12, Y - H * 0.08, X + W * 0.12, Y + H * 0.08], radius=8, fill=sh(c, 0.7))
    return light(L, 0.14, 15, 0.3, 0.1)


WALLET_VARIANTS = [
    dict(name='leather bifold', size='M', shape='square-ish bifold', color='brown', s=1.0, c='#7a4a2a',
         wh=(400, 320), kind='bifold'),
    dict(name='thick trifold', size='M', shape='trifold, thick edge', color='black', s=1.0, c='#262626',
         wh=(380, 300), kind='trifold'),
    dict(name='slim cardholder', size='S', shape='slim sleeve + card', color='tan', s=1.0, c='#c69c6d',
         wh=(300, 200), kind='cardholder'),
    dict(name='zip-around clutch', size='L', shape='long rectangle, zip', color='blush pink', s=1.0, c='#e8a3b0',
         wh=(470, 250), kind='zip', r=40),
    dict(name='wristlet with strap', size='L', shape='pouch + wrist loop', color='black', s=0.95, c='#2f2f33',
         wh=(430, 260), kind='wristlet', r=26),
    dict(name='kiss-lock coin purse', size='XS', shape='rounded pouch + clasp', color='navy', s=1.0,
         c='#283c74', wh=(280, 220), kind='coin'),
    dict(name='long snap wallet', size='L', shape='long rectangle + flap', color='maroon', s=1.0, c='#7c2238',
         wh=(500, 250), kind='long'),
    dict(name='nylon velcro wallet', size='M', shape='bifold, sporty', color='gray/green trim', s=1.0,
         c='#6c757d', wh=(400, 310), kind='velcro', trim='#2f9e44', r=14),
]


# ───────────────────────── 9. eyeglasses ─────────────────────────
def lens_pts(cx, cy, a, b, n, side, shape):
    pts = []
    for i in range(80):
        t = 2 * math.pi * i / 80
        ct, st_ = math.cos(t), math.sin(t)
        x = a * np.sign(ct) * abs(ct) ** (2 / n)
        y = b * np.sign(st_) * abs(st_) ** (2 / n)
        inner = (-x * side) / a
        if shape == 'cateye' and y < 0:
            y *= 1 + 0.45 * max(0, -inner) ** 2
            x *= 1 + 0.08 * max(0, -inner)
        if shape == 'aviator' and y > 0:
            y *= 1 + 0.35 * max(0, inner + 0.2)
        if shape == 'aviator' and y < 0:
            y *= 0.75
        pts.append((cx + x, cy + y))
    return pts


def eyeglasses(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']
    fc = C(v['c']); tint = C(v.get('tint', '#d8ecf7'), v.get('tint_a', 60))
    a, b = v['ab']; a *= s; b *= s; gap = v.get('gap', 46) * s; n = v['n']; shape = v.get('shape', 'normal')
    fw = int(v.get('fw', 12) * s)
    centers = [(X - gap / 2 - a, Y), (X + gap / 2 + a, Y)]
    lens_layer = layer(); ld = ImageDraw.Draw(lens_layer)
    polys = []
    for i, (cx, cy) in enumerate(centers):
        side = -1 if i == 0 else 1
        p = lens_pts(cx, cy, a, b, n, side, shape)
        polys.append(p)
        if v.get('gradient'):
            m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).polygon(p, fill=255)
            grad = Image.new('RGBA', (S, S))
            gd = ImageDraw.Draw(grad)
            for yy in range(int(cy - b * 1.3), int(cy + b * 1.3)):
                f = (yy - (cy - b)) / (2 * b)
                gd.line([(0, yy), (S, yy)], fill=tint[:3] + (int(240 - 160 * max(0, min(1, f))),))
            t = layer(); t.paste(grad, (0, 0), m); lens_layer.alpha_composite(t)
        else:
            ld.polygon(p, fill=tint)
        ld.line([(cx - a * 0.5, cy - b * 0.5), (cx - a * 0.1, cy - b * 0.75)], fill=(255, 255, 255, 110), width=6)
    L.alpha_composite(lens_layer)
    d = ImageDraw.Draw(L)
    if not v.get('rimless'):
        for p in polys:
            d.line(p + [p[0]], fill=fc, width=fw, joint='curve')
        if v.get('pattern'):
            P = pattern('tortoise', v['c'], v['c2'], rng)
            m = Image.new('L', (S, S), 0); md = ImageDraw.Draw(m)
            for p in polys:
                md.line(p + [p[0]], fill=255, width=fw, joint='curve')
            t = layer(); t.paste(P, (0, 0), m); L.alpha_composite(t)
            d = ImageDraw.Draw(L)
    bridge_y = Y - b * (0.45 if shape != 'aviator' else 0.6)
    if shape == 'aviator':
        d.line([(X - gap / 2 - 6, Y - b * 0.7), (X + gap / 2 + 6, Y - b * 0.7)], fill=fc, width=max(4, fw // 2))
    d.arc([X - gap / 2 - 8, bridge_y - gap * 0.35, X + gap / 2 + 8, bridge_y + gap * 0.5], 190, 350, fill=fc,
          width=max(5, int(fw * 0.8)))
    for i, (cx, cy) in enumerate(centers):
        side = -1 if i == 0 else 1
        ex = cx + side * a * 1.02
        d.rounded_rectangle([ex - 10 * s, cy - b * 0.55, ex + 10 * s, cy - b * 0.25], radius=4, fill=fc)
        tx = ex + side * 10 * s
        d.line([(tx, cy - b * 0.4), (tx + side * 18 * s, cy - b * 0.2), (cx - side * a * 0.2, cy + b * 0.75)],
               fill=sh(fc, 0.85), width=max(4, int(fw * 0.6)), joint='curve')
    return light(L, 0.1)


GLASSES_VARIANTS = [
    dict(name='round wire frames', size='S', shape='round', color='black metal', s=1.0, c='#1b1b1b', ab=(118, 118),
         n=2, fw=8),
    dict(name='thick rectangular frames', size='M', shape='rectangle', color='black acetate', s=1.0, c='#141414',
         ab=(150, 98), n=5, fw=26),
    dict(name='cat-eye tortoiseshell', size='M', shape='cat-eye', color='tortoise', s=1.0, c='#6b3d1e',
         c2='#d9922e', ab=(145, 100), n=3, fw=22, shape_='cateye', pattern=True),
    dict(name='aviator sunglasses', size='M', shape='aviator teardrop', color='gold / dark green lens', s=1.0,
         c='#c9a646', ab=(150, 125), n=2.4, fw=8, tint='#28402c', tint_a=215),
    dict(name='classic wayfarer sunglasses', size='M', shape='trapezoid', color='black / dark lens', s=1.0,
         c='#151515', ab=(150, 105), n=4, fw=28, tint='#1e1f22', tint_a=225),
    dict(name='rimless readers', size='S', shape='rimless oval', color='clear / silver', s=0.9, c='#a0a4a8',
         ab=(130, 85), n=2.5, fw=6, rimless=True, tint='#e3f2fb', tint_a=110),
    dict(name="kids' glasses", size='XS', shape='round-square', color='clear blue', s=0.75, c='#4dabf7',
         ab=(125, 110), n=3, fw=24),
    dict(name='oversized square sunglasses', size='L', shape='oversized square', color='brown gradient', s=1.08,
         c='#4a2f1f', ab=(170, 145), n=4.5, fw=26, tint='#5a3c28', gradient=True),
]
for _gv in GLASSES_VARIANTS:
    if 'shape_' in _gv:
        _gv['shape_kind'] = _gv.pop('shape_')


def eyeglasses_wrap(v, rng):
    vv = dict(v); vv['shape'] = v.get('shape_kind', 'aviator' if 'aviator' in v['name'] else 'normal')
    return eyeglasses(vv, rng)


# ───────────────────────── 10. backpack ─────────────────────────
def backpack(v, rng):
    L = layer(); d = ImageDraw.Draw(L); s = v['s']; c = C(v['c']); c2 = C(v.get('c2', v['c']))
    W, H = v.get('wh', (440, 560)); W *= s; H *= s
    x0, y0, x1, y1 = X - W / 2, Y - H / 2 + 30 * s, X + W / 2, Y + H / 2 + 30 * s
    kind = v.get('kind', 'standard'); zc = C('#2b2b2b')
    if kind == 'drawstring':
        d.polygon([(x0 + W * 0.12, y0), (x1 - W * 0.12, y0), (x1, y1), (x0, y1)], fill=c)
        for k in range(6):
            d.line([(x0 + W * (0.15 + k * 0.14), y0 + 4), (x0 + W * (0.17 + k * 0.14), y0 + 30 * s)],
                   fill=sh(c, 0.7), width=4)
        cc = C(v.get('cord', '#f1f3f5'))
        d.line([(x0 + W * 0.12, y0 + 8), (x0 + 10, y1 - 10)], fill=cc, width=int(12 * s))
        d.line([(x1 - W * 0.12, y0 + 8), (x1 - 10, y1 - 10)], fill=cc, width=int(12 * s))
        d.arc([x0 + W * 0.1, y0 - H * 0.35, x1 - W * 0.1, y0 + H * 0.15], 190, 350, fill=cc, width=int(12 * s))
        for gx in (x0 + 10, x1 - 10):
            d.ellipse([gx - 14 * s, y1 - 24 * s, gx + 14 * s, y1 + 4 * s], fill=C('#c0c0c0'))
        return light(L, 0.18)
    if kind == 'sling':
        d.line([(x1 - W * 0.2, y0 + H * 0.1), (x1 + W * 0.35, y0 - H * 0.35)], fill=sh(c, 0.8), width=int(50 * s))
        d.line([(x0 + W * 0.25, y1 - H * 0.05), (x0 - W * 0.3, y1 + H * 0.12)], fill=sh(c, 0.8), width=int(50 * s))
        pts = lens_pts(X, Y + 20 * s, W * 0.42, H * 0.32, 2.6, 1, 'normal')
        t = layer(); ImageDraw.Draw(t).polygon(pts, fill=c)
        L.alpha_composite(t.rotate(35, resample=Image.BICUBIC, center=(X, Y)))
        d = ImageDraw.Draw(L)
        d.arc([X - W * 0.3, Y - H * 0.2, X + W * 0.3, Y + H * 0.35], 200, 340, fill=zc, width=int(8 * s))
        d.rounded_rectangle([X + W * 0.2, Y - H * 0.12, X + W * 0.28, Y - H * 0.02], radius=6, fill=C('#adb5bd'))
        return light(L, 0.2, 18)
    # straps peeking out + top handle
    for sgn in (-1, 1):
        d.rounded_rectangle([X + sgn * W * 0.42 - 32 * s, y0 + H * 0.05, X + sgn * W * 0.42 + 32 * s, y1 - H * 0.08],
                            radius=24 * s, fill=sh(c, 0.6))
    d.arc([X - W * 0.16, y0 - H * 0.13, X + W * 0.16, y0 + H * 0.12], 180, 360, fill=sh(c, 0.6), width=int(16 * s))
    rad = W * v.get('top_r', 0.32)
    if kind == 'rolltop':
        d.rounded_rectangle([x0, y0 + H * 0.1, x1, y1], radius=W * 0.1, fill=c)
        d.rounded_rectangle([x0 - 6, y0, x1 + 6, y0 + H * 0.17], radius=30 * s, fill=sh(c, 0.85))
        for k in range(3):
            d.line([(x0 + 10, y0 + H * (0.04 + k * 0.045)), (x1 - 10, y0 + H * (0.04 + k * 0.045))],
                   fill=sh(c, 0.7), width=4)
        d.rectangle([X - 24 * s, y0 + H * 0.05, X + 24 * s, y0 + H * 0.55], fill=C('#1e1e1e'))
        d.rounded_rectangle([X - 36 * s, y0 + H * 0.45, X + 36 * s, y0 + H * 0.56], radius=8, fill=C('#3a3a3a'))
        d.rounded_rectangle([x0 + W * 0.15, y0 + H * 0.6, x1 - W * 0.15, y1 - H * 0.06], radius=24 * s,
                            fill=sh(c, 0.92))
        return light(L, 0.2, 18)
    d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=c)
    d.arc([x0 + 22 * s, y0 + 22 * s, x1 - 22 * s, y0 + 2 * rad], 185, 355, fill=zc, width=int(8 * s))
    d.rounded_rectangle([X + W * 0.25, y0 + rad * 0.32, X + W * 0.32, y0 + rad * 0.32 + 34 * s], radius=6,
                        fill=C('#adb5bd'))
    py0 = y0 + H * v.get('pocket_top', 0.5)
    d.rounded_rectangle([x0 + W * 0.1, py0, x1 - W * 0.1, y1 - H * 0.05], radius=W * 0.12, fill=c2)
    d.line([(x0 + W * 0.16, py0 + 26 * s), (x1 - W * 0.16, py0 + 26 * s)], fill=zc, width=int(7 * s))
    d.rounded_rectangle([x1 - W * 0.22, py0 + 18 * s, x1 - W * 0.17, py0 + 58 * s], radius=5, fill=C('#adb5bd'))
    if v.get('bottle_pocket'):
        for sgn in (-1, 1):
            bx = X + sgn * W / 2
            d.rounded_rectangle([bx - 40 * s, y1 - H * 0.38, bx + 40 * s, y1 - H * 0.04], radius=22 * s,
                                fill=sh(c2, 0.9))
            for k in range(6):
                d.line([(bx - 36 * s, y1 - H * (0.34 - k * 0.05)), (bx + 36 * s, y1 - H * (0.34 - k * 0.05))],
                       fill=sh(c2, 0.7), width=3)
    if v.get('patch'):
        d.rounded_rectangle([X - W * 0.12, y0 + H * 0.25, X + W * 0.12, y0 + H * 0.35], radius=10,
                            fill=C(v['patch']))
    return light(L, 0.2, 18, 0.3, 0.12)


BACKPACK_VARIANTS = [
    dict(name='standard school backpack', size='L', shape='rounded-top rectangle', color='navy', s=1.0,
         c='#23396b', c2='#2c4785'),
    dict(name='large laptop backpack', size='XL', shape='tall, squared top', color='black', s=1.12, c='#232425',
         c2='#2e3032', top_r=0.18, pocket_top=0.42, wh=(460, 600)),
    dict(name='small daypack', size='M', shape='rounded-top rectangle', color='red', s=0.82, c='#c92a2a',
         c2='#a61e1e'),
    dict(name='drawstring gym bag', size='M', shape='trapezoid, cords', color='heather gray', s=1.0, c='#868e96',
         kind='drawstring', wh=(440, 520)),
    dict(name='roll-top commuter pack', size='L', shape='rectangle, rolled top', color='olive', s=1.0,
         c='#5c6b3a', kind='rolltop', wh=(420, 600)),
    dict(name='crossbody sling bag', size='S', shape='teardrop, diagonal strap', color='teal', s=0.95,
         c='#0c8599', kind='sling', wh=(460, 420)),
    dict(name='mini backpack', size='S', shape='round, small', color='lilac', s=0.68, c='#c0a6e8', c2='#b196dd',
         top_r=0.48, wh=(420, 470)),
    dict(name='hiking pack w/ bottle pockets', size='XL', shape='tall + side mesh pockets', color='gray/orange',
         s=1.05, c='#5f656d', c2='#e8590c', bottle_pocket=True, patch='#e8590c', wh=(430, 600)),
]



# ───────────────────────── 0. RUID — Rutgers University ID (PRIORITY CLASS) ─────────────────────────
# Layout follows the current portrait RUID: red header with RUTGERS name, thin black rule, holder name
# top-left, role (STUDENT / FACULTY / STAFF) bottom-left, photo bottom-right.
# Deliberately NOT included: the university shield/seal artwork, real names, real faces, RUID numbers.
FONT_DIR = '/usr/share/fonts/truetype/dejavu/'
RU_RED = '#cc0033'
FIRST_NAMES = ['JORDAN', 'PRIYA', 'MARCUS', 'ELENA', 'DEVON', 'AISHA', 'TYLER', 'MEI', 'CARLOS', 'NORA', 'SAMIR',
               'HANNAH', 'KWAME', 'SOFIA', 'LIAM', 'ROHAN']
LAST_NAMES = ['MARTINEZ', 'OKAFOR', 'LINDQVIST', 'BRENNAN', 'NAKAMURA', 'DELACROIX', 'WHITFIELD', 'RAMIREZ',
              'KOWALSKI', 'ADEYEMI', 'HARTLEY', 'VENKATARAMAN', 'CHEN-MORALES', 'OSEI']
SKIN = ['#8d5524', '#a0662e', '#c68642', '#e0ac69', '#f1c27d', '#ffdbac']
HAIR = ['#141414', '#1b1b1b', '#2b1a10', '#4a2c18', '#6b4423', '#b08d57']


def _font(name, size):
    try:
        return ImageFont.truetype(FONT_DIR + name, max(6, int(size)))
    except OSError:
        return ImageFont.load_default()


def ruid_card_img(w, h, rr, role='STUDENT', back=False, worn=0.0, slot=False):
    pad = 24
    K = Image.new('RGBA', (int(w + 2 * pad), int(h + 2 * pad)), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    base = C('#f5f4f0'); red = C(RU_RED); rad = w * 0.06
    d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=base)
    if back:
        d.rectangle([x0, y0 + h * 0.07, x1, y0 + h * 0.165], fill=C('#151515'))
        for k in range(9):
            d.rounded_rectangle([x0 + w * 0.08, y0 + h * (0.22 + k * 0.034),
                                 x0 + w * (0.92 - rr.uniform(0, 0.35)), y0 + h * (0.22 + k * 0.034) + h * 0.011],
                                radius=3, fill=C('#a7a9ac'))
        bx0 = x0 + w * 0.12
        for k in range(40):
            ww = rr.choice([2, 3, 4])
            d.rectangle([bx0 + k * w * 0.0185, y0 + h * 0.6, bx0 + k * w * 0.0185 + ww, y0 + h * 0.72],
                        fill=C('#111111'))
        d.rectangle([x0 + w * 0.08, y0 + h * 0.8, x1 - w * 0.08, y0 + h * 0.88], fill=C('#ffffff'),
                    outline=C('#9a9a9a'), width=2)
    else:
        hh = h * 0.205
        d.rounded_rectangle([x0, y0, x1, y0 + hh], radius=rad, fill=red, corners=(True, True, False, False))
        d.rectangle([x0, y0 + hh, x1, y0 + hh + h * 0.022], fill=C('#111111'))
        cream = C('#fbf1e3')
        ex, ey, ew, eh = x0 + w * 0.05, y0 + hh * 0.16, hh * 0.52, hh * 0.68   # plain placeholder emblem
        d.rounded_rectangle([ex, ey, ex + ew, ey + eh], radius=ew * 0.18, outline=cream, width=max(2, int(w * 0.008)))
        tx = ex + ew + w * 0.05
        size = h * 0.09
        while True:
            f = _font('DejaVuSerif.ttf', size)
            tb = d.textbbox((0, 0), 'RUTGERS', font=f)
            if tb[2] - tb[0] <= (x1 - w * 0.05) - tx or size < 8:
                break
            size *= 0.94
        d.text((tx - tb[0], y0 + (hh - (tb[3] - tb[1])) / 2 - tb[1]), 'RUTGERS', font=f, fill=cream)
        nf = _font('DejaVuSans-Bold.ttf', h * 0.04)
        d.text((x0 + w * 0.13, y0 + h * 0.29), rr.choice(FIRST_NAMES), font=nf, fill=C('#1a1a1a'))
        d.text((x0 + w * 0.13, y0 + h * 0.345), rr.choice(LAST_NAMES), font=nf, fill=C('#1a1a1a'))
        d.text((x0 + w * 0.06, y0 + h * 0.855), role, font=_font('DejaVuSans-Bold.ttf', h * 0.055),
               fill=C('#2a2a2a'))
        px0, py0, px1, py1 = x0 + w * 0.57, y0 + h * 0.655, x0 + w * 0.95, y0 + h * 0.955
        d.rectangle([px0, py0, px1, py1], fill=C(rr.choice(['#e6e3e0', '#dfe3e8', '#ece9e4'])))
        pw, ph = px1 - px0, py1 - py0; cxp = (px0 + px1) / 2
        skin = C(rr.choice(SKIN)); hair = C(rr.choice(HAIR))
        d.chord([px0 + pw * 0.02, py0 + ph * 0.68, px1 - pw * 0.02, py0 + ph * 1.32], 180, 360,
                fill=C(rr.choice(['#1d1d1f', '#23395b', '#5c5f66', '#7a1f2b', '#2f4f3a'])))
        d.rectangle([cxp - pw * 0.08, py0 + ph * 0.55, cxp + pw * 0.08, py0 + ph * 0.72], fill=sh(skin, 0.88))
        d.ellipse([cxp - pw * 0.19, py0 + ph * 0.2, cxp + pw * 0.19, py0 + ph * 0.64], fill=skin)
        d.chord([cxp - pw * 0.22, py0 + ph * 0.12, cxp + pw * 0.22, py0 + ph * 0.5], 180, 360, fill=hair)
        if rr.random() < 0.4:
            for sgn in (-1, 1):
                d.rounded_rectangle([cxp + sgn * pw * 0.1 - pw * 0.075, py0 + ph * 0.36,
                                     cxp + sgn * pw * 0.1 + pw * 0.075, py0 + ph * 0.44], radius=4,
                                    outline=C('#3a3a3a'), width=2)
    if slot:
        d.rounded_rectangle([x0 + w / 2 - w * 0.12, y0 + h * 0.035, x0 + w / 2 + w * 0.12, y0 + h * 0.07],
                            radius=8, fill=(0, 0, 0, 0))
    if worn:
        arr = np.asarray(K).astype(np.float32)
        arr[..., :3] = arr[..., :3] * (1 - worn * 0.5) + np.array([232, 226, 210]) * worn * 0.5
        K = Image.fromarray(arr.astype(np.uint8), 'RGBA'); d = ImageDraw.Draw(K)
        d.rounded_rectangle([x0, y0, x1, y1], radius=rad, outline=C('#d6cfbf'), width=5)
        for _ in range(int(60 * worn)):
            xx, yy = rr.uniform(x0 + 8, x1 - 8), rr.uniform(y0 + 8, y1 - 8)
            r = rr.uniform(1, 3.5)
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=C('#8a857a', 170))
        d.line([(x0 + w * 0.05, y0 + h * 0.48), (x1 - w * 0.08, y0 + h * 0.5)], fill=C('#e2dccd'), width=3)
    return K


def ruid(v, rng):
    rr = random.Random(v['seed']); s = v['s']
    w, h = 340 * s, 540 * s
    K = ruid_card_img(w, h, rr, v.get('role', 'STUDENT'), v.get('back', False), v.get('worn', 0),
                      slot=bool(v.get('keyring') or v.get('lanyard') or v.get('reel')))
    return card_scene(v, K, w, h)


RUID_VARIANTS = [
    dict(name='RUID front, clean', size='M', shape='portrait CR80', color='red header / white', s=1.0, seed=11),
    dict(name='RUID front, worn & scuffed', size='M', shape='portrait CR80, worn edges', color='red header / off-white',
         s=1.0, seed=12, worn=0.6),
    dict(name='RUID on red lanyard', size='L', shape='portrait + lanyard', color='red lanyard', s=0.9, seed=13,
         lanyard=RU_RED),
    dict(name='RUID in clear badge sleeve', size='M', shape='portrait in sleeve', color='red header / clear', s=0.95,
         seed=14, sleeve=True),
    dict(name='RUID back side', size='M', shape='portrait, back (mag stripe)', color='white / black stripe', s=1.0,
         seed=15, back=True),
    dict(name='RUID on keyring', size='M', shape='portrait + punched slot + keys', color='red header / silver keys',
         s=0.88, seed=16, keyring=True),
    dict(name='RUID faculty card', size='M', shape='portrait CR80', color='red header / white', s=1.0, seed=17,
         role='FACULTY'),
    dict(name='RUID staff on badge reel', size='M', shape='portrait + badge reel', color='red reel', s=0.85, seed=18,
         role='STAFF', reel=RU_RED),
]


# ───────────────────────── registry + main ─────────────────────────
CLASSES = [
    ('ruid', ruid, RUID_VARIANTS, (-30, 30), 0.0),
    ('water_bottle', water_bottle, BOTTLE_VARIANTS, (-25, 25), 0.25),
    ('keys', keys, KEY_VARIANTS, (-180, 180), 0.0),
    ('other_id_card', id_card, ID_VARIANTS, (-20, 20), 0.0),
    ('earbuds', earbuds, EARBUD_VARIANTS, (-40, 40), 0.0),
    ('headphones', headphones, HEADPHONE_VARIANTS, (-25, 25), 0.0),
    ('phone', phone, PHONE_VARIANTS, (-30, 30), 0.15),
    ('umbrella', umbrella, UMBRELLA_VARIANTS, (-35, 35), 0.3),
    ('wallet', wallet, WALLET_VARIANTS, (-30, 30), 0.0),
    ('eyeglasses', eyeglasses_wrap, GLASSES_VARIANTS, (-15, 15), 0.0),
    ('backpack', backpack, BACKPACK_VARIANTS, (-12, 12), 0.0),
]


# Priority tier used by the app: P1 = surface first / notify owner immediately.
PRIORITY = {
    'ruid': 'P1-critical',        # identity + campus access card; app's top priority
    'wallet': 'P1', 'phone': 'P1', 'keys': 'P1',
    'other_id_card': 'P2', 'eyeglasses': 'P2', 'earbuds': 'P2', 'headphones': 'P2', 'backpack': 'P2',
    'water_bottle': 'P3', 'umbrella': 'P3',
}
# RUID gets extra renders (camera distance, tilt, surface) so it is the best-represented class.
EXTRA_RENDERS = {'ruid': 5}
AUGMENT = {'ruid': dict(zoom=(0.85, 1.35), persp=0.07)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--renders', type=int, default=1)
    ap.add_argument('--ruid-renders', type=int, default=EXTRA_RENDERS['ruid'])
    args = ap.parse_args()
    rng_np = np.random.default_rng(args.seed)
    rng = random.Random(args.seed)
    out = args.outdir
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'classes.txt'), 'w') as f:
        f.write('\n'.join(c[0] for c in CLASSES) + '\n')
    rows = []
    for ci, (cname, fn, variants, (amin, amax), p_side) in enumerate(CLASSES):
        os.makedirs(os.path.join(out, 'images', cname), exist_ok=True)
        os.makedirs(os.path.join(out, 'labels', cname), exist_ok=True)
        n_r = args.ruid_renders * args.renders if cname == 'ruid' else args.renders
        aug = AUGMENT.get(cname, {})
        for vi, v in enumerate(variants, 1):
            obj = fn(v, rng)
            for r in range(n_r):
                bgk = rng.choice(BACKGROUNDS)
                ang = rng.uniform(amin, amax)
                if rng.random() < p_side:
                    ang += rng.choice([-90, 90])
                zoom = rng.uniform(*aug['zoom']) if 'zoom' in aug else 1.0
                img, bb = compose(background(bgk, rng_np), obj, ang, zoom, aug.get('persp', 0.0), rng)
                stem = f'{cname}_v{vi}' + (f'_r{r + 1}' if n_r > 1 else '')
                img.save(os.path.join(out, 'images', cname, stem + '.jpg'), quality=92)
                cx, cy = (bb[0] + bb[2]) / 2 / OUT, (bb[1] + bb[3]) / 2 / OUT
                bw, bh = (bb[2] - bb[0]) / OUT, (bb[3] - bb[1]) / OUT
                with open(os.path.join(out, 'labels', cname, stem + '.txt'), 'w') as f:
                    f.write(f'{ci} {cx:.5f} {cy:.5f} {bw:.5f} {bh:.5f}\n')
                rows.append(dict(file=f'images/{cname}/{stem}.jpg', class_id=ci, class_name=cname, priority=PRIORITY[cname], variant=vi,
                                 variant_name=v['name'], size_class=v['size'], shape=v['shape'], color=v['color'],
                                 background=bgk, rotation_deg=round(ang, 1),
                                 bbox_x0=bb[0], bbox_y0=bb[1], bbox_x1=bb[2], bbox_y1=bb[3]))
            print(f'{cname} v{vi} done')
    with open(os.path.join(out, 'annotations.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    contact_sheet(out, rows)
    ruid_sheet(out, [r for r in rows if r['class_name'] == 'ruid'])


def ruid_sheet(out, rows):
    tw, cols = 200, 8
    n_rows = math.ceil(len(rows) / cols)
    sheet = Image.new('RGB', (cols * tw, n_rows * tw + 44), (250, 250, 248))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), f'RUID (priority class P1-critical) — {len(rows)} images: 8 variants x renders',
           fill=(204, 0, 51), font=_font('DejaVuSans-Bold.ttf', 18))
    for i, r in enumerate(rows):
        im = Image.open(os.path.join(out, r['file'])).resize((tw - 6, tw - 6), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * tw + 3, 44 + (i // cols) * tw + 3))
    sheet.save(os.path.join(out, 'ruid_contact_sheet.png'), optimize=True)


def contact_sheet(out, rows):
    tw = 200; lab = 34; cols = 8
    first = [r for r in rows if '_r' not in r['file'].rsplit('/', 1)[-1] or r['file'].endswith('_r1.jpg')]
    classes = sorted({r['class_id'] for r in first})
    rowh = tw + lab
    head = 40
    sheet = Image.new('RGB', (cols * tw + 170, head + len(classes) * rowh), (250, 250, 248))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
        bfont = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
    except OSError:
        font = bfont = ImageFont.load_default()
    for k in range(cols):
        d.text((170 + k * tw + 8, 12), f'variant {k + 1}', fill=(90, 90, 90), font=bfont)
    for ri, ci in enumerate(classes):
        rs = [r for r in first if r['class_id'] == ci][:cols]
        y = head + ri * rowh
        d.text((10, y + tw // 2 - 8), rs[0]['class_name'].replace('_', ' '), fill=(30, 30, 30), font=bfont)
        d.text((10, y + tw // 2 + 12), rs[0]['priority'], fill=(204, 0, 51) if rs[0]['priority'].startswith('P1')
               else (110, 110, 110), font=bfont)
        for k, r in enumerate(rs):
            im = Image.open(os.path.join(out, r['file'])).resize((tw - 6, tw - 6), Image.LANCZOS)
            sheet.paste(im, (170 + k * tw + 3, y + 3))
            txt = r['variant_name']
            if len(txt) > 30:
                txt = txt[:29] + '…'
            d.text((170 + k * tw + 5, y + tw + 2), txt, fill=(40, 40, 40), font=font)
            d.text((170 + k * tw + 5, y + tw + 17), f"{r['size_class']} · {r['color']}"[:32], fill=(120, 120, 120),
                   font=font)
    sheet.save(os.path.join(out, 'contact_sheet.png'), optimize=True)


if __name__ == '__main__':
    main()
