# Two-phone demo server

One laptop runs the backend and the app. Every phone that opens the app shares one catalog of
reports, claims and notifications, so the **sender** (finder) and **receiver** (owner) can be on
different phones. A seed script fills the campus with fake students so the app looks lived-in.

| Persona | Link | Role |
| --- | --- | --- |
| Jordan Lee | `<app url>/?as=jordan` | Sender: finds the item, scans the room, reviews the claim |
| Maya Patel | `<app url>/?as=maya` | Receiver: lost the item, claims it with a private detail |

The persona sticks to that phone after the first visit. It can also be switched in Settings → Demo persona.

## One command

```bash
./demo.sh           # stops old servers, starts backend + app + tunnel, prints both phone links
./demo.sh --fresh   # same, with freshly seeded demo data
```

## Set up by hand

```bash
# Terminal 1: backend (from the copy that has the room photos)
cd backend && source .venv/bin/activate
python tools/seed_demo.py        # fake students + reports; Maya lost a navy Hydro Flask in Hill Center 114
python app.py

# Terminal 2: app
cd frontend && npm run dev

# Terminal 3: public HTTPS link for the phones (use the port Vite printed)
cloudflared tunnel --url http://localhost:5173
```

Open `https://<tunnel>.trycloudflare.com/?as=jordan` on the sender phone and
`https://<tunnel>.trycloudflare.com/?as=maya` on the receiver phone.

`.env` must have `DEMO_LOGIN=true` (it is in `.env.example`); the shared catalog is off otherwise.

## The story

1. **Maya** (receiver) already has a lost report: navy blue Hydro Flask, Hill Center 114.
2. **Jordan** (sender) photographs the bottle, scans the room and posts it as found.
3. About 3 seconds later Maya's phone pops up **"Possible match near you: A blue water bottle was
   found in Hill Center, the same building where you lost it."** (on any screen). She taps it,
   opens the listing and claims it, giving the private detail: *Dent near the base and a cat
   sticker under the lid.*

   Matching: only a newly posted **found** report sends alerts, and only to the owner of the
   single best matching open **lost** listing. A match needs the same category plus either a
   shared distinctive word in the name ("hydro", "flask"; generic words like "bottle" don't
   count) or the same color (navy and blue count as the same). Posting keys, a backpack or a
   green bottle does not alert Maya. The alert says how close it is: same room, same building,
   about N min walk (from map coordinates), or same campus. Unread alerts collect in a
   collapsible "N new notifications" menu at the top of Explore.
4. Jordan gets the "New ownership claim" notification, sees Maya's private answer, approves it and
   arranges the return.
5. Maya gets "Your claim was approved", then "Item returned".

Bringing a different item? Re-seed with it:

```bash
python tools/seed_demo.py --owner-item "Wireless headphones" --owner-category Electronics \
  --owner-color Black --owner-detail "Left ear cushion is slightly torn" --owner-room ARC-103
```

## Reset between run-throughs

Run `python tools/seed_demo.py` again. No restart needed: open phones switch to the fresh data
within a few seconds. Options: `--reports 80` for a busier campus, `--fake-users 30`,
`--seed N` for different (but repeatable) data. Room ids come from `backend/data/classrooms.json`.

## How it works

- `backend/whereru/demo_sync.py`: `GET/POST /api/demo/catalog`, only when `DEMO_LOGIN=true` and not production.
- `backend/whereru/demo_store.py`: phones send their whole catalog; the server merges record by
  record (newest `updatedAt` wins, notifications stay read), so two phones acting at once don't
  overwrite each other. Stored in `backend/instance/demo_catalog.json` (not committed).
- Each seed starts a new *generation*; phones on an older one drop their local copy.
- `frontend/src/demoSync.ts`: pushes local changes immediately and polls every 2.5 s. Off when the
  backend isn't running, so the Figma preview still works on its own.
- Claim proof answers are shared through the demo catalog so the finder's phone can review them.
  That is fine for a demo of fake people, not for real users.
- Photos stay on the phone that took them; other phones show the category icon instead.

**After a Figma sync:** the hooks live in `frontend/src/reports.tsx` (`syncExport`, `syncReplace`,
`initialPersona`, and the `startDemoSync` effect in `ReportProvider`). If a sync overwrites that
file, re-apply those four pieces; `demoSync.ts` and `api.ts` are separate files.
