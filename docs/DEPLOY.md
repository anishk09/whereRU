# Public demo on Vercel

The public link is the app on its own, with no backend. That keeps it free, always on, and
maintenance-free. Everything runs in the visitor's browser:

- A fake campus (20 students, ~50 lost and found reports, past returns) is bundled in
  `frontend/src/demoSeed.json`. Times are moved forward on load, so "3h ago" always means 3h ago.
- Room scan and item photo analysis use their simulated versions and say so.
- The full story works on one phone: post the bottle as Jordan, switch to Maya in
  Profile → Demo persona, get the match alert, claim it, switch back and approve.
- Each visitor's changes stay in their own browser.

The two-phone demo with the real backend (`./demo.sh`) is unchanged. See [DEMO_SERVER.md](DEMO_SERVER.md).

## Deploy (one time)

1. On [vercel.com](https://vercel.com), sign in with GitHub and choose **Add New → Project**.
   Import this repository (allow Vercel access to it if GitHub asks).
2. Set **Root Directory** to `frontend`. Leave the rest: `frontend/vercel.json` sets the build
   (`VITE_BACKEND=off npm run build`, output `dist`) and `package.json` pins Node 22.
3. **Deploy.** For a nicer link, go to Project → Settings → Domains and pick a free
   `*.vercel.app` name (or add your own domain).

Every push to `main` redeploys automatically. To freeze the demo, turn that off under
Settings → Git, or point Production at a branch you don't push to.

## Refresh the bundled campus

```bash
cd backend
python tools/seed_demo.py --static-out ../frontend/src/demoSeed.json   # same options as a live seed
```

## How "backend off" works

`VITE_BACKEND=off` makes `api.isOnline()` return false without any network request, so every
feature takes its built-in demo path and the browser console stays clean.
