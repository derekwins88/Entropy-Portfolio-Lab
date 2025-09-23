import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path("/mnt/data/entropy-portfolio-lab")
ROOT.mkdir(parents=True, exist_ok=True)

GITIGNORE = """# Python
__pycache__/
*.pyc
.venv/
.env

# C#
bin/
obj/

# OS
.DS_Store

# Notebooks & data
*.ipynb_checkpoints/
data/
"""

README = """# Entropy Portfolio Lab

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
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# install core deps
python -m pip install --upgrade pip
pip install pandas numpy matplotlib pytest

# run smoke tests (once code is populated)
pytest -q
```

Backtesting entry points (after you add the code under backtest/):
•backtest/engine.py — event-driven runner with OHLC-aware brackets & sizing
•backtest/portfolio.py — simple equal-weight portfolio runner
•backtest/metrics.py — full metrics suite (Sharpe/Sortino/Calmar/Martin/Omega/VaR/CVaR/Alpha/Beta/IR/etc.)

A minimal example (once engine is in place):

from backtest.engine import run_backtest
from backtest.metrics import summarize
import pandas as pd

df = pd.read_csv("data/AAPL.csv", parse_dates=[0], index_col=0)
# strategy = ...  # construct your strategy
# rr = run_backtest(df, strategy, mode='delta', size_notional=10_000)
# stats = summarize(rr.equity_curve, rr.fills, rr.trade_log)
# print(stats)


⸻

Quick Start (C# / NinjaTrader)

Place the following under csharp/:
•MultiAssetPortfolioSizer.cs — portfolio-aware entropy sizer for live execution
•AethelredAegis.cs — example strategy that consumes the sizer + entropy regimes

Keep entropy thresholds / risk knobs mirrored in backtest/ so backtests and NT8 stay in sync.

⸻

Repo Structure

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

You can copy your existing SIMlab v4 files into backtest/ as a starting point.

⸻

Unified Spec (Manifest)

specs/manifest.json is the single source of truth connecting this repo’s parts:
•Roadmap → high-level phases & intent
•Python → research/backtest entry points (engine/portfolio/metrics)
•C# → execution components (sizer/strategy)
•Strategies → names, modules, and targets

This ensures parity when you evolve knobs (entropy thresholds, sizing rules, bracket logic).

⸻

Roadmap (from Road.pdf → repo tasks)

Phase 1 — Foundations (this repo)
•✅ Repo skeleton, CI, tests
•⬜ Backtest engine & portfolio runner code migrated
•⬜ Metrics wired & benchmark flags in CLI
•⬜ Entropy-aware sizer parity (Python ↔ C#)

Phase 2 — Research UX
•⬜ Walk-forward / OOS reporting
•⬜ Rolling metrics & regime overlays (notebooks/plots)
•⬜ Portfolio weights & constraints

Phase 3 — Execution UX
•⬜ Real-time alerting layer
•⬜ Live reconciliation checks against backtests
•⬜ Deployment playbooks

⸻

Contributing
•Keep code deterministic (seeds, reproducible datasets).
•Add one smoke test per new feature.
•Update specs/manifest.json whenever you change shared knobs.

⸻

License

Choose what fits (MIT/BSD-3-Clause/Apache-2.0). Default: MIT.
"""

MANIFEST = {
    "project": "Entropy Portfolio Lab",
    "roadmap": {
        "doc": "roadmap/Road.pdf",
        "phases": [
            "Backtest Engine",
            "Portfolio-Aware Entropy Sizer",
            "Strategy Layer (Aethelred’s Aegis)",
            "Quantum Optimizer (future)"
        ]
    },
    "python": {
        "engine": "backtest/engine.py",
        "portfolio": "backtest/portfolio.py",
        "metrics": "backtest/metrics.py",
        "tests": [
            "backtest/tests/test_engine.py",
            "backtest/tests/test_flips.py"
        ],
        "source_doc": "backtest/Back test z.pdf"
    },
    "csharp": {
        "sizer": "csharp/MultiAssetPortfolioSizer.cs",
        "strategy": "csharp/AethelredAegis.cs",
        "alignment": "Mirror entropy thresholds & risk knobs between Python and C#."
    },
    "strategies": [
        {
            "name": "Aethelred’s Aegis",
            "type": "Entropy Regime Strategy",
            "modules": [
                "Entropy Sizer",
                "Conviction Engine",
                "Multi-timeframe Confirmer"
            ],
            "target": "NinjaTrader live trading"
        }
    ]
}

CI = """name: CI
on:
  push: { branches: [ main, master ] }
  pull_request: { branches: [ main, master ] }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install --upgrade pip
      - run: pip install pandas numpy matplotlib pytest
      - run: pytest -q
"""

TEST_ENGINE = """import pandas as pd


def test_placeholder():
    idx = pd.date_range('2020-01-01', periods=3, freq='B')
    assert len(idx) == 3
"""

TEST_FLIPS = """def test_placeholder_flips():
    assert 1 + 1 == 2
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_uploaded_pdfs() -> None:
    src_road = Path("/mnt/data/Road.pdf")
    dst_road = ROOT / "roadmap" / "Road.pdf"
    if src_road.exists():
        shutil.copyfile(src_road, dst_road)

    src_back = Path("/mnt/data/Back test z.pdf")
    dst_back = ROOT / "backtest" / "Back test z.pdf"
    if src_back.exists():
        shutil.copyfile(src_back, dst_back)


def main() -> None:
    write(ROOT / ".gitignore", GITIGNORE)
    write(ROOT / "README.md", README)
    write(ROOT / "specs" / "manifest.json", json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    write(ROOT / ".github" / "workflows" / "ci.yml", CI)
    write(ROOT / "backtest" / "tests" / "test_engine.py", TEST_ENGINE)
    write(ROOT / "backtest" / "tests" / "test_flips.py", TEST_FLIPS)

    (ROOT / "roadmap").mkdir(parents=True, exist_ok=True)
    (ROOT / "backtest").mkdir(parents=True, exist_ok=True)
    (ROOT / "csharp").mkdir(parents=True, exist_ok=True)

    copy_uploaded_pdfs()

    zip_path = Path("/mnt/data/entropy-portfolio-lab_skeleton.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, _, files in os.walk(ROOT):
            for name in files:
                full = Path(folder) / name
                rel = full.relative_to(Path("/mnt/data"))
                zf.write(full, rel.as_posix())

    print(zip_path)


if __name__ == "__main__":
    main()
