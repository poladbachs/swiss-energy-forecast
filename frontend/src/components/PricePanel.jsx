import {
  ResponsiveContainer, ComposedChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { fmtDateTime, fmtHourOrDay } from '../theme'

const ACTUAL = { light: '#0891b2', dark: '#22d3ee' }
const IMPLIED = { light: '#a855f7', dark: '#c084fc' }

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-gray-900 dark:text-gray-100">{fmtDateTime(label)}</p>
      {row.actual != null && <p className="tabular-nums text-gray-700 dark:text-gray-300">realized {row.actual.toFixed(0)} EUR/MWh</p>}
      {row.implied != null && <p className="tabular-nums text-purple-600 dark:text-purple-400">implied by import-gap {row.implied.toFixed(0)} EUR/MWh</p>}
    </div>
  )
}

// Not a price forecast — a validation chart. price_implied_eur_mwh comes from
// a plain linear regression of realized price on the import gap (see
// models/price_model.py); this shows how much of the real price movement
// that weak-but-real relationship actually tracks.
export default function PricePanel({ backtest, dark }) {
  const priceModel = backtest?.summary?.price_model
  const points = (backtest?.points ?? []).filter(p => p.price_eur_mwh != null)
  if (!priceModel || points.length === 0) return null

  const data = points.map(p => ({ t: p.timestamp, actual: p.price_eur_mwh, implied: p.price_implied_eur_mwh }))
  const midnightTicks = data.filter(d => new Date(d.t).getUTCHours() % 12 === 0).map(d => d.t)
  const actualColor = dark ? ACTUAL.dark : ACTUAL.light
  const impliedColor = dark ? IMPLIED.dark : IMPLIED.light
  const grid = dark ? '#27272a' : '#f3f4f6'
  const ink = dark ? '#a1a1aa' : '#6b7280'
  const priceMae = backtest.summary?.price_mae_eur_mwh

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-2 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">Does the import gap actually price?</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Realized Swiss day-ahead price vs. a plain linear estimate from import gap + hour-of-day + weekend.
          </p>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
          r²={priceModel.r2.toFixed(2)} · +{priceModel.slope_eur_per_100mw.toFixed(2)} EUR/100MW
          {priceMae != null && ` · ${priceMae.toFixed(0)} EUR/MWh MAE`}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={midnightTicks} tickFormatter={fmtHourOrDay}
                 tick={{ fontSize: 10, fill: ink }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: ink }} width={48} axisLine={false} tickLine={false}
                 domain={['auto', 'auto']} tickFormatter={v => `${v}`} />
          <Tooltip content={<PriceTooltip />} />
          <Line dataKey="actual" stroke={actualColor} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls={false} name="realized" />
          <Line dataKey="implied" stroke={impliedColor} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} connectNulls={false} name="implied" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: actualColor }} /> realized price
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: impliedColor, borderTop: `1.5px dashed ${impliedColor}` }} /> import-gap implied
        </span>
        <span className="ml-auto">
          Low r² is the honest finding: CH price is set mostly by the wider European market, not domestic balance alone.
        </span>
      </div>
    </div>
  )
}
