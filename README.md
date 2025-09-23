![Paper Forward Test](https://github.com/entropy-lab/Entropy-Portfolio-Lab/actions/workflows/forward-test.yml/badge.svg)
[![CI](https://github.com/entropy-lab/Entropy-Portfolio-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/entropy-lab/Entropy-Portfolio-Lab/actions/workflows/ci.yml)

# Entropy Portfolio Lab

A unified, research-to-execution repository for **entropy-aware portfolio trading**.

This lab ties together:
- **Roadmap** (design intent & milestones)
- **Python backtester** (research & validation)
- **C# / NinjaTrader components** (execution-grade sizers/strategies)
- **Specs** (one manifest that maps roadmap → code → strategy)

> Goal: keep research and live execution aligned via shared specifications and metrics.

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
- ⬜ Backtest engine & portfolio runner code migrated
- ⬜ Metrics wired & benchmark flags in CLI
- ⬜ Entropy-aware sizer parity (Python ↔ C#)

**Phase 2 — Research UX**
- ⬜ Walk-forward / OOS reporting
- ⬜ Rolling metrics & regime overlays (notebooks/plots)
- ⬜ Portfolio weights & constraints

**Phase 3 — Execution UX**
- ⬜ Real-time alerting layer
- ⬜ Live reconciliation checks against backtests
- ⬜ Deployment playbooks

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

