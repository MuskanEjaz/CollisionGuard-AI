/**
 * ConjunctionMetrics — Mission Summary Strip
 *
 * Displays only backend-returned values. Every field has a unit and label.
 * "Not provided" is shown for any missing field (relative_velocity not in schema).
 * Risk basis, covariance note, and expandable methodology included.
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
import { useState } from 'react'

export default function ConjunctionMetrics({ analysis }) {
  const [showMethodology, setShowMethodology] = useState(false)

  if (!analysis) return null

  const {
    nominal_miss_distance_km,
    tca_offset_seconds,
    tca_utc,
    risk,
    conjunction_threshold_km,
    orbit_element_age_note,
    risk_basis_label,
    is_conjunction,
    data_quality,
  } = analysis

  const tcaMin  = tca_offset_seconds != null ? (tca_offset_seconds / 60).toFixed(1) : null
  const tcaDate = tca_utc ? new Date(tca_utc).toUTCString() : null

  // relative_velocity is not in the current FullAnalysisResponse schema
  const relVel = analysis.relative_velocity_ms ?? null

  const riskClass = risk?.color_hint ?? 'green'

  return (
    <div>
      {/* Risk badge row */}
      <div
        style={{ marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.7rem', flexWrap: 'wrap' }}
        aria-label={`Risk status: ${risk?.label}`}
      >
        <span className={`risk-badge ${riskClass}`} role="status">
          {risk?.level ?? 'Unknown'} — {risk?.label ?? 'Unavailable'}
        </span>
        {is_conjunction && (
          <span style={{ fontSize: '0.67rem', color: 'var(--yellow)' }} role="note">
            Miss distance &lt; {conjunction_threshold_km} km threshold
          </span>
        )}
      </div>

      {/* Mission summary strip */}
      <div
        className="mission-strip"
        aria-label="Mission summary metrics"
        role="region"
      >
        <div className={`metric-cell risk-${riskClass}`}>
          <div className="metric-label" id="lbl-miss">Miss Distance</div>
          <div
            className="metric-value"
            aria-labelledby="lbl-miss"
          >
            {nominal_miss_distance_km != null
              ? nominal_miss_distance_km.toFixed(4)
              : 'Unavailable'}
          </div>
          <div className="metric-unit">km</div>
        </div>

        <div className="metric-cell">
          <div className="metric-label" id="lbl-tca-min">Time to TCA</div>
          <div className="metric-value" aria-labelledby="lbl-tca-min">
            {tcaMin ?? 'Unavailable'}
          </div>
          <div className="metric-unit">min from epoch</div>
        </div>

        <div className="metric-cell">
          <div className="metric-label" id="lbl-tca-utc">TCA (UTC)</div>
          <div
            className="metric-value sm"
            aria-labelledby="lbl-tca-utc"
          >
            {tcaDate ?? 'Unavailable'}
          </div>
          <div className="metric-unit">&nbsp;</div>
        </div>

        <div className="metric-cell">
          <div className="metric-label" id="lbl-relvel">Relative Velocity</div>
          <div className="metric-value" aria-labelledby="lbl-relvel">
            {relVel != null ? relVel.toFixed(1) : 'Not provided'}
          </div>
          <div className="metric-unit">m/s (not in schema)</div>
        </div>

        <div className="metric-cell">
          <div className="metric-label" id="lbl-risklv">Risk Level</div>
          <div
            className="metric-value sm"
            style={{
              color: riskClass === 'red' ? 'var(--red)'
                   : riskClass === 'yellow' ? 'var(--yellow)'
                   : 'var(--green)',
            }}
            aria-labelledby="lbl-risklv"
          >
            {risk?.level ?? 'Unknown'}
          </div>
          <div className="metric-unit">&nbsp;</div>
        </div>
      </div>

      {/* Risk basis */}
      <div
        style={{
          marginTop: '0.7rem',
          fontSize: '0.65rem',
          color: 'var(--muted)',
          borderLeft: '2px solid var(--border2)',
          paddingLeft: '0.6rem',
          lineHeight: 1.6,
        }}
        role="note"
      >
        <strong style={{ color: 'var(--text-dim)' }}>Risk basis:</strong>{' '}
        {risk_basis_label ?? 'Not provided'}
      </div>

      {/* Covariance / uncertainty note from data_quality */}
      {data_quality?.find(q => q.field === 'Probability of collision') && (
        <div
          style={{
            marginTop: '0.35rem',
            fontSize: '0.63rem',
            color: 'var(--muted)',
            paddingLeft: '0.6rem',
          }}
          role="note"
        >
          ⚠ {data_quality.find(q => q.field === 'Probability of collision').note}
        </div>
      )}

      {/* Orbit element age */}
      {orbit_element_age_note && (
        <div
          style={{ marginTop: '0.3rem', fontSize: '0.63rem', color: 'var(--muted)', paddingLeft: '0.6rem' }}
          role="note"
        >
          {orbit_element_age_note}
        </div>
      )}

      {/* NASA CARA guidance — labelled as guidance only */}
      <div
        style={{
          marginTop: '0.5rem',
          fontSize: '0.63rem',
          color: 'var(--muted)',
          borderLeft: '2px solid var(--border)',
          paddingLeft: '0.6rem',
          lineHeight: 1.6,
        }}
        role="note"
        aria-label="NASA CARA threshold guidance — informational only"
      >
        <strong style={{ color: 'var(--text-dim)' }}>Threshold guidance</strong>{' '}
        (NASA CARA tiers, for reference only — not certified):
        {' '}Pc &gt; 1×10⁻⁴ = high concern · Pc &lt; 1×10⁻⁷ = low concern · between = monitor.
        {' '}This prototype does not compute Pc.
      </div>

      {/* Expandable methodology */}
      <div style={{ marginTop: '0.5rem' }}>
        <button
          className="methodology-toggle"
          onClick={() => setShowMethodology(v => !v)}
          aria-expanded={showMethodology}
          aria-controls="methodology-panel"
        >
          {showMethodology ? '▾ Hide methodology' : '▸ Show methodology'}
        </button>
        {showMethodology && (
          <div
            id="methodology-panel"
            className="methodology-panel"
            role="region"
            aria-label="Risk estimation methodology"
          >
            Risk metric: miss distance from SGP4 two-body propagation (TEME frame, 24-hour
            window). TCA found by coarse 30-second grid sweep then Brent's-method refinement
            (tol = 0.01 s). Conjunction threshold: 1.0 km (hard-coded business rule).
            No real CDM covariance is used. This is a screening-level estimate only.
            J2, atmospheric drag, and solar-pressure perturbations are not modelled.
            Orbit elements are synthetic — not live CelesTrak data.
          </div>
        )}
      </div>
    </div>
  )
}
