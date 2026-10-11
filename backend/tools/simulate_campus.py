"""Campus activity simulator: fake students post lost and found reports, and some items get returned,
live, while you demo. Everything goes through the backend's shared demo catalog, so every phone sees
it within a few seconds (feed, map, items-near-you counter).

    python tools/simulate_campus.py               # one event every ~20 s (Ctrl+C to stop)
    python tools/simulate_campus.py --every 8     # busier
    python tools/simulate_campus.py --pause       # freeze activity (e.g. right before the live find)
    python tools/simulate_campus.py --resume

It never touches the Jordan/Maya story: no reports in the category of the personas' open lost
items, nothing that names Maya's item, no claims on persona reports and no notifications to them.
Needs the backend running with DEMO_LOGIN=true. Uses only the standard library.
"""
import argparse
import importlib.util
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PAUSE_FILE = BACKEND / 'instance/simulator.paused'
PERSONAS = {'demo-jordan', 'demo-maya'}


def _load_seed():
    spec = importlib.util.spec_from_file_location('seed_demo', BACKEND / 'tools/seed_demo.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_seed()


class Api:
    def __init__(self, base):
        self.base = base.rstrip('/')

    def _call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={'Content-Type': 'application/json'} if data else {})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())

    def state(self):
        return self._call('GET', '/api/demo/catalog')

    def push(self, generation, reports=(), claims=()):
        return self._call('POST', '/api/demo/catalog', {
            'generation': generation,
            'catalog': {'reports': list(reports), 'claims': list(claims), 'notifications': []},
            'claim_answers': {},
        })


def words(text):
    return {w for w in ''.join(c if c.isalnum() else ' ' for c in text.lower()).split() if len(w) >= 4}


class Simulator:
    def __init__(self, api, rng, verbose=True):
        self.api, self.rng, self.verbose = api, rng, verbose
        self.rooms = seed.classrooms()
        self.coords = {}
        self.count = 0

    def log(self, text):
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}", flush=True)

    def students(self, state):
        fake = [p for p in state.get('personas') or [] if p.get('role') == 'fake']
        if fake:
            return fake
        ids = {r['reporterId'] for r in state['catalog']['reports'] if r['reporterId'] not in PERSONAS}
        return [{'id': i, 'firstName': i.split('-')[2].title() if i.count('-') >= 3 else 'A student',
                 'lastName': i.split('-')[3].title() if i.count('-') >= 3 else ''} for i in sorted(ids)] or \
            [{'id': 'demo-user-sim', 'firstName': 'A', 'lastName': 'student'}]

    def off_limits(self, reports):
        """Categories and words the simulator must not use, so the live story stays clean."""
        categories, names = set(), set()
        for r in reports:
            if r['reporterId'] in PERSONAS and r['status'] in ('active', 'possible_match', 'claim_under_review'):
                categories.add(r['category'])
                names |= words(r['itemName'])
        return categories, names

    def pick_item(self, categories, names):
        options = [(c, item) for c, items in seed.ITEMS.items() if c not in categories
                   for item in items if not (words(item[0]) & names)]
        return self.rng.choice(options) if options else ('Other', seed.ITEMS['Other'][1])

    def location(self, kind):
        if self.rng.random() < 0.55:
            return seed.room_location(self.rng, self.rng.choice(self.rooms), self.coords)
        return seed.place_location(self.rng, self.rng.choice(seed.PLACES), kind)

    def new_report(self, state, kind):
        reports = state['catalog']['reports']
        categories, names = self.off_limits(reports)
        category, item = self.pick_item(categories, names)
        student = self.rng.choice(self.students(state))
        now = datetime.now(timezone.utc)
        observed = now - timedelta(minutes=self.rng.randint(5, 90))
        self.count += 1
        rid = f"sim-{int(time.time() * 1000)}-{self.count}"
        report = seed.make_report(rid, student['id'], kind, category, item, self.location(kind), observed, 'active', now, self.rng)
        # created "now" so it tops the feed
        report['createdAt'] = report['updatedAt'] = seed.iso(now)
        state = self.api.push(state['generation'], reports=[report])
        where = report['location']['approximateLabel'].replace('Near ', 'near ').replace('Around ', 'around ')
        self.log(f"{kind.title():5} {item[1].lower()} {item[0]} {where} ({student['firstName']})")
        return state

    def resolve(self, state):
        """A fake student gets their item back: claim + return on an open fake found report."""
        reports = state['catalog']['reports']
        open_found = [r for r in reports if r['type'] == 'found' and r['status'] in ('active', 'possible_match')
                      and r['reporterId'] not in PERSONAS and r['visibility'] == 'public']
        if not open_found:
            return self.new_report(state, 'found')
        report = self.rng.choice(open_found)
        others = [s for s in self.students(state) if s['id'] != report['reporterId']]
        if not others:
            return state
        owner = self.rng.choice(others)
        stamp = seed.iso(datetime.now(timezone.utc))
        claim = {'id': f"sim-claim-{report['id']}", 'reportId': report['id'], 'claimantId': owner['id'],
                 'status': 'returned', 'createdAt': stamp, 'updatedAt': stamp}
        returned = {**report, 'status': 'returned', 'updatedAt': stamp}
        state = self.api.push(state['generation'], reports=[returned], claims=[claim])
        self.log(f"Returned {report['itemName']} to {owner['firstName']}")
        return state

    def step(self, state):
        roll = self.rng.random()
        if roll < 0.5:
            return self.new_report(state, 'found')
        if roll < 0.82:
            return self.new_report(state, 'lost')
        return self.resolve(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default='http://127.0.0.1:5001', help='Backend address (default http://127.0.0.1:5001)')
    parser.add_argument('--every', type=float, default=20, help='Average seconds between events (default 20)')
    parser.add_argument('--count', type=int, default=0, help='Stop after this many events (default: run until Ctrl+C)')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for repeatable runs')
    parser.add_argument('--pause', action='store_true', help='Pause a running simulator and exit')
    parser.add_argument('--resume', action='store_true', help='Resume a paused simulator and exit')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    if args.pause:
        PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PAUSE_FILE.write_text('paused\n')
        print('Simulator paused. Resume with: python tools/simulate_campus.py --resume')
        return
    if args.resume:
        PAUSE_FILE.unlink(missing_ok=True)
        print('Simulator resumed.')
        return
    if args.every <= 0:
        parser.error('--every must be positive')

    api = Api(args.url)
    sim = Simulator(api, random.Random(args.seed), verbose=not args.quiet)
    try:
        state = api.state()
    except (urllib.error.URLError, OSError) as error:
        sys.exit(f'Backend not reachable at {args.url} ({error}). Start it first (python app.py or ./demo.sh).')
    if not state.get('generation'):
        sys.exit('No demo catalog yet. Run python tools/seed_demo.py first.')
    sim.log(f"Simulating campus activity every ~{args.every:g}s against {args.url}. Ctrl+C to stop.")
    done, was_paused = 0, None
    try:
        while not args.count or done < args.count:
            paused = PAUSE_FILE.exists()
            if paused != was_paused and was_paused is not None:
                sim.log('Paused.' if paused else 'Resumed.')
            was_paused = paused
            if not paused:
                try:
                    state = api.state()          # fresh copy: phones and re-seeds change it
                    state = sim.step(state)
                    done += 1
                except urllib.error.HTTPError as error:
                    if error.code == 404:
                        sys.exit('Demo sync is off on the backend (needs DEMO_LOGIN=true).')
                    sim.log(f'Backend answered {error.code}; retrying.')
                except (urllib.error.URLError, OSError) as error:
                    sim.log(f'Backend not reachable ({error}); retrying.')
            if args.count and done >= args.count:
                break
            time.sleep(sim.rng.uniform(0.5, 1.5) * args.every)
    except KeyboardInterrupt:
        print()
    sim.log(f'Stopped after {done} events.')


if __name__ == '__main__':
    main()
