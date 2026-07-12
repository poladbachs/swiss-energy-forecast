// One color system for every chart. Price is the star (amber, the energy
// signal); teal is the realized/cleared truth; blue is the supporting demand
// model; grey is any naive baseline. Light-mode variants are darkened for
// contrast against white panels.

export const SERIES = {
  dark:  { price: '#f5b53c', actual: '#2dd4bf', demand: '#5b9dff', naive: '#606775' },
  light: { price: '#b7791f', actual: '#0d9488', demand: '#2563eb', naive: '#9aa0aa' },
}

export const series = dark => (dark ? SERIES.dark : SERIES.light)

// Axis / grid / cursor colors, kept in one place so every chart matches.
export const chartTheme = dark => dark
  ? { grid: '#1b2029', ink: '#5f6673', tick: '#7a828f' }
  : { grid: '#eceef1', ink: '#9aa0aa', tick: '#6b7280' }

export const MONO = '"JetBrains Mono", ui-monospace, monospace'

export const fmtMW = v =>
  Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)} GW` : `${Math.round(v)} MW`

export const fmtAxis = (v, maxAbs) =>
  maxAbs >= 1000 ? `${(v / 1000).toFixed(1)}` : `${Math.round(v)}`

export const fmtTime = ts =>
  new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })

export const fmtDateTime = ts =>
  new Date(ts).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC', timeZoneName: 'short',
  })

export const fmtDay = ts =>
  new Date(ts).toLocaleDateString('en-GB', {
    weekday: 'long', day: '2-digit', month: 'long', timeZone: 'UTC',
  })

export const fmtHourOrDay = ts => {
  const d = new Date(ts)
  return d.getUTCHours() === 0
    ? d.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
    : fmtTime(ts)
}
