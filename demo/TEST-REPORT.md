# WhereRU? verification report

Latest claim-policy update: 12 additional cases verify everyday requests without evidence, optional short messages, valuable/electronics/private-report evidence enforcement, owner-marked valuable lost reports, evidence updates, client-flag bypass rejection, and reclassification before approval. The 51 related recovery/privacy/concurrency checks passed three times (9.28s, 7.45s, 7.88s). The earlier complete 106-test suite below predates these 12 additional cases. TypeScript checking and the production build passed again. Browser checks used an isolated test database: a tablet showed the mandatory owner-only answer, a bottle showed the optional message form, and the bottle request submitted successfully with no answer. Evidence: `verification/valuable-only-question.png`, `verification/everyday-return-request.png`, `verification/valuable-policy-pass-{1,2,3}.txt`. The live rehearsal data was preserved.

Verified locally on October 11, 2026, in `/Users/sujai/Documents/Codex/WhereRU-Hackathon`. No Gemini credentials or real Gemini calls were used. Results establish the scenarios below; they cannot guarantee all future photos, devices or network conditions.

## Five verification layers

| Layer | What was verified | Result / evidence |
|---|---|---|
| 1. Source and build | Strict TypeScript, production Vite build, whitespace checks; original GitHub shared UI and stylesheet unchanged | Passed. `verification/level-1-types.txt`, `verification/level-1-build.txt`, `verification/source-check.json` |
| 2. Local components | 27 tests for local image drafts, all seven supplied examples after resize/recompression, native OCR, HEIC conversion, official-reference room comparison, unknown-room rejection, nearby privacy/deduplication and demo access guards | **27 passed**. `verification/level-2-local.txt` |
| 3. API and integration | All 106 tests, including accounts, CSRF, ownership, private reports/photos, uploads, statuses, matches, claims, messages, competing claims, dual confirmation, reputation idempotency, maps, maintenance, feeds, saved shortlists, seven-day deletion and the real five-hall scene model | **106 passed in each of three complete runs**. Logs below |
| 4. Browser workflows | Actual Figma frontend, three independent presenter sessions, lost/found photographs, match and nearby notifications, private claims, conversation, two-person return and points; profile preferences, registration, heatmap and feed | Passed in the local browser. Screenshots listed below. Feed also checked at 375×812 and 430×932 in light/dark themes |
| 5. Live HTTP and concurrency | Live presentation server via loopback and Wi-Fi address, independent cookies, private media and a server restart; separate repeated load tests with 20 simultaneous authenticated users | Live check passed; **4,578 stress requests, 60 new accounts, 30 returns and three isolated restarts**, with zero unexpected errors |

## Repeated complete suite

- Pass 1: **106 passed in 83.08s** — `verification/update-full-pass-1.txt`.
- Pass 2: **106 passed in 76.02s** — `verification/update-full-pass-2.txt`.
- Pass 3: **106 passed in 76.36s** — `verification/update-full-pass-3.txt`.

The suite includes the optional provider's key-free fallback/validation paths. Real Gemini responses are not verified. Email is intentionally a development/demo flow, not SMTP delivery.

## Concurrent-user stress results

`backend/tools/stress_demo.py` starts a real threaded HTTP server with the same application and an isolated temporary SQLite database for each round. It never resets or changes the presentation database. Each round creates **20 normal authenticated accounts** with independent cookie jars and CSRF tokens, while retaining the default authentication rate limit.

The script exercises ten concurrent owner/finder pairs, nearby subscriptions and alerts, private saved shortlists, object analysis, 20 private photo uploads, unauthorized access denials, private claims/messages, ten completed handoffs, 60 repeated confirmation requests, two competing approvals, 1,000 mixed reads, and a restart with cookies, private images, shortlists and points preserved. It checks foreign keys and exactly one reputation award per participant.

| Round | New accounts | Total requests | Mixed reads | Read p95 | Read p99 | Completed returns | Restart |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 20 | 1,526 | 1,000 | 143.37 ms | 184.67 ms | 10 | Passed |
| 2 | 20 | 1,526 | 1,000 | 149.74 ms | 202.04 ms | 10 | Passed |
| 3 | 20 | 1,526 | 1,000 | 133.57 ms | 169.68 ms | 10 | Passed |

All three rounds had **zero unexpected HTTP/application errors**. Intentional 403/404 privacy denials, the losing claim's 409, and an over-limit sign-in request's 429 passed their assertions. These are HTTP clients on this Mac, not 20 physical devices. Latencies were measured locally and include concurrent validation work; they are not a production capacity guarantee. Raw evidence: `verification/update-stress.txt`, `verification/stress-report.json`.

The separate `backend/tools/live_check.py` used localhost, 127.0.0.1 and the Mac's Wi-Fi address with three independent users against the running presentation app. It verified notifications, media, privacy boundaries, claims, messages, return confirmation, 30 concurrent reads and persistence across an actual launcher/server restart. Evidence: `verification/level-5-live.txt`.

## Browser evidence

- `verification/owner-match-alert.png`: Maya receives a potential match after another account posts the red bottle in Richard Weeks Hall.
- `verification/nearby-alert.png`: Alex receives a nearby request for the deliberately shared Richard Weeks Hall search area.
- `verification/missing-feed.png`: initial missing-item feed using the existing Figma styles; see the updated all-listings screen below.
- `verification/feed-filters-phone.png`: combined campus/category filters on a phone-sized viewport.
- `verification/feed-dark.png`: feed in the existing dark theme.
- `verification/heatmap.png`: actual API-backed aggregation of sample reports.
- `verification/local-room-comparison.png`: official Academic Building West 1150A reference produces a confirmed-review candidate; no guessed IDEA3 room number.
- `verification/weeks-room-suggestion.png`: supplied Weeks lecture-room reference returns RWH-105 with explicit reviewed-reference provenance and mandatory confirmation.

Feed checks covered 24→48 pagination, combined campus/category/date/search filters, sorting, public-only details, save/reload/unsave, private shortlist isolation, empty results and clearing filters. Private exact rooms and identifying evidence are not in feed responses.

## Image recognition scope and false-positive checks

The seven supplied photographs form a reviewed local collection of three objects. All seven match after resize/JPEG recompression, with edits still required. A real 24-megapixel HEIC uploads successfully and is normalized to a metadata-free JPEG. Unknown image details remain uncertain. Apple Vision OCR/classification runs locally when the native executable is available.

Your IDEA3 label comes from your explicit room confirmation. The app says this is a user-labeled example lookup, not an official panorama identification. No numeric lab room is fabricated.

Thirty-three verified Rutgers classroom panoramas provide 792 perspective views; two official ABW stills and the supplied Weeks reference make **795 indexed views**. Conservative feature-count, geometric-consistency, spatial-spread and ambiguity thresholds reject weak matches. A previous low threshold produced incorrect room candidates during testing and was tightened before the final suite. Unknown/blank rooms now fall back to manual selection. A cropped/recompressed official ABW reference remains a positive test.

The supplied Weeks lecture photo did **not** independently match an official panorama using the earlier strict homography threshold. The newly integrated DINOv2 five-hall scene matcher **does independently rank RWH-105 first using official views**, excluding the supplied photo from its references. Its RWH-105 label is a reviewed visual inference against the official panorama. It is now a supplied reference, and cropped/recompressed versions match it. The app exposes that provenance and requires confirmation. Source details are in `SOURCES.md`.

## Listings, expiry and five-hall update

The bottom navigation now reads **Home, Listings, Photo, Map, Profile**. Listings displays all active public LOST and FOUND reports, with separate type filters, combined campus/category/date/status filters, Saved, search, sorting and pagination. It refreshes while visible. Desktop browser checks verified All/Lost/Found counts, combined Busch/bottle filters and the expiry explanation; the existing layout and shared design styles remain unchanged. The separate tester successfully scanned the Weeks photo, displayed local model evidence and required a manual room selection. A no-match result offers manual entry.

Seven additional expiry tests cover the exact seven-day posting-time boundary, old occurrences with fresh posting dates, deletion across all statuses, physical photo deletion, private data and saved-list cleanup, stale notifications and matches, release of a newer counterpart from an expired accepted claim, retained completed-return points, 20 concurrent cleanup calls, startup catch-up and non-reused IDs. Cleanup is transactional and uses a retry queue for failed file deletions. The existing local database was backed up before the ID-preserving migration; 143 runtime reports were present afterward and foreign-key checks were clean. Rehearsal work was not reset.

Nine scene-model tests use the installed, real DINOv2-small and uploaded geometry matcher: new yaw/pitch/FOV, changed lighting and JPEG compression for each of five lecture halls; the supplied real Weeks photo compared **only with official views**; rejection of the supplied bottle and an out-of-catalogue ABW room; blank image rejection and API scope validation. All five novel synthetic viewpoints ranked the correct room first. The supplied Weeks photo scored approximately 0.755 against RWH-105, versus 0.69 for the runner-up. These similarities are model rankings, not calibrated probabilities. Every candidate requires confirmation. The earlier uploaded repository's benchmark claims were not used as our test results.

The matcher now persists model embeddings and reference features, avoiding first-scan reference recomputation. Model inference, geometric checks and image processing run on the host. The initial uncached scene-model evaluation took 23.7 seconds; subsequent isolated evaluations took about four seconds. This is a local measurement, not a promise about concurrent scans or other hardware. Physical photographs from all five classrooms have not been collected; the changed-viewpoint tests are rendered from their official panoramas.

Updated evidence:

- `verification/update-types.txt`, `verification/update-build.txt`: strict TypeScript and production build passed.
- `verification/update-expiry.txt`, `verification/update-scene-model.txt`: focused expiry/model checks.
- `verification/update-full-pass-1.txt` through `update-full-pass-3.txt`: three complete 106-test passes.
- `verification/update-stress.txt`: three new 20-account stress rounds, 4,578 requests and zero unexpected errors.
- `verification/update-live.txt`: 120 successful live reads with 20 concurrent clients across three independent loopback/LAN sessions; public-field and expiry checks passed without changing rehearsal reports.
- `verification/listings-update.png`: all-listings screen and five-tab bottom navigation.
- `verification/five-hall-model.png`: live RWH-105 scene-model suggestion from official references.
- `verification/update-source-check.json`: exact shared-style preservation, source/model version and catalogue counts.

## Reproduce the checks

```sh
cd /Users/sujai/Documents/Codex/WhereRU-Hackathon
./start-demo.command --check
backend/.venv/bin/python backend/tools/stress_demo.py
```

The live HTTP check changes only the named demo accounts' data; use it during rehearsal, not in the middle of a presentation:

```sh
backend/.venv/bin/python backend/tools/live_check.py --lan http://CURRENT-WIFI-IP:5003 --pause-for-restart
```

Keep this process open, restart the hosting server in its terminal, confirm `/api/health` responds, then press Enter in the check process. Use the current IP printed by the launcher.

## Remaining rehearsal and limits

- Visibility timer UI: verified 19 enabled duration choices from 15 minutes to one week, both scroll arrows, shortest/longest selections, keyboard selection, end-action preview and selection retention when returning from Review. The review still correctly says Private report. Custom timers are explicitly labeled as previews; the global seven-day deletion remains the active behavior. Strict TypeScript checking and a production build passed after this UI update.

- The app is running locally on port 5003. Verify one actual phone can load the current Wi-Fi address before the presentation. Campus Wi-Fi peer isolation, phone-specific behavior and closed-app OS push have not been verified.
- Notifications are in-app polling every two seconds while open. Keep receiving pages visible.
- Local photo matching is bounded; it is not general scene understanding or ownership proof. Claims are reviewed by the finder, and returns require both participants.
- Public basemap tiles need internet. Shared-area data, image lookup, matching, notifications and recovery run on the local server.
- Real email, Gemini, public deployment, lockers, verified institutional custody, trusted-helper membership and custom timed publication are outside this demo. The global seven-day deletion is implemented.
- All 140 seeded reports are labeled synthetic sample data. The original photos and old projects are untouched. The original latest `src/index.css` and `src/ui.tsx` are byte-for-byte unchanged; additions use scoped styling.

Use `DEMO-SCRIPT.md` for the three-minute rehearsal. Reset rehearsal only before a new run; the launcher preserves saved work.
