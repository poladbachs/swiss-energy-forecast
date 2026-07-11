import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { SERIES, fmtDateTime, fmtTime } from '../theme'

function AuctionTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'forecast')?.payload
  if (!row) return null
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-xs shadow-lg shadow-zinc-950/10 dark:shadow-black/40">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">{fmtDateTime(label)}</p>
      <p className="mt-0.5 font-mono tabular-nums" style={{ color: 'var(--price-color)' }}>
        forecast {row.forecast.toFixed(1)} <span className="opacity-60">({row.band_low.toFixed(0)} to {row.band_high.toFixed(0)})</span>
      </p>
      {row.actual != null && (
        <p className="font-mono tabular-nums" style={{ color: 'var(--actual-color)' }}>cleared {row.actual.toFixed(1)}</p>
      )}
    </div>
  )
}

// The latest cleared auction, replayed out-of-sample: the model was trained
// only on data from before this delivery day, exactly what it would have
// known before the auction. When the daily pre-auction window is open
// (between the TSOs' load-forecast publication and the ~12:45 CET clearing),
// the not-yet-cleared next auction shows instead.
export default function PriceAuction({ priceDA, dark }) {
  const colors = dark ? SERIES.dark : SERIES.light
  const live = priceDA.next_auction
  const auction = live ?? priceDA.latest_auction
  if (!auction?.hours?.length) return null

  const data = auction.hours.map(h => ({
    t: h.timestamp,
    forecast: h.forecast,
    band_low: h.band_low,
    band: h.band_high - h.band_low,
    band_high: h.band_high,
    actual: h.actual ?? null,
  }))
  const grid = dark ? '#27272a' : '#e4e4e7'
  const ink = dark ? '#71717a' : '#a1a1aa'
  const ticks = data.filter(d => new Date(d.t).getUTCHours() % 6 === 0).map(d => d.t)

  return (
    <div className="space-y-3" style={{ '--price-color': colors.price, '--actual-color': colors.actual }}>
      <p className="text-sm text-zinc-500 dark:text-zinc-500 leading-relaxed">
        {live ? (
          <>Forecast for the auction that has not cleared yet, built only from pre-auction inputs.</>
        ) : (
          <>Delivery day {auction.delivery_day}, forecast with a model trained only on data from before
          that day, next to what the auction actually cleared: <span className="font-mono tabular-nums text-zinc-700 dark:text-zinc-300">{auction.mae.toFixed(1)}</span> vs.
          naive <span className="font-mono tabular-nums text-zinc-700 dark:text-zinc-300">{auction.naive24_mae.toFixed(1)}</span> EUR/MWh MAE.
          Refreshes after every auction.</>
        )}
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data} margin={{ top: 8, right: 52, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
          <XAxis dataKey="t" ticks={ticks} tickFormatter={fmtTime}
                 tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: ink, fontFamily: '"JetBrains Mono", monospace' }} width={44}
                 axisLine={false} tickLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<AuctionTooltip />} cursor={{ stroke: ink, strokeDasharray: '3 3' }} />
          <Area dataKey="band_low" stackId="b" stroke="none" fill="transparent" activeDot={false} isAnimationActive={false} />
          <Area dataKey="band" stackId="b" stroke="none" fill={colors.price} fillOpacity={dark ? 0.14 : 0.1} activeDot={false} isAnimationActive={false} />
          <Line dataKey="forecast" stroke={colors.price} strokeWidth={2} dot={false} isAnimationActive={false} />
          {!live && (
            <Line dataKey="actual" stroke={colors.actual} strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: colors.price }} /> model, pre-auction
        </span>
        {!live && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 rounded-full" style={{ backgroundColor: colors.actual }} /> cleared price
          </span>
        )}
        <span className="ml-auto text-zinc-400 dark:text-zinc-600">
          band: middle 80% of real out-of-sample errors
        </span>
      </div>
    </div>
  )
}
