import { z } from 'zod'
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
