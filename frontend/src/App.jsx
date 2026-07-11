import { useState, useEffect, useRef } from 'react'
import { useForecast } from './hooks/useForecast'
import { useBacktest } from './hooks/useBacktest'
import { useFeatureImportance } from './hooks/useFeatureImportance'
import StatTiles from './components/StatTiles'
import ForecastChart from './components/ForecastChart'
import BacktestReplay from './components/BacktestReplay'
import PriceOutlook from './components/PriceOutlook'
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
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="text-sm text-zinc-500 dark:text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded">
        How to read this
      </button>
      <div
        role="dialog"
        aria-label="How to read this"
        className={`absolute right-0 z-20 mt-3 w-72 p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-lg shadow-zinc-950/5 dark:shadow-black/40 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400 space-y-2.5 origin-top-right transition-[opacity,transform] duration-150 ease-out ${open ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}>
        <p>The chart is the demand guess for each of the next 48 hours. The shaded band is how wrong past guesses on similar hours have been. Real outcomes land inside it about 9 times out of 10.</p>
        <p>The backtest replays the last 14 days: our guess vs. what actually happened vs. the dumbest reasonable guess, which is the same hour one week earlier.</p>
        <p>The price outlook is a typical-price estimate fit on the last 12 months of real prices. It is not a guaranteed number, but a real, checked relationship.</p>
      </div>
    </div>
  )
}

function DataFreshness({ forecast, backtest }) {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-400 dark:text-zinc-600 font-mono tabular-nums">
      {forecast?.generated_at && <span>forecast · {fmtDateTime(forecast.generated_at)}</span>}
      {backtest?.generated_at && <span>backtest · {fmtDateTime(backtest.generated_at)}</span>}
    </div>
  )
}

function humanizeFeature(feature) {
  return feature.replace('demand_mw', '').replace(/_/g, ' ').trim().replace(/^./, c => c.toUpperCase())
}

// What actually drives the demand number. Full feature-importance detail
// still lives in the repo; this is the one line that matters on the page.
function WhyItMatters({ featureImportance }) {
  const topFeature = featureImportance?.demand_mw?.[0]
  if (!topFeature) return null

  return (
    <p className="text-sm text-zinc-500 dark:text-zinc-500 leading-relaxed">
      What drives this forecast most: <span className="text-zinc-800 dark:text-zinc-200 font-medium">{humanizeFeature(topFeature.feature)}</span>
      {' '}(<span className="font-mono tabular-nums">{(topFeature.importance * 100).toFixed(0)}%</span> of the model's weight), then hour of day, weekday, and weather.
    </p>
  )
}

function Section({ title, meta, children, delay = 0 }) {
  return (
    <section
      className="pt-8 border-t border-zinc-200 dark:border-zinc-800 animate-[fadeup_0.5s_ease-out_backwards]"
      style={{ animationDelay: `${delay}ms` }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{title}</h2>
        {meta && <div className="text-xs text-zinc-500 dark:text-zinc-500 font-mono tabular-nums">{meta}</div>}
      </div>
      {children}
    </section>
  )
}

export default function App() {
  const [dark, setDark] = useDarkMode()

  const { data, error } = useForecast({ horizon: 48 })
  const { data: backtest } = useBacktest()
  const { data: featureImportance } = useFeatureImportance()

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <div className="text-center space-y-2">
        <p className="text-red-500 font-medium">Could not load forecast: {error}</p>
        <p className="text-sm text-zinc-500">Is the API running?</p>
      </div>
    </div>
  )
  if (!data) return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-zinc-500">
      Loading forecast...
    </div>
  )

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <main className="max-w-3xl mx-auto px-6 py-12 space-y-8">
        <header className="space-y-6">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-zinc-500 dark:text-zinc-500">Alpine Grid Pulse</span>
            <div className="flex items-center gap-5">
              <InfoPopover />
              <button
                onClick={() => setDark(!dark)}
                aria-label="Toggle dark mode"
                className="text-zinc-400 hover:text-zinc-800 dark:text-zinc-500 dark:hover:text-zinc-200 transition-colors duration-150 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded">
                {dark ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" /></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinecap="round" strokeLinejoin="round" /></svg>
                )}
              </button>
            </div>
          </div>
          <div>
            <h1 className="text-3xl md:text-[2.75rem] font-semibold tracking-tightest leading-[1.1] text-balance">
              Swiss electricity demand, next 48 hours, and what that means for price.
            </h1>
            <p className="mt-3 text-base text-zinc-600 dark:text-zinc-400 max-w-[60ch] leading-relaxed">
              A demand forecast checked against a real baseline, plus a typical-price outlook fit on
              real historical prices. An actual per-hour estimate, not a caveat.
            </p>
          </div>
          <StatTiles forecasts={data.forecasts} backtest={backtest} />
          <DataFreshness forecast={data} backtest={backtest} />
        </header>

        <Section title="Demand forecast" delay={80}>
          <ForecastChart forecasts={data.forecasts} dark={dark} />
        </Section>

        {backtest && (
          <Section
            title="Backtest, 24h ahead"
            meta="replays the last 14 days"
            delay={140}>
            <BacktestReplay backtest={backtest} dark={dark} />
          </Section>
        )}

        <Section title="Price outlook, next 48h" delay={200}>
          <PriceOutlook forecasts={data.forecasts} priceModel={backtest?.summary?.price_model} dark={dark} />
        </Section>

        <div className="pt-8 border-t border-zinc-200 dark:border-zinc-800 space-y-6">
          <WhyItMatters featureImportance={featureImportance} />
          <footer className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400 dark:text-zinc-600">
            <span>Demand forecast · Backtest vs. baseline · Price outlook</span>
            <a href="https://github.com/poladbachs/swiss-energy-forecast"
               className="underline decoration-zinc-300 dark:decoration-zinc-700 underline-offset-4 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors duration-150">
              source on GitHub
            </a>
          </footer>
        </div>
      </main>
    </div>
  )
}
