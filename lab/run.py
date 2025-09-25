from __future__ import annotations
import os, yaml, numpy as np, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

from strategies.etrp import run_etrp
# NEW: stress zoo hook
try:
    from lab.data.stress_zoo import generate_stress_zoo
except Exception:
    # allow running even if module not present yet
    generate_stress_zoo = None

# ---------------- utilities

def _read_prices_from_folder(folder: Path, universe: list[str]) -> pd.DataFrame:
    """
    Load prices from either per-symbol CSVs (Date, Close) or a combined prices.csv (wide).
    """
    combined = folder / "prices.csv"
    if combined.exists():
        df = pd.read_csv(combined, parse_dates=["Date"]).set_index("Date")
        cols = [c for c in universe if c in df.columns]
        if not cols:
            raise ValueError(f"No requested symbols found in combined file: {combined}")
        return df[cols]
    # fallback: per-symbol files
    frames = []
    for sym in universe:
        f = folder / f"{sym}.csv"
        if f.exists():
            s = pd.read_csv(f, parse_dates=["Date"]).set_index("Date")["Close"].rename(sym)
            frames.append(s)
        else:
            frames.append(None)
    if all(s is None for s in frames):
        raise FileNotFoundError(f"No CSVs found for requested tickers in {folder}")
    return pd.concat([s for s in frames if s is not None], axis=1)

def _resolve_data_dir(cfg: dict) -> Path:
    """
    Supports:
      - regular path (e.g., 'data')
      - special form 'stress_zoo:<scenario>' which auto-generates if missing
    """
    data_dir_spec = cfg["data"]["data_dir"]
    universe = list(cfg["data"]["universe"])
    root = Path("data")  # default root for zoo generation

    if isinstance(data_dir_spec, str) and data_dir_spec.startswith("stress_zoo:"):
        scenario = data_dir_spec.split(":", 1)[1].strip()
        zoo_root = root / "stress_zoo"
        scen_dir = zoo_root / scenario

        if not scen_dir.exists():
            if generate_stress_zoo is None:
                raise RuntimeError(
                    "stress_zoo requested but generator not available. "
                    "Add lab/data/stress_zoo.py from earlier scaffold."
                )
            # generate all scenarios so user can poke around, but we’ll read the one we asked for
            print(f"[run] stress_zoo requested -> generating scenario '{scenario}' under {zoo_root} ...")
            meta = generate_stress_zoo(outdir=str(zoo_root), universe=universe, n_days=252*5, seed=cfg.get("seed", 42))
            if scenario not in meta["scenarios"]:
                raise ValueError(f"Scenario '{scenario}' not generated; available: {list(meta['scenarios'].keys())}")
        return scen_dir

    # regular path
    return Path(str(data_dir_spec))

def load_prices(cfg: dict) -> pd.DataFrame:
    universe = list(cfg["data"]["universe"])
    start = pd.Timestamp(cfg["backtest"]["start"])
    end = pd.Timestamp(cfg["backtest"]["end"])

    data_dir = _resolve_data_dir(cfg)

    if data_dir.exists():
        px = _read_prices_from_folder(data_dir, universe)
    else:
        # same behavior as before
        if cfg["data"].get("use_synth_if_missing", True):
            print(f"[run] data_dir '{data_dir}' missing; using synthetic GBM-ish data.")
            np.random.seed(cfg.get("seed", 42))
            idx = pd.date_range(start, end, freq="B")
            synth = {}
            for i, sym in enumerate(universe):
                mu, sig = 0.06, 0.18
                eps = np.random.normal(0, sig/np.sqrt(252), size=len(idx))
                r = (mu/252) + eps
                synth[sym] = 100 * (1 + pd.Series(r, index=idx)).cumprod()
            px = pd.DataFrame(synth)
        else:
            raise FileNotFoundError(f"Data dir not found: {data_dir}")

    px = px.loc[start:end].dropna(how="all")
    return px

def main(config_path: str = "configs/etrp.yml"):
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    outdir = Path(cfg["output"]["out_dir"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)

    px = load_prices(cfg)
    res = run_etrp(px, cfg)

    # save
    res["weights_me"].to_csv(outdir / "weights_monthly.csv")
    res["port_monthly"].to_csv(outdir / "portfolio_monthly.csv", header=["ret"])
    res["equity"].to_csv(outdir / "equity.csv", header=["equity"])

    m = res["metrics"]
    print(f"[metrics] CAGR={m['CAGR']:.2%}  VolAnn={m['VolAnn']:.2%}  Sharpe={m['Sharpe']:.2f}  MaxDD={m['MaxDD']:.2%}")

    if cfg["output"].get("plot", True):
        fig, ax = plt.subplots(figsize=(9,4))
        res["equity"].plot(ax=ax, title="ETRP – Equity Curve")
        ax.grid(True, alpha=.3)
        fig.tight_layout()
        fig.savefig(outdir / "equity.png", dpi=150)

if __name__ == "__main__":
    main()
