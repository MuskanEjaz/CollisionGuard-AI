/**
 * HealthStatus — fetches GET /health on mount and renders the result.
 *
 * IMPORTANT: This component renders ONLY values returned by the API.
 * It never computes or hardcodes health conclusions.
 */
import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'

const STATUS_STYLES = {
  ok: { background: '#d1fae5', color: '#065f46', border: '1px solid #6ee7b7' },
  degraded: { background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d' },
  unknown: { background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db' },
}

export default function HealthStatus() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/health')
      .then(setHealth)
      .catch((err) => setError(err.message))
  }, [])

  const statusKey = health?.status ?? 'unknown'
  const style = STATUS_STYLES[statusKey] ?? STATUS_STYLES.unknown

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
        Backend Health
      </h2>

      {error && (
        <div style={{ color: '#dc2626', fontSize: '0.875rem' }}>
          Unable to reach backend: {error}
        </div>
      )}

      {!error && !health && (
        <div style={{ color: '#6b7280', fontSize: '0.875rem' }}>Checking…</div>
      )}

      {!error && health && (
        <div
          style={{
            display: 'inline-block',
            padding: '0.4rem 0.9rem',
            borderRadius: '0.375rem',
            fontSize: '0.875rem',
            fontWeight: 500,
            ...style,
          }}
        >
          Status: <strong>{health.status}</strong> — v{health.version}
        </div>
      )}
    </div>
  )
}
