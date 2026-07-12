import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { series, chartTheme, MONO, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

function DemandTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'point')?.payload
  if (!row) return null
  return (
    <div className="rounded-xl border px-3 py-2 text-xs num shadow-[var(--shadow)]"
         style={{ background: 'var(--panel)', borderColor: 'var(--border-strong)' }}>
      <p className="font-sans font-medium" style={{ color: 'var(--text)' }}>{fmtDateTime(label)}</p>
      <p className="mt-1" style={{ color: 'var(--demand)' }}>
        {fmtMW(row.point)}
        <span style={{ color: 'var(--text-3)' }}> ({fmtMW(row.lower)}&ndash;{fmtMW(row.upper)})</span>
      </p>
    </div>
  )
}

export default function ForecastChart({ forecasts, dark }) {
  const c = series(dark)
  const t = chartTheme(dark)
  const data = forecasts.map(f => ({
    t: f.timestamp, point: f.demand.point, lower: f.demand.lower,
    upper: f.demand.upper, band: f.demand.upper - f.demand.lower,
  }))
  const ticks = data.filter(d => new Date(d.t).getUTCHours() % 6 === 0).map(d => d.t)
  const maxAbs = Math.max(...data.map(d => Math.abs(d.upper)))

  return (
    <div style={{ '--demand': c.demand }}>
      <ResponsiveContainer width="100%" height={248}>
        <ComposedChart data={data} margin={{ top: 10, right: 58, left: -6, bottom: 0 }}>
          <defs>
            <linearGradient id="demandFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.demand} stopOpacity={dark ? 0.2 : 0.14} />
              <stop offset="100%" stopColor={c.demand} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke={t.grid} vertical={false} />
          <XAxis dataKey="t" ticks={ticks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 11, fill: t.tick, fontFamily: MONO }} axisLine={false} tickLine={false} dy={6} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 11, fill: t.tick, fontFamily: MONO }} width={40}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<DemandTooltip />} cursor={{ stroke: t.ink, strokeWidth: 1, strokeDasharray: '3 4' }} />
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area dataKey="band" stackId="band" stroke="none" fill={c.demand} fillOpacity={dark ? 0.1 : 0.08} isAnimationActive={false} />
          <Area dataKey="point" stroke="none" fill="url(#demandFill)" isAnimationActive={false} />
          <Line dataKey="point" stroke={c.demand} strokeWidth={2.25} dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 8} y={y + 3} fontSize={11} fontWeight={600} fill={c.demand} fontFamily={MONO}>demand</text> : null} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
