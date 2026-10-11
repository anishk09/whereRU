# Open and test WhereRU?

The working project is **`/Users/sujai/Documents/Codex/WhereRU-Hackathon`**. Your uploaded `Downloads/whereRU-main` folder is the source reference and remains unchanged.

## 1. Open it on this Mac

1. Open Terminal and run:

   ```sh
   cd /Users/sujai/Documents/Codex/WhereRU-Hackathon
   ./start-demo.command
   ```

   You can also double-click `start-demo.command` in Finder. Keep its server terminal open. If the app is already running, the launcher says so and preserves your data.
2. Open **http://localhost:5003** in Safari or Chrome. Refresh a previously open app tab to load the latest frontend. Port **8443** is the older frontend; use **5003** for this complete app.
3. Choose Maya, Jordan or Alex. Continue and enter demo code **000000**, then continue with the displayed name.
4. The bottom navigation is **Home · Listings · Photo · Map · Profile**.

## 2. Open it on a phone or second laptop

1. Connect both devices to the same Wi-Fi network or shared hotspot. Leave the hosting Mac awake and its server running.
2. Read the **Other devices on this Wi-Fi** URL printed by the launcher. At verification it was **http://10.75.93.89:5003**.
3. Type that URL into the phone's Safari/Chrome address bar. `localhost` on a phone refers to the phone, so use the Mac's printed address.
4. Choose a different participant on each device and sign in with **000000**. For example, Maya on your Mac, Jordan on the first phone and Alex on the second phone.
5. Keep the receiving app page open for live notifications. Use Upload for photos and choose recent search areas manually during this local demo. Browser GPS requires a secure connection; the local Wi-Fi URL uses HTTP.

If the phone cannot connect, try a shared hotspot: some campus Wi-Fi networks isolate devices. Use the launcher's new address after changing networks. If macOS asks whether Python may accept incoming connections, allow it for your chosen local network.

## 3. Test the Listings tab

1. Open **Listings**. **All** shows every active public lost/found report, including returns in progress. Returned reports are available through the Status filter until their seven-day expiry.
2. Select **Lost** or **Found**, then **Filters**. Combine campus, category, last-seen time and status; search and sort can be used together.
3. Use **+** to save a report, then select **Saved** to view your private shortlist. Reload and verify the saved report remains there. Saved reports are specific to the signed-in account.
4. Use **Load more reports** to browse beyond the first 24. Listings refresh while the page is visible, so another device's new public report appears within about five seconds.
5. Open a report to see its details and expiry date. Exact rooms, private photos and identifying ownership evidence remain protected.

## 4. Test the integrated five-hall room model

1. Open **Home → Test classroom recognition**. This test does not publish a listing.
2. Set **Room comparison** to **Five lecture halls · local scene model**. It compares ARC-103, LSH-A102, PHY-001, RWH-105 and SEC-111.
3. Select **Use your example photos → Weeks Hall lecture room** to try the supplied photo. The model should suggest **Richard Weeks Hall 105**, with its local scene-comparison evidence.
4. Or select **Upload** and choose a new room photo. Capture the front wall, seating, windows and boards. The first scan after restarting loads the model; later scans are faster. Inference happens on the hosting Mac.
5. Review the evidence and select the correct suggestion. Use **Change** to test another photo. If there is no reliable match, choose the room manually or try a clearer photo. The app offers up to five supported candidates and does not force five guesses.
6. Choose **All installed rooms** when testing the broader catalogue or your seven IDEA3 item photos. IDEA3 remains a user-confirmed example label, separate from the five lecture halls.

The pinned DINOv2-small model and official classroom references are already installed on this Mac. No Gemini API key is needed, and scan images stay local.

## 5. Verify the one-week deletion now

You do not have to wait a week. These checks simulate posting dates in temporary databases and leave your rehearsal data unchanged:

```sh
cd /Users/sujai/Documents/Codex/WhereRU-Hackathon
backend/.venv/bin/python -m pytest backend/tests/test_expiry.py -q
```

The checks cover the exact seven-day boundary, recent reports about old losses, every report status, private photos, saved entries, notifications, claims/messages, preserved earned points, 20 concurrent cleanup calls, non-reused IDs and expiry while the server is offline.

Deletion runs on API access, server startup and a background sweep every minute. Expiry is seven days after **posting**, not seven days after last seen or the latest edit. Expired reports and their report-linked private data are permanently removed from the live database. An unfinished return linked to an expired report is removed; its newer counterpart becomes open again. Completed-return reputation survives.

## 6. Rehearse the multi-device demo

The sensitive lost-item flow also includes an interactive visibility-timer **preview**. Swipe or scroll the duration row, or use its arrow buttons, to choose among 19 durations from 15 minutes to one week. The selected duration and end action update the preview. Custom release/deletion scheduling is not active: sensitive reports stay private and every report is deleted seven days after posting.

1. Maya posts a red lost bottle in Richard Weeks Hall.
2. Jordan uses **Photo**, selects the red bottle example, reviews its description, confirms a location and posts the found report.
3. Maya receives a potential-match notification. For an everyday bottle, Maya sends a return request with an optional message; Jordan reviews it. For a tablet, wallet, keys, ID or a report marked valuable/sensitive, Maya must submit the private owner-only answer instead.
4. Arrange a public pickup, then confirm the return separately on both devices. Jordan earns 10 points and Maya earns 2.
5. Alex chooses a nearby search area in Profile. Maya posts another lost report and deliberately shares a search area near Alex. Alex receives a nearby search notification.

For exact presenter wording see **DEMO-SCRIPT.md**. In-app notifications arrive while the app is open; closed-app OS push notifications are outside this demo.

## Complete checks

```sh
./start-demo.command --check
backend/.venv/bin/python backend/tools/stress_demo.py
```

The stress script uses isolated temporary databases and independent sessions. It does not reset your app. **Profile → Reset rehearsal** is the separate action that replaces the live rehearsal data with the 140 sample reports; use it only when you deliberately want a fresh rehearsal.
