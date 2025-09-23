import TickerPanel from '../components/TickerPanel'
import Heatmap from '../components/Heatmap'
export default function Live(){
  return (
    <div style={{display:'grid', gap:12}}>
      <TickerPanel/>
      <Heatmap/>
    </div>
  )
}
