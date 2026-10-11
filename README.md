# Where RU?

**Student-to-student lost & found for Rutgers.** Built at HackRU Fall 2026.

Every lost item is asking the same question: where are you? Where RU? answers it.
A finder photographs the item and scans the room it was found in. The app identifies the
classroom and privately reaches the students who posted matching lost listings. The owner
proves ownership before anyone's identity is shared.

> Where RU? is an independent student project. It is not affiliated with or endorsed by Rutgers University.

## What works today

| Feature | Status |
| --- | --- |
| Found flow: real photo, room scan, review, publish | Working end to end with the backend |
| Room scan | **On-device computer vision** (OpenCV feature matching against classroom reference photos). No API key or internet needed |
| Item photo analysis | Dominant color from the photo (on-device); details are user-edited |
| Lost flow: report, known room or retraced steps, matches | Working end to end; matches come from the backend's matching engine |
| Matching + notifications | Working (backend ranks by category, wording, campus, area, and time) |
| Claims, private verification, handoff | Backend API complete; app screens still use demo data |
| Campus heatmap | Sample data |
| Sign-in | Email code supported by the backend; the demo uses "Skip for demo" (dev only) |
| Gemini | Optional (`AI_MODE=gemini`). Free-tier keys currently fail with `limit: 0`, so the demo runs on-device |

Without the backend running, the app falls back to built-in demo data and every screen still works.

## Run it locally (two terminals)

**Terminal 1: backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # AI_MODE=local and DEMO_LOGIN=true are already set
python app.py                 # http://127.0.0.1:5001/api/health
```

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev                   # open the printed URL; /api is proxied to Flask
```

To open it on a phone on the same Wi-Fi: `npm run dev -- --host`, then visit the Network URL.
Camera capture on phones needs HTTPS or localhost; uploading from the photo library works either way.

**Room scan needs reference photos.** Add 2 photos per classroom, see [docs/ROOM_PHOTOS.md](docs/ROOM_PHOTOS.md).

**Two-phone demo** (sender + receiver + fake students): `python tools/seed_demo.py`, then open
`?as=jordan` and `?as=maya` on two phones. See [docs/DEMO_SERVER.md](docs/DEMO_SERVER.md).

## Project layout

```
frontend/   React + Vite + TypeScript (designed in Figma Make). src/api.ts talks to the backend.
backend/    Flask + SQLite API, on-device vision (whereru/vision.py), optional Gemini
docs/       API reference, room photo guide, demo notes
```

## Data and privacy

- Building codes and sample rooms come from the public Rutgers Schedule of Classes feed.
- No FERPA-protected rosters or enrollment data are used. Long term, an authorized Rutgers
  integration could replace opt-in schedules; that is a future possibility, not a partnership.

## Frontend workflow (during the hackathon)

The UI is being designed in Figma Make. Figma is the source of truth for `frontend/src` until the UI is frozen.
To sync: in Figma Make's code view, download the project, then copy its `src/` over `frontend/src/` and commit.
Do not edit `frontend/src` here and in Figma at the same time, or one will overwrite the other.
