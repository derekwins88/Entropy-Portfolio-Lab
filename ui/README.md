# Entropy Portfolio UI (Phase 3)
React + Vite (TS), React Query, Zustand, Recharts. Demo mode default.

## Quick start
```bash
cd ui
cp .env.example .env   # edit if you have real API/WS
npm i
npm run dev
```

Demo mode
	•	VITE_DEMO=1 (default): uses /demo/*.json and fake WS ticks.
	•	Set VITE_DEMO=0 and configure VITE_API_URL / VITE_WS_URL to hit real services.

Scripts
	•	npm run dev — local dev
	•	npm run build && npm run preview — prod preview
	•	npm run test — Vitest unit
	•	npm run test:ui — Playwright e2e

Pages
	•	/live — Ticker/heatmap (placeholder), live metrics
	•	/backtests — list + filters (demo data)
	•	/analytics — equity chart demo
	•	/proofs — proof capsules viewer (stub)
	•	/settings — env toggles (stub)
