#!/usr/bin/env bash
set -eu
CORTIA_PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CORTIA_PROJECT"
umask 077
uv venv --python 3.12 --allow-existing .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt
cd frontend
npm ci
npm run build
