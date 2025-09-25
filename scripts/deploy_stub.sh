#!/usr/bin/env bash
# deploy_stub.sh - example scheduled runner for "set-and-forget" operation
# Cron: run daily or hourly depending on execution cadence.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# activate venv (assumes .venv)
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# run backtest (or live/paper hook)
python -m lab.run --config configs/etrp.yml

# example: produce metrics CSV and call watchdog manually (if you want)
python - <<'PY'
import yaml, pandas as pd
from pathlib import Path
from lab.run import load_prices
from strategies.etrp import run_etrp
from lab.adaptive.regime_classifier import classify_regime
from lab.adaptive.vol_targeter import compute_target_scalar
from lab.adaptive.watchdog import Watchdog, WatchdogConfig

cfg = yaml.safe_load(open("configs/etrp.yml"))
px = load_prices(cfg)
res = run_etrp(px, cfg)
m = res["metrics"]
# example adaptive hooks
labels = classify_regime(px.pct_change().dropna())
regime = labels.iloc[-1] if not labels.empty else "unknown"
scalar = compute_target_scalar(res.get("port_monthly"))
# instantiate watchdog
wcfg = WatchdogConfig(max_dd=0.25, min_sharpe=-0.5, webhook=None)
wd = Watchdog(wcfg)
wd.check(m, context={"note":"scheduled-run", "regime": regime, "scalar": scalar})
print("done", regime, f"scalar={scalar:.3f}")
PY
