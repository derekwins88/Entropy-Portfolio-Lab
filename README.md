# Entropy Portfolio Lab

<!-- ===== Project Badges ===== -->
[![python-ci](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-python.yml/badge.svg?branch=main)](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-python.yml)
[![ui](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-ui.yml/badge.svg?branch=main)](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-ui.yml)
[![proof](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-proof.yml/badge.svg?branch=main)](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-proof.yml)
[![docs-diagrams](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/docs-diagrams.yml/badge.svg?branch=main)](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/docs-diagrams.yml)

![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Node 20](https://img.shields.io/badge/Node-20-339933?logo=node.js&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](.github/CONTRIBUTING.md)
[![Last commit](https://img.shields.io/github/last-commit/derekwins88/Entropy-Portfolio-Lab.svg)](https://github.com/derekwins88/Entropy-Portfolio-Lab/commits/main)

<!-- Enable after adding the workflows:
[![CodeQL](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/codeql.yml/badge.svg?branch=main)](…)
[![playwright](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-playwright.yml/badge.svg?branch=main)](…)
[![lighthouse](https://github.com/derekwins88/Entropy-Portfolio-Lab/actions/workflows/ci-lighthouse.yml/badge.svg?branch=main)](…)
-->

A unified, research-to-execution repository for **entropy-aware portfolio trading**.

This lab ties together:
- **Roadmap** (design intent & milestones)
- **Python backtester** (research & validation)
- **C# / NinjaTrader components** (execution-grade sizers/strategies)
- **Specs** (one manifest that maps roadmap → code → strategy)

## Strategy Integration

The `AlphaBreakoutEntropy_v1_1` strategy now ships alongside the other NinjaTrader components in `csharp/`. Sensitive helpers (for example, `AlphaBreakoutEntropyPrivateLogic.cs`) stay outside version control while the public entry point is referenced in `specs/manifest.json` for parameter exposure and coordination with the research stack.

### Data schemas (what the repo expects)

**Single-asset (per-symbol) CSV** — used by loaders & validators in `data/`  
| column     | type     | notes                      |
|------------|----------|----------------------------|
| `datetime` | ISO8601  | UTC recommended            |
| `open`     | float    |                            |
| `high`     | float    |                            |
| `low`      | float    |                            |
| `close`    | float    |                            |
| `volume`   | integer  | optional for some assets   |

**Multi-asset “wide” CSV** — used in quick backtests and examples  
| column                | type    | notes                                  |
|-----------------------|---------|----------------------------------------|
| `datetime`            | ISO8601 | index column                           |
| `<SYM>_Close` …       | float   | one `_Close` column per symbol (e.g., `SPY_Close`, `QQQ_Close`, `TLT_Close`) |
| `<SYM>_Volume` (opt.) | integer | optional                               |

> CI now generates a tiny deterministic sample at `data/sample_multi_asset_data.csv` so the examples run out-of-the-box.

## Data Pipeline

Fetch live data using the included script:

```bash
python scripts/fetch_data.py --symbols AAPL SPY QQQ --interval 1d --output data/
```

> Requires `yfinance` (`pip install yfinance`).

## Licensing

Default: MIT. Consider dual-licensing (e.g., MIT + Commercial) for IP protection (e.g., proof capsules). Consult a lawyer if needed.

### Deterministic quick-run

```bash
# reproducible smoke on the generated sample (seed = 42)
python -m backtest.cli run \
  --csv data/sample_multi_asset_data.csv \
  --strategy sma_cross \
  --seed 42 \
  --out-csv artifacts/equity.csv
```

### Walk-forward (expanding train → OOS test)

```bash
python -m backtest.cli wf-json \
  --csv data/sample_multi_asset_data.csv \
  --strategy sma_cross \
  --params '{"fast": 10, "slow": 30}' \
  --train-years 0.05 --test-months 0.5 --step-months 0.5 \
  --seed 42 \
  --out-json wf_report.json
```

The command writes `wf_report.json` with per-fold metrics and an aggregate block.
Use this in CI to guard regressions without leaking future data. The sample
dataset is only a few dozen rows, so the window sizes above are intentionally
small—bump them up for real research data.

> Goal: keep research and live execution aligned via shared specifications and metrics.

### Walk-forward with tuning (train grid → pick best → test)

```bash
python -m backtest.cli wf-opt \
  --csv data/SPY.csv \
  --strategy trinity \
  --grid 'entropy_lookback=40,60 breakout_period=55,70 entry_entropy_threshold=0.015,0.02 ema_fast=21 ema_slow=100' \
  --metric-key Sharpe_annualized --train-years 2.0 --test-months 6.0 --step-months 6.0 \
  --mode target --seed 42 --out-json wf_trinity.json
```

The report captures the best parameter set per fold along with out-of-sample metrics.
Pass `--mode delta` and include `signal_mode=delta` in the grid if you prefer delta
signals.

### Walk-Forward (Trinity)

```bash
python -m backtest.cli wf \
  --csv data/SPY.csv \
  --grid "entropy_lookback=40 entry_entropy_threshold=0.015,0.02 breakout_period=55,70 ema_fast=21 ema_slow=100" \
  --mode target --out-csv artifacts/wf_oos_returns.csv
# Then summarize
python -m backtest.cli metrics --csv artifacts/wf_oos_returns.csv
```

This command runs anchored folds (train → select → test) using the Trinity strategy,
logging out-of-sample daily returns to `artifacts/wf_oos_returns.csv`.

### Praetorian (adaptive risk) — Walk-Forward

```bash
python -m backtest.cli wf \
  --strategy praetorian \
  --csv data/SPY.csv \
  --grid "entropy_lookback=40 entry_entropy_threshold=0.012,0.015,0.02 breakout_period=55,70 ema_fast=21 ema_slow=100 vwap_max_distance_atr=0.8,1.0 base_risk_percent=1.0,1.5 conviction_gain=0.2 conviction_loss=0.4" \
  --mode target --out-csv artifacts/wf_oos_returns.csv
python -m backtest.cli metrics --csv artifacts/wf_oos_returns.csv
```

---

### Validator handoff

`strategy_validation_suite 2.py` (yep, that filename) can now ingest
`artifacts/wf_oos_returns.csv` directly. The CSV exposes a `ret_oos` column with
daily returns; if the consumer just expects "last column wins" it'll still work.

See **[docs/system_diagram.md](docs/system_diagram.md)** for architecture and flow diagrams.

---

## Quick Start (Python / Research)

```bash
# create and activate a virtualenv (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# install core deps
python -m pip install --upgrade pip
pip install pandas numpy matplotlib pytest

# run smoke tests (once code is populated)
pytest -q
```

**Backtesting entry points** (after you add the code under `backtest/`):
- `backtest/engine.py` — event-driven runner with OHLC-aware brackets & sizing
- `backtest/portfolio.py` — simple equal-weight portfolio runner
- `backtest/metrics.py` — full metrics suite (Sharpe/Sortino/Calmar/Martin/Omega/VaR/CVaR/Alpha/Beta/IR/etc.)

A minimal example (once engine is in place):
```python
from backtest.engine import run_backtest
from backtest.metrics import summarize
import pandas as pd

df = pd.read_csv("data/AAPL.csv", parse_dates=[0], index_col=0)
# strategy = ...  # construct your strategy
# rr = run_backtest(df, strategy, mode='delta', size_notional=10_000)
# stats = summarize(rr.equity_curve, rr.fills, rr.trade_log)
# print(stats)
```

### Cerberus Hyperion (turbo) — optimize & ADR

```bash
# run a tiny grid and print the best params + ADR (%/day)
python -m backtest.optimize_hyperion --csv data/sample_multi_asset_data.csv --out-csv artifacts/hyperion_grid.csv --seed 42
# smoke-test
pytest -q backtest/tests/test_hyperion_smoke.py
```

---

## Quick Start (C# / NinjaTrader)

Place the following under `csharp/`:
- `MultiAssetPortfolioSizer.cs` — portfolio-aware entropy sizer for live execution
- `AethelredAegis.cs` — example strategy that consumes the sizer + entropy regimes

> Keep entropy thresholds / risk knobs mirrored in `backtest/` so backtests and NT8 stay in sync.

---

## Repo Structure

```
entropy-portfolio-lab/
├── README.md
├── .gitignore
├── roadmap/
│   └── Road.pdf                  # (drop the roadmap here)
├── backtest/
│   ├── Back test z.pdf           # (drop the engine spec here)
│   ├── engine.py                 # (code to be added / imported from SIMlab lineage)
│   ├── portfolio.py              # (code to be added)
│   ├── metrics.py                # (code to be added)
│   └── tests/
│       ├── test_engine.py
│       └── test_flips.py
├── csharp/
│   ├── MultiAssetPortfolioSizer.cs
│   └── AethelredAegis.cs
├── specs/
│   └── manifest.json             # unified spec mapping roadmap ↔ python ↔ c#
└── .github/
    └── workflows/
        └── ci.yml                # basic CI: pytest -q
```

> You can copy your existing SIMlab v4 files into `backtest/` as a starting point.

---

## Unified Spec (Manifest)

`specs/manifest.json` is the single source of truth connecting this repo’s parts:

- **Roadmap** → high-level phases & intent
- **Python** → research/backtest entry points (engine/portfolio/metrics)
- **C#** → execution components (sizer/strategy)
- **Strategies** → names, modules, and targets

This ensures parity when you evolve knobs (entropy thresholds, sizing rules, bracket logic).

---

## Roadmap (from Road.pdf → repo tasks)

**Phase 1 — Foundations (this repo)**
- ✅ Repo skeleton, CI, tests  
- ✅ Backtest engine & portfolio runner code migrated  
- ✅ Metrics wired & benchmark flags in CLI  
- ✅ Entropy-aware sizer parity (Python ↔ C#)

**Phase 2 — Research UX**
- ✅ Walk-forward / OOS reporting  
- ✅ Rolling metrics & regime overlays (notebooks/plots)  
- ✅ Portfolio weights & constraints

**Phase 3 — Execution UX**
- ✅ Real-time alerting layer  
- ✅ Live reconciliation checks against backtests  
- ✅ Deployment playbooks

---

## Contributing

- Keep code **deterministic** (seeds, reproducible datasets).
- Add **one smoke test** per new feature.
- Update `specs/manifest.json` whenever you change shared knobs.

---

## License

Choose what fits (MIT/BSD-3-Clause/Apache-2.0). Default: MIT.

### Backtest Core — Quick sanity

```bash
# install deps
python -m pip install --upgrade pip
pip install pandas numpy matplotlib pytest

# run tests
pytest backtest/tests -q

# run a flat strategy
python -m backtest.cli run --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat --mode target

# SMA cross (target sizing)
python -m backtest.cli run --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.sma:SMACross --mode target

# RSI/EMA mean reversion (delta sizing with brackets)
python -m backtest.cli run --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.rsi_ema:RSIEmaMeanRevert --mode delta

# portfolio example (spec file)
echo '[{"name":"AAPL","csv":"backtest/samples/AAPL.csv","strategy":"backtest.strategies.flat:Flat","params":{}}]' > port.json
python -m backtest.cli portfolio --spec port.json --mode target
```

**Benchmarked runs**

```bash
python -m backtest.cli run \
  --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --bench backtest/samples/AAPL.csv
```

Prints Alpha, Beta, Information Ratio, Up/Down Capture, and Tracking Error (because numbers are friends).

## Phase 2 — Advanced Analysis
See [docs/phase2.md](docs/phase2.md) for optimization, walk-forward, attribution, and proof capsules.


### Demo data & UI

- Placeholder CSVs live in `data/*.csv` (header only). CI validates their schema.
- Run the mock API/WS locally:
  ```bash
  cd tools/mock-server && npm i && npm start
  ```
- UI expects:
  ```
  VITE_API_URL=http://localhost:8787
  VITE_WS_URL=ws://localhost:8787
  ```
- Copy `ui/.env.example` → `ui/.env` and adjust as needed.

## Quick commands

```bash
# run all CI-equivalent checks locally
make test

# UI dev with mock data (opens Vite)
make ui

# build + e2e + Lighthouse
make ui-build && make ui-test

# regenerate docs diagrams from Mermaid blocks
make diagram
```

Repro versions
  • Node: cat .nvmrc → install with nvm use
  • Python: 3.11.x (see requirements.txt)
