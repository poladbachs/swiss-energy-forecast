import {
  ResponsiveContainer, ComposedChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtDateTime, fmtHourOrDay } from '../theme'

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (row?.price == null) return null
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-xs shadow-lg shadow-zinc-950/10 dark:shadow-black/40">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">{fmtDateTime(label)}</p>
      <p className="mt-0.5 font-mono tabular-nums" style={{ color: 'var(--price-color)' }}>~{row.price.toFixed(0)} EUR/MWh</p>
    </div>
  )
}

// Typical price for each forecasted hour, from a plain regression of real
// historical Swiss day-ahead prices on demand-minus-domestic-generation,
// time of day, and weekend. Fit on the trailing 12 months only (see
// scripts/fit_price_model.py): 2022's gas-price shock is a real regime
// break, and blending it in makes today's relationship look weaker than it
// is. A typical-price estimate, not a guaranteed number.
export default function PriceOutlook({ forecasts, priceModel, dark }) {
  const points = forecasts.filter(f => f.price_implied_eur_mwh != null)
  if (points.length === 0) return null

  const color = (dark ? SERIES.dark : SERIES.light).price
  const data = points.map(f => ({ t: f.timestamp, price: f.price_implied_eur_mwh }))
  const midnightTicks = data.filter(d => new Date(d.t).getUTCHours() % 6 === 0).map(d => d.t)
  const grid = dark ? '#27272a' : '#e4e4e7'
  const ink = dark ? '#71717a' : '#a1a1aa'

  const priciest = points.reduce((a, b) => (b.price_implied_eur_mwh > a.price_implied_eur_mwh ? b : a))
  const cheapest = points.reduce((a, b) => (b.price_implied_eur_mwh < a.price_implied_eur_mwh ? b : a))

  return (
    <div className="space-y-3" style={{ '--price-color': color }}>
      <p className="text-sm text-zinc-500 dark:text-zinc-500 leading-relaxed">
        Typical EUR/MWh per hour, from how demand and time of day have actually priced over the last
        12 months.{priceModel && <> Explains about <span className="font-mono tabular-nums text-zinc-700 dark:text-zinc-300">{(priceModel.r2 * 100).toFixed(0)}%</span> of real price moves in that window.</>}
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} width={44} axisLine={false} tickLine={false}
                 domain={['auto', 'auto']} />
          <Tooltip content={<PriceTooltip />} cursor={{ stroke: ink, strokeDasharray: '3 3' }} />
          <Line dataKey="price" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} name="price" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-500 font-mono tabular-nums">
        <span>priciest {fmtDateTime(priciest.timestamp)}, ~{priciest.price_implied_eur_mwh.toFixed(0)}</span>
        <span>cheapest {fmtDateTime(cheapest.timestamp)}, ~{cheapest.price_implied_eur_mwh.toFixed(0)}</span>
      </div>
    </div>
  )
}
