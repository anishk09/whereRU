"""Seed the shared demo catalog: a sender, a receiver and a crowd of fake students.

    python tools/seed_demo.py                 # fresh demo (replaces the shared catalog)
    python tools/seed_demo.py --reports 80    # busier campus
    python tools/seed_demo.py --owner-item "Black JBL headphones" --owner-category Electronics

Personas (they match the app's built-in demo users):
    Jordan Lee  (demo-jordan) - the SENDER: finds an item, scans the room, reviews the claim
    Maya Patel  (demo-maya)   - the RECEIVER: lost the item, gets the match, claims it

Open the app with ?as=jordan on one phone and ?as=maya on the other. Every phone that is open
switches to the new data within a few seconds; no restart needed. Everything generated here is
fictional and labeled as sample data in the app.
"""
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _load_demo_store():
    # Load the module by path so this script runs without the backend's packages installed.
    import importlib.util
    spec = importlib.util.spec_from_file_location('demo_store', BACKEND / 'whereru/demo_store.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo_store = _load_demo_store()

CAMPUS_CENTERS = {
    'College Ave': (-74.4518, 40.5020),
    'Busch': (-74.4600, 40.5225),
    'Livingston': (-74.4370, 40.5235),
    'Cook/Douglass': (-74.4360, 40.4835),
}

# Non-classroom places (same names and coordinates the app's map uses).
PLACES = [
    ('College Ave', 'College Ave Student Center', (-74.4518, 40.5034), 'building'),
    ('College Ave', 'Alexander Library', (-74.4522, 40.5045), 'library'),
    ('College Ave', 'Scott Hall bus stop', (-74.4490, 40.4998), 'bus_stop'),
    ('Busch', 'Busch Student Center', (-74.4584, 40.5235), 'building'),
    ('Busch', 'Busch Dining Hall', (-74.4596, 40.5241), 'dining'),
    ('Busch', 'Library of Science and Medicine', (-74.4629, 40.5257), 'library'),
    ('Livingston', 'Livingston Student Center', (-74.4369, 40.5241), 'dining'),
    ('Livingston', 'Livingston Plaza', (-74.4359, 40.5249), 'outdoor'),
    ('Cook/Douglass', 'Cook Campus Center', (-74.4364, 40.4813), 'building'),
    ('Cook/Douglass', 'Douglass Student Center', (-74.4370, 40.4855), 'outdoor'),
]

FIRST = ['Alex', 'Sam', 'Priya', 'Daniel', 'Aisha', 'Kevin', 'Sofia', 'Marcus', 'Emily', 'Omar', 'Hannah',
         'Ryan', 'Fatima', 'Chris', 'Grace', 'Ethan', 'Nina', 'Tyler', 'Leah', 'Jamal', 'Olivia', 'Arjun',
         'Chloe', 'Diego', 'Mei', 'Noah', 'Zara', 'Lucas', 'Ava', 'Ibrahim']
LAST = ['Nguyen', 'Garcia', 'Shah', 'Kim', 'Rahman', 'Chen', 'Rossi', 'Johnson', 'Park', 'Haddad', 'Cohen',
        'Murphy', 'Ali', 'Brown', 'Liu', 'Martinez', 'Desai', 'Wilson', 'Okafor', 'Lopez']

# category -> list of (item name, color, public description, private detail)
ITEMS = {
    'Bottles': [
        ('Hydro Flask water bottle', 'Navy blue', 'Insulated bottle with a straw lid.', 'Dent near the base and a NJ sticker.'),
        ('Nalgene bottle', 'Clear green', 'Wide-mouth plastic bottle.', 'Initials written on the lid in marker.'),
        ('Stanley tumbler', 'Cream', '40 oz tumbler with a handle.', 'Chip in the paint on the handle.'),
    ],
    'Electronics': [
        ('AirPods case', 'White', 'Charging case, no earbuds visible.', 'Engraved with a small star.'),
        ('TI-84 calculator', 'Black', 'Graphing calculator in a slide cover.', 'Name scratched inside the battery cover.'),
        ('USB-C laptop charger', 'White', '65W charger with a coiled cable.', 'Green tape on the brick.'),
        ('Wireless headphones', 'Black', 'Over-ear headphones.', 'Left ear cushion is slightly torn.'),
    ],
    'Wallets/IDs': [
        ('Wallet', 'Brown', 'Leather bifold wallet.', 'Holds a Rutgers ID and a library card.'),
        ('Rutgers ID card', 'Red and white', 'Student ID card.', 'Name and photo on the card.'),
    ],
    'Keys': [
        ('Keys on a lanyard', 'Silver and red', 'Several keys on a Rutgers lanyard.', 'Includes a uniquely shaped apartment key.'),
        ('Car key fob', 'Black', 'Key fob with one key.', 'Toyota fob with a blue keychain.'),
    ],
    'Bags': [
        ('Backpack', 'Black', 'Black backpack with laptop sleeve.', 'Has a physics textbook inside.'),
        ('Tote bag', 'Beige', 'Canvas tote bag.', 'Printed design from a local bookstore.'),
    ],
    'Clothing': [
        ('Rutgers hoodie', 'Gray', 'Pullover hoodie.', 'Size M, small paint stain on the sleeve.'),
        ('Rain jacket', 'Dark green', 'Light rain jacket.', 'Receipt in the left pocket.'),
        ('Beanie', 'Scarlet', 'Knit beanie.', 'Pom-pom on top.'),
    ],
    'School Supplies': [
        ('Spiral notebook', 'Blue', 'Five-subject notebook.', 'Orgo notes, name on the inside cover.'),
        ('Pencil case', 'Purple', 'Zip pencil case.', 'Has a highlighter set inside.'),
    ],
    'Other': [
        ('Umbrella', 'Black', 'Compact folding umbrella.', 'Wooden handle.'),
        ('Glasses case', 'Tortoiseshell', 'Hard glasses case.', 'Prescription glasses inside.'),
    ],
}
SENSITIVE = {'Wallets/IDs', 'Keys', 'Electronics'}


def iso(when):
    return when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f'{when.microsecond // 1000:03d}Z'


def seed_iso_now():
    return iso(datetime.now(timezone.utc))


def classrooms():
    data = json.loads((BACKEND / 'data/classrooms.json').read_text())
    return data['rooms']


def building_coordinates(rng, campus, cache, building):
    if building not in cache:
        x, y = CAMPUS_CENTERS[campus]
        cache[building] = (round(x + rng.uniform(-0.004, 0.004), 5), round(y + rng.uniform(-0.003, 0.003), 5))
    return cache[building]


def room_location(rng, room, cache):
    coords = building_coordinates(rng, room['campus'], cache, room['building'])
    return {
        'campus': room['campus'], 'area': room['building'], 'building': room['building'], 'room': room['room'],
        'source': 'room-scan', 'placeType': 'classroom', 'approximateLabel': f"Near {room['building']}",
        'approximateCoordinates': list(coords),
        'precise': {'label': f"{room['building']} {room['room']}", 'coordinates': list(coords)},
    }


def place_location(rng, place, kind):
    campus, name, (x, y), place_type = place
    coords = [round(x + rng.uniform(-0.0006, 0.0006), 5), round(y + rng.uniform(-0.0005, 0.0005), 5)]
    return {
        'campus': campus, 'area': name, 'building': name, 'source': 'timeline' if kind == 'lost' else 'manual-area',
        'placeType': place_type, 'approximateLabel': f'Near {name}' if kind == 'found' else f'Around {name}',
        'approximateCoordinates': coords, 'precise': {'label': name, 'coordinates': coords},
    }


def make_report(rid, reporter, kind, category, item, location, observed, status, now, rng, sample=True):
    name, color, public, private = item
    sensitive = category in SENSITIVE
    created = min(observed + timedelta(minutes=rng.randint(10, 90)), now)
    return {
        'id': rid, 'reporterId': reporter, 'type': kind, 'itemName': name, 'category': category, 'color': color,
        'publicDescription': public, 'privateDetails': private, 'photoUrl': None, 'location': location,
        'observedAt': iso(observed), 'createdAt': iso(created), 'updatedAt': iso(created), 'status': status,
        'visibility': 'trusted-only' if sensitive else 'public', 'sensitive': sensitive, 'sample': sample,
    }


def build(args):
    rng = random.Random(args.seed)
    now = datetime.now(timezone.utc)
    rooms = classrooms()
    by_id = {r['id']: r for r in rooms}
    coords = {}

    fake_users = []
    names = rng.sample([(f, l) for f in FIRST for l in LAST], args.fake_users)
    for first, last in names:
        uid = f'demo-user-{first.lower()}-{last.lower()}'
        fake_users.append({'id': uid, 'firstName': first, 'lastName': last,
                           'email': f'{first.lower()}.{last.lower()}@scarletmail.rutgers.edu'})

    reports, claims, notifications = [], [], []

    def anywhere(kind):
        if rng.random() < 0.55:
            return room_location(rng, rng.choice(rooms), coords)
        return place_location(rng, rng.choice(PLACES), kind)

    # The crowd: open lost and found reports all over campus.
    statuses = ['active'] * 8 + ['possible_match'] * 2 + ['returned', 'closed']
    for n in range(args.reports):
        kind = 'found' if rng.random() < 0.55 else 'lost'
        category = rng.choice(list(ITEMS))
        # Keep the receiver's item unique so the live find is the obvious match.
        choices = [i for i in ITEMS[category] if i[0].lower() != args.owner_item.lower()] or ITEMS['Other']
        item = rng.choice(choices)
        if item not in ITEMS[category]:
            category = 'Other'
        status = rng.choice(statuses)
        observed = now - timedelta(hours=rng.uniform(0.5, 24 * 6))
        reporter = rng.choice(fake_users)['id']
        report = make_report(f'seed-{n:03d}', reporter, kind, category, item, anywhere(kind), observed, status, now, rng)
        reports.append(report)
        if status == 'returned' and kind == 'found':
            claimant = rng.choice([u for u in fake_users if u['id'] != reporter])['id']
            claims.append({'id': f'seed-claim-{n:03d}', 'reportId': report['id'], 'claimantId': claimant,
                           'status': 'returned', 'createdAt': report['createdAt'], 'updatedAt': report['updatedAt']})

    # Jordan (sender): a finder with some history.
    jordan_history = [
        ('Electronics', ITEMS['Electronics'][1], 'returned', 72, by_id.get('ARC-103')),
        ('Clothing', ITEMS['Clothing'][1], 'returned', 150, None),
        ('Electronics', ITEMS['Electronics'][0], 'active', 5, None),
    ]
    for i, (category, item, status, hours, room) in enumerate(jordan_history):
        location = room_location(rng, room, coords) if room else place_location(rng, PLACES[1 + i], 'found')
        report = make_report(f'jordan-found-{i}', 'demo-jordan', 'found', category, item, location,
                             now - timedelta(hours=hours), status, now, rng)
        reports.append(report)
        if status == 'returned':
            claimant = fake_users[i]['id']
            claims.append({'id': f'jordan-claim-{i}', 'reportId': report['id'], 'claimantId': claimant,
                           'status': 'returned', 'createdAt': report['createdAt'], 'updatedAt': report['updatedAt']})
            notifications.append({'id': f'jordan-note-{i}', 'userId': 'demo-jordan', 'reportId': report['id'],
                                  'claimId': f'jordan-claim-{i}', 'title': 'Item returned',
                                  'body': f"{item[0]} is back with its owner. Thanks for helping!",
                                  'createdAt': report['updatedAt'], 'read': True, 'demo': True})

    # Maya (receiver): her lost item is the one the sender finds live on stage.
    owner_room = by_id.get(args.owner_room) or rooms[0]
    owner_category = args.owner_category
    owner_item = (args.owner_item, args.owner_color, f'{args.owner_color} {args.owner_item.lower()}.',
                  args.owner_detail)
    reports.append(make_report('maya-lost', 'demo-maya', 'lost', owner_category, owner_item,
                               room_location(rng, owner_room, coords), now - timedelta(hours=3), 'active', now, rng,
                               sample=False))
    reports.append(make_report('maya-lost-history', 'demo-maya', 'lost', 'Other', ITEMS['Other'][0],
                               place_location(rng, PLACES[6], 'lost'), now - timedelta(hours=240), 'returned', now, rng))

    catalog = {'reports': reports, 'claims': claims, 'notifications': notifications}
    personas = [
        {'id': 'demo-jordan', 'firstName': 'Jordan', 'lastName': 'Lee', 'email': 'jordan.lee@rutgers.edu', 'role': 'sender'},
        {'id': 'demo-maya', 'firstName': 'Maya', 'lastName': 'Patel', 'email': 'maya.patel@rutgers.edu', 'role': 'receiver'},
    ] + [{**u, 'role': 'fake'} for u in fake_users]
    return catalog, personas, owner_room


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--static-out', metavar='PATH',
                        help='Instead of seeding the backend, write the data the static web demo bundles '
                             '(frontend/src/demoSeed.json); times are shifted to "now" when the app loads')
    parser.add_argument('--out', default=str(BACKEND / 'instance/demo_catalog.json'),
                        help='Catalog file the backend serves (default: instance/demo_catalog.json)')
    parser.add_argument('--reports', type=int, default=48, help='Number of reports from fake students (default 48)')
    parser.add_argument('--fake-users', type=int, default=20, help='Number of fake students (default 20)')
    parser.add_argument('--seed', type=int, default=2026, help='Random seed, for the same data every time')
    parser.add_argument('--owner-item', default='Hydro Flask water bottle', help="Maya's lost item")
    parser.add_argument('--owner-category', default='Bottles', choices=list(ITEMS), help="Maya's item category")
    parser.add_argument('--owner-color', default='Navy blue')
    parser.add_argument('--owner-detail', default='Dent near the base and a cat sticker under the lid.',
                        help='Private detail Maya uses to prove ownership')
    parser.add_argument('--owner-room', default='HLL-114', help='Room id from data/classrooms.json where Maya lost it')
    args = parser.parse_args(argv)
    if not 0 < args.fake_users <= len(FIRST) * len(LAST) or args.fake_users < 4:
        parser.error('--fake-users must be at least 4')
    if args.reports < 0 or args.reports > 1000:
        parser.error('--reports must be between 0 and 1000')

    catalog, personas, owner_room = build(args)
    if args.static_out:
        out = Path(args.static_out)
        out.write_text(json.dumps({'generatedAt': seed_iso_now(), **catalog}, indent=1) + '\n')
        print(f"Wrote {len(catalog['reports'])} reports for the static demo -> {out}")
        return
    state = demo_store.reset(args.out, catalog, personas=personas)
    reports = catalog['reports']
    print(f"Seeded {len(reports)} reports ({sum(r['type'] == 'found' for r in reports)} found, "
          f"{sum(r['type'] == 'lost' for r in reports)} lost), {len(catalog['claims'])} past claims, "
          f"{len(personas) - 2} fake students -> {args.out}")
    print(f"Generation {state['generation']}. Open phones will switch to this data within a few seconds.")
    print(f"  Sender  (Jordan): <app url>/?as=jordan")
    print(f"  Receiver (Maya):  <app url>/?as=maya   lost: {args.owner_color} {args.owner_item} "
          f"in {owner_room['building']} {owner_room['room']}")
    print(f"  Maya's private proof detail: {args.owner_detail}")


if __name__ == '__main__':
    main()
