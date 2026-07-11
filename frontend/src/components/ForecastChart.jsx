import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

function DemandTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'point')?.payload
  if (!row) return null
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-xs shadow-lg shadow-zinc-950/10 dark:shadow-black/40">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">{fmtDateTime(label)}</p>
      <p className="mt-0.5 font-mono tabular-nums text-zinc-600 dark:text-zinc-400">
        {fmtMW(row.point)} <span className="text-zinc-400 dark:text-zinc-600">({fmtMW(row.lower)} to {fmtMW(row.upper)})</span>
      </p>
    </div>
  )
}

export default function ForecastChart({ forecasts, dark }) {
  const color = (dark ? SERIES.dark : SERIES.light).demand
  const data = forecasts.map(f => ({
    t: f.timestamp,
    point: f.demand.point,
    lower: f.demand.lower,
    upper: f.demand.upper,
    band: f.demand.upper - f.demand.lower,
  }))
  const midnightTicks = data.filter(d => new Date(d.t).getUTCHours() % 6 === 0).map(d => d.t)
  const maxAbs = Math.max(...data.map(d => Math.abs(d.upper)), ...data.map(d => Math.abs(d.lower)))
  const grid = dark ? '#27272a' : '#e4e4e7'
  const ink = dark ? '#71717a' : '#a1a1aa'

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 48, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
               tick={{ fontSize: 11, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 11, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} width={60}
               axisLine={false} tickLine={false} domain={['auto', 'auto']} />
        <Tooltip content={<DemandTooltip />} cursor={{ stroke: ink, strokeDasharray: '3 3' }} />
        <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
        <Area dataKey="band" stackId="band" stroke="none" fill={color} fillOpacity={dark ? 0.18 : 0.12} activeDot={false} isAnimationActive={false} />
        <Line dataKey="point" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false}
              label={({ index, x, y }) => index === data.length - 1
                ? <text x={x + 8} y={y + 3} fontSize={11} fontWeight={600} fill={color} fontFamily='"JetBrains Mono", monospace'>demand</text> : null} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
