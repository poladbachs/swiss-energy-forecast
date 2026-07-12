import { useState, useEffect, useRef } from 'react'
import { useForecast } from './hooks/useForecast'
import { useBacktest } from './hooks/useBacktest'
import { usePriceDA } from './hooks/usePriceDA'
import { useWalkforward } from './hooks/useWalkforward'
import { useFeatureImportance } from './hooks/useFeatureImportance'
import StatTiles from './components/StatTiles'
import PriceAuction from './components/PriceAuction'
import WalkforwardChart from './components/WalkforwardChart'
import ForecastChart from './components/ForecastChart'
import BacktestReplay from './components/BacktestReplay'
import { fmtDateTime } from './theme'

function useDarkMode() {
  const [dark, setDark] = useState(() =>
    !('theme' in localStorage) || localStorage.theme === 'dark'
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
    const onDown = e => { if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false) }
    const onKey = e => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey) }
  }, [])
  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open}
        className="text-sm transition-colors duration-150 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 rounded"
        style={{ color: 'var(--text-2)' }}>
        How to read this
      </button>
      <div role="dialog"
        className={`absolute right-0 z-30 mt-3 w-80 p-4 rounded-xl text-xs leading-relaxed space-y-2.5 origin-top-right transition-[opacity,transform] duration-150 ${open ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}
        style={{ background: 'var(--panel)', border: '1px solid var(--border-strong)', boxShadow: 'var(--shadow-lg)', color: 'var(--text-2)' }}>
        <p>Every European day-ahead auction clears at the same instant, so tomorrow's German price can't be used to predict tomorrow's Swiss one. This model uses only what exists <em>before</em> the auction: cleared prices through today, the TSOs' own next-day load forecasts, the German wind+solar forecast, and lagged reservoir levels.</p>
        <p>Every headline number is out-of-sample: 24 months replayed one at a time, each trained only on data before that month.</p>
        <p>The band around the forecast is built from the model's real historical errors, not an assumed distribution.</p>
      </div>
    </div>
  )
}

function ThemeToggle({ dark, onToggle }) {
  return (
    <button onClick={onToggle} aria-label="Toggle theme"
      className="press w-8 h-8 grid place-items-center rounded-lg transition-colors duration-150 hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
      style={{ color: 'var(--text-2)', border: '1px solid var(--border)' }}>
      {dark ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" /></svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinecap="round" strokeLinejoin="round" /></svg>
      )}
    </button>
  )
}

function Panel({ title, index, meta, children, className = '', delay = 0 }) {
  return (
    <section className={`panel panel-hover p-5 md:p-6 rise ${className}`} style={{ animationDelay: `${delay}ms` }}>
      {title && (
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <div className="flex items-baseline gap-2.5">
            {index && <span className="eyebrow" style={{ color: 'var(--text-3)' }}>{index}</span>}
            <h2 className="text-base font-semibold tracking-tight" style={{ color: 'var(--text)' }}>{title}</h2>
          </div>
          {meta && <span className="text-xs num" style={{ color: 'var(--text-3)' }}>{meta}</span>}
        </div>
      )}
      {children}
    </section>
  )
}

function humanizeFeature(f) {
  return f.replace('demand_mw', '').replace(/_/g, ' ').trim().replace(/^./, c => c.toUpperCase())
}

export default function App() {
  const [dark, setDark] = useDarkMode()
  const { data: priceDA, error } = usePriceDA()
  const { data: walkforward } = useWalkforward()
  const { data: demand } = useForecast({ horizon: 48 })
  const { data: backtest } = useBacktest()
  const { data: featureImportance } = useFeatureImportance()

  if (error) return (
    <div className="min-h-screen grid place-items-center" style={{ background: 'var(--canvas)' }}>
      <div className="text-center space-y-2">
        <p className="font-medium text-red-500">Could not load the price artifact.</p>
        <p className="text-sm" style={{ color: 'var(--text-3)' }}>{error}</p>
      </div>
    </div>
  )
  if (!priceDA) return (
    <div className="min-h-screen grid place-items-center num text-sm" style={{ background: 'var(--canvas)', color: 'var(--text-3)' }}>
      loading…
    </div>
  )

  const live = Boolean(priceDA.next_auction)
  const topFeature = featureImportance?.demand_mw?.[0]

  return (
    <div className="min-h-screen relative canvas-glow" style={{ background: 'var(--canvas)', color: 'var(--text)' }}>
      {/* top bar */}
      <header className="sticky top-0 z-20 backdrop-blur-md"
        style={{ background: 'color-mix(in srgb, var(--canvas) 82%, transparent)', borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-5xl mx-auto px-5 md:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: 'var(--price, #f5b53c)', boxShadow: '0 0 0 3px color-mix(in srgb, #f5b53c 22%, transparent)' }} />
            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text)' }}>Alpine Grid Pulse</span>
            <span className="hidden sm:inline eyebrow ml-1.5">Swiss power markets</span>
          </div>
          <div className="flex items-center gap-4">
            <InfoPopover />
            <ThemeToggle dark={dark} onToggle={() => setDark(!dark)} />
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-5xl mx-auto px-5 md:px-6 py-8 md:py-10 space-y-5">
        {/* hero copy */}
        <div className="rise pt-1 pb-2 max-w-2xl">
          <h1 className="text-[28px] md:text-4xl font-semibold tracking-tight leading-[1.08] text-balance"
              style={{ color: 'var(--text)' }}>
            What tomorrow's Swiss power price looks like, hour by hour.
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            Forecast before the day-ahead auction clears, on live ENTSO-E data across four coupled
            bidding zones, using only what a trader actually knows at that moment.
          </p>
        </div>

        {/* hero: the forecast itself */}
        <PriceAuction priceDA={priceDA} dark={dark} />

        {/* scorecard */}
        <div className="rise" style={{ animationDelay: '60ms' }}>
          <div className="flex items-center gap-2.5 mb-3 px-1">
            <span className="eyebrow">Track record</span>
            <span className="text-xs" style={{ color: 'var(--text-3)' }}>· why you can trust that curve</span>
          </div>
          <StatTiles walkforward={walkforward} dark={dark} />
        </div>

        {/* evidence */}
        {walkforward && (
          <Panel index="01" title="24-month walk-forward" delay={100}
                 meta={`${walkforward.total_hours?.toLocaleString?.() ?? ''} hours out-of-sample`}>
            <p className="text-sm leading-relaxed mb-4 max-w-2xl" style={{ color: 'var(--text-2)' }}>
              Each month is trained only on data strictly before it, then predicted blind. Monthly MAE,
              lower is better. The baseline is yesterday's price at the same hour, the strongest simple
              guess in this market.
            </p>
            <WalkforwardChart walkforward={walkforward} dark={dark} />
          </Panel>
        )}

        {/* supporting demand model */}
        <div className="pt-3 flex items-center gap-2.5 px-1 rise" style={{ animationDelay: '140ms' }}>
          <span className="eyebrow">Supporting model</span>
          <span className="text-xs" style={{ color: 'var(--text-3)' }}>· demand is a core price input, so it earns a place here</span>
        </div>
        {demand && (
          <Panel index="02" title="Swiss demand forecast, next 48h" delay={160}>
            <ForecastChart forecasts={demand.forecasts} dark={dark} />
          </Panel>
        )}
        {backtest && (
          <Panel index="03" title="Demand backtest, 24h ahead" meta="last 14 days" delay={200}>
            <BacktestReplay backtest={backtest} dark={dark} />
          </Panel>
        )}

        {/* footnotes */}
        <div className="pt-4 space-y-3 text-sm leading-relaxed rise" style={{ color: 'var(--text-2)', animationDelay: '240ms' }}>
          <p>
            <span className="eyebrow" style={{ color: 'var(--text-3)' }}>Inputs&nbsp;&nbsp;</span>
            CH, German, French and North-Italian day-ahead prices (lagged a full day), the four zones'
            pre-auction load forecasts, the German wind+solar forecast, weekly Swiss reservoir levels,
            and the calendar. All from ENTSO-E, the EU's official market-data platform.
          </p>
          {topFeature && (
            <p>
              <span className="eyebrow" style={{ color: 'var(--text-3)' }}>Demand driver&nbsp;&nbsp;</span>
              most weight on <span style={{ color: 'var(--text)' }} className="font-medium">{humanizeFeature(topFeature.feature)}</span>
              {' '}(<span className="num">{(topFeature.importance * 100).toFixed(0)}%</span>), then hour of day, weekday, and weather.
            </p>
          )}
          <p>
            <span className="eyebrow" style={{ color: 'var(--text-3)' }}>Rejected signal&nbsp;&nbsp;</span>
            bridge days (the working day between a holiday and the weekend) show ~12% lower demand in the
            raw data, but with only 11 in 6 years the model couldn't learn a reliable split, so it was
            tested and not shipped. The experiment is committed in the repo.
          </p>
        </div>

        <footer className="pt-6 pb-2 flex flex-wrap items-center justify-between gap-2 text-xs num"
                style={{ color: 'var(--text-3)', borderTop: '1px solid var(--border)' }}>
          <span className="pt-4">
            price · {priceDA.generated_at && fmtDateTime(priceDA.generated_at)}
          </span>
          <a href="https://github.com/poladbachs/swiss-energy-forecast"
             className="pt-4 underline underline-offset-4 transition-colors duration-150 hover:opacity-80"
             style={{ textDecorationColor: 'var(--border-strong)' }}>
            source on GitHub
          </a>
        </footer>
      </main>
    </div>
  )
}
