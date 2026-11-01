#!/usr/bin/env bash
set -eu
CORTIA_PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export CORTIA_DATA_DIR="$(mktemp -d /tmp/cortia-e2e.XXXXXX)"
trap 'rm -rf -- "$CORTIA_DATA_DIR"' EXIT
cd "$CORTIA_PROJECT/backend"
"$CORTIA_PROJECT/.venv/bin/python" -m uvicorn cortia.main:create_app --factory --host 127.0.0.1 --port 8011
