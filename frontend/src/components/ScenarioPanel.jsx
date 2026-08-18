/**
 * ScenarioPanel — fetches GET /scenarios on mount and renders each scenario.
 *
 * IMPORTANT:
 *  - This component renders ONLY values returned by the API.
 *  - It never computes orbital mechanics, miss distances, or any derived value.
 *  - null propagation fields are displayed as "Pending propagation analysis."
 */
import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'

const TYPE_STYLES = {
  conjunction: {
    background: '#fee2e2',
    color: '#991b1b',
    border: '1px solid #fca5a5',
    label: 'CONJUNCTION',
  },
  safe: {
    background: '#d1fae5',
    color: '#065f46',
    border: '1px solid #6ee7b7',
    label: 'SAFE',
  },
}

function ScenarioCard({ scenario }) {
  const typeStyle = TYPE_STYLES[scenario.scenario_type] ?? {}

  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '0.5rem',
        padding: '1rem 1.25rem',
        marginBottom: '1rem',
        background: '#ffffff',
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.5rem',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: '1rem' }}>
          {scenario.scenario_id}
        </span>
        <span
          style={{
            padding: '0.2rem 0.65rem',
            borderRadius: '0.25rem',
            fontSize: '0.75rem',
            fontWeight: 600,
            ...typeStyle,
          }}
        >
          {typeStyle.label ?? scenario.scenario_type.toUpperCase()}
        </span>
      </div>

      {/* Description */}
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', color: '#374151' }}>
        {scenario.description}
      </p>

      {/* Metadata table */}
      <table style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
        <tbody>
          <MetaRow label="Epoch (UTC)" value={scenario.epoch_utc} />
          <MetaRow label="Our satellite" value={scenario.our_satellite.name} />
          <MetaRow label="Threat object" value={scenario.threat_object.name} />
          <MetaRow
            label="Miss distance"
            value={
              scenario.predicted_miss_distance_km !== null
                ? `${scenario.predicted_miss_distance_km} km`
                : 'Pending propagation analysis'
            }
          />
          <MetaRow
            label="Time to closest approach"
            value={
              scenario.time_to_closest_approach_s !== null
                ? `${scenario.time_to_closest_approach_s} s`
                : 'Pending propagation analysis'
            }
          />
        </tbody>
      </table>
    </div>
  )
}

function MetaRow({ label, value }) {
  return (
    <tr>
      <td
        style={{
          width: '45%',
          padding: '0.2rem 0',
          color: '#6b7280',
          verticalAlign: 'top',
        }}
      >
        {label}
      </td>
      <td style={{ padding: '0.2rem 0', color: '#1f2328', fontWeight: 500 }}>
        {value}
      </td>
    </tr>
  )
}

export default function ScenarioPanel() {
  const [scenarios, setScenarios] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiGet('/scenarios')
      .then((data) => setScenarios(data.scenarios))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
        Scenarios
      </h2>

      {loading && (
        <div style={{ color: '#6b7280', fontSize: '0.875rem' }}>Loading scenarios…</div>
      )}

      {error && (
        <div style={{ color: '#dc2626', fontSize: '0.875rem' }}>
          Unable to load scenarios: {error}
        </div>
      )}

      {!loading && !error && scenarios.length === 0 && (
        <div style={{ color: '#6b7280', fontSize: '0.875rem' }}>No scenarios found.</div>
      )}

      {scenarios.map((s) => (
        <ScenarioCard key={s.scenario_id} scenario={s} />
      ))}
    </div>
  )
}
