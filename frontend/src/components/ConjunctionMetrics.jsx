/** ConjunctionMetrics -- displays propagation results and risk classification */
export default function ConjunctionMetrics({ analysis }) {
  if (!analysis) return null

  const { nominal_miss_distance_km, tca_offset_seconds, tca_utc, risk,
          conjunction_threshold_km, orbit_element_age_note, risk_basis_label,
          is_conjunction } = analysis

  const tcaMin = (tca_offset_seconds / 60).toFixed(1)
  const tcaDate = tca_utc ? new Date(tca_utc).toUTCString() : '—'

  return (
    <div>
      {/* Risk badge */}
      <div style={{ marginBottom: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <span className={`risk-badge ${risk.color_hint}`}>{risk.label}</span>
        {is_conjunction && (
          <span style={{ fontSize: '0.68rem', color: 'var(--yellow)' }}>
            Miss distance &lt; {conjunction_threshold_km} km threshold
          </span>
        )}
      </div>

      {/* Key metrics */}
      <div className="metric-grid">
        <div className="metric-cell">
          <div className="metric-label">Miss Distance</div>
          <div className="metric-value">{nominal_miss_distance_km.toFixed(4)}</div>
          <div className="metric-unit">km</div>
        </div>
        <div className="metric-cell">
          <div className="metric-label">Time to TCA</div>
          <div className="metric-value">{tcaMin}</div>
          <div className="metric-unit">min from epoch</div>
        </div>
        <div className="metric-cell">
          <div className="metric-label">TCA (UTC)</div>
          <div className="metric-value" style={{ fontSize: '0.65rem' }}>{tcaDate}</div>
          <div className="metric-unit">&nbsp;</div>
        </div>
        <div className="metric-cell">
          <div className="metric-label">Risk Level</div>
          <div className="metric-value" style={{ fontSize: '0.85rem' }}>{risk.level}</div>
          <div className="metric-unit">&nbsp;</div>
        </div>
      </div>

      {/* Risk basis */}
      <div style={{ marginTop: '0.75rem', fontSize: '0.65rem', color: 'var(--muted)',
                    borderLeft: '2px solid var(--border)', paddingLeft: '0.6rem' }}>
        <strong>Risk basis:</strong> {risk_basis_label}
      </div>

      {/* Orbit element age */}
      <div style={{ marginTop: '0.4rem', fontSize: '0.65rem', color: 'var(--muted)' }}>
        {orbit_element_age_note}
      </div>
    </div>
  )
}
