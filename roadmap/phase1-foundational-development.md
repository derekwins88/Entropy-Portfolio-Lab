# Phase 1 Tracking Pack — GitHub Issues Ready

## Master Issue — Phase 1: Foundational Development

**Title:** Phase 1 — Foundational Development (baseline you can trust)

**Scope**
- Make the multi-asset stack tradeable, testable, and boring (in the best way).
- Capture baseline metrics so Phase 2/3 improvements have something real to beat.

**Checklist**
- [ ] 1) Multi-Asset Strategy Integration
- [ ] 2) Rolling Correlation Tracking
- [ ] 3) Execution Modeling (slippage/latency/partials)
- [ ] 4) Baseline Metrics Recorder (entropy/risk/corr)
- [ ] 5) Data Consistency Guard (multi-asset safe)
- [ ] 6) Unit Test Harness for Phase 1 modules
- [ ] 7) CI upgrades (matrix + artifacts)
- [ ] 8) Docs: quick recipes + contribution template

---

## Issue 1 — Multi-Asset Strategy Integration

**Title:** feat(backtest): MultiAssetEntropyStrategy + portfolio sizing glue

**Why**
Without a portfolio-aware strategy entrypoint, everything stays academic.

**Tasks**
- [ ] Add `backtest/strategies/entropy_portfolio.py` with:
      - class `MultiAssetEntropyStrategy(BarStrategy)`
      - `on_bar()` reads per-asset signals; emits target or delta by asset
- [ ] Extend `backtest/core/portfolio.py` to accept per-asset params & weights
- [ ] Add simple demo spec (`port_mae.json`) with 2–3 assets
- [ ] CLI example in README

**Definition of Done**
- `python -m backtest.cli portfolio --spec port_mae.json` runs end-to-end
- Equity curve produced; no KeyErrors/NaNs; logs present in `forwardtest/`

---

## Issue 2 — Rolling Correlation Tracking

**Title:** feat(backtest): rolling correlation matrix + summary stats

**Why**
Portfolio realism starts with correlation, not vibes.

**Tasks**
- [ ] Add `backtest/core/corr.py` with `rolling_corr(prices, window=90)`
- [ ] Compute portfolio-level metrics each bar:
      - `avg_abs_corr`, cluster hints (optional)
- [ ] Expose to `metrics.summarize()` as `"AvgAbsCorr"`
- [ ] Add test with contrived series: high corr vs low corr sanity

**Definition of Done**
- `pytest backtest/tests/test_corr.py -q` passes
- README: one 5-line example of using the helper

---

## Issue 3 — Execution Modeling (slippage/latency/partials)

**Title:** feat(execution): slippage bps, latency bars, partial fills w/ liquidity cap

**Why**
Backtests that ignore microstructure lie to you.

**Tasks**
- [ ] Extend `backtest/core/broker.py`:
      - existing bps slippage (keep)
      - latency: apply fills on t+N bars (configurable)
      - partials: cap per-bar fill notional or units
- [ ] Add config passthrough in `engine.run_backtest(...)`
- [ ] Write tests:
      - slippage applied on both sides
      - latency shifts fill timestamps
      - 100 units requested, only 50 filled when cap=50

**Definition of Done**
- `pytest backtest/tests/test_execution.py -q` passes

---

## Issue 4 — Baseline Metrics Recorder

**Title:** feat(metrics): daily recorder (entropy, risk%, avg corr) + CSV

**Why**
You can't improve what you don't record.

**Tasks**
- [ ] Add `backtest/report.py` -> `record_daily(run_result, extras: dict)` -> `DataFrame`
- [ ] Record per-day: equity, drawdown, realized risk %, avg_abs_corr, (optional) entropy
- [ ] CLI: `--out-daily daily.csv` on run/portfolio subcommands
- [ ] Forward-test: append daily to `forwardtest/logs/*.equity.csv`

**Definition of Done**
- Running CLI with `--out-daily` writes a well-formed CSV
- README snippet showing 2-line usage

---

## Issue 5 — Data Consistency Guard

**Title:** fix(data): multi-asset guardrails (skip bad symbols, no silent corruption)

**Why**
One NaN shouldn't sabotage the whole portfolio.

**Tasks**
- [ ] Add `assert_data_ok_multi(df_map)` -> returns `(ok_symbols, skipped)`
- [ ] Engine/portfolio loop: skip symbols with NaN/duplicate index at bar
- [ ] Emit warning count; include `"SkippedSymbols"` in `summarize()`

**Definition of Done**
- Synthetic test with one broken CSV => portfolio still runs; `"SkippedSymbols"` >= 1

---

## Issue 6 — Unit Test Harness (Phase 1)

**Title:** test: Phase 1 harness (sizer, corr, execution) + fixtures

**Why**
We like green checks. They keep us honest.

**Tasks**
- [ ] `tests/fixtures.py` (tiny OHLC generators)
- [ ] `test_sizer.py`: size recommendation across entropy/corr scenarios
- [ ] `test_corr.py`: high vs low corr sanity (window=10)
- [ ] `test_execution.py`: slippage/latency/partials
- [ ] `test_guard.py`: missing OHLC handled without crash

**Definition of Done**
- `pytest backtest/tests -q` green on CI

---

## Issue 7 — CI Upgrades (matrix + artifacts)

**Title:** chore(ci): python 3.10–3.12 matrix + store daily/forward logs

**Why**
If it isn’t tested there, it doesn’t exist.

**Tasks**
- [ ] Update `.github/workflows/ci.yml` with `strategy.matrix` (3.10, 3.11, 3.12)
- [ ] Cache pip; upload `backtest/out/*.csv` as artifacts if present
- [ ] Ensure forward-test workflow publishes logs every run

**Definition of Done**
- All jobs green; artifacts visible under Actions

---

## Issue 8 — Docs & Contributor Starter

**Title:** docs: quick recipes + strategy template + issue templates

**Why**
Gift repo energy.

**Tasks**
- [ ] `docs/recipes.md` (run, portfolio, walk-forward, forward-test)
- [ ] `backtest/strategies/template.py` (commented stub)
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md` & `feature_request.md`
- [ ] README: “Contributing strategies” section w/ checklist

**Definition of Done**
- New contributor can add a strategy with copy/paste and 1 test

---

## Paste-ready Task List

- [ ] MultiAssetEntropyStrategy + portfolio glue
- [ ] Rolling correlation matrix + AvgAbsCorr metric
- [ ] Execution modeling: latency + partial fills
- [ ] Baseline daily metrics recorder + --out-daily
- [ ] Data consistency guard (skip bad symbols, count)
- [ ] Tests: sizer, corr, execution, guard + fixtures
- [ ] CI matrix & log artifacts
- [ ] Docs: recipes + strategy template + issue templates

**Suggested Labels**
- `type:feature`, `type:test`, `type:docs`, `area:execution`, `area:portfolio`
- `good first issue` (only for the template/doc bits)
- `priority:p1` for Issues 1–5, `priority:p2` for the rest

**Quick Commands (drop into PR descriptions)**
```bash
pytest backtest/tests -q
python -m backtest.cli portfolio --spec port_mae.json --mode delta --out-daily daily.csv
```
