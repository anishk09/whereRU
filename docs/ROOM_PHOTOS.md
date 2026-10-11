# Adding classroom reference photos (room scan)

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
