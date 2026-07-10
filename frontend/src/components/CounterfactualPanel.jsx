const RESET = { solarMultiplier: 1.0, windMultiplier: 1.0, demandMultiplier: 1.0, bandMultiplier: 1.0 }

// These four are real model reruns: static_forecast.py perturbs the actual
// weather/calendar input (temperature, wind speed, solar radiation, holiday
// flag) and re-predicts with the trained boosters. Selecting one swaps in
// forecast.scenarios[key] as-is — nothing here rescales the output.
const MODEL_SCENARIOS = [
  { key: 'cold_snap', label: '❄️ Cold snap' },
  { key: 'holiday',   label: '🏖️ Holiday' },
  { key: 'low_wind',  label: '🌬️ Low wind' },
  { key: 'low_solar', label: '☀️ Low solar' },
]

// Event shock has no counterpart feature in the model (no strike/outage
// signal exists yet — see README), so it can't be a real rerun. It's kept as
// an explicit, labeled multiplier overlay instead of pretending it's modeled.
const EVENT_SHOCK_PRESET = { label: '⚡ Event shock', demandMultiplier: 1.10, bandMultiplier: 1.30 }

export default function CounterfactualPanel({
  multipliers, onChange, summary, baseSummary, scenarios, selectedScenario, onSelectScenario,
}) {
  const set = (key, val) => { onSelectScenario(null); onChange({ ...multipliers, [key]: parseFloat(val) }) }
  const applyEventShock = () => { onSelectScenario(null); onChange({ ...RESET, ...EVENT_SHOCK_PRESET }) }
  const selectModelScenario = key => { onChange(RESET); onSelectScenario(key) }
  const reset = () => { onChange(RESET); onSelectScenario(null) }

  const isBaseline = selectedScenario == null && Object.keys(RESET).every(k => multipliers[k] === RESET[k])
  const diff = baseSummary
    ? summary.confirmed_surplus_hours - baseSummary.confirmed_surplus_hours
    : null

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-4 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">
          Scenario lab
        </h2>
        <div className="flex items-center gap-2">
          {multipliers.bandMultiplier !== 1.0 && selectedScenario == null && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300">
              range ×{multipliers.bandMultiplier.toFixed(1)}
            </span>
          )}
          {diff !== null && !isBaseline && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              diff > 0 ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
              : diff < 0 ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
            }`}>
              {diff > 0 ? '+' : ''}{diff} confirmed surplus hours vs today
            </span>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
          Model reruns — real perturbation of the trained model's inputs, not a rescaled output
        </p>
        <div className="flex flex-wrap gap-2">
          {MODEL_SCENARIOS.map(s => (
            <button key={s.key}
              disabled={!scenarios?.[s.key]}
              onClick={() => selectModelScenario(s.key)}
              aria-pressed={selectedScenario === s.key}
              className={`text-xs px-2.5 py-1 rounded-full border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-40 disabled:cursor-not-allowed ${
                selectedScenario === s.key
                  ? 'border-violet-500 bg-violet-100 text-violet-900 dark:bg-violet-900/50 dark:text-violet-200'
                  : 'border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/30'
              }`}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
          Manual overlay — no strike/outage feature exists in the model yet, so this is an assumption, not a prediction
        </p>
        <button
          onClick={applyEventShock}
          className="text-xs px-2.5 py-1 rounded-full border border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          {EVENT_SHOCK_PRESET.label}
        </button>
      </div>

      <label className="block text-sm text-gray-600 dark:text-gray-300">
        <span className="flex justify-between">
          <span>Demand shock (manual)</span>
          <span className="font-mono tabular-nums">×{multipliers.demandMultiplier.toFixed(1)}</span>
        </span>
        <input
          type="range" min="0.8" max="1.3" step="0.05"
          value={multipliers.demandMultiplier}
          onChange={e => set('demandMultiplier', e.target.value)}
          className="w-full mt-1 accent-blue-600"
        />
      </label>

      <label className="block text-sm text-gray-600 dark:text-gray-300">
        <span className="flex justify-between">
          <span>Solar supply (manual)</span>
          <span className="font-mono tabular-nums">×{multipliers.solarMultiplier.toFixed(1)}</span>
        </span>
        <input
          type="range" min="0.5" max="3.0" step="0.1"
          value={multipliers.solarMultiplier}
          onChange={e => set('solarMultiplier', e.target.value)}
          className="w-full mt-1 accent-amber-500"
        />
      </label>

      <label className="block text-sm text-gray-600 dark:text-gray-300">
        <span className="flex justify-between">
          <span>Wind supply (manual)</span>
          <span className="font-mono tabular-nums">×{multipliers.windMultiplier.toFixed(1)}</span>
        </span>
        <input
          type="range" min="0.5" max="3.0" step="0.1"
          value={multipliers.windMultiplier}
          onChange={e => set('windMultiplier', e.target.value)}
          className="w-full mt-1 accent-emerald-600"
        />
      </label>

      <button
        onClick={reset}
        disabled={isBaseline}
        className="text-xs px-2.5 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        Reset to baseline
      </button>
    </div>
  )
}
