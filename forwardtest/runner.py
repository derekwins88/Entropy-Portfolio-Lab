"""Simple forward-test orchestrator for paper trading."""

from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from backtest.core.engine import run_backtest
from backtest.core.metrics import summarize


def _ensure_parent(path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_csv_any(path: str | pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    df.index = pd.to_datetime(df.index)
    df.index.name = "datetime"
    df = df.sort_index()
    columns = {col.lower(): col for col in df.columns}
    close_col = (
        columns.get("adj close")
        or columns.get("adj_close")
        or columns.get("adjusted close")
        or columns.get("close")
    )
    if close_col is None:
        # fallback: first numeric column
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                close_col = col
                break
    if close_col is None:
        raise ValueError(f"Could not infer close column in {path}")
    rename: Dict[str, str] = {}
    if close_col != "close":
        rename[close_col] = "close"
    for field in ("open", "high", "low"):
        original = columns.get(field)
        if original:
            rename[original] = field
    if rename:
        df = df.rename(columns=rename)
    return df.dropna(subset=["close"]).copy()


def assert_data_ok(df: pd.DataFrame, expect_ohlc: bool = False) -> None:
    if not df.index.is_monotonic_increasing:
        raise AssertionError("Index must be increasing (sorted by time)")
    if df.index.duplicated().any():
        raise AssertionError("Duplicate timestamps detected")
    if df["close"].isna().any():
        raise AssertionError("NaN values detected in close column")
    if expect_ohlc:
        for column in ("high", "low", "open"):
            if column not in df.columns:
                raise AssertionError(f"Missing required column '{column}' for OHLC runs")


@dataclass
class FTPaths:
    root: pathlib.Path
    state: pathlib.Path
    logs: pathlib.Path


def ft_paths(root: str | pathlib.Path = "forwardtest") -> FTPaths:
    root_path = pathlib.Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    logs = root_path / "logs"
    logs.mkdir(exist_ok=True)
    return FTPaths(root=root_path, state=root_path / "state.json", logs=logs)


def load_state(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_state(path: pathlib.Path, state: Dict[str, Any]) -> None:
    _ensure_parent(path).write_text(json.dumps(state, indent=2))


def _resolve_strategy(path: str) -> Any:
    module, cls = path.rsplit(":", 1)
    return getattr(import_module(module), cls)


def _filter_new_rows(df: pd.DataFrame, last_timestamp: Optional[pd.Timestamp]) -> pd.DataFrame:
    if last_timestamp is None:
        return df
    return df[df.index > last_timestamp]


def _strategy_instance(strategy_path: str, params: Optional[Dict[str, Any]]) -> Any:
    cls = _resolve_strategy(strategy_path)
    return cls(params or {})


def run_once(spec: Dict[str, Any], root: str | pathlib.Path = "forwardtest") -> str:
    """Run a forward-test update for ``spec``."""

    paths = ft_paths(root)
    state = load_state(paths.state)

    df = load_csv_any(spec["csv"])
    assert_data_ok(df, expect_ohlc=spec.get("expect_ohlc", False))

    last_ts = state.get(spec["name"])
    last_seen = pd.to_datetime(last_ts) if last_ts else None
    new_rows = _filter_new_rows(df, last_seen)
    if last_seen is not None and new_rows.empty:
        print("noop")
        return "noop"

    strat = _strategy_instance(spec["strategy"], spec.get("params"))
    result = run_backtest(
        df,
        strat,
        starting_cash=spec.get("cash", 100_000.0),
        mode=spec.get("mode", "target"),
        size=spec.get("size", 1),
        size_notional=spec.get("size_notional"),
        risk_R=spec.get("risk_R"),
        atr_len=spec.get("atr_len"),
        risk_pct=spec.get("risk_pct", 0.01),
        commission=spec.get("commission", 0.0),
        slippage_bps=spec.get("slippage", 0.0),
    )

    strategy_name = spec["strategy"].rsplit(":", 1)[1]
    trades_path = _ensure_parent(paths.logs / f"{spec['name']}_{strategy_name}.trades.csv")
    equity_path = _ensure_parent(paths.logs / f"{spec['name']}_{strategy_name}.equity.csv")

    trades_df = pd.DataFrame(result.trade_log)
    trades_df.to_csv(trades_path, index=False)

    equity_df = pd.DataFrame(
        {"datetime": result.equity_curve.index, "equity": result.equity_curve.values}
    )
    equity_df.to_csv(equity_path, index=False)

    last_bar = df.index[-1]
    state[spec["name"]] = last_bar.isoformat()
    save_state(paths.state, state)

    stats = summarize(result.equity_curve, result.fills, result.trade_log)
    sharpe = stats.get("Sharpe_annualized", stats.get("Sharpe_d", 0.0))
    max_dd = abs(stats.get("MaxDrawdown", 0.0))
    trades = int(stats.get("Trades", len(trades_df)))
    line = (
        f"{spec['name']} {strategy_name}  "
        f"EndEq={result.equity_curve.iloc[-1]:.2f}  "
        f"CAGR={stats.get('CAGR', 0.0):.2%}  "
        f"Sharpe={sharpe:.2f}  "
        f"DD={max_dd:.2%}  "
        f"Trades={trades}"
    )
    print(line)
    return line


def _load_specs(value: str) -> List[Dict[str, Any]]:
    path = pathlib.Path(value)
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = json.loads(value)
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        raise ValueError("Spec payload must decode to a list of dicts")
    return data


def main(argv: Optional[Iterable[str]] = None) -> List[str]:
    parser = argparse.ArgumentParser(prog="forwardtest")
    parser.add_argument("--spec", required=True, help="JSON file or literal spec list")
    parser.add_argument("--root", default="forwardtest", help="Output directory root")
    args = parser.parse_args(list(argv) if argv is not None else None)

    specs = _load_specs(args.spec)
    outputs: List[str] = []
    for spec in specs:
        outputs.append(run_once(spec, root=args.root))
    return outputs


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
