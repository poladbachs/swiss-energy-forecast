import { fmtMW, fmtDateTime } from '../theme'

function Stat({ label, value, unit, sub, accent }) {
  return (
    <div className="flex-1 min-w-[9rem] py-4 px-5 first:pl-0">
      <p className="text-xs uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-500">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold font-mono tabular-nums tracking-tight" style={accent ? { color: accent } : undefined}>
        {value}{unit && <span className="ml-1 text-sm font-normal text-zinc-400 dark:text-zinc-500">{unit}</span>}
      </p>
      {sub && <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-500">{sub}</p>}
    </div>
  )
}

// Three facts, not three cards: a data strip divided by hairlines. Here's
// the forecast, here's proof it beats a real baseline, here's what that
// means for price.
export default function StatTiles({ forecasts, backtest }) {
  const peakDemand = forecasts.reduce((a, b) => (b.demand.point > a.demand.point ? b : a))
  const demandMaE = backtest?.summary?.demand_mae
  const demandCoverage = backtest?.summary?.demand_coverage_pct
  const demandImprovementPct = backtest?.summary?.demand_mae_improvement_pct

  const priced = forecasts.filter(f => f.price_implied_eur_mwh != null)
  const priciest = priced.length ? priced.reduce((a, b) => (b.price_implied_eur_mwh > a.price_implied_eur_mwh ? b : a)) : null

  return (
    <div className="flex flex-wrap divide-x divide-zinc-200 dark:divide-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50">
      <Stat
        label="Peak demand"
        value={fmtMW(peakDemand.demand.point)}
        sub={fmtDateTime(peakDemand.timestamp)}
      />
      <Stat
        label="Beats baseline by"
        value={demandImprovementPct != null ? `${demandImprovementPct >= 0 ? '-' : '+'}${Math.abs(demandImprovementPct).toFixed(0)}%` : (demandMaE != null ? fmtMW(demandMaE) : 'n/a')}
        sub={demandCoverage != null ? `${fmtMW(demandMaE)} MAE vs. last week` : 'stability check'}
      />
      {priciest && (
        <Stat
          label="Priciest hour"
          value={`~${priciest.price_implied_eur_mwh.toFixed(0)}`}
          unit="EUR/MWh"
          sub={fmtDateTime(priciest.timestamp)}
        />
      )}
    </div>
  )
}
