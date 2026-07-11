import {
  ResponsiveContainer, ComposedChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES } from '../theme'

function FoldTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  const win = row.model < row.naive
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-xs shadow-lg shadow-zinc-950/10 dark:shadow-black/40">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">{label}</p>
      <p className="mt-0.5 font-mono tabular-nums" style={{ color: 'var(--price-color)' }}>model {row.model.toFixed(1)} EUR/MWh</p>
      <p className="font-mono tabular-nums text-zinc-500">naive {row.naive.toFixed(1)} EUR/MWh</p>
      <p className={`font-mono tabular-nums ${win ? 'text-teal-600 dark:text-teal-400' : 'text-red-500'}`}>
        {win ? '-' : '+'}{Math.abs(100 * (1 - row.model / row.naive)).toFixed(0)}% error
      </p>
    </div>
  )
}

// 24 monthly out-of-sample folds: for each month the model was trained only
// on data strictly before it, then predicted the whole month. Lower is
// better; the gap between the two lines is the whole product.
export default function WalkforwardChart({ walkforward, dark }) {
  const folds = walkforward?.folds
  if (!folds?.length) return null
  const colors = dark ? SERIES.dark : SERIES.light
  const grid = dark ? '#27272a' : '#e4e4e7'
  const ink = dark ? '#71717a' : '#a1a1aa'

  const data = folds.map(f => ({ month: f.month, model: f.model_mae, naive: f.naive24_mae }))
  const ticks = data.filter((_, i) => i % 4 === 0).map(d => d.month)

  return (
    <div className="space-y-3" style={{ '--price-color': colors.price }}>
      <p className="text-sm text-zinc-500 dark:text-zinc-500 leading-relaxed">
        Each month trained only on data strictly before it, then predicted out-of-sample. Monthly MAE,
        lower is better. The naive baseline is yesterday's price at the same hour, the strongest
        simple guess in this market.
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 8, right: 52, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="month" ticks={ticks}
                 tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} width={36}
                 axisLine={false} tickLine={false} domain={[0, 'auto']} />
          <Tooltip content={<FoldTooltip />} cursor={{ stroke: ink, strokeDasharray: '3 3' }} />
          <Line dataKey="naive" stroke={ink} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 8} y={y + 3} fontSize={11} fill={ink} fontFamily='"JetBrains Mono", monospace'>naive</text> : null} />
          <Line dataKey="model" stroke={colors.price} strokeWidth={2} dot={false} isAnimationActive={false}
                label={({ index, x, y }) => index === data.length - 1
                  ? <text x={x + 8} y={y + 3} fontSize={11} fontWeight={600} fill={colors.price} fontFamily='"JetBrains Mono", monospace'>model</text> : null} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
