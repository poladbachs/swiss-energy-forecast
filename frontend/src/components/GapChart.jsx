import { useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts'
import { SERIES, STATUS, STATUS_META, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

function GapTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'point')?.payload
  if (!row) return null
  const meta = STATUS_META[row.status]
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-gray-900 dark:text-gray-100">{fmtDateTime(label)}</p>
      <p className="mt-1 tabular-nums text-gray-700 dark:text-gray-300">
        gap {fmtMW(row.point)} <span className="text-gray-400">({fmtMW(row.lower)} … {fmtMW(row.upper)})</span>
      </p>
      {row.baseGap != null && (
        <p className="tabular-nums text-gray-500 dark:text-gray-400">baseline {fmtMW(row.baseGap)}</p>
      )}
      {row.residual != null && (
        <p className="tabular-nums text-violet-600 dark:text-violet-400">
          after nuclear + hydro {fmtMW(row.residual)}
        </p>
      )}
      <p className="mt-1 font-medium" style={{ color: STATUS[row.status] }}>
        {meta.glyph} {meta.label}
      </p>
    </div>
  )
}

// Supply gap (demand minus renewables) with the conformal band and a zero
// line. When the sliders are off 1.0x, a dashed baseline ghost appears.
export default function GapChart({ forecasts, baseline, dark, onHover }) {
  const colors = dark ? SERIES.dark : SERIES.light
  const hasClean = forecasts[0]?.clean_mw != null
  const [showResidual, setShowResidual] = useState(false)
  const showBaseline = baseline && baseline.length === forecasts.length &&
    forecasts.some((f, i) => Math.abs(f.supply_gap.point - baseline[i].supply_gap.point) > 1)

  const data = forecasts.map((f, i) => ({
    t: f.timestamp,
    point: f.supply_gap.point,
    lower: f.supply_gap.lower,
    upper: f.supply_gap.upper,
    band: f.supply_gap.upper - f.supply_gap.lower,
    status: f.coverage_status,
    baseGap: showBaseline ? baseline[i].supply_gap.point : null,
    residual: hasClean && showResidual ? f.supply_gap.point - f.clean_mw : null,
  }))
  const midnightTicks = data.filter(d => new Date(d.t).getUTCHours() % 6 === 0).map(d => d.t)
  const maxAbs = Math.max(...data.map(d => Math.abs(d.upper)), ...data.map(d => Math.abs(d.lower)))
  const grid = dark ? '#27272a' : '#f3f4f6'
  const ink = dark ? '#a1a1aa' : '#6b7280'

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">Supply gap: demand minus renewables</h2>
        <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
          {hasClean && (
            <label className="inline-flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" checked={showResidual}
                     onChange={e => setShowResidual(e.target.checked)}
                     className="accent-violet-600" />
              after nuclear + hydro
            </label>
          )}
          <span>below zero = surplus, 90% band</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart
          data={data}
          syncId="fc"
          margin={{ top: 12, right: 70, left: 0, bottom: 0 }}
          onMouseMove={s => onHover?.(s?.activeTooltipIndex ?? null)}
          onMouseLeave={() => onHover?.(null)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 11, fill: ink }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 11, fill: ink }} width={68}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<GapTooltip />} />
          <ReferenceLine y={0} stroke={ink} strokeWidth={1}
                         label={{ value: 'surplus ↓', position: 'insideBottomRight', fontSize: 10, fill: ink }} />
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
          <Area dataKey="band" stackId="band" stroke="none" fill={colors.gap} fillOpacity={dark ? 0.25 : 0.16} activeDot={false} isAnimationActive={false} />
          {showBaseline && (
            <Line dataKey="baseGap" stroke={ink} strokeWidth={1.5} strokeDasharray="5 4" dot={false}
                  isAnimationActive={false} name="baseline 1.0×"
                  label={({ index, x, y }) => index === data.length - 1
                    ? <text x={x + 6} y={y + 3} fontSize={10} fill={ink}>1.0×</text> : null} />
          )}
          {showResidual && (
            <Line dataKey="residual" stroke={dark ? '#a78bfa' : '#7c3aed'} strokeWidth={1.5}
                  strokeDasharray="3 3" dot={false} isAnimationActive={false}
                  label={({ index, x, y }) => index === data.length - 1
                    ? <text x={x + 6} y={y + 3} fontSize={10} fill={dark ? '#a78bfa' : '#7c3aed'}>residual</text> : null} />
          )}
          <Line dataKey="point" stroke={colors.gap} strokeWidth={2} dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 6} y={y + 3} fontSize={11} fontWeight={600} fill={colors.gap}>gap</text> : null} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
