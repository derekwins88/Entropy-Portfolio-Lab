import express from "express";
import cors from "cors";
import { WebSocketServer } from "ws";

const PORT = process.env.PORT || 8787;
const app = express();
app.use(cors());

/** REST: minimal backtest listings + details */
const runs = [
  { id: "bt_001", strategy: "SMACross", sharpe: 0.9, mdd: -0.12, when: Date.now() - 86400000 },
  { id: "bt_002", strategy: "RSI/EMA MR", sharpe: 1.3, mdd: -0.09, when: Date.now() - 43200000 }
];

app.get("/api/backtests", (_req, res) => res.json(runs));
app.get("/api/backtests/:id/results", (req, res) => {
  const id = req.params.id;
  // tiny equity stub
  const now = Date.now();
  const equity = Array.from({ length: 50 }, (_, i) => ({
    t: now - (50 - i) * 3600_000,
    v: 100000 * (1 + 0.001 * i + 0.02 * Math.sin(i / 10))
  }));
  res.json({ id, equity, metrics: { Sharpe: 1.1, MaxDD: -0.1 } });
});
app.get("/api/proofs/:id", (req, res) => {
  res.json({ id: req.params.id, claim: "Sharpe >= 1.0", status: "green", sha: "deadbeef" });
});

const server = app.listen(PORT, () => console.log(`REST on :${PORT}`));

/** WS: periodic “capsules” */
const wss = new WebSocketServer({ server });
wss.on("connection", ws => {
  ws.send(JSON.stringify({ type: "hello", version: 1 }));
  const iv = setInterval(() => {
    const now = Date.now();
    const payload = {
      type: "capsule",
      version: 1,
      capsule_id: `cap_${now}`,
      timestamp: now,
      metrics: {
        entropy: Math.random(),
        risk: 0.5 + 0.1 * Math.sin(now / 5000),
        pl: (Math.random() - 0.5) * 100
      },
      annotations: { regime: Math.random() > 0.5 ? "P" : "NP" }
    };
    try { ws.send(JSON.stringify(payload)); } catch {}
  }, 1000);
  ws.on("close", () => clearInterval(iv));
});

process.on("SIGINT", () => { server.close(); process.exit(0); });
