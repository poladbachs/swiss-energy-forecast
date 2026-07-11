import { useState, useEffect } from 'react'

// Day-ahead price artifact: walk-forward summary, the latest cleared
// auction replayed out-of-sample, and (when the pre-auction window is open)
// the next auction's forecast. Regenerated daily by CI.
export function usePriceDA() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/price_forecast_da.json')
      .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  return { data, error }
}
