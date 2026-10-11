# Backend: Where RU? API

Flask service that does the AI work the frontend currently simulates.
The frontend calls it through one file: `frontend/src/roomRecognition.ts`.
Today that file uses `demoRecognizer` (fake results). When these endpoints work,
we add a `geminiRecognizer` that calls them and switch `activeRecognizer` to it.
No screen changes are needed.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install flask flask-cors google-genai pillow python-dotenv
cp .env.example .env        # add GEMINI_API_KEY; never commit .env
flask --app app run --port 5001 --debug
```

Rules:
- Keep the Gemini key on the server only. The frontend never sees it.
- Every endpoint must also work with `DEMO_MODE=true` (return the sample data below
  without calling Gemini) so the live demo survives bad Wi-Fi.
- Accept images up to 15 MB: JPEG, PNG, WEBP, HEIC. Strip EXIF before storing anything.

## API contract

All requests are `multipart/form-data` with an `image` file field. All responses are JSON.
The shapes match the TypeScript types in `frontend/src/roomRecognition.ts`. Keep them identical.

### 1. `POST /api/describe-item`
Photo of the found item, returning editable details.

Response:
```json
{ "title": "Blue water bottle", "category": "Water bottle", "color": "Navy blue",
  "description": "Insulated bottle with a silver lid and a small sticker" }
```
Use `null`-free strings; return `""` when unsure. Never invent a brand.
Put identifying details (stickers, dents, engravings) in `description` only; the frontend hides them publicly.

### 2. `POST /api/read-placard`
Photo of a room number sign, returning the room.

Response (or `null` if unreadable):
```json
{ "campus": "College Ave", "code": "HH", "building": "Hardenbergh Hall", "room": "A2" }
```
`campus` is one of `"College Ave" | "Busch" | "Livingston" | "Cook/Douglass"`.
`code` must be a building code from the Rutgers Schedule of Classes feed (see below).

### 3. `POST /api/recognize-room`  (the headline feature)
Photo of a classroom interior, plus optional form field `campus` (same values as above)
from the phone's approximate location. Returns up to 3 candidate rooms, best first.

Response:
```json
[
  { "location": { "campus": "College Ave", "code": "HH", "building": "Hardenbergh Hall",
                  "room": "A2", "source": "room-scan" },
    "features": ["Tiered seating", "Two chalkboards", "No windows"] }
]
```
`features` are short visible traits Gemini noticed (2 to 4). Return `[]` when nothing matches;
the frontend then offers the placard scan and manual choice.
Do not return confidence percentages. The UI ranks by order only.

Suggested approach: keep a small reference index (`rooms.json`) of the demo rooms with a few
descriptive traits each (seating type, boards, windows, size). Send Gemini the photo plus the
candidate rooms for the campus and ask it to pick and rank the best matches as structured JSON.
Only use reference images we are allowed to use (photos we take ourselves).

### 4. `GET /api/sections?building=HH&room=A2&day=M&before=1400`  (stretch)
Sections that met in a room shortly before a time, from the public Schedule of Classes feed:
`https://classes.rutgers.edu/soc/api/courses.json?year=2026&term=9&campus=NB`.
Download once at startup and index by `buildingCode + roomNumber`.
Notes: Thursday is `"H"`; skip online sections (empty room); de-duplicate cross-listed sections.

## Demo data
Sample responses live in `frontend/src/roomRecognition.ts` (`demoRecognizer`).
Return the same samples when `DEMO_MODE=true`.
