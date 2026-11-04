#!/usr/bin/env bash
# TruthLens one-click launcher for Mac and Linux.
#   Mac: right-click > Open the first time (or rename to start_truthlens.command and double-click).
#   Linux: ./start_truthlens.sh
# The first run sets TruthLens up (a few minutes, needs internet once); then it opens in your browser.
cd "$(dirname "$0")" || exit 1
[ -f pyproject.toml ] || { [ -f truthlens/pyproject.toml ] && cd truthlens; }
[ -f pyproject.toml ] || { echo "Could not find the TruthLens files. Keep this launcher inside the TruthLens folder."; exit 1; }
SAMPLE="$PWD/samples/sample_report_v05.html"
[ -f "$SAMPLE" ] || SAMPLE="$PWD/samples/sample_report_v041.html"
open_url() { (open "$1" || xdg-open "$1") >/dev/null 2>&1; }

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.9 or later is not installed. Get it from https://www.python.org/downloads/ and run this again."
  echo "Meanwhile, the sample report opens in your browser (no internet needed)."
  [ -f "$SAMPLE" ] && open_url "$SAMPLE"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up TruthLens. This takes a few minutes..."
  "$PY" -m venv .venv || { echo "Could not create the Python environment (on Debian/Ubuntu: sudo apt install python3-venv)."; exit 1; }
fi
if ! .venv/bin/python -c "import fastapi, uvicorn, truthlens.pipeline" 2>/dev/null; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
  if ! .venv/bin/python -m pip install -e ".[api]"; then
    echo "The install did not finish (no internet, or a proxy blocking pypi.org)."
    echo "Meanwhile, the sample report opens in your browser (no internet needed)."
    [ -f "$SAMPLE" ] && open_url "$SAMPLE"
    exit 1
  fi
fi
# Optional (v0.7): "match by meaning" in the compare tab. Tried once; TruthLens works without it.
if [ ! -f .venv/meaning-tried.txt ]; then
  if ! .venv/bin/python -c "import fastembed" 2>/dev/null; then
    echo 'Adding the optional "match by meaning" feature (about 145 MB, tried once)...'
    if .venv/bin/python -m pip install -e ".[api,meaning]" >/dev/null 2>&1; then
      echo '"Match by meaning" is installed; its model (67 MB) downloads the first time you use it.'
    else
      echo 'The optional "match by meaning" feature could not be installed. TruthLens works without it.'
    fi
  fi
  echo tried > .venv/meaning-tried.txt
fi
echo "TruthLens is running at http://127.0.0.1:8765 (press Ctrl+C or close this window to stop)"
( sleep 3; open_url http://127.0.0.1:8765 ) &
exec .venv/bin/python -m uvicorn truthlens.api:app --host 127.0.0.1 --port 8765
