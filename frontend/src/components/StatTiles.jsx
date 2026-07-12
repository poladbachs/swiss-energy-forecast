import { series, f } from '../theme'

// A win/loss strip: one cell per walk-forward month, filled when the model
// beat the naive baseline that month. Turns "23/24" into something you see.
function WinStrip({ folds, dark }) {
  const c = series(dark)
  if (!folds?.length) return null
  return (
    <div className="mt-2.5 flex gap-[3px]">
      {folds.map(f => {
        const win = f.model_mae < f.naive24_mae
        return (
          <span key={f.month} title={`${f.month}: ${win ? 'beat' : 'lost to'} naive`}
                className="h-2.5 flex-1 rounded-[2px]"
                style={{ background: win ? c.price : 'var(--border-strong)', opacity: win ? 1 : 0.5 }} />
        )
      })}
    </div>
  )
}

function Metric({ label, value, unit, sub, accent, first, children }) {
  return (
    <div className="px-5 py-4 flex-1 min-w-[10rem]"
         style={!first ? { borderColor: 'var(--border)' } : undefined}>
      <p className="eyebrow">{label}</p>
      <p className="mt-1.5 num text-[26px] font-semibold tracking-tight leading-none flex items-baseline gap-1"
         style={{ color: accent || 'var(--text)' }}>
        {value}{unit && <span className="text-sm font-normal" style={{ color: 'var(--text-3)' }}>{unit}</span>}
      </p>
      {sub && <p className="mt-1 text-xs" style={{ color: 'var(--text-3)' }}>{sub}</p>}
      {children}
    </div>
  )
}

// Three out-of-sample facts. No in-sample numbers on this strip.
export default function StatTiles({ walkforward, dark }) {
  const wf = walkforward
  if (!wf) return null
  const c = series(dark)

  return (
    <div className="panel grid grid-cols-1 sm:grid-cols-3
                    [&>*+*]:border-t [&>*+*]:border-[color:var(--border)]
                    sm:[&>*+*]:border-t-0 sm:[&>*+*]:border-l">
      <Metric
        first
        label="Beats naive by"
        value={`${f(Math.abs(wf.mae_improvement_pct))}%`}
        unit="lower error"
        sub={`${f(wf.model_mae, 1)} vs ${f(wf.naive24_mae, 1)} €/MWh MAE`}
        accent={c.price}
      />
      <Metric
        label="Months won"
        value={wf.months_beating_naive24 ?? '—'}
        unit={`/ ${wf.n_fold_months ?? '—'}`}
        sub="out-of-sample, one month at a time">
        <WinStrip folds={wf.folds} dark={dark} />
      </Metric>
      <Metric
        label="Direction hit rate"
        value={`${f(wf.direction_hit_rate_pct)}%`}
        sub="up or down vs. yesterday, hourly"
      />
    </div>
  )
}
