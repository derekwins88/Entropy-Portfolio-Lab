import { create } from 'zustand'
type LiveState = { last?: { ts:string, entropy:number, risk:number, pl:number }, count:number }
export const useLive = create<LiveState>((set)=>({
  last: undefined, count: 0,
  setLast: (ts:string, entropy:number, risk:number, pl:number) => set({ last:{ ts, entropy, risk, pl }, count: (s)=>s.count+1 } as any)
}))
