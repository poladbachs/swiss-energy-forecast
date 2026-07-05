import { useState, useEffect, useMemo } from 'react'
import { useForecast } from './hooks/useForecast'
import { useBacktest } from './hooks/useBacktest'
import { applyMultipliers } from './lib/counterfactual'
import StatTiles from './components/StatTiles'
import GapChart from './components/GapChart'
import ForecastChart from './components/ForecastChart'
import CoverageTimeline from './components/CoverageTimeline'
import CounterfactualPanel from './components/CounterfactualPanel'
import BacktestReplay from './components/BacktestReplay'
import { fmtDateTime } from './theme'

function useDarkMode() {
  const [dark, setDark] = useState(() =>
    localStorage.theme === 'dark' ||
    (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.theme = dark ? 'dark' : 'light'
  }, [dark])
  return [dark, setDark]
}

function InfoPopover() {
  return (
    <details className="relative text-sm">
      <summary className="cursor-pointer list-none rounded text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        ⓘ how to read this
      </summary>
      <div className="absolute right-0 z-10 mt-2 w-80 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg text-xs text-gray-600 dark:text-gray-300 space-y-2">
        <p>
          Each shaded band is a <strong>90% conformal prediction interval</strong>, calibrated on
          held-out data so that at least 90% of future observations fall inside it.
        </p>
        <p>
          The supply gap is demand minus (solar + wind). Its bounds pair high demand with
          low renewables, so an hour is only marked <strong>✓ confirmed surplus</strong> when
          renewables beat demand even in the worst case.
        </p>
        <p>
          The sliders scale the solar and wind forecasts and their bounds before the gap
          is recomputed, so counterfactual scenarios keep calibrated uncertainty.
        </p>
      </div>
    </details>
  )
}

function DataFreshness({ forecast, backtest }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
      {forecast?.generated_at && <span>Forecast updated {fmtDateTime(forecast.generated_at)}</span>}
      {backtest?.generated_at && <span>Backtest updated {fmtDateTime(backtest.generated_at)}</span>}
    </div>
  )
}

export default function App() {
  const [multipliers, setMultipliers] = useState({
    solarMultiplier: 1.0, windMultiplier: 1.0, demandMultiplier: 1.0, bandMultiplier: 1.0,
  })
  const [dark, setDark] = useDarkMode()
  const [hoverIdx, setHoverIdx] = useState(null)

  const { data: baseline, error } = useForecast({ horizon: 48 })
  const { data: backtest } = useBacktest()
  const data = useMemo(() => applyMultipliers(baseline, multipliers), [baseline, multipliers])

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="text-center space-y-2">
        <p className="text-red-500 font-medium">Could not load forecast: {error}</p>
        <p className="text-sm text-gray-500">Is the API running on port 8000?</p>
      </div>
    </div>
  )
  if (!data) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 text-gray-500">
      Loading forecast…
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <main className="max-w-6xl mx-auto p-6 space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Swiss Energy Forecast</h1>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 max-w-2xl">
              48-hour forecast of Swiss electricity demand, solar and wind, with conformal
              prediction intervals that carry a provable 90% coverage guarantee.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <InfoPopover />
            <button
              onClick={() => setDark(!dark)}
              aria-label="Toggle dark mode"
              className="text-sm px-2.5 py-1 rounded-full border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
              {dark ? '☀ light' : '☾ dark'}
            </button>
          </div>
        </header>

        <StatTiles forecasts={data.forecasts} summary={data.summary} />
        <DataFreshness forecast={baseline} backtest={backtest} />
        <GapChart forecasts={data.forecasts} baseline={baseline?.forecasts} dark={dark} onHover={setHoverIdx} />
        <CoverageTimeline forecasts={data.forecasts} summary={data.summary} hoverIdx={hoverIdx} onHover={setHoverIdx} />
        <ForecastChart forecasts={data.forecasts} dark={dark} />
        <CounterfactualPanel
          multipliers={multipliers}
          onChange={setMultipliers}
          summary={data.summary}
          baseSummary={baseline?.summary}
        />
        {backtest && <BacktestReplay backtest={backtest} dark={dark} />}

        <footer className="pt-4 pb-8 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-400 dark:text-gray-500">
          <div className="flex flex-wrap gap-1.5">
            {['LightGBM', 'MAPIE conformal', 'MLflow', 'Optuna', 'FastAPI', 'PostgreSQL', 'React', 'Recharts'].map(t => (
              <span key={t} className="px-2 py-0.5 rounded-full border border-gray-200 dark:border-gray-700">{t}</span>
            ))}
          </div>
          <a href="https://github.com/tharrmeehan/swiss-energy-forecast"
             className="underline hover:text-gray-600 dark:hover:text-gray-300">
            source on GitHub
          </a>
        </footer>
      </main>
    </div>
  )
}
