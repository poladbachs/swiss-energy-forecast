function Stat({ label, value, unit, sub }) {
  return (
    <div className="flex-1 min-w-[9rem] py-4 px-5 first:pl-0">
      <p className="text-xs uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-500">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold font-mono tabular-nums tracking-tight">
        {value}{unit && <span className="ml-1 text-sm font-normal text-zinc-400 dark:text-zinc-500">{unit}</span>}
      </p>
      {sub && <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-500">{sub}</p>}
    </div>
  )
}

// The three numbers that ARE the product, every one of them out-of-sample
// from the 24-month walk-forward. No in-sample fits on this strip.
export default function StatTiles({ walkforward }) {
  if (!walkforward) return null
  const wf = walkforward

  return (
    <div className="flex flex-wrap divide-x divide-zinc-200 dark:divide-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50">
      <Stat
        label="Beats naive by"
        value={`-${Math.abs(wf.mae_improvement_pct).toFixed(0)}%`}
        unit="error"
        sub={`${wf.model_mae.toFixed(1)} vs. ${wf.naive24_mae.toFixed(1)} EUR/MWh MAE`}
      />
      <Stat
        label="Months won"
        value={`${wf.months_beating_naive24}/${wf.n_fold_months}`}
        sub="out-of-sample walk-forward"
      />
      <Stat
        label="Direction hit rate"
        value={`${wf.direction_hit_rate_pct.toFixed(0)}%`}
        sub="up or down vs. yesterday, hourly"
      />
    </div>
  )
}
