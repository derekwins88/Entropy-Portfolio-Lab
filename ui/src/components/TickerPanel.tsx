import { useEffect } from 'react'
import { subscribe } from '../lib/ws'
import { useLive } from '../state/store'
export default function TickerPanel(){
  const last = useLive(s=>s.last); const setLast = (useLive as any).getState().setLast
  useEffect(()=> subscribe(m => setLast(m.timestamp, m.metrics.entropy, m.metrics.risk, m.metrics.pl)), [])
  return (
    <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8}}>
      <Card label="Last Capsule">{last?.ts ?? '—'}</Card>
      <Card label="Entropy">{last ? last.entropy.toFixed(3) : '—'}</Card>
      <Card label="Risk">{last ? (last.risk*100).toFixed(1)+'%' : '—'}</Card>
      <Card label="P/L">{last ? last.pl.toFixed(2) : '—'}</Card>
    </div>
  )
}
function Card({label, children}:{label:string, children:any}){
  return <div style={{background:'#0f1622', border:'1px solid #1c2740', padding:12, borderRadius:8}}>
    <div style={{opacity:0.7, fontSize:12}}>{label}</div>
    <div style={{fontSize:18, fontWeight:600}}>{children}</div>
  </div>
}
