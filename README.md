# Where RU?

**Student-to-student lost & found for Rutgers.** Built at HackRU Fall 2026.

Every lost item is asking the same question: where are you? Where RU? answers it.
A finder photographs the item and scans the room it was found in. The app identifies the
classroom and privately reaches the students who posted matching lost listings. The owner
proves ownership before anyone's identity is shared.

> Where RU? is an independent student project. It is not affiliated with or endorsed by Rutgers University.

## What works today vs. what is simulated

| Feature | Status |
| --- | --- |
| Full found-item flow: photo, location, review, notify, verify, handoff | Working frontend |
| Real camera capture / upload with preview, retake, and file validation | Working |
| Location picker: room scan (primary), placard (fallback), manual choice | UI working, recognition **simulated** |
| Lost-item flow: retrace steps, known room, priority spots, visibility timer | Working frontend |
| Sensitive items, reputation, theme (system/light/dark) | Working frontend |
| Campus map with heatmap (MapLibre) | Working, **sample data** |
| Email sign-in | **Demo**: any 6-digit code is accepted |
| Room recognition, placard reading, item description (Gemini) | **Simulated** behind `RoomRecognizer` in `frontend/src/roomRecognition.ts` |
| Matching, notifications, ownership verification | **Simulated**, backend planned |

Simulated results are labeled "Demo" in the app.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

## Project layout

```
frontend/   React + Vite + TypeScript (prototyped in Figma Make)
backend/    Flask + Gemini service (planned)
```

## Data and privacy

- Building codes and sample rooms come from the public Rutgers Schedule of Classes feed.
- No FERPA-protected rosters or enrollment data are used. Long term, an authorized Rutgers
  integration could replace opt-in schedules; that is a future possibility, not a partnership.

## Frontend workflow (during the hackathon)

The UI is being designed in Figma Make. Figma is the source of truth for `frontend/src` until the UI is frozen.
To sync: in Figma Make's code view, download the project, then copy its `src/` over `frontend/src/` and commit.
Do not edit `frontend/src` here and in Figma at the same time, or one will overwrite the other.
