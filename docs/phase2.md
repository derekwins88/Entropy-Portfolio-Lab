# Phase 2 — Advanced Analysis & Validation

## CLI Commands

### Grid Search

```bash
python -m backtest.cli opt --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --grid foo=1,2 bar=a,b
```

### Walk-Forward (anchored)

```bash
python -m backtest.cli walk --csv backtest/samples/AAPL.csv \
  --strategy backtest.strategies.flat:Flat \
  --grid x=1,2 --train-years 1 --test-years 1
```

### Performance Attribution

```bash
python -m backtest.cli attr --trades forwardtest/LOG.trades.csv
```

Provide a regimes CSV with `--regimes` to split contributions by entropy state or
other overlays.

## Proof Capsules

Use the manual GitHub Action "Proof Capsules" to verify walk-forward results:

1. Generate a CSV (e.g., `python -m backtest.cli walk ... --out-csv wf.csv`).
2. Trigger the workflow and supply the CSV path along with Sharpe/MaxDD
   thresholds.
3. Download the capsule artifact containing JSON + Lean stubs.
