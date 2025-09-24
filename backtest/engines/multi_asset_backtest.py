"""Simple multi-asset backtest runner used by the CLI and smoke tests."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd


def _coerce(value: object) -> object:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"none", "null"}:
            return None
        try:
            if "." in lowered:
                return float(lowered)
            return int(lowered)
        except ValueError:
            return value
    return value


def _parse_params(params: Optional[object]) -> Dict[str, object]:
    if params is None:
        return {}
    if isinstance(params, dict):
        return {str(k): _coerce(v) for k, v in params.items()}
    if isinstance(params, Iterable) and not isinstance(params, (str, bytes)):
        result: Dict[str, object] = {}
        for item in params:
            if not isinstance(item, str) or "=" not in item:
                continue
            key, raw = item.split("=", 1)
            result[key.strip()] = _coerce(raw.strip())
        return result
    return {}


def _load_data(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    if "DATE" in frame.columns:
        frame["DATE"] = pd.to_datetime(frame["DATE"])
        frame = frame.set_index("DATE").sort_index()
    else:
        frame.index = pd.RangeIndex(start=0, stop=len(frame))
    return frame


def legacy_run_backtest(
    strategy,
    csv_path,
    params=None,
    out_csv: str | Path = "equity.csv",
    trades_csv: str | Path | None = None,
    plot: bool = False,
    headless: bool = False,
    seed: Optional[int] = None,
    **_,
):
    # --- Determinism guard (safe even if libs are absent) ---
    try:
        import random, os

        random.seed(seed if seed is not None else 0)
        os.environ["PYTHONHASHSEED"] = str(seed if seed is not None else 0)
        try:
            import numpy as np

            np.random.seed(seed if seed is not None else 0)
        except Exception:
            pass
    except Exception:
        pass

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    frame = _load_data(csv_path)
    close_cols = [col for col in frame.columns if col.endswith("_Close")]
    if not close_cols:
        raise ValueError("CSV must contain *_Close columns")

    closes = frame[close_cols]
    returns = closes.pct_change().fillna(0.0)

    params_dict = _parse_params(params)
    fast = int(params_dict.get("fast", 10) or 10)
    slow = int(params_dict.get("slow", 30) or 30)
    if fast <= 0 or slow <= 0:
        raise ValueError("SMA lengths must be positive integers")

    strat_name = str(strategy or "sma_cross").lower()
    if strat_name != "sma_cross":
        raise ValueError(f"Unsupported strategy: {strategy}")

    agg_close = closes.mean(axis=1)
    fast_sma = agg_close.rolling(window=fast, min_periods=1).mean()
    slow_sma = agg_close.rolling(window=slow, min_periods=1).mean()
    signal = (fast_sma > slow_sma).astype(float)

    weights = {col: 1.0 / len(close_cols) for col in close_cols}
    portfolio_returns = (returns.mul(weights).sum(axis=1)) * signal.shift(1).fillna(0.0)

    equity = (1.0 + portfolio_returns).cumprod()
    equity.index.name = frame.index.name or "DATE"

    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    equity.to_frame("equity").to_csv(out_path)

    if trades_csv:
        trades_path = Path(trades_csv)
        trades_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["timestamp", "symbol", "qty", "price"]).to_csv(trades_path, index=False)

    if plot:
        try:
            import matplotlib.pyplot as plt

            ax = equity.plot(title="Equity Curve")
            ax.set_ylabel("Equity")
            fig = ax.get_figure()
            fig.tight_layout()
            if isinstance(plot, str):
                fig.savefig(plot)
            else:
                fig.show() if not headless else None
            plt.close(fig)
        except Exception:
            pass

    total_return = float(equity.iloc[-1] - 1.0) if not equity.empty else 0.0
    stdev = float(portfolio_returns.std(ddof=0)) if len(portfolio_returns) > 1 else 0.0
    mean_ret = float(portfolio_returns.mean()) if not portfolio_returns.empty else 0.0
    sharpe = math.sqrt(252.0) * mean_ret / stdev if stdev > 0 else 0.0
    running_max = equity.cummax()
    drawdown = (equity / running_max) - 1.0
    mdd = float(drawdown.min()) if not drawdown.empty else 0.0

    return {"sharpe": sharpe, "mdd": mdd, "total_return": total_return}


from ..core.engine import run_backtest

__all__ = ["legacy_run_backtest", "run_backtest"]
