import { useState, useEffect, useMemo } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

const STEP_MS = 55

function ReplayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'predPoint')?.payload
  if (!row || row.actual == null) return null
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-xs shadow-lg shadow-zinc-950/10 dark:shadow-black/40">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">{fmtDateTime(label)}</p>
      <p className="mt-0.5 font-mono tabular-nums text-zinc-600 dark:text-zinc-400">
        predicted {fmtMW(row.predPoint)} <span className="text-zinc-400 dark:text-zinc-600">({fmtMW(row.predLower)} to {fmtMW(row.predUpper)})</span>
      </p>
      <p className="font-mono tabular-nums" style={{ color: row.covered ? '#0d9488' : '#dc2626' }}>
        actual {fmtMW(row.actual)} {row.covered ? 'covered' : 'missed'}
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
      predLower: shown ? p.demand.lower : null,
      predUpper: shown ? p.demand.upper : null,
      predBand: shown ? p.demand.upper - p.demand.lower : null,
      predPoint: shown ? p.demand.point : null,
      actual: shown ? p.demand.actual : null,
      covered: p.demand_covered ?? p.covered,
    }
  }), [points, revealed])

  const coveredSoFar = useMemo(
    () => points.slice(0, revealed).filter(p => p.demand_covered ?? p.covered).length,
    [points, revealed]
  )

  const midnightTicks = chartData.filter(d => new Date(d.t).getUTCHours() % 12 === 0).map(d => d.t)
  const colors = dark ? SERIES.dark : SERIES.light
  const grid = dark ? '#27272a' : '#e4e4e7'
  const ink = dark ? '#71717a' : '#a1a1aa'
  const maxAbs = Math.max(...points.map(p => Math.abs(p.demand.upper)), ...points.map(p => Math.abs(p.demand.actual)))
  const pct = revealed > 0 ? ((coveredSoFar / revealed) * 100).toFixed(1) : '0.0'
  const demandMae = backtest.summary?.demand_mae
  const demandNaiveMae = backtest.summary?.demand_naive_168h_mae
  const demandImprovementPct = backtest.summary?.demand_mae_improvement_pct
  const demandCoverage = backtest.summary?.demand_coverage_pct

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-2 text-xs text-zinc-500 dark:text-zinc-500">
        <span>each point is one observed hour, UTC</span>
        <span className="font-mono tabular-nums">
          {coveredSoFar}/{revealed} covered ({pct}%)
        </span>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} width={60}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<ReplayTooltip />} cursor={{ stroke: ink, strokeDasharray: '3 3' }} />
          <Area dataKey="predLower" stackId="band" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
          <Area dataKey="predBand" stackId="band" stroke="none" fill={colors.demand} fillOpacity={dark ? 0.15 : 0.1} activeDot={false} isAnimationActive={false} />
          <Line dataKey="predPoint" stroke={colors.demand} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} name="predicted" />
          <Line dataKey="actual" stroke={colors.actual} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} connectNulls={false} name="actual" />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex items-center gap-3">
        <button
          onClick={() => { if (revealed >= points.length) setRevealed(0); setPlaying(p => !p) }}
          className="shrink-0 text-xs px-3 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors duration-150 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
          {playing ? 'pause' : revealed >= points.length ? 'replay' : 'play'}
        </button>
        <input
          type="range" min="0" max={points.length} step="1" value={revealed}
          onChange={e => { setPlaying(false); setRevealed(parseInt(e.target.value, 10)) }}
          className="w-full accent-zinc-500"
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: colors.demand }} /> forecast range
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: colors.actual }} /> actual
        </span>
        {demandMae != null && (
          <span className="ml-auto font-mono tabular-nums">
            model {fmtMW(demandMae)}
            {demandNaiveMae != null && <> vs. baseline {fmtMW(demandNaiveMae)}</>}
            {demandImprovementPct != null && (
              <span className={demandImprovementPct >= 0 ? 'text-teal-600 dark:text-teal-400' : 'text-red-500'}>
                {' '}({demandImprovementPct >= 0 ? '-' : '+'}{Math.abs(demandImprovementPct).toFixed(1)}%)
              </span>
            )}
            {' '}· {demandCoverage != null ? `${demandCoverage.toFixed(1)}%` : '0%'} coverage
          </span>
        )}
      </div>
    </div>
  )
}
