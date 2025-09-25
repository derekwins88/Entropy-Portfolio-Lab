"""
Simple online learner for a few hyperparameters using exponentially-weighted updates.
Designed to be safe (bounded updates) and interpretable.

Interface:
    state = OnlineLearnerState(params=dict(tilt=0.5, vol_target=0.10), adapt_rate=0.01)
    learner = OnlineLearner(state)
    new_params = learner.update(metrics_dict)  # metrics: {'sharpe':..., 'dd':..., 'entropy':...}
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import logging

log = logging.getLogger(__name__)

@dataclass
class OnlineLearnerState:
    params: dict
    adapt_rate: float = 0.01        # base learning rate for parameter updates
    bounds: dict = field(default_factory=lambda: {})
    momentum: float = 0.9           # momentum for param smoothing
    expl_noise: float = 0.0         # optional exploration noise (small)
    ema_cache: dict = field(default_factory=dict)

class OnlineLearner:
    def __init__(self, state: OnlineLearnerState):
        self.state = state
        # ensure bounds exist for each param
        for k, v in self.state.params.items():
            if k not in self.state.bounds:
                # default bounds: (0.0, 10.0) for scalars; user should override
                self.state.bounds[k] = (0.0, 10.0)
        # init ema cache
        for k, v in self.state.params.items():
            self.state.ema_cache.setdefault(k, v)

    def _clip(self, k, v):
        lo, hi = self.state.bounds.get(k, (None, None))
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return v

    def update(self, metrics: dict) -> dict:
        """
        Update parameters using a simple reward-based rule:
        - metrics should contain numeric signals we care about (e.g. sharpe, dd, entropy)
        - we compute a tiny gradient proxy for each param using finite-diff style perturbations
        - apply EWMA/momentum and clip to bounds
        Returns updated params (and updates internal state).
        """
        params = self.state.params
        lr = float(self.state.adapt_rate)
        new_params = params.copy()
        # Baseline reward: prefer higher Sharpe, lower drawdown, lower entropy
        reward = (
            float(metrics.get("sharpe", 0.0))
            - float(metrics.get("maxdd", 0.0)) * 5.0
            - float(metrics.get("entropy", 0.0)) * 0.5
        )
        # simple per-param sensitivity heuristics (user should override in production)
        sens = {
            "tilt": 0.1,       # how strongly to change tilt based on reward
            "vol_target": 0.05,
            "adapt_rate": 0.001,
        }
        for k in list(params.keys()):
            base = params[k]
            s = sens.get(k, 0.01)
            # gradient sign: if reward positive, increase aggressive params, else decrease
            direction = 1.0 if reward > 0 else -1.0
            delta = lr * s * direction * abs(reward)
            # apply momentum via EMA
            ema_prev = self.state.ema_cache.get(k, base)
            ema = self.state.momentum * ema_prev + (1 - self.state.momentum) * (base + delta)
            # optional exploration noise (small)
            noise = np.random.default_rng().normal(scale=self.state.expl_noise) if self.state.expl_noise else 0.0
            updated = ema + noise
            updated = self._clip(k, updated)
            new_params[k] = updated
            self.state.ema_cache[k] = ema
            log.debug("OL update param=%s base=%.4f delta=%.6f ema=%.4f updated=%.4f", k, base, delta, ema, updated)
        # commit (and gently floor/ceiling)
        self.state.params = new_params
        return new_params
