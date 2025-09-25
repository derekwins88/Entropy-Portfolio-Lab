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

    # optional: overwrite strategy target_vol_ann from persisted learner state
    try:
        from lab.adaptive.persistence import load_pickle
        st_path = cfg.get("adaptive", {}).get("persistence", {}).get("state_path", "")
        if st_path and os.path.exists(st_path):
            state = load_pickle(st_path)
            if hasattr(state, "params"):
                cfg["strategy"]["target_vol_ann"] = float(
                    state.params.get("vol_target", cfg["strategy"]["target_vol_ann"])
                )
                print(
                    f"[adaptive] using persisted vol_target={cfg['strategy']['target_vol_ann']:.3f}"
                )
    except Exception as exc:
        print(f"[adaptive] warning: failed to apply persisted params: {exc}")

    outdir = Path(cfg["output"]["out_dir"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)

    px = load_prices(cfg)
    res = run_etrp(px, cfg)

    # --- adaptive integration with persistence ---
    if cfg.get("adaptive", {}).get("enabled", False):
        from lab.adaptive.online_learner import OnlineLearner, OnlineLearnerState
        from lab.adaptive.regime_classifier import classify_regime
        from lab.adaptive.vol_targeter import compute_target_scalar
        from lab.adaptive.persistence import save_pickle, load_pickle, save_json

        adaptive_cfg = cfg["adaptive"]
        persistence_cfg = adaptive_cfg.get("persistence", {})
        state_path = persistence_cfg.get("state_path", "runs/adaptive_state.pkl")
        snapshot_json = persistence_cfg.get("snapshot_json", "runs/adaptive_state.json")
        keep_json = bool(persistence_cfg.get("keep_json", True))

        learner_cfg = adaptive_cfg["online_learner"]
        init_params = learner_cfg.get(
            "init_params",
            {
                "tilt": 0.5,
                "vol_target": cfg["strategy"]["target_vol_ann"],
                "adapt_rate": learner_cfg.get("adapt_rate", 0.01),
            },
        )
        bounds = {k: tuple(v) for k, v in learner_cfg.get("bounds", {}).items()}
        init_state = OnlineLearnerState(
            params=init_params,
            adapt_rate=learner_cfg.get("adapt_rate", 0.01),
            momentum=learner_cfg.get("momentum", 0.9),
            expl_noise=learner_cfg.get("expl_noise", 0.0),
            bounds=bounds,
        )

        if os.path.exists(state_path):
            try:
                state = load_pickle(state_path)
                print(f"[adaptive] loaded state from {state_path}: {state.params}")
            except Exception as exc:
                print(f"[adaptive] failed to load state ({exc}); using fresh state.")
                state = init_state
        else:
            state = init_state
            print("[adaptive] no prior state; starting fresh.")

        learner = OnlineLearner(state)

        metrics = res["metrics"]
        new_params = learner.update(
            {
                "sharpe": metrics.get("Sharpe", 0.0),
                "maxdd": metrics.get("MaxDD", 0.0),
                "entropy": 0.0,
            }
        )
        print(f"[adaptive] updated params: {new_params}")

        regime_cfg = adaptive_cfg["regime"]
        labels = classify_regime(
            px.pct_change().dropna(),
            entropy=None,
            vol_window=regime_cfg["vol_window"],
            ent_window=regime_cfg["ent_window"],
        )
        latest_regime = labels.dropna().iloc[-1] if not labels.dropna().empty else "unknown"
        print(f"[adaptive] latest regime: {latest_regime}")

        scalar = compute_target_scalar(
            res["port_monthly"],
            base_target_ann=new_params.get("vol_target", cfg["strategy"]["target_vol_ann"]),
        )
        print(f"[adaptive] exposure scalar (next run hint): {scalar:.3f}")

        save_pickle(state_path, learner.state)
        if keep_json:
            try:
                save_json(
                    snapshot_json,
                    {"params": learner.state.params, "bounds": learner.state.bounds},
                )
            except Exception:
                pass
        print(
            f"[adaptive] state saved → {state_path}" +
            (f" and {snapshot_json}" if keep_json else "")
        )

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
