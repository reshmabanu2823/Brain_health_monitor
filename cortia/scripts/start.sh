#!/usr/bin/env bash
set -eu
CORTIA_PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CORTIA_PROJECT"
umask 077
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
  echo 'Run bash scripts/setup.sh first.' >&2
  exit 1
fi
cd backend
exec ../.venv/bin/python -m uvicorn cortia.main:create_app --factory --host 127.0.0.1 --port 8010 --workers 1
