import { useState, useEffect, useMemo } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

const ACTUAL = { light: '#0891b2', dark: '#22d3ee' }
const STEP_MS = 60

function ReplayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'predPoint')?.payload
  if (!row || row.actual == null) return null
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-gray-900 dark:text-gray-100">{fmtDateTime(label)}</p>
      <p className="tabular-nums text-gray-700 dark:text-gray-300">
        predicted {fmtMW(row.predPoint)} <span className="text-gray-400">({fmtMW(row.predLower)} … {fmtMW(row.predUpper)})</span>
      </p>
      <p className="tabular-nums" style={{ color: row.covered ? '#16a34a' : '#ef4444' }}>
        actual {fmtMW(row.actual)} {row.covered ? '✓ covered' : '✕ missed'}
      </p>
    </div>
  )
}

export default function BacktestReplay({ backtest, dark }) {
  const points = backtest.points
  const [revealed, setRevealed] = useState(points.length)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!playing) return
    if (revealed >= points.length) { setPlaying(false); return }
    const id = setTimeout(() => setRevealed(r => r + 1), STEP_MS)
    return () => clearTimeout(id)
  }, [playing, revealed, points.length])

  const chartData = useMemo(() => points.map((p, i) => {
    const shown = i < revealed
    return {
      t: p.timestamp,
      predLower: shown ? p.supply_gap.lower : null,
      predUpper: shown ? p.supply_gap.upper : null,
      predBand: shown ? p.supply_gap.upper - p.supply_gap.lower : null,
      predPoint: shown ? p.supply_gap.point : null,
      actual: shown ? p.supply_gap.actual : null,
      covered: p.covered,
    }
  }), [points, revealed])

  const coveredSoFar = useMemo(
    () => points.slice(0, revealed).filter(p => p.covered).length,
    [points, revealed]
  )

  const midnightTicks = chartData.filter(d => new Date(d.t).getUTCHours() % 12 === 0).map(d => d.t)
  const colors = dark ? SERIES.dark : SERIES.light
  const actualColor = dark ? ACTUAL.dark : ACTUAL.light
  const grid = dark ? '#27272a' : '#f3f4f6'
  const ink = dark ? '#a1a1aa' : '#6b7280'
  const maxAbs = Math.max(...points.map(p => Math.abs(p.supply_gap.upper)), ...points.map(p => Math.abs(p.supply_gap.actual)))
  const pct = revealed > 0 ? ((coveredSoFar / revealed) * 100).toFixed(1) : '—'

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-3 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">
            Backtest: {backtest.horizon_h}h-ahead predictions vs actuals
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Each point is the observed hour in UTC; the forecast was made {backtest.horizon_h} hours earlier.
          </p>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {coveredSoFar} / {revealed} hours covered so far
          <span className="ml-1 font-mono tabular-nums font-medium text-gray-700 dark:text-gray-300">({pct}%)</span>
          <span className="ml-1">— target 90%</span>
        </span>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={chartData} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10, fill: ink }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 10, fill: ink }} width={68}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<ReplayTooltip />} />
          <Area dataKey="predLower" stackId="band" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
          <Area dataKey="predBand" stackId="band" stroke="none" fill={colors.gap} fillOpacity={dark ? 0.2 : 0.14} activeDot={false} isAnimationActive={false} />
          <Line dataKey="predPoint" stroke={colors.gap} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} name="predicted" />
          <Line dataKey="actual" stroke={actualColor} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} connectNulls={false} name="actual" />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex items-center gap-3">
        <button
          onClick={() => { if (revealed >= points.length) setRevealed(0); setPlaying(p => !p) }}
          className="text-xs px-3 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          {playing ? '⏸ pause' : revealed >= points.length ? '▶ replay' : '▶ play'}
        </button>
        <input
          type="range" min="0" max={points.length} step="1" value={revealed}
          onChange={e => { setPlaying(false); setRevealed(parseInt(e.target.value, 10)) }}
          className="w-full accent-gray-500"
        />
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: colors.gap }} /> predicted (90% band)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: actualColor, borderTop: `1.5px dashed ${actualColor}` }} /> actual
        </span>
      </div>
    </div>
  )
}
