import { useState, useEffect, useMemo, useRef } from 'react'
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
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    const onPointerDown = event => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    const onKeyDown = event => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  return (
    <div ref={rootRef} className="relative text-sm">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="cursor-pointer list-none rounded text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        ⓘ how to read this
      </button>
        <div
        role="dialog"
        aria-label="How to read this"
        className={`absolute right-0 z-10 mt-2 w-80 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg text-xs text-gray-600 dark:text-gray-300 space-y-2 ${open ? '' : 'hidden'}`}>
        <p>
          The main chart is demand. The balance chart shows how much supply pressure remains after
          solar and wind are subtracted.
        </p>
        <p>
          The shaded band is the forecast range. It is based on past errors, so it should cover
          about 9 out of 10 future hours.
        </p>
        <p>
          The scenario controls let you stress demand, wind, and solar together and see how
          quickly the system gets tight.
        </p>
      </div>
    </div>
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
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-gray-200/80 dark:border-gray-700 bg-white/80 dark:bg-gray-900/80 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-gray-500 dark:text-gray-400 backdrop-blur">
              Alpine Grid Pulse · demand first
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-balance">
                Swiss power demand, balance pressure, and scenario risk.
              </h1>
              <p className="text-sm md:text-base text-gray-600 dark:text-gray-400 mt-2 max-w-2xl">
                A live forecast stack for the Swiss power market: demand first, then the balance
                pressure that renewables leave behind, with scenario controls and backtest coverage.
              </p>
            </div>
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

        <StatTiles forecasts={data.forecasts} summary={data.summary} backtest={backtest} />
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
            {['Demand forecast', 'Balance monitor', 'Scenario lab', 'Backtest replay'].map(t => (
              <span key={t} className="px-2 py-0.5 rounded-full border border-gray-200 dark:border-gray-700">{t}</span>
            ))}
          </div>
          <a href="https://github.com/poladbachs/swiss-energy-forecast"
             className="underline hover:text-gray-600 dark:hover:text-gray-300">
            source on GitHub
          </a>
        </footer>
      </main>
    </div>
  )
}
