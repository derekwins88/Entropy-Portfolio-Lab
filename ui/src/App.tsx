import { NavLink, Outlet } from 'react-router-dom'
export default function App() {
  return (
    <div style={{display:'grid', gridTemplateRows:'48px 1fr', height:'100vh', background:'#0b0f14', color:'#e6f1ff'}}>
      <header style={{display:'flex', alignItems:'center', gap:12, padding:'0 12px', borderBottom:'1px solid #1a2332'}}>
        <strong>Entropy Lab</strong>
        <nav style={{display:'flex', gap:10}}>
          <NavLink to="/live">Live</NavLink>
          <NavLink to="/backtests">Backtests</NavLink>
          <NavLink to="/analytics">Analytics</NavLink>
          <NavLink to="/proofs">Proofs</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
      </header>
      <main style={{padding:12, overflow:'auto'}}>
        <Outlet/>
      </main>
    </div>
  )
}
