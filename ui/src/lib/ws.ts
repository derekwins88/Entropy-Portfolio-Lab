type Capsule = {
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
