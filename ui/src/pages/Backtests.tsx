import { useQuery } from '@tanstack/react-query'
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
