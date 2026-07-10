// Apply capacity multipliers to a base (1.0x) forecast client side.
// Mirrors the API logic: scale solar/wind points and bounds, then rebuild
// the import gap, coverage status and summary. Hydro/nuclear are trailing
// point estimates (not sliders), so they hold steady while solar/wind scale.
//
// This is the *heuristic* path — used by the raw sliders and the "event
// shock" preset, neither of which has a real feature in the trained model to
// perturb. The other four scenario presets (cold snap, holiday, low wind,
// low solar) don't go through this file at all: they're precomputed server
// side by actually perturbing the model's real inputs and rerunning the
// boosters (see scripts/static_forecast.py), and are read directly from
// `forecast.scenarios[name]`.

const classify = (gapPt, gapHi) =>
  gapHi < 0 ? 'confirmed_surplus' : gapPt < 0 ? 'possible_surplus' : 'deficit'

const scale = (iv, m) => ({ point: iv.point * m, lower: iv.lower * m, upper: iv.upper * m })

// Widens (or narrows) the interval around its own point, independent of the
// point's magnitude — models added forecast uncertainty (e.g. a demand shock
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
    const domestic = (f.hydro_mw ?? 0) + (f.nuclear_mw ?? 0)
    const import_gap = {
      point: demand.point - (solar.point + wind.point + domestic),
      lower: demand.lower - (solar.upper + wind.upper + domestic),
      upper: demand.upper - (solar.lower + wind.lower + domestic),
    }
    return { ...f, demand, solar, wind, import_gap, coverage_status: classify(import_gap.point, import_gap.upper) }
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

// Wrap a precomputed real scenario (forecast.scenarios[name], a plain array
// of hour objects from static_forecast.py) in the same {forecasts, summary}
// shape the rest of the app expects. No rescaling — these are already full
// model reruns.
export function scenarioForecast(base, scenarioHours) {
  if (!base || !scenarioHours) return null
  const count = s => scenarioHours.filter(f => f.coverage_status === s).length
  return {
    ...base,
    forecasts: scenarioHours,
    summary: {
      confirmed_surplus_hours: count('confirmed_surplus'),
      possible_surplus_hours: count('possible_surplus'),
      deficit_hours: count('deficit'),
    },
  }
}
