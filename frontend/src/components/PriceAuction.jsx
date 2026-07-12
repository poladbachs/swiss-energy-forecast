import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts'
import { series, chartTheme, MONO, fmtDateTime, fmtDay, fmtTime } from '../theme'

function AuctionTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload.find(p => p.dataKey === 'forecast')?.payload
  if (!row) return null
  return (
    <div className="rounded-xl border px-3 py-2 text-xs num shadow-[var(--shadow)]"
         style={{ background: 'var(--panel)', borderColor: 'var(--border-strong)' }}>
      <p className="font-sans font-medium" style={{ color: 'var(--text)' }}>{fmtDateTime(label)}</p>
      <p className="mt-1" style={{ color: 'var(--price)' }}>
        forecast {row.forecast.toFixed(1)}
        <span style={{ color: 'var(--text-3)' }}> ({row.band_low.toFixed(0)}&ndash;{row.band_high.toFixed(0)})</span>
      </p>
      {row.actual != null && <p style={{ color: 'var(--actual)' }}>cleared {row.actual.toFixed(1)}</p>}
    </div>
  )
}

function Kpi({ label, value, unit, sub, color }) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p className="mt-1 num text-2xl font-semibold tracking-tight leading-none" style={{ color: color || 'var(--text)' }}>
        {value}<span className="ml-1 text-sm font-normal" style={{ color: 'var(--text-3)' }}>{unit}</span>
      </p>
      {sub && <p className="mt-1 text-xs" style={{ color: 'var(--text-3)' }}>{sub}</p>}
    </div>
  )
}

export default function PriceAuction({ priceDA, dark }) {
  const c = series(dark)
  const t = chartTheme(dark)
  const live = priceDA.next_auction
  const auction = live ?? priceDA.latest_auction
  if (!auction?.hours?.length) return null

  const data = auction.hours.map(h => ({
    t: h.timestamp,
    forecast: h.forecast,
    band_low: h.band_low,
    band: h.band_high - h.band_low,
    actual: h.actual ?? null,
  }))
  const ticks = data.filter(d => new Date(d.t).getUTCHours() % 4 === 0).map(d => d.t)

  const peak = auction.hours.reduce((a, b) => (b.forecast > a.forecast ? b : a))
  const low = auction.hours.reduce((a, b) => (b.forecast < a.forecast ? b : a))
  const avg = auction.hours.reduce((s, h) => s + h.forecast, 0) / auction.hours.length

  return (
    <div className="panel panel-hover p-5 md:p-6"
         style={{ '--price': c.price, '--actual': c.actual }}>
      {/* header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow" style={{ color: c.price }}>
            {live ? 'Next auction · pre-market' : 'Latest auction · replayed blind'}
          </p>
          <h2 className="mt-1.5 text-xl md:text-2xl font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            {fmtDay(auction.hours[0].timestamp)}
          </h2>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-2)' }}>
            {live
              ? 'Forecast for the auction that has not cleared yet.'
              : `Model trained only on data before this day, vs. what actually cleared.`}
          </p>
        </div>
        <div className="flex gap-6 md:gap-8">
          <Kpi label="Peak" value={`~${peak.forecast.toFixed(0)}`} unit="€" sub={fmtTime(peak.timestamp)} color={c.price} />
          <Kpi label="Low" value={`~${low.forecast.toFixed(0)}`} unit="€" sub={fmtTime(low.timestamp)} />
          <Kpi label="Avg" value={`~${avg.toFixed(0)}`} unit="€/MWh" sub="over 24h" />
        </div>
      </div>

      {/* chart */}
      <div className="mt-5 -mx-1">
        <ResponsiveContainer width="100%" height={264}>
          <ComposedChart data={data} margin={{ top: 10, right: 12, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c.price} stopOpacity={dark ? 0.22 : 0.16} />
                <stop offset="100%" stopColor={c.price} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke={t.grid} vertical={false} />
            <XAxis dataKey="t" ticks={ticks} tickFormatter={fmtTime}
                   tick={{ fontSize: 11, fill: t.tick, fontFamily: MONO }} axisLine={false} tickLine={false} dy={6} />
            <YAxis tick={{ fontSize: 11, fill: t.tick, fontFamily: MONO }} width={44}
                   axisLine={false} tickLine={false} domain={['auto', 'auto']}
                   tickFormatter={v => `${v}`} />
            <Tooltip content={<AuctionTooltip />} cursor={{ stroke: t.ink, strokeWidth: 1, strokeDasharray: '3 4' }} />
            <ReferenceLine y={0} stroke={t.grid} strokeWidth={1} />
            {/* uncertainty band, stacked */}
            <Area dataKey="band_low" stackId="b" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area dataKey="band" stackId="b" stroke="none" fill={c.price} fillOpacity={dark ? 0.1 : 0.08} isAnimationActive={false} />
            {/* the forecast line + soft area under it */}
            <Area dataKey="forecast" stroke="none" fill="url(#priceFill)" isAnimationActive={false} />
            <Line dataKey="forecast" stroke={c.price} strokeWidth={2.25} dot={false} isAnimationActive={false} />
            {!live && (
              <Line dataKey="actual" stroke={c.actual} strokeWidth={1.75} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* legend / footer */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs" style={{ color: 'var(--text-2)' }}>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-4 h-[3px] rounded-full" style={{ background: c.price }} /> forecast
        </span>
        {!live && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 h-0 border-t-2 border-dashed" style={{ borderColor: c.actual }} /> cleared price
          </span>
        )}
        {!live && auction.mae != null && (
          <span className="num ml-auto" style={{ color: 'var(--text)' }}>
            {auction.mae.toFixed(1)}
            <span style={{ color: 'var(--text-3)' }}> vs naive {auction.naive24_mae.toFixed(1)} €/MWh</span>
          </span>
        )}
      </div>
    </div>
  )
}
