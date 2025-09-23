# System Diagram — Entropy Portfolio Lab

Below are Mermaid diagrams you can view on GitHub (yes, it renders now).  
They show the whole stack and the lifecycle of a typical backtest → proof → UI pipeline.

## 1) Architecture (components & data flow)

```mermaid
%%{init: { "theme": "dark", "logLevel": "fatal" }}%%
flowchart TD

UI["UI (Vite/React)"]:::svc
Mock["Mock API/WS (Express+WS)"]:::svc
BT["Backtest Engine (Python)"]:::core
Attr["Attribution (by_symbol / regime)"]:::core
Proofs["Proofs (grid cert)"]:::proof
NT8["NinjaTrader 8 Strategy + Sizer"]:::ext
Store["Artifacts (CSV, PNG, cert)"]:::store

UI --- Mock
Mock --> BT
BT --> Attr
BT --> Store
Attr --> UI
Proofs --> Store
UI --> NT8

classDef svc  fill:#0ea5e9,stroke:#0369a1,color:#fff,rx:4,ry:4
classDef core fill:#22c55e,stroke:#15803d,color:#081c15,rx:4,ry:4
classDef proof fill:#f59e0b,stroke:#92400e,color:#111827,rx:4,ry:4
classDef ext  fill:#d946ef,stroke:#86198f,color:#fff,rx:4,ry:4
classDef store fill:#94a3b8,stroke:#334155,color:#0f172a,rx:4,ry:4

class UI,Mock svc
class BT,Attr core
class Proofs proof
class NT8 ext
class Store store
```

## 2) Lifecycle (single backtest → proof → UI)

```mermaid
sequenceDiagram
  participant Dev as Dev/CI
  participant CLI as backtest.cli
  participant Eng as Engine/Portfolio
  participant Mx as Metrics/Attribution
  participant Pr as Proof Generator
  participant L4 as Lean4
  participant API as REST API (mock)
  participant UI as React UI

  Dev->>CLI: run --strategy ... [grid|walk]
  CLI->>Eng: load CSV/bench, brackets, sizing
  Eng-->>CLI: equity.csv, trades.csv
  CLI->>Mx: summarize(equity, fills, trades, bench)
  Mx-->>CLI: stats.json (Sharpe, DD, Alpha/Beta/IR,…)
  CLI->>Pr: gen_grid_cert.py (claims from stats)
  Pr->>L4: lake build / sorry-check
  L4-->>Pr: proof status + artifacts
  CLI->>API: POST results (equity, metrics)  (mocked)
  API-->>UI: GET /backtests/:id/results
  API-->>UI: WS capsules (entropy/risk/notes)
  UI-->>Dev: dashboards render + proof status
```

Notes
- OHLC-aware brackets: stops/targets evaluate intrabar High/Low if present, else Close.
- Sizing: units, notional, or ATR-risk (risk_R × ATR, risk_pct of equity).
- Proof capsules: JSON claims + Lean sources + SHA256; CI fails if claims aren’t met.

---

### Legend
- *Engine* = event loop + broker + bracket manager (+ warmup)  
- *Portfolio* = runs multiple assets, combines curves (equal-weight for now)  
- *Metrics* = full suite (incl. Alpha/Beta/IR vs bench)  
- *Optimize/Walk-Forward* = param search + OOS validation, optional Monte Carlo  
- *Proofs* = claim generator → Lean build → artifacts (capsule)  
- *UI* = React/Vite, hits REST for backtest results, WS for live capsules  
- *CI* = Python tests/schema, UI checks/build, proof build (manual/triggered), nightly backtest matrix

### Where to add things quickly
- New strategy research ➜ `backtest/strategies/*`
- New metric ➜ `backtest/metrics/*` and wire into summarize()
- New UI panel ➜ `ui/src/components/*` then route in `/analytics`
- New proof claim ➜ `proofs/gen_grid_cert.py` + `proofs/templates/*`
- New nightly run ➜ `.github/workflows/nightly.yml` (matrix)

---

You drop these files in, and anyone skimming your repo can see the head and the spine at once. It also makes your third-party review read like “uh-huh yep” instead of “what is this mysterious folder called proofs.”

> Rendered images: see `docs/assets/diagram_0.{png,svg}`, `diagram_1.{png,svg}` (CI-generated).
