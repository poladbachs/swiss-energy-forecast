import { fmtMW, STATUS, STATUS_META, fmtDateTime, fmtTime } from '../theme'

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

export default function StatTiles({ forecasts, summary }) {
  const peak = forecasts.reduce((a, b) => (b.supply_gap.point > a.supply_gap.point ? b : a))
  const peakIsSurplus = peak.supply_gap.point < 0
  const surplusWin = nextWindow(forecasts, 'confirmed_surplus') || nextWindow(forecasts, 'possible_surplus')
  const surplusKind = nextWindow(forecasts, 'confirmed_surplus') ? 'confirmed' : 'possible'

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Tile
        label="Confirmed surplus"
        value={`${summary.confirmed_surplus_hours} / ${forecasts.length} h`}
        sub={`${STATUS_META.confirmed_surplus.glyph} renewables beat demand even in the worst case`}
        accent={STATUS.confirmed_surplus}
      />
      <Tile
        label="Possible surplus"
        value={`${summary.possible_surplus_hours} / ${forecasts.length} h`}
        sub="interval straddles zero"
        accent={STATUS.possible_surplus}
      />
      <Tile
        label={peakIsSurplus ? 'Smallest surplus' : 'Peak deficit'}
        value={fmtMW(Math.abs(peak.supply_gap.point))}
        sub={`at ${fmtDateTime(peak.timestamp)}`}
        accent={peakIsSurplus ? STATUS.confirmed_surplus : STATUS.deficit}
      />
      <Tile
        label="Next surplus window"
        value={surplusWin ?? 'none'}
        sub={surplusWin ? `${surplusKind} surplus` : 'in the next 48h'}
      />
    </div>
  )
}
