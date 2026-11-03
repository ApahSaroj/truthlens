#!/usr/bin/env bash
# Mac/Linux: double-click (Mac: rename to .command) or run ./start-truthlens.sh
cd "$(dirname "$0")"
PY=python3; command -v $PY >/dev/null || { echo "Install Python 3.9+ from https://www.python.org/downloads/"; exit 1; }
[ -x .venv/bin/python ] || { echo "First run: setting up TruthLens..."; $PY -m venv .venv; }
.venv/bin/python -c "import truthlens, fastapi, uvicorn" 2>/dev/null || .venv/bin/python -m pip install -e ".[api]" || exit 1
echo "TruthLens is running at http://127.0.0.1:8765 (Ctrl+C to stop)"
( sleep 3; (open http://127.0.0.1:8765 || xdg-open http://127.0.0.1:8765) >/dev/null 2>&1 ) &
exec .venv/bin/python -m uvicorn truthlens.api:app --host 127.0.0.1 --port 8765
