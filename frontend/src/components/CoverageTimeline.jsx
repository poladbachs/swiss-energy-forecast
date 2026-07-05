import { useState } from 'react'
import { STATUS, STATUS_META, fmtMW, fmtDateTime, fmtHourOrDay } from '../theme'

export default function CoverageTimeline({ forecasts, summary, hoverIdx, onHover }) {
  const [localIdx, setLocalIdx] = useState(null)
  const active = localIdx ?? hoverIdx
  const activeHour = active != null ? forecasts[active] : null

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-2 transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">Renewable coverage, next {forecasts.length}h</h2>
        <div className="flex gap-3 text-xs text-gray-600 dark:text-gray-400">
          {Object.entries(STATUS_META).map(([k, m]) => (
            <span key={k} className="inline-flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: STATUS[k] }} />
              {m.glyph} {m.label}
            </span>
          ))}
        </div>
      </div>

      <div className="flex gap-px rounded-md overflow-hidden"
           onMouseLeave={() => { setLocalIdx(null); onHover?.(null) }}>
        {forecasts.map((f, i) => (
          <div
            key={f.timestamp}
            className="h-10 flex-1 cursor-default transition-transform"
            style={{
              backgroundColor: STATUS[f.coverage_status],
              opacity: active == null || active === i ? 1 : 0.45,
              transform: active === i ? 'scaleY(1.15)' : 'none',
            }}
            onMouseEnter={() => { setLocalIdx(i); onHover?.(i) }}
          />
        ))}
      </div>

      <div className="flex justify-between text-xs text-gray-400 min-h-[1.25rem]">
        {activeHour ? (
          <span className="text-gray-700 dark:text-gray-300 tabular-nums">
            {fmtDateTime(activeHour.timestamp)}: {STATUS_META[activeHour.coverage_status].glyph}{' '}
            {STATUS_META[activeHour.coverage_status].label},{' '}
            {activeHour.supply_gap.point >= 0
              ? `${fmtMW(activeHour.supply_gap.point)} deficit`
              : `${fmtMW(-activeHour.supply_gap.point)} surplus`}
          </span>
        ) : (
          <>
            <span>{fmtHourOrDay(forecasts[0]?.timestamp)}</span>
            <span>{fmtHourOrDay(forecasts[forecasts.length - 1]?.timestamp)}</span>
          </>
        )}
      </div>
    </div>
  )
}
