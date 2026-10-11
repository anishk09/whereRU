#!/usr/bin/env bash
# Restart the whole demo in one go: backend, app and the public HTTPS tunnel for the phones.
#
#   ./demo.sh           restart, keep the current demo data
#   ./demo.sh --fresh   restart with freshly seeded demo data (tools/seed_demo.py)
#
# Stops anything already on ports 5001/5173 and any running cloudflared first.
# Press Ctrl+C to stop everything. Logs: /tmp/whereru-*.log
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
FRESH=0
[ "${1:-}" = "--fresh" ] && FRESH=1
PIDS=""

stop_port() {
  local pids
  pids="$(lsof -ti tcp:"$1" 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null
}

cleanup() {
  echo
  echo "Stopping demo..."
  [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
  exit 0
}

wait_for() { # url, name
  for _ in $(seq 1 60); do
    curl -s -o /dev/null "$1" && return 0
    sleep 1
  done
  echo "!! $2 did not start. See its log in /tmp/whereru-*.log"
  return 1
}

command -v cloudflared >/dev/null || { echo "Install the tunnel first: brew install cloudflared"; exit 1; }
[ -d "$ROOT/backend/.venv" ] || { echo "No backend/.venv. Set up the backend first (see README)."; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)
if ! grep -q '^DEMO_LOGIN=true' "$ROOT/backend/.env" 2>/dev/null; then
  echo "!! backend/.env needs DEMO_LOGIN=true for the shared demo (Jordan/Maya). Add it and rerun."
  exit 1
fi

echo "Stopping old servers..."
stop_port 5001
stop_port 5173
pkill -f "cloudflared tunnel --url" 2>/dev/null
sleep 1
trap cleanup INT TERM

cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
if [ "$FRESH" = 1 ] || [ ! -f instance/demo_catalog.json ]; then
  python tools/seed_demo.py | sed 's/^/  /'
fi
python app.py >/tmp/whereru-backend.log 2>&1 &
PIDS="$PIDS $!"

cd "$ROOT/frontend"
npm run dev -- --port 5173 --strictPort >/tmp/whereru-frontend.log 2>&1 &
PIDS="$PIDS $!"

echo "Starting backend and app..."
wait_for http://127.0.0.1:5001/api/health "Backend" || cleanup
wait_for http://localhost:5173/ "App" || cleanup

cloudflared tunnel --url http://localhost:5173 >/tmp/whereru-tunnel.log 2>&1 &
PIDS="$PIDS $!"
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/whereru-tunnel.log | head -1)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "!! Tunnel did not start. See /tmp/whereru-tunnel.log"; cleanup; }

echo
echo "Demo is running. Open on the phones (give the link ~10 seconds the first time):"
echo "  Jordan (sender):   $URL/?as=jordan"
echo "  Maya   (receiver): $URL/?as=maya"
echo
echo "Reset demo data any time (no restart):  cd backend && python tools/seed_demo.py"
echo "Press Ctrl+C to stop everything."
wait
