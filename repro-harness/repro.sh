#!/usr/bin/env bash
set -euo pipefail

echo "== Repro Harness v1.0 =="
python -V

# Create venv if missing
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run tests
pytest -q

echo "== PASS =="
