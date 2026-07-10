import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

const DEFS = [
  { key: 'demand', label: 'Demand', title: 'Demand forecast', height: 224 },
  { key: 'solar',  label: 'Solar', title: 'Solar supply', height: 104 },
  { key: 'wind',   label: 'Wind', title: 'Wind supply', height: 104 },
]

function SmallTooltip({ active, payload, label, name }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'point')?.payload
  if (!row) return null
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-gray-900 dark:text-gray-100">{fmtDateTime(label)}</p>
      <p className="tabular-nums text-gray-700 dark:text-gray-300">
        {name} {fmtMW(row.point)} <span className="text-gray-400">({fmtMW(row.lower)} … {fmtMW(row.upper)})</span>
      </p>
    </div>
  )
}

function Chart({ forecasts, seriesKey, label, title, color, dark, height = 160, compact = false }) {
  const data = forecasts.map(f => ({
    t: f.timestamp,
    point: f[seriesKey].point,
    lower: f[seriesKey].lower,
    upper: f[seriesKey].upper,
    band: f[seriesKey].upper - f[seriesKey].lower,
  }))
  const midnightTicks = data.filter(d => new Date(d.t).getUTCHours() % 12 === 0).map(d => d.t)
  const maxAbs = Math.max(...data.map(d => Math.abs(d.upper)), ...data.map(d => Math.abs(d.lower)))
  const grid = dark ? '#27272a' : '#f3f4f6'
  const ink = dark ? '#a1a1aa' : '#6b7280'

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">{title ?? label}</h2>
          {compact && <p className="text-xs text-gray-500 dark:text-gray-400">support signal</p>}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} syncId="fc" margin={{ top: 12, right: 56, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10, fill: ink }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 10, fill: ink }} width={68}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<SmallTooltip name={label} />} />
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
          <Area dataKey="band" stackId="band" stroke="none" fill={color} fillOpacity={dark ? 0.25 : 0.16} activeDot={false} isAnimationActive={false} />
          <Line dataKey="point" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 6} y={y + 3} fontSize={11} fontWeight={600} fill={color}>{label}</text> : null} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function ForecastChart({ forecasts, dark }) {
  const colors = dark ? SERIES.dark : SERIES.light
  return (
    <div className="grid gap-3 lg:grid-cols-[1.6fr_1fr]">
      <Chart
        forecasts={forecasts}
        seriesKey="demand"
        label="Demand"
        title="Demand forecast"
        color={colors.demand}
        dark={dark}
        height={224}
      />
      <div className="grid gap-3">
        {DEFS.filter(s => s.key !== 'demand').map(s => (
          <Chart
            key={s.key}
            forecasts={forecasts}
            seriesKey={s.key}
            label={s.label}
            title={s.title}
            color={colors[s.key]}
            dark={dark}
            height={104}
            compact
          />
        ))}
      </div>
    </div>
  )
}
