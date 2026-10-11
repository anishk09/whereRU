# Hackathon demonstration

## Reliable backend demonstration now

Run `python demo_flow.py`. It exercises a complete private recovery using temporary data and no external services. This demonstrates permissions, match notification, review, private messages, two independent confirmations and exactly-once reputation. Run `python -m pytest -q` for the broader negative/access-control tests.

Run `python manage.py seed-demo`, start Flask, and use `python client_demo.py` to inspect the persistent demonstration reports. All seeded report titles include DEMO. The density coordinates are illustrative fixtures, not verified campus-room measurements.

## Camera/AI demonstration after configuration

1. Supply 10–20 labeled classroom reference photos you may use. Include similar rooms.
2. Configure the Gemini key/model and test independent phone photos, including rooms outside the catalog.
3. Create a found report and upload its photo through the API.
4. Analyze the item and recognize a room; review suggestions, then explicitly edit/apply confirmed data.
5. Create a matching lost report with a second account. Optionally index both descriptions semantically with each owner's consent.
6. Show the match notification, private claim, messages and return confirmation.
7. When integrating the frontend, render the community GeoJSON and the per-item selected search areas. Do not substitute the old frontend's random map data for real records without labeling it.

Demo mode alone does not demonstrate Gemini intelligence. For honest judging, show the AI mode, failure fallback, measured response latency, and benchmark with your own labeled examples. Never present a similarity score as the probability of ownership, or a search cloud as a tracked object.

## Still needed for a phone app

The backend is ready for client integration. The phone client must implement camera/file selection, consent prompts, optional location capture, cookie/CSRF handling, API-backed state, map rendering and error states. Native background tracking is a separate project decision; no backend endpoint can retrieve earlier unrecorded GPS history.
