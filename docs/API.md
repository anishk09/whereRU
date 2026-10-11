# WhereRU? API

Base URL: `http://127.0.0.1:5001`. JSON errors contain `error` and `message`. Dates must include an offset or Z. The server stores event times normalized to UTC.

## Authentication contract

All endpoints except health, code request, and code verification require the HttpOnly `whereru_session` cookie. All authenticated POST/PATCH/DELETE requests require `X-CSRF-Token` from sign-in or `/api/auth/me`. Send JSON (`{}` for actions without other fields). Uploads use multipart instead. Cookies last at most 24 hours and are revoked on logout.

A frontend should use `credentials: "include"`, retain the CSRF token in memory, and retrieve it again through `/api/auth/me` on reload. Do not place authentication tokens in URL parameters. Choose either localhost or 127.0.0.1 consistently. Configure explicit ALLOWED_ORIGINS if the future frontend uses another origin. Native/mobile clients must preserve their cookie jar as well as the CSRF token.

| Method | Endpoint | Body / purpose |
|---|---|---|
| GET | `/api/health` | Application, AI mode and delivery mode |
| POST | `/api/auth/request-code` | `{"email":"owner@example.com"}` |
| POST | `/api/auth/verify-code` | `{"email":"owner@example.com","code":"123456"}`; use the actual code |
| GET | `/api/auth/me` | User and CSRF token |
| POST | `/api/auth/logout` | `{}` |
| PATCH | `/api/me` | `{"display_name":"Alex","notifications_enabled":true}` |
| GET | `/api/me/activity` | Report/claim/return counts and reputation |

Console-code accounts have `email_verified: false`. SMTP-delivered codes establish email control and set it true. Passwords and password resets are intentionally absent: this is an email-code design.

## Reports

POST `/api/listings`:

```json
{
  "type": "LOST",
  "title": "Blue water bottle",
  "description": "Insulated bottle",
  "category": "bottle",
  "attributes": {"color":"blue","brand":null,"distinctive_features":["Unique private mark"]},
  "campus": "College Ave",
  "location": "Library",
  "private_location": "Room detail",
  "private_description": "Private ownership evidence",
  "occurred_at": "2026-10-10T14:00:00-04:00",
  "visibility": "PUBLIC",
  "reward": 0
}
```

Required: type, title, occurred_at. Categories: `bottle`, `electronics`, `clothing`, `bag`, `keys`, `wallet`, `id_card`, `financial_card`, `cash`, `other`. Sensitive categories must be PRIVATE. Text and image scanning cannot guarantee discovery of all personal information; use private fields deliberately.

The server sets creator and status. `attributes` supports color, brand, material, model and distinctive_features. Unique identifying features are creator-only. Public `description` and `location` must not contain details the creator intends to keep secret.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/listings` | Signed-in public OPEN feed; q/type/category/campus/from/to filters |
| GET | `/api/me/listings` | Your reports including closed/returned and private fields |
| GET | `/api/listings/{id}` | Authorized detail; creator sees private fields |
| PATCH | `/api/listings/{id}` | Partial update, creator-only, OPEN only; type/creator/status cannot change |
| POST | `/api/listings/{id}/close` | `{"reason":"WITHDRAWN"}` or `SELF_RECOVERED` for LOST; closes without reputation |
| GET | `/api/listings/{id}/history` | Creator-only event history |
| POST | `/api/listings/{id}/drop-off` | `{"place":"Staffed information desk"}`; user-reported custody, not completed return |

Feeds generally support `limit` (1–100, default 30) and `offset`. Public feed always omits private evidence and creator ID, even when the viewer is the report creator. Use owner/detail endpoints for private data. Private inaccessible and nonexistent IDs both return 404.

## Images

POST `/api/listings/{id}/images` with multipart field `image`, cookie and CSRF header. JPEG/PNG/WebP, at most 16 MB and 60 megapixels (the app shrinks phone photos to about 1600 px before upload); at most five per report. The backend re-encodes and strips metadata. Uploads are always private initially.

- GET `/api/images/{id}` — authorized JPEG bytes.
- PATCH `/api/images/{id}` with `{"is_public":true}` — explicit sharing on a public report; sensitive images cannot be shared.
- DELETE `/api/images/{id}` with `{}` — creator of OPEN report only.

No file path is ever accepted from the API. An image URL is not a bypass of report privacy.

## AI

See GEMINI.md. All calls require report ownership and `consent_to_ai:true`.

`AI_MODE=local` runs without any API key: `recognize-room` uses on-device OpenCV feature matching against the reference photos in `data/classrooms.json` (see ROOM_PHOTOS.md), and `analyze` adds the item's dominant color from the photo. Optional body field `campus` narrows the rooms compared.

Development only: `POST /api/auth/demo-login` with `{"email":"...","display_name":"..."}` signs in without a code when `DEMO_LOGIN=true` and `APP_ENV` is not production. It powers the app's "Skip for demo" button.

- POST `/api/listings/{id}/analyze` — `{"consent_to_ai":true,"image_ids":[]}`. Returns analysis ID and suggestions.
- POST `/api/analyses/{id}/apply` — `{"confirm":true,"corrections":{}}`. Applies reviewed item suggestions if revision is current.
- POST `/api/listings/{id}/semantic-index` — sends current title/description/category to embeddings; enables cross-report semantic ranking where both owners opted in.
- GET `/api/classrooms` — configured reference metadata only.
- POST `/api/listings/{id}/recognize-room` — `{"consent_to_ai":true,"image_id":1,"building":"Optional building"}`.
- POST `/api/listings/{id}/scan-items` — `{"consent_to_ai":true,"image_id":1}`; separate drafts requiring review.

AI runs synchronously with a bounded provider timeout. This keeps the hackathon deployment simple; move to a durable background queue for larger workloads. Provider responses are validated. Model-call failures do not prevent manual reporting.

## Matches and notifications

- GET `/api/matches` — candidates belonging to your lost reports. Cross-campus candidates are allowed.
- GET `/api/matches/{id}` — current authorized candidate.
- POST `/api/matches/{id}/feedback` — `{"decision":"NOT_MINE"}` or `POSSIBLE`.
- GET `/api/notifications` — recipient-only records and unread_count.
- POST `/api/notifications/{id}/read` — `{}`.

Restricted found reports yield a generic match invitation, not private descriptions, locations, photos or numeric scores. The match ID permits the lost reporter to submit private claim evidence against its found ID. It does not grant access to the private report itself. Finders do not receive the identities of every possible lost owner.

A notification has kind, resource_id and a generic message. Route MATCH to `/api/matches/{resource_id}`; CLAIM/MESSAGE/HANDOFF to `/api/claims/{resource_id}`. Every destination rechecks access. Old alerts can remain in history even when their candidate is inactive.

## Claims, messages and handoffs

POST `/api/claims`:

```json
{"found_id":2,"lost_id":1,"evidence":"Private detail only the owner should know"}
```

lost_id is optional, but when supplied it must identify your own OPEN lost report. Public eligible found reports can be claimed; private found reports require a current match to your lost report. You cannot claim your own find. Each user has at most one active claim per found report and at most three total submissions for it.

| Method | Endpoint | Body / purpose |
|---|---|---|
| GET | `/api/claims` | Claims where you are claimant or finder |
| GET | `/api/claims/{id}` | Participant-only evidence and decision |
| POST | `/api/claims/{id}/evidence` | Claimant supplies updated `evidence` while pending/needs-info |
| POST | `/api/claims/{id}/review` | Finder supplies `decision`: ACCEPTED, REJECTED, NEEDS_INFO; optional `note` |
| POST | `/api/claims/{id}/cancel` | `{}`; cannot cancel after a participant confirms transfer |
| GET | `/api/claims/{id}/messages` | Private paginated conversation |
| POST | `/api/claims/{id}/messages` | `{"body":"Meet at the student center?"}` |
| POST | `/api/claims/{id}/handoff` | `{"method":"MEETUP","place":"Student center","arranged_at":"2026-10-11T15:00:00-04:00"}` |
| GET | `/api/claims/{id}/handoff` | Participant-only arrangements |
| POST | `/api/claims/{id}/handoff/confirm` | `{}` from each participant separately |
| GET | `/api/return-guidance` | Official source links; not a Rutgers partnership |

Handoff methods: MEETUP or STAFFED_DROP_OFF. Sensitive item categories require staffed handling. A reported drop-off is not institutional verification. Two-party confirmation records the participants' assertions; the app cannot independently verify physical transfer. Finder receives 10 contribution credits and recipient 2, once per completed handoff. No financial payment is processed.

Transitions: OPEN → CLAIMED only on acceptance; CLAIMED → RETURNED only on both confirmations. OPEN → CLOSED handles withdrawal/self-recovery without credits. Cancellation before transfer can reopen CLAIMED reports. Accepted claims and linked reports are updated in one database transaction. Other competing claims are rejected; cancelling the winner does not automatically revive them.

## Maps: no public movement trails

POST `/api/listings/{id}/potential-locations` REPLACES that report's selected locations:

```json
{"locations":[{"label":"Library","latitude":40.503,"longitude":-74.452,"priority":3,"share_public":true}]}
```

At most 20 points; priority is a reporter-supplied weight from 1 to 3. Sharing is off by default. It is separate from whether the report itself is public.

- GET `/api/listings/{id}/search-areas` returns GeoJSON points with intensity/radius/reason. Creators see all selected places; others see only explicitly shared places on PUBLIC reports. It does not return routes, times, or historical phone points. These are search suggestions based on reporter choices, not calibrated probabilities.
- GET `/api/maps/density` aggregates active PUBLIC LOST reports' explicitly shared places into 0.002-degree cells. One report contributes at most one unit total. Supports category/campus/from/to filters. Reports without shared coordinates do not appear; restricted reports never contribute. Density is reporting activity, not population-adjusted loss risk.

## Optional private recording

- POST `/api/location-sessions` with `{"consent":true}`.
- POST `/api/location-sessions/{id}/points` with `{"points":[{"latitude":40.5,"longitude":-74.45,"accuracy":20,"recorded_at":1791670000.0}]}`. Replace the example timestamp with the actual current Unix seconds after consent.
- GET `/api/location-sessions/{id}` — owner-only points.
- POST `/api/location-sessions/{id}/stop` with `{}`.
- DELETE `/api/location-sessions/{id}` with `{}`.

Only points after session consent and no more than 30 seconds in the future are accepted. Sessions expire after 24 hours. Expired data is inaccessible and is deleted by `manage.py cleanup` or on a subsequent recording start. Run cleanup regularly for physical retention enforcement. The server does not get GPS by itself and cannot recover locations from before recording. Frontend native/background permission work remains separate.


## Room scan without storing the photo

`POST /api/recognize-room` (signed in, CSRF header, `multipart/form-data`)

- `image`: JPEG, PNG or WebP, at most 16 MB and 60 megapixels (the app shrinks phone photos to about 1600 px before upload)
- `campus` (optional): a hint only. The room is chosen among all catalog rooms; a winner on another campus is returned with a note in `conflicts`.

The photo is validated, compared in memory and discarded. Limit: 60 scans per user per hour.

Response: `{mode, candidates:[{room_id, building, room, campus, evidence[], conflicts[]}], needs_confirmation, uncertainty}`. An empty `candidates` list means no room was clearly identified.


## Item photo analysis without storing the photo

`POST /api/analyze-item` (signed in, CSRF header, `multipart/form-data`, field `image`)

Returns `{mode, suggestion: {title, category, attributes: {color}, priority?, sensitive?, uncertainty}}`.
Empty `title` means the item type wasn't clear; the finder fills it in. The photo is compared in
memory and discarded. Limit: 60 per user per hour.
