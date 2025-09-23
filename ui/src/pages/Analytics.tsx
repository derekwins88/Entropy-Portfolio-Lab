import EquityChart from '../components/EquityChart'
const demo = Array.from({length:250}, (_,i)=>({ t:String(i), equity: 100000*Math.exp(0.0009*i + 0.05*Math.sin(i/15)) }))
export default function Analytics(){ return <EquityChart rows={demo}/> }
