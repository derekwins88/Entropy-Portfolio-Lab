import numpy as np

def backtest(prices, risk_free=0.0):
    rets = prices.pct_change().dropna()
    sharpe = ((rets.mean() - risk_free/252) / rets.std()) * (252 ** 0.5) if rets.std() else 0.0
    print(f"Sharpe (entropylab): {sharpe:.2f}")
    return {"sharpe": float(sharpe)}
