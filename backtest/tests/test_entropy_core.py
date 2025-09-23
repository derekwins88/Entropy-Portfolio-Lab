from engines.multi_asset_backtest import run_backtest


def test_run_backtest_is_deterministic(tmp_path):
    # Use tiny sample; rely on in-repo CSV
    m1 = run_backtest(strategy="sma_cross",
                      csv_path="data/sample_multi_asset_data.csv",
                      out_csv=tmp_path/"e1.csv",
                      headless=True,
                      seed=42)
    m2 = run_backtest(strategy="sma_cross",
                      csv_path="data/sample_multi_asset_data.csv",
                      out_csv=tmp_path/"e2.csv",
                      headless=True,
                      seed=42)
    # Compare a stable scalar (e.g., sharpe to 10^-9) to avoid FP noise
    assert round(m1["sharpe"] - m2["sharpe"], 12) == 0.0
