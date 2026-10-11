#!/bin/zsh
set -eu
cd "$(dirname "$0")"
# Use the existing Codex runtime when it is installed; ordinary Node/pnpm also work.
TASK_NODE_ROOT='/Users/sujai/.cache/codex-runtimes/codex-primary-runtime/dependencies'
if [[ -d "$TASK_NODE_ROOT/node/bin" ]]; then
  export PATH="$TASK_NODE_ROOT/node/bin:$TASK_NODE_ROOT/bin/fallback:$PATH"
fi
if [[ ! -x backend/.venv/bin/python ]]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
fi
if [[ ! -f backend/.env ]]; then cp backend/.env.example backend/.env; fi
if [[ ! -d node_modules ]]; then pnpm install --frozen-lockfile; fi
if [[ ! -x backend/.tools/local-vision ]] && command -v swiftc >/dev/null; then
  mkdir -p backend/.tools
  swiftc backend/tools/local_vision.swift -o backend/.tools/local-vision
fi
if [[ ! -f backend/.tools/room-model-ready.json ]] || [[ ! -f backend/.tools/dinov2_vits14_pretrain.pth ]] || [[ ! -f backend/.tools/dinov2/hubconf.py ]] || ! backend/.venv/bin/python -c 'import torch' >/dev/null 2>&1; then
  backend/.venv/bin/python -m pip install -r backend/requirements-rooms.txt
  backend/.venv/bin/python backend/tools/prepare_references.py
  backend/.venv/bin/python backend/tools/prepare_scene_model.py
fi
pnpm exec tsc --noEmit
pnpm build
if [[ "${1:-}" == '--check' ]]; then
  backend/.venv/bin/python -m pytest backend/tests -q
  exit
fi
TASK_LAN_IP="$(/usr/sbin/ipconfig getifaddr en0 2>/dev/null || true)"
printf '\nWhereRU? local demo: http://localhost:5003\n'
if [[ -n "$TASK_LAN_IP" ]]; then printf 'Other devices on this Wi-Fi: http://%s:5003\n' "$TASK_LAN_IP"; fi
if /usr/bin/curl --fail --silent --max-time 2 http://localhost:5003/api/demo/status >/dev/null; then
  printf 'The local demo is already running. Open the URL above.\n'
  exit
fi
printf 'Keep this terminal open. Press Control-C to stop this server.\n'
exec backend/.venv/bin/python backend/app.py
