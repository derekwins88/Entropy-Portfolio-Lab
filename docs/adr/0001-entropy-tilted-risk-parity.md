# ADR 0001: Strategy – Entropy-Tilted Risk Parity (ETRP)

- **Date:** 2025-09-24
- **Status:** Proposed (pilot in backtester)

## Context
We need a baseline multi-asset strategy that (a) is simple enough to validate in Python, (b) maps to execution components in C#/NinjaTrader, and (c) explicitly uses entropy as a signal.

## Decision
Adopt ETRP:
- Universe: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, LQD, GLD, SHY (configurable)
- Rebalance: monthly; long-only; weight cap 30%
- Base weights: inverse 63-day realized volatility
- Entropy signal: Shannon entropy of 63-day daily returns (20-bin histogram) normalized 0–1 over a 3-year window
- Tilt: `w_i ← w_i * (1 - H_i_norm)` with renormalization to sum to 1
- Regime: if portfolio vol in 95th pct **or** average entropy in 80th pct → shift 50% weight to IEF/TLT/SHY for one month
- Risk: scalar to 10% annualized portfolio vol; turnover cap 50%

## Consequences
**Pros**
- Transparent, explainable; one extra feature (entropy) added to a classic risk-parity base
- Maps neatly to Python backtests and C# execution
- Regime overlay reduces tail exposure when uncertainty spikes

**Cons**
- Entropy estimation is data-hungry and sensitive to binning; risk of over-smoothing
- Long-only with caps may underperform in strong equity regimes vs momentum-only

## Implementation Notes
- Module: `lab/strategies/etrp.py` with pandas + numpy helpers (numba optional later)
- Config in `configs/etrp.yml` (universe, windows, caps)
- Unit tests: synthetic series with known entropy ordering
- Metrics: CAGR, stdev, max DD, Sharpe, Sortino, Calmar, turnover, hit rate
