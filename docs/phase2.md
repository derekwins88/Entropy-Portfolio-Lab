# Phase 2 — Advanced Analysis & Validation

## CLI Commands

### Single Strategy

```bash
python -m backtest.cli run --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --bench backtest/samples/SPY.csv \
  --out-daily daily.csv
```

Adding a benchmark unlocks Alpha/Beta/Information Ratio alongside the up/down
capture figures, while `--out-daily` writes a CSV with equity, returns,
drawdown and rolling Sharpe for quick inspection.

### Grid Search

```bash
python -m backtest.cli opt --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --grid foo=1,2 bar=a,b
```

Include `--bench backtest/samples/SPY.csv` to score candidate parameter sets on
active statistics such as Information Ratio.

### Walk-Forward (anchored)

```bash
python -m backtest.cli walk --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --grid x=1,2 --train-years 1 --test-years 1
```

Benchmarks propagate through walk-forward reporting as well, so mix in the same
`--bench` flag when you want the summaries to be market-aware.

### Performance Attribution

```bash
python -m backtest.cli attr --trades forwardtest/LOG.trades.csv
```

Provide a regimes CSV with `--regimes` to split contributions by entropy state or
other overlays.

```bash
python -m backtest.cli attr --trades forwardtest/LOG.trades.csv \
  --plot attribution.png
```

The optional `--plot` flag produces a stacked bar PNG showing how each asset
contributed across regimes.

## Proof Capsules

Use the manual GitHub Action "Proof Capsules" to verify walk-forward results:

1. Generate a CSV (e.g., `python -m backtest.cli walk ... --out-csv wf.csv`).
2. Trigger the workflow and supply the CSV path along with Sharpe/MaxDD
   thresholds.
3. Download the capsule artifact containing JSON + Lean stubs.
