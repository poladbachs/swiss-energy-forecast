// Apply capacity multipliers to a base (1.0x) forecast client side.
// Mirrors the API logic: scale solar/wind points and bounds, then rebuild
// the supply gap, coverage status and summary.

const classify = (gapPt, gapHi) =>
  gapHi < 0 ? 'confirmed_surplus' : gapPt < 0 ? 'possible_surplus' : 'deficit'

const scale = (iv, m) => ({ point: iv.point * m, lower: iv.lower * m, upper: iv.upper * m })

// Widens (or narrows) the interval around its own point, independent of the
// point's magnitude — models added forecast uncertainty (e.g. a cold snap
// making demand harder to predict) without shifting the central estimate.
const widen = (iv, m) => ({
  point: iv.point,
  lower: iv.point - (iv.point - iv.lower) * m,
  upper: iv.point + (iv.upper - iv.point) * m,
})

export function applyMultipliers(base, {
  solarMultiplier = 1, windMultiplier = 1, demandMultiplier = 1, bandMultiplier = 1,
} = {}) {
  if (!base) return null
  if (solarMultiplier === 1 && windMultiplier === 1 && demandMultiplier === 1 && bandMultiplier === 1) return base

  const forecasts = base.forecasts.map(f => {
    const demand = widen(scale(f.demand, demandMultiplier), bandMultiplier)
    const solar = widen(scale(f.solar, solarMultiplier), bandMultiplier)
    const wind = widen(scale(f.wind, windMultiplier), bandMultiplier)
    const supply_gap = {
      point: demand.point - (solar.point + wind.point),
      lower: demand.lower - (solar.upper + wind.upper),
      upper: demand.upper - (solar.lower + wind.lower),
    }
    return { ...f, demand, solar, wind, supply_gap, coverage_status: classify(supply_gap.point, supply_gap.upper) }
  })

  const count = s => forecasts.filter(f => f.coverage_status === s).length
  return {
    ...base,
    solar_multiplier: solarMultiplier,
    wind_multiplier: windMultiplier,
    demand_multiplier: demandMultiplier,
    band_multiplier: bandMultiplier,
    forecasts,
    summary: {
      confirmed_surplus_hours: count('confirmed_surplus'),
      possible_surplus_hours: count('possible_surplus'),
      deficit_hours: count('deficit'),
    },
  }
}
