# WhereRU? — backend MVP

A standalone Flask + SQLite backend for a phone-first campus lost-and-found app. The frontend is intentionally deferred. The API runs locally on **port 5001**, leaving your existing CampusFind server and database alone.

**You can add the Gemini API key after downloading this ZIP.** Demo mode works without a key. Photos are stored and protected, but demo mode does not pretend to recognize photos, classrooms, or multiple objects.

## Start here on your Mac

1. Extract this ZIP into a new folder. Do not copy these files over the old CampusFind backend.
2. Open the extracted `WhereRU` folder in VS Code.
3. Open Terminal → New Terminal and run:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python manage.py init
python -m pytest -q
python demo_flow.py
python manage.py seed-demo
python app.py
```

Use Python 3.11 or newer (tested with 3.12). `requirements-lock.txt` also records the exact tested dependency environment if you need to reproduce it. If `.env` already exists, preserve it rather than repeating the copy command. Your backend database is created automatically in `backend/instance/whereru.db`.

Open **http://127.0.0.1:5001/api/health**. It should show `WhereRU?`, `ai_mode: demo`, and `auth_delivery: console`.

There is no website at `/` yet. A 404 at the root is expected. API routes other than health and sign-in require authentication; simply opening `/api/listings` in a browser returns 401 until that browser signs in.

## Try it against the running server

Keep Flask running. In a second terminal in `backend`:

```sh
./.venv/bin/python client_demo.py
```

Use `owner@example.com`, then enter the six-digit code printed in the Flask terminal. The script shows your demo reports, matches, notifications, and density map data. It signs out afterwards. Codes expire in ten minutes. The script's cookies are separate from browser cookies.

`python demo_flow.py` demonstrates a full private recovery in a temporary database: two accounts → lost/found reports → match → claim → message → handoff → independent confirmations → reputation awarded once. It deletes its temporary data afterwards.

## What is implemented

- Email-code accounts, sessions, logout, profile preferences, activity counts; console delivery and configurable SMTP.
- Signed-in public search with type/category/campus/date filters and pagination.
- Lost/found reports, server-assigned ownership, protected private fields, sensitive-item restrictions, editing, closing, and history.
- Validated JPEG/PNG/WebP uploads, metadata stripping, private-by-default media, explicit public-image choice.
- Gemini item suggestions with review/corrections, text-only fallback, optional semantic embeddings, classroom reference comparisons, and multi-item scan drafts.
- Automatic cross-campus matching on report create/edit and semantic indexing, duplicate-safe notifications, feedback.
- Private claims, human review, competing-claim protection, claim-linked messages, meetup/drop-off arrangements, two-party returns and contribution credits.
- Public density GeoJSON, per-item selected search-area GeoJSON, optional private location recording sessions, stop/delete/expiry controls.
- Read-only legacy listing import, local backups, cleanup, sample data, automated tests, and a matching benchmark.

## Three things you configure later

1. **Gemini:** set `AI_MODE=gemini` and `GEMINI_API_KEY` in `backend/.env`, then restart Flask. Model identifiers are configurable. See `docs/GEMINI.md`.
2. **Email:** fill the SMTP settings and set `AUTH_DELIVERY=smtp`. Console codes are local testing credentials, not verified control of an email address. See `docs/DEPLOYMENT.md`.
3. **Classroom references:** add permitted labeled reference photos to `backend/data` and populate `classrooms.json`. The catalog is intentionally empty; the app does not claim to recognize all Rutgers rooms without data.

## Preserve and import your existing work

The old CampusFind project is not included or changed. Its real database, accounts, secrets, or photos are never bundled.

Optional import from your existing Mac folder:

```sh
python manage.py import-legacy /Users/sujai/Downloads/CampusFind/backend/campusfind.db
```

This reads the old database without modifying it and copies listing fields into the NEW database. Imported reports are ownerless unless you explicitly use `--owner-id` with an existing WhereRU? user ID. Do not assign other people's reports to yourself. The importer does not transfer old sessions, accounts, photos, claims, or passwords. Reimporting identical data adds nothing. Naive legacy times are treated as UTC; review them if your old times meant something else.

Back up the new database with `python manage.py backup`. Original listings with status CLAIMED are imported CLOSED because their old claim workflow is not transferable. Imported historical returns do not create reputation credits.

## Scope and truthful limitations

This is a runnable **backend MVP**, not a completed mobile application or an audited production service. You still need the phone frontend to collect photos/GPS and render the maps. Foreground/background GPS collection is a client feature; the server cannot retrieve historical phone movements. Public routes are never generated from full private recordings.

Live Gemini, actual SMTP delivery, and real classroom accuracy require your credentials/reference dataset and have not been verified by a live service call. The test suite uses mocked AI responses for integration checks. The small supplied benchmark is synthetic and not evidence of deployment accuracy.

Some master-spec “Next/Future” features remain outside this package: institutional staff verification, moderator dashboards, trusted-helper audiences, direct invitations, native background tracking, push/email event notifications, claim proof attachments, payments, physical lockers, and fully automated real-world custody verification. See `docs/FEATURE_MATRIX.md`.

Start with `docs/API.md` for endpoint payloads, `docs/openapi.json` for the endpoint inventory, and `docs/DEMO.md` for the hackathon presentation flow.
