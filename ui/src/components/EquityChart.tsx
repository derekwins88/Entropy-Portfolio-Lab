import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
type Row = { t:string, equity:number, dd?:number }
export default function EquityChart({rows}:{rows:Row[]}) {
  return (
    <div style={{height:260, background:'#0f1622', border:'1px solid #1c2740', borderRadius:8, padding:8}}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid stroke="#172036" />
          <XAxis dataKey="t" hide />
          <YAxis domain={['auto','auto']} />
          <Tooltip />
          <Line type="monotone" dataKey="equity" stroke="#4cc9f0" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
