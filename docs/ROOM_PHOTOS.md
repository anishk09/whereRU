# Adding classroom reference photos (room scan)

## Fastest: import DCS 360° panoramas (5 CS lecture halls)

Rutgers DCS publishes a 360° panorama for each classroom. The importer downloads the
panorama for a few demo rooms and slices it into 16 phone-camera-style views
(8 directions x 2 tilts), which is what the matcher compares against.

```bash
cd backend
source .venv/bin/activate
python tools/import_dcs.py            # all 29 rooms in tools/import_dcs.py (about 1 minute)
python tools/import_dcs.py --core     # only ARC-103, LSH-A102, PHY-001, RWH-105, SEC-111
python tools/import_dcs.py ARC-103    # or just some of them
```

Then restart Flask. It loads the room features in the background (about 10 seconds),
and each scan then takes about 2-3 seconds.

The images are saved only on your laptop (`data/rooms/` is git-ignored) because they belong
to Rutgers DCS. Only room metadata with a source link goes in `data/classrooms.json`.
To add another room, put its verified details from its DCS page into `ROOMS` in the script.

Tested on synthetic 360° rooms: 20/20 correct from in-between angles with different zoom and
lighting. Real rooms should be tested in person, so take one photo in the room and try it.

## Your own photos (works for any room)

Room scan works without Gemini (`AI_MODE=local`). It compares the finder's photo against
reference photos of each classroom using on-device feature matching (OpenCV SIFT + RANSAC).
A room can only be recognized if it has at least one reference photo.

## Take the photos (5 minutes per room)

For each classroom:

1. Stand near the back, facing the front. Take one wide photo that shows the boards,
   front wall, and the first rows of seating.
2. Take a second photo from a back corner at an angle.
3. Optional third photo from the side.
4. No people in the frame. Photos you take yourself are fine to use.

Distinctive things help most: boards, screens, posters, windows, door, clock, wall trim.
Plain empty walls do not.

## Add them to the catalog

1. Save the photos as `backend/data/rooms/<ROOM-ID>/1.jpg`, `2.jpg`, ...
   (for example `backend/data/rooms/HH-A2/1.jpg`).
2. Add the room to `backend/data/classrooms.json`:

```json
{
  "rooms": [
    {
      "id": "HH-A2",
      "campus": "College Ave",
      "building": "Hardenbergh Hall",
      "room": "A2",
      "source_url": "https://sis.rutgers.edu/soc/",
      "images": ["rooms/HH-A2/1.jpg", "rooms/HH-A2/2.jpg"]
    }
  ]
}
```

`campus` must be one of: `College Ave`, `Busch`, `Livingston`, `Cook/Douglass`.
Image paths are relative to `backend/data/`.

3. Restart Flask. Check `GET /api/classrooms` lists the room.

## Test it

Take a new photo in the same room from a different spot, upload it to a report, and call
`POST /api/listings/{id}/recognize-room` with `{"consent_to_ai": true, "image_id": <id>}`.
The response lists up to three rooms with how many visual features matched.
A room is only returned when at least 18 features agree on one camera geometry,
so unknown rooms return no candidates instead of a wrong guess.

Measured on test scenes: 39/40 correct top match across perspective, crop, and lighting
changes; 0/8 false matches on scenes outside the catalog.

## Scene model (recommended)

Feature matching needs the photo to be taken from close to where a reference photo was taken.
A DCS panorama is shot from one spot, so a photo from the other side of the room often won't
match. With PyTorch installed, the backend also compares the overall look of the room using
a pretrained DINOv2 model (runs on your laptop, no API key, about 90 MB downloaded once):

```bash
pip install torch
python tools/test_room_photo.py ~/Downloads/photo.jpg
```

The tool prints each room's `similarity`. A room is suggested when its similarity is at least
`ROOM_MIN_SIMILARITY` (default 0.70; unrelated lecture halls score about 0.57–0.70) and beats the next room by `ROOM_MIN_MARGIN` (default 0.06).
Both can be set in `.env`. Without PyTorch the app uses feature matching only.

## How reference photos are found

`data/classrooms.json` lists each room's details. The app adds every photo it finds in
`data/rooms/<room id>/` (DCS views and your own photos, any of .jpg .jpeg .png .webp) except
`pano.jpg`. So to add your own photos, just drop them in the room's folder and restart Flask.

With the scene model installed, every scan compares against all rooms by overall look, then runs
the slower detail matching only on the 4 closest rooms, so adding rooms barely slows scans down.
