import { fmtMW, STATUS, fmtDateTime, fmtTime } from '../theme'

const fmtWindow = (start, end) => {
  const s = new Date(start), e = new Date(end)
  const day = s.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC' })
  return `${day} ${fmtTime(s)}–${fmtTime(e)} UTC`
}

function nextWindow(forecasts, status) {
  const i = forecasts.findIndex(f => f.coverage_status === status)
  if (i === -1) return null
  let j = i
  while (j + 1 < forecasts.length && forecasts[j + 1].coverage_status === status) j++
  // the window ends one hour after the last matching hour
  return fmtWindow(forecasts[i].timestamp, new Date(new Date(forecasts[j].timestamp).getTime() + 36e5))
}

function Tile({ label, value, sub, accent }) {
  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums" style={accent ? { color: accent } : undefined}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function StatTiles({ forecasts, summary, backtest }) {
  const peakDemand = forecasts.reduce((a, b) => (b.demand.point > a.demand.point ? b : a))
  const peakPressure = forecasts.reduce((a, b) => (b.import_gap.point > a.import_gap.point ? b : a))
  const surplusWin = nextWindow(forecasts, 'confirmed_surplus') || nextWindow(forecasts, 'possible_surplus')
  const surplusKind = nextWindow(forecasts, 'confirmed_surplus') ? 'confirmed' : 'possible'
  const demandCoverage = backtest?.summary?.demand_coverage_pct
  const demandMaE = backtest?.summary?.demand_mae
  const demandImprovementPct = backtest?.summary?.demand_mae_improvement_pct
  const priceModel = backtest?.summary?.price_model

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <Tile
        label="Peak demand"
        value={fmtMW(peakDemand.demand.point)}
        sub={`at ${fmtDateTime(peakDemand.timestamp)}`}
        accent={STATUS.deficit}
      />
      <Tile
        label="Peak import gap"
        value={fmtMW(peakPressure.import_gap.point)}
        sub={`tightest balance at ${fmtDateTime(peakPressure.timestamp)}`}
        accent={STATUS.deficit}
      />
      <Tile
        label="Demand MAE vs seasonal-naive"
        value={demandImprovementPct != null ? `${demandImprovementPct >= 0 ? '−' : '+'}${Math.abs(demandImprovementPct).toFixed(0)}% error` : (demandMaE != null ? fmtMW(demandMaE) : '—')}
        sub={demandCoverage != null ? `${fmtMW(demandMaE)} MAE · ${demandCoverage.toFixed(1)}% interval coverage` : 'stability check'}
        accent={STATUS.confirmed_surplus}
      />
      <Tile
        label="Next relief window"
        value={surplusWin ?? 'none'}
        sub={surplusWin ? `${surplusKind} surplus` : 'none in the next 48h'}
      />
      <Tile
        label="Import gap → price"
        value={priceModel ? `+${priceModel.slope_eur_per_100mw.toFixed(2)} EUR/100MW` : '—'}
        sub={priceModel ? `r²=${priceModel.r2.toFixed(2)} on ${priceModel.n_obs.toLocaleString()}h — weak but real link` : 'no price data'}
      />
    </div>
  )
}
