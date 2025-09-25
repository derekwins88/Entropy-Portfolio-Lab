"""
Watchdog monitors metrics and triggers actions.
- Supports simple threshold alerts, and periodic health checks.
- For now, it logs events and optionally posts to a webhook (if provided).
"""
from __future__ import annotations
import logging
import time
import json
import requests  # lightweight; user may prefer aiohttp in production
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

@dataclass
class WatchdogConfig:
    max_dd: float = 0.30                # 30% drawdown triggers alert
    min_sharpe: float = -1.0            # too negative triggers
    max_turnover: float = 2.0           # monthly turnover threshold
    webhook: str | None = None          # optional webhook URL
    cooldown_secs: int = 3600           # suppress repeat alerts this long
    enabled: bool = True

@dataclass
class WatchdogState:
    last_alert: dict = field(default_factory=dict)

class Watchdog:
    def __init__(self, cfg: WatchdogConfig, state: WatchdogState | None = None):
        self.cfg = cfg
        self.state = state or WatchdogState()

    def _post(self, payload: dict):
        if not self.cfg.webhook:
            log.info("[watchdog] webhook not configured; skipping post. payload=%s", payload)
            return
        try:
            headers = {"Content-Type": "application/json"}
            r = requests.post(self.cfg.webhook, data=json.dumps(payload), headers=headers, timeout=5)
            r.raise_for_status()
            log.info("[watchdog] posted alert successfully")
        except Exception as e:
            log.exception("watchdog post failed: %s", e)

    def check(self, metrics: dict, context: dict | None = None):
        """
        Check metrics and maybe alert.
        metrics should include keys like 'MaxDD', 'Sharpe', 'Turnover'
        """
        if not self.cfg.enabled:
            return None
        now = int(time.time())
        alerts = []
        # drawdown
        dd = float(metrics.get("MaxDD", 0.0))
        if dd < 0 and abs(dd) >= self.cfg.max_dd:
            alerts.append(("max_dd", f"Max drawdown {dd:.2%} exceeds {self.cfg.max_dd:.2%}"))
        # sharpe
        sharpe = float(metrics.get("Sharpe", 0.0))
        if sharpe <= self.cfg.min_sharpe:
            alerts.append(("sharpe", f"Sharpe {sharpe:.2f} <= {self.cfg.min_sharpe:.2f}"))
        # turnover
        turn = float(metrics.get("Turnover", 0.0))
        if turn >= self.cfg.max_turnover:
            alerts.append(("turnover", f"Turnover {turn:.2f} >= {self.cfg.max_turnover:.2f}"))
        out = []
        for k, msg in alerts:
            last = self.state.last_alert.get(k, 0)
            if now - last >= self.cfg.cooldown_secs:
                payload = {"type": k, "message": msg, "metrics": metrics, "context": context or {}}
                log.warning("[watchdog] alert: %s", msg)
                self._post(payload)
                self.state.last_alert[k] = now
                out.append(payload)
            else:
                log.info("[watchdog] suppressed repeated alert '%s' (cooldown)", k)
        return out
