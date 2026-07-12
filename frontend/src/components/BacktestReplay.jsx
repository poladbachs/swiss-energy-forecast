import { useState, useEffect, useMemo } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { series, chartTheme, MONO, fmtMW, fmtAxis, fmtDateTime, fmtHourOrDay } from '../theme'

const STEP_MS = 55

function ReplayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'predPoint')?.payload
  if (!row || row.actual == null) return null
  return (
    <div className="rounded-xl border px-3 py-2 text-xs num shadow-[var(--shadow)]"
         style={{ background: 'var(--panel)', borderColor: 'var(--border-strong)' }}>
      <p className="font-sans font-medium" style={{ color: 'var(--text)' }}>{fmtDateTime(label)}</p>
      <p className="mt-1" style={{ color: 'var(--demand)' }}>predicted {fmtMW(row.predPoint)}</p>
      <p style={{ color: row.covered ? 'var(--actual)' : '#ef4444' }}>
        actual {fmtMW(row.actual)} {row.covered ? '✓' : '✕'}
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

  const c = series(dark)
  const t = chartTheme(dark)
  const ticks = chartData.filter(d => new Date(d.t).getUTCHours() % 12 === 0).map(d => d.t)
  const maxAbs = Math.max(...points.map(p => Math.abs(p.demand.upper)))
  const pct = revealed > 0 ? ((coveredSoFar / revealed) * 100).toFixed(0) : '0'

  return (
    <div className="space-y-3" style={{ '--demand': c.demand, '--actual': c.actual }}>
      <div className="flex items-baseline justify-between gap-2 text-xs" style={{ color: 'var(--text-3)' }}>
        <span>each point is one observed hour, UTC</span>
        <span className="num">{coveredSoFar}/{revealed} in band ({pct}%)</span>
      </div>

      <ResponsiveContainer width="100%" height={208}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: -6, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke={t.grid} vertical={false} />
          <XAxis dataKey="t" ticks={ticks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10.5, fill: t.tick, fontFamily: MONO }} axisLine={false} tickLine={false} dy={6} />
          <YAxis tickFormatter={v => fmtAxis(v, maxAbs)} tick={{ fontSize: 10.5, fill: t.tick, fontFamily: MONO }} width={40}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<ReplayTooltip />} cursor={{ stroke: t.ink, strokeWidth: 1, strokeDasharray: '3 4' }} />
          <Area dataKey="predLower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area dataKey="predBand" stackId="band" stroke="none" fill={c.demand} fillOpacity={dark ? 0.1 : 0.08} isAnimationActive={false} />
          <Line dataKey="predPoint" stroke={c.demand} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="actual" stroke={c.actual} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} connectNulls={false} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex items-center gap-3">
        <button
          onClick={() => { if (revealed >= points.length) setRevealed(0); setPlaying(p => !p) }}
          className="press shrink-0 num text-xs px-3 py-1.5 rounded-lg border transition-colors duration-150"
          style={{ borderColor: 'var(--border-strong)', color: 'var(--text-2)' }}>
          {playing ? 'pause' : revealed >= points.length ? '↻ replay' : '▶ play'}
        </button>
        <input
          type="range" min="0" max={points.length} step="1" value={revealed}
          onChange={e => { setPlaying(false); setRevealed(parseInt(e.target.value, 10)) }}
          className="w-full h-1 rounded-full appearance-none cursor-pointer"
          style={{ accentColor: c.demand, background: 'var(--border)' }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs" style={{ color: 'var(--text-2)' }}>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-4 h-[3px] rounded-full" style={{ background: c.demand }} /> predicted
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-4 h-0 border-t-2 border-dashed" style={{ borderColor: c.actual }} /> actual
        </span>
        {backtest.summary?.demand_mae != null && (
          <span className="num ml-auto" style={{ color: 'var(--text)' }}>
            {fmtMW(backtest.summary.demand_mae)}
            <span style={{ color: 'var(--text-3)' }}> vs seasonal-naive {fmtMW(backtest.summary.demand_naive_168h_mae)}</span>
          </span>
        )}
      </div>
    </div>
  )
}
