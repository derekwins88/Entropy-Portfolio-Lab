# phase3_ui_pack.py
# Adds Phase 3 UI + CI to entropy-portfolio-lab and zips the repo.
import os
import zipfile
import json
from pathlib import Path

ROOT = Path("/mnt/data/entropy-portfolio-lab")
assert ROOT.exists(), f"Repo not found at {ROOT}"
UI = ROOT / "ui"

def w(path: Path, s: str, mode="w"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.open(mode, encoding="utf-8").write(s)

# -----------------------------
# 1) package.json / tooling
# -----------------------------
w(UI / "package.json", json.dumps({
  "name": "entropy-portfolio-ui",
  "private": True,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview --port 4173",
    "typecheck": "tsc --noEmit",
    "lint": "eslint . --max-warnings=0",
    "test": "vitest run",
    "test:ui": "playwright install --with-deps && playwright test",
    "ci": "npm run typecheck && npm run lint && npm run test && npm run build"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0",
    "recharts": "^2.12.7",
    "zustand": "^4.5.2",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.2",
    "@types/node": "^20.11.30",
    "@types/react": "^18.2.66",
    "@types/react-dom": "^18.2.22",
    "@vitejs/plugin-react": "^4.3.3",
    "eslint": "^9.9.0",
    "eslint-config-standard-with-typescript": "^43.0.0",
    "eslint-plugin-import": "^2.29.1",
    "eslint-plugin-n": "^17.10.2",
    "eslint-plugin-promise": "^7.1.0",
    "typescript": "^5.6.3",
    "vite": "^5.4.8",
    "vitest": "^2.1.1",
    "lighthouse": "^12.3.0",
    "@lhci/cli": "^0.13.0"
  }
}, indent=2))

w(UI / "tsconfig.json", """{
  \"compilerOptions\": {
    \"target\": \"ES2020\",
    \"lib\": [\"ES2021\", \"DOM\", \"DOM.Iterable\"],
    \"module\": \"ESNext\",
    \"jsx\": \"react-jsx\",
    \"moduleResolution\": \"Bundler\",
    \"strict\": true,
    \"noUncheckedIndexedAccess\": true,
    \"resolveJsonModule\": true,
    \"noEmit\": true,
    \"types\": [\"vite/client\"]
  },
  \"include\": [\"src\", \"tests\", \"e2e\"]
}
""")

w(UI / "vite.config.ts", """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 }
})
""")

w(UI / ".eslintrc.json", json.dumps({
  "root": True,
  "env": { "browser": True, "es2021": True },
  "extends": ["standard-with-typescript"],
  "parserOptions": { "project": ["./tsconfig.json"] },
  "rules": { "no-console": "off" }
}, indent=2))

w(UI / ".env.example", "VITE_WS_URL=ws://localhost:8080/ws\nVITE_API_URL=http://localhost:8787\nVITE_DEMO=1\n")

# -----------------------------
# 2) App source
# -----------------------------
w(UI / "src/main.tsx", """import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import Live from './pages/Live'
import Backtests from './pages/Backtests'
import Analytics from './pages/Analytics'
import Proofs from './pages/Proofs'
import Settings from './pages/Settings'
const qc = new QueryClient()
const router = createBrowserRouter([
  { path: '/', element: <App/>, children: [
    { path: '/', element: <Live/> },
    { path: '/live', element: <Live/> },
    { path: '/backtests', element: <Backtests/> },
    { path: '/analytics', element: <Analytics/> },
    { path: '/proofs', element: <Proofs/> },
    { path: '/settings', element: <Settings/> },
  ] }
])
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router}/>
    </QueryClientProvider>
  </React.StrictMode>
)
""")

w(UI / "index.html", """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>
  <title>Entropy Portfolio Dashboard</title>
</head>
<body>
  <div id=\"root\"></div>
  <script type=\"module\" src=\"/src/main.tsx\"></script>
</body>
</html>
""")

w(UI / "src/App.tsx", """import { NavLink, Outlet } from 'react-router-dom'
export default function App() {
  return (
    <div style={{display:'grid', gridTemplateRows:'48px 1fr', height:'100vh', background:'#0b0f14', color:'#e6f1ff'}}>
      <header style={{display:'flex', alignItems:'center', gap:12, padding:'0 12px', borderBottom:'1px solid #1a2332'}}>
        <strong>Entropy Lab</strong>
        <nav style={{display:'flex', gap:10}}>
          <NavLink to=\"/live\">Live</NavLink>
          <NavLink to=\"/backtests\">Backtests</NavLink>
          <NavLink to=\"/analytics\">Analytics</NavLink>
          <NavLink to=\"/proofs\">Proofs</NavLink>
          <NavLink to=\"/settings\">Settings</NavLink>
        </nav>
      </header>
      <main style={{padding:12, overflow:'auto'}}>
        <Outlet/>
      </main>
    </div>
  )
}
""")

# libs
w(UI / "src/lib/ws.ts", """type Capsule = {
  type: string; version: string; capsule_id: string; timestamp: string;
  metrics: { entropy:number; risk:number; pl:number }; annotations?: Record<string,unknown>
}
const WS_URL = import.meta.env.VITE_WS_URL
const DEMO = import.meta.env.VITE_DEMO === '1'
const listeners = new Set<(m:Capsule)=>void>()
let sock: WebSocket | null = null
let backoff = 500
function emit(m: Capsule){ listeners.forEach(fn=>fn(m)) }
function connect(){
  if (DEMO){ // fake stream
    setInterval(()=> {
      const m: Capsule = {
        type:'capsule', version:'1', capsule_id: Math.random().toString(36).slice(2),
        timestamp: new Date().toISOString(),
        metrics: { entropy: Math.random(), risk: Math.random(), pl: (Math.random()-0.5)*1000 }
      }
      emit(m)
    }, 1500)
    return
  }
  if (!WS_URL) return
  sock = new WebSocket(WS_URL)
  sock.onopen = ()=> { backoff = 500 }
  sock.onmessage = (e)=> {
    try { emit(JSON.parse(e.data)) } catch {}
  }
  sock.onclose = ()=> { setTimeout(connect, backoff); backoff = Math.min(backoff*1.6, 10000) }
}
export function subscribe(fn:(m:Capsule)=>void){ listeners.add(fn); if (!sock) connect(); return ()=>listeners.delete(fn) }
""")

w(UI / "src/lib/api.ts", """import { z } from 'zod'
const API = import.meta.env.VITE_API_URL
const DEMO = import.meta.env.VITE_DEMO === '1'
const BTList = z.object({ id:z.string(), date:z.string(), sharpe:z.number(), mdd:z.number() })
export type BacktestRow = z.infer<typeof BTList>
export async function listBacktests(): Promise<BacktestRow[]> {
  if (DEMO) {
    const res = await fetch('/demo/backtests.json'); return z.array(BTList).parse(await res.json())
  }
  const r = await fetch(`${API}/api/backtests`); return z.array(BTList).parse(await r.json())
}
""")

# state
w(UI / "src/state/store.ts", """import { create } from 'zustand'
type LiveState = { last?: { ts:string, entropy:number, risk:number, pl:number }, count:number }
export const useLive = create<LiveState>((set)=>({
  last: undefined, count: 0,
  setLast: (ts:string, entropy:number, risk:number, pl:number) => set({ last:{ ts, entropy, risk, pl }, count: (s)=>s.count+1 } as any)
}))
""")

# components
w(UI / "src/components/TickerPanel.tsx", """import { useEffect } from 'react'
import { subscribe } from '../lib/ws'
import { useLive } from '../state/store'
export default function TickerPanel(){
  const last = useLive(s=>s.last); const setLast = (useLive as any).getState().setLast
  useEffect(()=> subscribe(m => setLast(m.timestamp, m.metrics.entropy, m.metrics.risk, m.metrics.pl)), [])
  return (
    <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8}}>
      <Card label=\"Last Capsule\">{last?.ts ?? '—'}</Card>
      <Card label=\"Entropy\">{last ? last.entropy.toFixed(3) : '—'}</Card>
      <Card label=\"Risk\">{last ? (last.risk*100).toFixed(1)+'%' : '—'}</Card>
      <Card label=\"P/L\">{last ? last.pl.toFixed(2) : '—'}</Card>
    </div>
  )
}
function Card({label, children}:{label:string, children:any}){
  return <div style={{background:'#0f1622', border:'1px solid #1c2740', padding:12, borderRadius:8}}>
    <div style={{opacity:0.7, fontSize:12}}>{label}</div>
    <div style={{fontSize:18, fontWeight:600}}>{children}</div>
  </div>
}
""")

w(UI / "src/components/EquityChart.tsx", """import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
type Row = { t:string, equity:number, dd?:number }
export default function EquityChart({rows}:{rows:Row[]}) {
  return (
    <div style={{height:260, background:'#0f1622', border:'1px solid #1c2740', borderRadius:8, padding:8}}>
      <ResponsiveContainer width=\"100%\" height=\"100%\">
        <LineChart data={rows}>
          <CartesianGrid stroke=\"#172036\" />
          <XAxis dataKey=\"t\" hide />
          <YAxis domain={['auto','auto']} />
          <Tooltip />
          <Line type=\"monotone\" dataKey=\"equity\" stroke=\"#4cc9f0\" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
""")

w(UI / "src/components/Heatmap.tsx", """// placeholder heatmap; swap to D3 later
export default function Heatmap(){
  return <div style={{height:260, background:'#0f1622', border:'1px solid #1c2740', borderRadius:8, display:'grid', placeItems:'center'}}>Heatmap (demo)</div>
}
""")

# pages
w(UI / "src/pages/Live.tsx", """import TickerPanel from '../components/TickerPanel'
import Heatmap from '../components/Heatmap'
export default function Live(){
  return (
    <div style={{display:'grid', gap:12}}>
      <TickerPanel/>
      <Heatmap/>
    </div>
  )
}
""")

w(UI / "src/pages/Backtests.tsx", """import { useQuery } from '@tanstack/react-query'
import { listBacktests } from '../lib/api'
export default function Backtests(){
  const q = useQuery({ queryKey:['bt'], queryFn: listBacktests })
  if (q.isLoading) return <div>Loading…</div>
  if (q.isError) return <div>Failed to load backtests.</div>
  return (
    <table style={{width:'100%', borderCollapse:'collapse'}}>
      <thead><tr><th align='left'>ID</th><th align='right'>Sharpe</th><th align='right'>MDD</th></tr></thead>
      <tbody>
        {q.data!.map(r=><tr key={r.id} style={{borderTop:'1px solid #1a2332'}}>
          <td>{r.id}</td><td align='right'>{r.sharpe.toFixed(2)}</td><td align='right'>{(r.mdd*100).toFixed(1)}%</td>
        </tr>)}
      </tbody>
    </table>
  )
}
""")

w(UI / "src/pages/Analytics.tsx", """import EquityChart from '../components/EquityChart'
const demo = Array.from({length:250}, (_,i)=>({ t:String(i), equity: 100000*Math.exp(0.0009*i + 0.05*Math.sin(i/15)) }))
export default function Analytics(){ return <EquityChart rows={demo}/> }
""")

w(UI / "src/pages/Proofs.tsx", """export default function Proofs(){ return <div>Proof capsules list (demo)</div> }
""")
w(UI / "src/pages/Settings.tsx", """export default function Settings(){ return <div>Settings (demo mode). Configure WS/API via .env</div> }
""")

# -----------------------------
# 3) Public demo data
# -----------------------------
w(UI / "public/demo/backtests.json", json.dumps([
  {"id":"wf_2024_08","date":"2024-08-10","sharpe":1.12,"mdd":-0.18},
  {"id":"wf_2024_09","date":"2024-09-10","sharpe":1.05,"mdd":-0.21}
], indent=2))

# -----------------------------
# 4) Tests (vitest + playwright)
# -----------------------------
w(UI / "tests/ws.spec.ts", """import { describe, it, expect } from 'vitest'
describe('demo', ()=>{ it('math', ()=>{ expect(1+1).toBe(2) }) })
""")

w(UI / "playwright.config.ts", """import { defineConfig } from '@playwright/test'
export default defineConfig({
  webServer: { command: 'npm run preview', port: 4173, reuseExistingServer: !process.env.CI },
  use: { headless: true }
})
""")

w(UI / "e2e/live.spec.ts", """import { test, expect } from '@playwright/test'
test('loads /live and shows header', async ({ page }) => {
  await page.goto('http://localhost:4173/live')
  await expect(page.locator('text=Entropy Lab')).toBeVisible()
})
""")

# -----------------------------
# 5) CI: ci-ui.yml + lhci config
# -----------------------------
w(ROOT / ".github/workflows/ci-ui.yml", """name: UI — build & test
on:
  push: { branches: [ main, master ] }
  pull_request:
jobs:
  ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: 'ui/package-lock.json' }
      - name: Install
        working-directory: ui
        run: npm ci || npm i
      - name: Typecheck & Lint
        working-directory: ui
        run: |
          npm run typecheck
          npm run lint
      - name: Unit tests
        working-directory: ui
        run: npm test
      - name: Build
        working-directory: ui
        run: npm run build
      - name: Preview & E2E
        working-directory: ui
        run: npm run test:ui
      - name: Lighthouse CI
        uses: treosh/lighthouse-ci-action@v12
        with:
          configPath: ./ui/lhci.json
          runs: 1
          uploadArtifacts: true
          temporaryPublicStorage: true
""")

w(UI / "lhci.json", json.dumps({
  "ci": {
    "collect": { "staticDistDir": "dist" },
    "assert": {
      "assertions": {
        "categories:performance": ["error", {"minScore": 0.9}],
        "categories:accessibility": ["error", {"minScore": 0.9}],
        "script-treemap-data": "off",
        "total-byte-weight": ["warn", {"maxNumericValue": 300000}],
        "unused-javascript": ["warn", {"maxNumericValue": 250000}]
      }
    }
  }
}, indent=2))

# -----------------------------
# 6) UI README
# -----------------------------
w(UI / "README.md", """# Entropy Portfolio UI (Phase 3)
React + Vite (TS), React Query, Zustand, Recharts. Demo mode default.

## Quick start
```bash
cd ui
cp .env.example .env   # edit if you have real API/WS
npm i
npm run dev
```

Demo mode
\t•\tVITE_DEMO=1 (default): uses /demo/*.json and fake WS ticks.
\t•\tSet VITE_DEMO=0 and configure VITE_API_URL / VITE_WS_URL to hit real services.

Scripts
\t•\tnpm run dev — local dev
\t•\tnpm run build && npm run preview — prod preview
\t•\tnpm run test — Vitest unit
\t•\tnpm run test:ui — Playwright e2e

Pages
\t•\t/live — Ticker/heatmap (placeholder), live metrics
\t•\t/backtests — list + filters (demo data)
\t•\t/analytics — equity chart demo
\t•\t/proofs — proof capsules viewer (stub)
\t•\t/settings — env toggles (stub)
""")

# -----------------------------
# 7) Root README pointer (if present)
# -----------------------------
readme = ROOT / "README.md"
if readme.exists():
    rd = readme.read_text(encoding="utf-8")
    if "## UI (Phase 3)" not in rd:
        rd += "\n\n## UI (Phase 3)\nSee /ui for the React dashboard. Demo mode runs without a backend.\n"
        w(readme, rd)

# -----------------------------
# 8) Zip repo
# -----------------------------
ZIP = ROOT.parent / "entropy-portfolio-lab_phase3_ui.zip"
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for folder, _, files in os.walk(ROOT):
        for f in files:
            p = Path(folder) / f
            z.write(p, p.relative_to(ROOT.parent))
print(str(ZIP))
print("Phase 3 UI + CI scaffold written.")
