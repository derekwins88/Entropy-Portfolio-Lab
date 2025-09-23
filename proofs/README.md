# Proof Capsules

This directory stores machine-checkable capsules describing performance or risk
claims derived from research artifacts. The workflow is intentionally lightweight:

1. Produce a CSV with walk-forward or Monte Carlo results.
2. Generate a capsule using :mod:`proofs.capsule` with the desired thresholds.
3. Upload the produced JSON/Lean files as build artifacts (CI workflow provided).

Capsules encode the observed metrics and the thresholds being asserted. The JSON
format is friendly to automated verification pipelines while the Lean stub offers
an optional entry point for formal proofs if desired.
