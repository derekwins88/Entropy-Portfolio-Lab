import numpy as np
import pandas as pd
from lab.adaptive.online_learner import OnlineLearner, OnlineLearnerState
from lab.adaptive.regime_classifier import classify_regime
from lab.adaptive.vol_targeter import compute_target_scalar
from lab.adaptive.watchdog import Watchdog, WatchdogConfig

def test_online_learner_updates():
    state = OnlineLearnerState(params={"tilt":0.5, "vol_target":0.10}, adapt_rate=0.05, bounds={"tilt":(0.0,0.95), "vol_target":(0.01,0.5)})
    ol = OnlineLearner(state)
    m_good = {"sharpe": 1.0, "maxdd": -0.02, "entropy": 0.1}
    p1 = ol.update(m_good)
    assert "tilt" in p1 and "vol_target" in p1
    m_bad = {"sharpe": -1.0, "maxdd": -0.5, "entropy": 1.0}
    p2 = ol.update(m_bad)
    assert p2["tilt"] >= 0.0 and p2["tilt"] <= 0.95

def test_regime_classifier_basic():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    rng = np.random.default_rng(0)
    # create low-vol then high-vol sequence
    r = np.zeros((len(idx), 3))
    r[:200] = rng.normal(0, 0.002, size=(200,3))
    r[200:] = rng.normal(0, 0.03, size=(200,3))
    df = pd.DataFrame(r, index=idx, columns=["A","B","C"])
    labels = classify_regime(df)
    assert labels.isin(["calm","normal","turbo","panic"]).all()

def test_vol_targeter_scaling():
    idx = pd.date_range("2020-01-01", periods=36, freq="ME")
    # small random monthly returns
    r = pd.Series(np.random.default_rng(1).normal(0.01/12, 0.03, size=len(idx)), index=idx)
    scalar = compute_target_scalar(r, base_target_ann=0.10)
    assert scalar > 0


def test_watchdog_alert_triggers():
    cfg = WatchdogConfig(max_dd=0.10, min_sharpe=0.0, max_turnover=1.0, webhook=None, cooldown_secs=0)
    wd = Watchdog(cfg)
    metrics = {"MaxDD": -0.2, "Sharpe": -0.5, "Turnover": 1.5}
    alerts = wd.check(metrics, context={})
    assert alerts and {a["type"] for a in alerts} >= {"max_dd", "sharpe", "turnover"}
