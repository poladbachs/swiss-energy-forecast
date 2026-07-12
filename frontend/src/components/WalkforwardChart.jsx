import {
  ResponsiveContainer, ComposedChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { series, chartTheme, MONO, f } from '../theme'

function FoldTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  const win = row.model < row.naive
  return (
    <div className="rounded-xl border px-3 py-2 text-xs num shadow-[var(--shadow)]"
         style={{ background: 'var(--panel)', borderColor: 'var(--border-strong)' }}>
      <p className="font-sans font-medium" style={{ color: 'var(--text)' }}>{label}</p>
      <p className="mt-1" style={{ color: 'var(--price)' }}>model {f(row.model, 1)}</p>
      <p style={{ color: 'var(--text-3)' }}>naive {f(row.naive, 1)} €/MWh</p>
      <p style={{ color: win ? 'var(--pos)' : '#ef4444' }}>
        {win ? '−' : '+'}{f(Math.abs(100 * (1 - row.model / row.naive)))}% error
      </p>
    </div>
  )
}

export default function WalkforwardChart({ walkforward, dark }) {
  const folds = walkforward?.folds
  if (!folds?.length) return null
  const c = series(dark)
  const t = chartTheme(dark)
  const data = folds.map(f => ({ month: f.month, model: f.model_mae, naive: f.naive24_mae }))
  const ticks = data.filter((_, i) => i % 4 === 0).map(d => d.month)

  return (
    <div style={{ '--price': c.price, '--pos': dark ? '#34d399' : '#059669' }}>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 10, right: 52, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke={t.grid} vertical={false} />
          <XAxis dataKey="month" ticks={ticks}
                 tick={{ fontSize: 10.5, fill: t.tick, fontFamily: MONO }} axisLine={false} tickLine={false} dy={6} />
          <YAxis tick={{ fontSize: 10.5, fill: t.tick, fontFamily: MONO }} width={34}
                 axisLine={false} tickLine={false} domain={[0, 'auto']} />
          <Tooltip content={<FoldTooltip />} cursor={{ stroke: t.ink, strokeWidth: 1, strokeDasharray: '3 4' }} />
          <Line dataKey="naive" stroke={c.naive} strokeWidth={1.5} strokeDasharray="4 4" dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 8} y={y + 3} fontSize={10.5} fill={c.naive} fontFamily={MONO}>naive</text> : null} />
          <Line dataKey="model" stroke={c.price} strokeWidth={2.25} dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 8} y={y + 3} fontSize={10.5} fontWeight={600} fill={c.price} fontFamily={MONO}>model</text> : null} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
