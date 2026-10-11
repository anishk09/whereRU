# Campus Lost & Found — synthetic image dataset (Rutgers edition)

120 images (512×512 JPEG, q92): **RUID (priority class, 40 images)** + 10 of the items most often turned in to
college lost-and-found offices × 8 variants each.

## ⚑ Priority class: RUID (class 0, `P1-critical`)
The Rutgers University ID is the app's top-priority item, so it is class 0 and the best-represented class:
8 variants × 5 renders = 40 images, with extra camera-distance (zoom) and tilt (perspective) augmentation,
including a streaky gray laminate surface like typical campus desks.

| # | RUID variant |
|---|---|
| 1 | front, clean (portrait card: red header, black rule, name top-left, STUDENT bottom-left, photo bottom-right) |
| 2 | front, worn & scuffed |
| 3 | on red lanyard |
| 4 | in clear badge sleeve |
| 5 | back side (mag stripe + barcode) |
| 6 | on a keyring (punched slot + key) |
| 7 | FACULTY card |
| 8 | STAFF card on badge reel |

Names are fictional, photos are silhouettes, no ID numbers, and the university seal artwork is replaced by a
plain placeholder, so no image is a usable ID. `other_id_card` (non-Rutgers IDs, driver license) was recolored
so it never looks like a RUID — it serves as a hard negative.

### Priority tiers (`priority` column in annotations.csv)
| tier | classes |
|---|---|
| P1-critical | ruid |
| P1 | wallet, phone, keys |
| P2 | other_id_card, eyeglasses, earbuds, headphones, backpack |
| P3 | water_bottle, umbrella |

## All classes
Each variant changes **size, shape/style and color** of the same object, and is shown on a campus surface
(wood desk, library table, carpet, concrete, tile, lab bench, laminate, lawn) with random rotation and a soft shadow.

## Why these 10 classes
Campus lost-and-found staff consistently name the same items: water bottles, keys, student IDs/cards,
earphones/headphones, phones, umbrellas, wallets, glasses and bags (University of Toronto, Santa Barbara
City College, Southeastern Louisiana, WVU Mountainlair, Rizvi College reporting).

| class | variants (size · shape) |
|---|---|
| water_bottle | insulated w/ loop · slim flip-top · wide-mouth · disposable plastic · straw tumbler · sport squeeze · glass w/ sleeve · 64 oz jug |
| keys | single key · 2 on ring · car fob + key · 3 color-capped · on lanyard · tiny mailbox key · with charm · dorm fob + key |
| other_id_card | other-school · portrait on lanyard · in sleeve · badge reel · back/mag stripe · oversized badge · driver license · worn/faded |
| earbuds | pill case · square case · puck case · case in cover + clip · loose stem buds · loose round buds · wired · egg case |
| headphones | over-ear L · over-ear white · on-ear compact · kids · folded · neckband · gaming w/ mic · padded band |
| phone | large front · compact · clear case · rugged case · cracked · back w/ triple camera · flip phone · wallet case |
| umbrella | compact black · polka dot · with sleeve · long J-hook · long plaid · mini · golf · rainbow |
| wallet | bifold · trifold · cardholder · zip clutch · wristlet · coin purse · long snap · nylon velcro |
| eyeglasses | round wire · thick rectangle · cat-eye tortoise · aviator · wayfarer · rimless · kids · oversized square |
| backpack | standard · laptop XL · daypack · drawstring · roll-top · sling · mini · hiking w/ side pockets |

## Files
- `images/<class>/<class>_v<N>.jpg`
- `labels/<class>/<class>_v<N>.txt` — YOLO format: `class_id cx cy w h` (normalized)
- `classes.txt` — YOLO class order (0 = ruid)
- `annotations.csv` — variant name, size class (XS–XL), shape, color, background, rotation, pixel bbox
- `contact_sheet.png` — overview grid (one row per class, priority shown)
- `ruid_contact_sheet.png` — all 40 RUID images
- `generate_dataset.py` — regenerate or scale up:
  `python3 generate_dataset.py out_dir --renders 20 --ruid-renders 5 --seed 1` → 20 renders per variant,
  and RUID gets 5× that (800 RUID images out of 2,400). Requires Pillow + NumPy.

## Limits
These are clean, stylized renders, not photos. Good for prototyping a matching/search UI, demos, and
bootstrapping a classifier; for a model that works on real phone photos, mix in real images (below) and
fine-tune on photos taken in your own lost-and-found.

## Real-photo datasets covering the same classes
- **Open Images V7** (Google) — has Backpack, Umbrella, Mobile phone, Glasses, Sunglasses, Headphones, Bottle, Wallet-like Handbag; boxes included.
- **COCO 2017** — backpack, umbrella, handbag, bottle, cell phone, laptop.
- **ImageNet-1k** — classes incl. water bottle, umbrella, wallet, sunglasses, backpack, cellular telephone.
- **Roboflow Universe** — community lost-and-found sets, e.g. "Lost and Found Detector" and "Belonging Detection".
