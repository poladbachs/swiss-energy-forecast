import { useState, useEffect } from 'react'

// Full walk-forward result incl. the 24 per-month folds
// (written by scripts/walkforward_price.py).
export function useWalkforward() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/price_walkforward.json')
      .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  return { data, error }
}
