#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "A settings file (.env) was created. Add at least one AI key to it, save, then press Enter."
  ${EDITOR:-nano} .env
fi
python check_key.py || true
echo "Starting INFINITY AI on http://localhost:8000  (Ctrl+C to stop)"
python -m uvicorn main:app --reload
