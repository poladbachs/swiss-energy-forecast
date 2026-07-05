import { useState, useEffect, useCallback } from 'react'

// Fetch the base (1.0x) forecast once. In dev this hits the local FastAPI;
// in production it falls back to the static forecast.json that CI refreshes.
// Counterfactual multipliers are applied client side (lib/counterfactual.js).
export function useForecast({ horizon = 48 } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const fetch_ = useCallback(async () => {
    setError(null)
    try {
      let res = await fetch(`/api/forecast?horizon=${horizon}`).catch(() => null)
      if (!res?.ok) res = await fetch('/forecast.json')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
    } catch (e) {
      setError(e.message)
    }
  }, [horizon])

  useEffect(() => { fetch_() }, [fetch_])

  return { data, error, refetch: fetch_ }
}
