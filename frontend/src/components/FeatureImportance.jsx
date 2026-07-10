import { useState } from 'react'
import { SERIES } from '../theme'

const TARGETS = [
  { key: 'demand_mw', label: 'Demand' },
  { key: 'solar_mw', label: 'Solar' },
  { key: 'wind_mw', label: 'Wind' },
]

function humanize(feature, target) {
  return feature
    .replace(target, '')
    .replace(/_/g, ' ')
    .replace(/\bmw\b/g, '')
    .trim()
    .replace(/^./, c => c.toUpperCase())
}

// What actually drives each model's prediction — LightGBM gain-based
// importance, exported straight from the trained booster (models/export.py).
// Not a black box: this is the same number the booster itself reports.
export default function FeatureImportance({ data, dark }) {
  const [target, setTarget] = useState('demand_mw')
  if (!data) return null

  const colors = dark ? SERIES.dark : SERIES.light
  const rows = data[target] ?? []
  const color = colors[target.replace('_mw', '')] ?? colors.gap
  const max = Math.max(...rows.map(r => r.importance), 0.0001)

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-3 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">What drives the forecast</h2>
        <div className="flex gap-1">
          {TARGETS.map(t => (
            <button key={t.key}
              onClick={() => setTarget(t.key)}
              aria-pressed={target === t.key}
              className={`text-xs px-2.5 py-1 rounded-full border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                target === t.key
                  ? 'border-gray-400 dark:border-gray-500 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                  : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Top {rows.length} features by LightGBM gain, normalized to share of total.
      </p>
      <div className="space-y-1.5">
        {rows.map(r => (
          <div key={r.feature} className="flex items-center gap-2 text-xs">
            <span className="w-32 shrink-0 text-gray-600 dark:text-gray-300 truncate">{humanize(r.feature, target)}</span>
            <div className="flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(r.importance / max) * 100}%`, backgroundColor: color }} />
            </div>
            <span className="w-10 shrink-0 text-right font-mono tabular-nums text-gray-500 dark:text-gray-400">
              {(r.importance * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
