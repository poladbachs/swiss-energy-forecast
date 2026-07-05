// Palettes validated with the six-checks validator (lightness band, chroma floor,
// CVD separation, surface contrast) against #fcfcfb (light) and #1a1a19 (dark).
// Amber and emerald sit below 3:1 contrast in light mode, so each chart
// renders a direct series label as the required secondary encoding.

export const SERIES = {
  light: { demand: '#3b82f6', solar: '#f59e0b', wind: '#10b981', gap: '#64748b' },
  dark:  { demand: '#3b82f6', solar: '#d97706', wind: '#059669', gap: '#94a3b8' },
}

// This status set passes the lightness band in both modes. Keeping it
// identical means the timeline never repaints when the theme flips.
export const STATUS = {
  confirmed_surplus: '#16a34a',
  possible_surplus:  '#b45309',
  deficit:           '#ef4444',
}

export const STATUS_META = {
  confirmed_surplus: { glyph: '✓', label: 'Confirmed surplus' },
  possible_surplus:  { glyph: '~', label: 'Possible surplus' },
  deficit:           { glyph: '✕', label: 'Deficit' },
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
