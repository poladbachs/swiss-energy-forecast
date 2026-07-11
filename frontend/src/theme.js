// One accent per series, used identically everywhere it appears. Demand is
// the primary signal (cool blue); price is the secondary signal (warm
// amber), chosen so the two never get confused on the same page. Neutrals
// are zinc, tuned slightly cooler in dark mode to avoid muddy gray.

export const SERIES = {
  light: { demand: '#2563eb', price: '#b45309', actual: '#0f766e' },
  dark:  { demand: '#60a5fa', price: '#fbbf24', actual: '#2dd4bf' },
}

export const fmtMW = v =>
  Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v)} MW`

// Axis ticks share one unit (picked from the largest tick), so a 0 gridline
// doesn't read "0 MW" next to siblings like "7.5 GW".
export const fmtAxis = (v, maxAbs) =>
  maxAbs >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v)} MW`

export const fmtTime = ts =>
  new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })

export const fmtDateTime = ts =>
  new Date(ts).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  })

export const fmtHourOrDay = ts => {
  const d = new Date(ts)
  return d.getUTCHours() === 0
    ? d.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
    : fmtTime(ts)
}
