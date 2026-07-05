import { useState, useEffect } from 'react'

// Static, CI-refreshed backtest of the horizon_h-ahead forecast vs what
// actually happened — regenerated every 6h alongside forecast.json.
export function useBacktest() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/backtest.json')
      .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  return { data, error }
}
