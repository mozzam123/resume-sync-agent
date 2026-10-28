#!/bin/zsh
# Double-click this file in Finder, or run: ./start.command

set -euo pipefail

PROJECT_DIR="${0:A:h}"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
STREAMLIT="$VENV_DIR/bin/streamlit"
BACKEND_PID=""
PID_FILE="$PROJECT_DIR/data/backend.pid"

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -f "$PID_FILE" ]] && [[ "$(<"$PID_FILE")" == "$BACKEND_PID" ]]; then
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/data"

if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON" -m pip install -q -r requirements.txt

if "$PYTHON" -c '
from urllib.request import urlopen
urlopen("http://127.0.0.1:8000/api/platforms", timeout=1)
' 2>/dev/null; then
  echo "A backend is already running on port 8000."
  echo "Stop its Terminal window with Control-C, then run ./start.command again."
  exit 1
fi

if ! PLAYWRIGHT_BROWSERS_PATH="$PROJECT_DIR/data/playwright-browsers" "$PYTHON" -c '
from pathlib import Path
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
path = Path(p.chromium.executable_path)
p.stop()
raise SystemExit(0 if path.exists() else 1)
'; then
  PLAYWRIGHT_BROWSERS_PATH="$PROJECT_DIR/data/playwright-browsers" \
    "$PYTHON" -m playwright install chromium
fi

"$PYTHON" main.py > "$PROJECT_DIR/data/backend.log" 2>&1 &
BACKEND_PID="$!"
echo "$BACKEND_PID" > "$PID_FILE"

for _ in {1..20}; do
  if "$PYTHON" -c '
from urllib.request import urlopen
urlopen("http://127.0.0.1:8000/api/health", timeout=1)
' 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if ! "$PYTHON" -c '
from urllib.request import urlopen
urlopen("http://127.0.0.1:8000/api/health", timeout=1)
' 2>/dev/null; then
  echo "The backend could not start. See data/backend.log for details."
  exit 1
fi

echo "Resume Sync Agent is starting. Press Control-C here when finished."
"$STREAMLIT" run streamlit_app.py --browser.gatherUsageStats false
