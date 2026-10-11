# Run the complete WhereRU? presentation demo

The finished demo lives in `demo/`. The team's existing `frontend/`, `backend/` and `docs/` are preserved separately. Run the demo using the root launcher rather than the original two-terminal setup.

## Start on a Mac

Prerequisites: **Python 3.12**, **Node.js 22** and **pnpm 10.34.3**, available in Terminal. The checked-in `demo/.mise.toml` records the Node and pnpm versions.

From the root of this checkout:

```sh
python3.12 -m venv demo/backend/.venv
./start-demo.command
```

Create the virtual environment once. On later starts, run just `./start-demo.command`. You can also double-click the launcher in Finder. First setup requires internet to install dependencies, download official classroom references and prepare the local DINOv2 scene model. Keep the terminal open and wait for its printed URL. Later launches reuse the installed assets.

Open **http://localhost:5003**, select a participant and use verification code **000000**. Gemini is optional; the included `.env.example` selects demo mode with an empty API key. The launcher creates the ignored `demo/backend/.env` when missing.

## Use two devices

Connect both devices to the same Wi-Fi or a shared hotspot. Keep the hosting Mac awake. On the second device, open the **Other devices on this Wi-Fi** address printed by the launcher. Use different participants: Maya for the owner, Jordan for the finder, Alex for the nearby helper. Keep the receiving app page visible for notifications.

On one Mac, `http://localhost:5003` and `http://127.0.0.1:5003` have separate login cookies. Two tabs on the same hostname share a session.

## Rehearse and check

- [Three-minute presentation script](demo/DEMO-SCRIPT.md)
- [Feature-by-feature testing instructions](demo/RUN-AND-TEST.md)
- [Completed verification and limits](demo/TEST-REPORT.md)

After setup:

```sh
./start-demo.command --check
demo/backend/.venv/bin/python demo/backend/tools/stress_demo.py
```

The checks use isolated databases. Use **Profile → Reset rehearsal** on the hosting Mac only when you deliberately want to replace live rehearsal data with the 140 sample reports.

## What is included

The complete app includes the Figma frontend, Listings feed and filters, image uploads, local item and classroom suggestions, matching, in-app notifications, nearby search alerts, claims, return confirmation and a seeded heatmap. The owner-only identifying answer is required for valuable or sensitive items; everyday reports use an optional message. All reports expire seven days after posting. Custom visibility durations remain a preview.

No local account database, private uploads, credentials, dependency directories or model weights are committed. The launcher's first setup prepares the model/reference assets. Optional Apple Vision classification requires Apple's Swift compiler tools; reviewed example-photo and classroom matching paths work locally without Gemini.

## Move the demo to another repository

Copy the **contents** of `demo/`, including hidden files, into the intended new project directory. It is self-contained: its own launcher, backend, frontend, dependency locks, example photos and docs move together. Commit the extracted source rather than `.env`, `instance/`, `.venv/`, `.tools/`, `node_modules/` or downloaded reference caches.

The demo source was copied exactly from local commit `e6040c5ba8c3cc19eb6db2cf5250233195dee8bf`. Paths documented for the already-prepared Mac inside its historical reports are machine-specific; use this guide for a fresh checkout.

Before committing this integration on October 11, 2026, the root launcher passed strict TypeScript, a production build and **118 tests in 74.51 seconds** using isolated test databases. Existing team application files remain unchanged; the repository README gained the demo instructions above.
