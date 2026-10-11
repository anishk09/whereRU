# WhereRU? — hackathon demo

A local, working lost-and-found demo using the newest `PranavBala01/whereru-figma` frontend fetched on October 11, 2026. The Figma layout, typography, colors, shared UI and dark/light theme remain the design foundation. Accounts, reports, matching, private claims and returns now use the Flask API and SQLite.

## Open the app

Double-click **start-demo.command**, or run:

```sh
cd /Users/sujai/Documents/Codex/WhereRU-Hackathon
./start-demo.command
```

Keep the server terminal open. On this Mac use **http://localhost:5003**. The launcher prints the current Wi-Fi address for other devices; the address during verification was **http://10.75.93.89:5003**. All devices must be on the same network. If a campus network isolates devices, use a shared hotspot. This is a local presentation server, not a public deployment.

Select a demo participant, continue, enter **000000**, then continue with the displayed name. Each device has its own session:

- **Maya** — lost-item owner: `http://localhost:5003/?role=owner`
- **Jordan** — finder: `http://127.0.0.1:5003/?role=finder`
- **Alex** — nearby helper: `http://10.75.93.89:5003/?role=helper`

On separate phones, all three use the Wi-Fi address and select different participants. For rehearsal on one Mac, the three different hostnames above provide independent cookie sessions. Tabs on the *same* hostname share a login. Changing participants affects that session only and does not reset anyone else's reports.

**Profile → Reset rehearsal** on the hosting Mac restores the dedicated sample database and 140 reports. The hosting session becomes Maya; the other sessions are signed out and must sign in again. Reset before rehearsing. It is disabled for remote LAN clients. The launcher does not reset saved work. `backend/instance/whereru-demo.db` and private uploads persist across restarts.

See **DEMO-SCRIPT.md** for the three-minute presentation.

## Features to show

- Lost and found reports with creator ownership and OPEN → CLAIMED → RETURNED status.
- Your seven photos, including HEIC upload and conversion with metadata removed.
- Local item drafts for the red bottle, gray Hydro Flask and tablet; editable descriptions, colors and private identifying details.
- **Owner match alert** when another account posts a compatible found report.
- **Nearby helper alert** when an opted-in helper is within 350 m of a deliberately shared search area. Area selection is private and expires after 24 hours. Exact room, timeline and evidence are excluded from that alert.
- Private evidence, finder review, messages, public meetup or staffed pickup arrangements, separate return confirmations and contribution points.
- A bottom **Listings** tab for every active public lost/found report: search, combined campus/category/last-seen/status filters, All/Lost/Found tabs, sorting, live refresh, pagination and a private saved shortlist that persists across restarts. Reports expire seven days after posting.
- Four-campus heatmap, private item registration, saved notification preferences and public lost/found browsing.

Notifications are live **in-app** updates while the page is open, polled every two seconds. OS push notifications when the app is closed are outside this demo. Allow the receiving page to stay visible during the presentation.

## Image and room recognition without an API key

The app works with `AI_MODE=demo` and an empty `GEMINI_API_KEY`. No Gemini call is required for either demonstration.

Your supplied photos form a reviewed local reference collection. Perceptual image comparison retrieves their item details even after resizing/recompression. New images also use macOS Apple Vision classification and OCR when available; uncertain fields stay blank and require review. This is a bounded reference/demo feature, not general-purpose Gemini vision or proof of ownership. Distinctive printing and stickers stay private by default.

You confirmed that all seven examples were taken in **IDEA3 Lab, Richard Weeks Hall, Busch**. Matching those example images offers that *user-confirmed* location and explicitly says it did not come from an official panorama. No numeric IDEA3 room number is invented.

Separately, the local room index contains **33 actual Rutgers classroom panoramas**, converted into perspective views and compared using visual features and geometric checks. Four are in Richard Weeks Hall: 102, 105, 206 and 208. None has been verified as IDEA3. Unknown or weakly matched rooms fall back to manual selection. Every suggestion requires confirmation. `Try an official Rutgers reference photo` demonstrates the separate Rutgers-reference comparison.

The supplied **Weeks lecture hall** photograph is an additional reviewed reference in the room gallery. Its layout was visually compared with the official RWH-105 panorama and labeled Richard Weeks Hall 105. The geometric reference matcher identifies repeat/cropped versions of that reference. The newly integrated five-hall DINOv2 scene model separately selected RWH-105 from official views, with the supplied photo excluded from that model’s references. The suggestion states its provenance and requires confirmation.

The building marker used for Richard Weeks is approximate, from the Rutgers RWH-206 map. Public heatmap cells and nearby alerts represent broad search areas, not evidence that an item is physically present.

## Five-hall room model

The uploaded `whereRU-main/backend/whereru/vision.py` supplies the DINOv2 scene embedding and one-to-one SIFT/fundamental-matrix matcher, adapted in `backend/whereru/scene_matcher.py`. Original code is preserved in `design-source/uploaded-room-matcher.py`. The five-room catalogue covers **ARC-103, LSH-A102, PHY-001, RWH-105 and SEC-111**. All official references and the pinned DINOv2-small weights are installed on this Mac. After setup, scans require no network or API key.

On Home, select **Test classroom recognition → Five lecture halls · local scene model → Upload**. Choose a photo, review the suggested rooms and confirm a room. The app offers up to five supported candidates; it does not fill weak results with guesses. **All installed rooms** retains the broader catalogue and user-confirmed IDEA3 examples. These are different recognition scopes. The standalone tester does not create a listing.

The launcher installs the model if missing. To rebuild it explicitly:

```sh
backend/.venv/bin/python -m pip install -r backend/requirements-rooms.txt
backend/.venv/bin/python backend/tools/prepare_references.py
backend/.venv/bin/python backend/tools/prepare_scene_model.py
```

## Seven-day deletion

Every report is deleted **seven days after its posting time**, including private, claimed and returned reports. Last-seen time and edits do not extend its lifetime. Startup, API access and a background sweep every minute enforce expiry; an offline server catches up when restarted. Stored report photos, identifying evidence, claim conversations, related matches and stale notifications are removed. Saved entries and potential locations are removed with the report. Already earned return points and return counts are retained as per-user totals. A newer counterpart of an expired accepted claim becomes open again. Expired IDs are never reused.

The expiry tests use isolated temporary databases and simulated posting dates, so you can verify the one-week boundary now without changing your rehearsal data. See **RUN-AND-TEST.md** for exact steps.

## Design and source

Original Figma-generated code is preserved in `design-source/`. The unchanged latest `index.css` and `ui.tsx` underpin the connected app in `src/`; scoped styles in `src/demo-tools.css` support the photo gallery, notifications, feed and participant selector. Source commit and reference provenance are in **SOURCES.md**. The prepared draft branch is `codex/hackathon-demo`.

## Development and verification

Python virtual environment: `backend/.venv`. Node/pnpm dependencies are installed. VS Code workspace settings and tasks are included.

```sh
./start-demo.command --check
```

This runs strict TypeScript, a production build and the complete API/local-image test suite. Other commands:

```sh
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python -m pytest backend/tests/test_local_features.py -q
backend/.venv/bin/python backend/tools/live_check.py --lan http://10.75.93.89:5003
backend/.venv/bin/python backend/tools/stress_demo.py
```

For hot reload: keep Flask on 5003 and run `pnpm dev`, then visit port 8444. `backend/tools/prepare_references.py --download` refreshes the official room references. The eight reviewed, metadata-stripped demo JPEGs are included in `public/examples/`. Private uploads, downloaded classroom reference caches, model weights, native binaries, runtime data and test screenshots are excluded from Git. The launcher prepares the official classroom references and local scene model on first setup; this requires internet and takes longer than launching the already-prepared Mac.

Everyday claims use a return request with an optional message. Electronics, sensitive categories (keys, wallet, ID, cards and cash), and reports marked valuable/sensitive require at least eight characters of private ownership evidence. The server checks the found report and any linked lost report; hiding the prompt in the client cannot bypass this rule. Both flows require finder approval and independent return confirmation by both participants.

**TEST-REPORT.md** records five distinct verification layers, commands, outcomes and limits. Passing checks establishes the tested scenarios; it does not guarantee every possible device, photo or network condition.

## Presentation scope

Real email delivery is intentionally skipped. Demo accounts and the fixed code belong only to the isolated development demo. Gemini, public deployment, closed-app push delivery, institutional custody verification, trusted-helper membership, timed publication, lockers and real schedule import are not implemented presentation features. Related Figma options show their limitations or remain disabled. Private sensitive reports and secure access boundaries are implemented; private registry photos are attached when filing a lost report.
