import { useState, useEffect } from 'react'

// Static, CI-refreshed LightGBM gain-based feature importances per target
// (models/export.py writes this alongside every promoted model).
export function useFeatureImportance() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/feature_importance.json')
      .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  return { data, error }
}
