/**
 * ConjunctionMetrics — Right-panel risk status card.
 *
 * Shows: risk tier, miss distance, TCA, relative velocity (not in schema → noted),
 * estimate basis, and a compact expandable methodology.
 *
 * Only displays backend-returned values. "Not provided" for absent fields.
 * NASA CARA tiers labelled as "guidance only".
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
import { useState } from 'react'

export default function ConjunctionMetrics({ analysis }) {
  const [showMethod, setShowMethod] = useState(false)

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
    safe_count,
    total_count,
    relative_velocity_km_s,
    relative_velocity_frame,
    relative_velocity_basis,
    covariance_available,
    covariance_source,
  } = analysis

  const tcaMin  = tca_offset_seconds != null ? (tca_offset_seconds / 60).toFixed(1) : null
  const tcaDate = tca_utc ? new Date(tca_utc).toUTCString() : null
  const relVel  = relative_velocity_km_s ?? null

  const lvl = risk?.color_hint ?? 'green'  // 'red' | 'yellow' | 'green'
  const levelClass = lvl === 'red' ? 'critical' : lvl === 'yellow' ? 'monitor' : 'safe'
  const icon       = lvl === 'red' ? '⚠' : lvl === 'yellow' ? '◉' : '✓'

  const covNote = data_quality?.find(q => q.field === 'Probability of collision')?.note

  return (
    <div className="risk-status-card">
      {/* Header — risk tier */}
      <div className="risk-status-header">
        <div className="risk-tier">
          <span className="risk-icon" aria-hidden="true">{icon}</span>
          <div>
            <div className={`risk-level ${levelClass}`} role="status" aria-label={`Risk: ${risk?.label}`}>
              {risk?.level ?? 'Unknown'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--tx-lo)', marginTop: 1 }}>
              {risk?.label ?? 'Not provided'}
            </div>
          </div>
        </div>
        <span className="risk-basis-chip">Screening estimate</span>
      </div>

      {/* Metrics */}
      <div className="risk-metrics">
        <div>
          <div className="metric-row">
            <span className="metric-name" id="m-miss">Miss Distance</span>
            <span className={`metric-val ${levelClass}`} aria-labelledby="m-miss">
              {nominal_miss_distance_km != null
                ? nominal_miss_distance_km.toFixed(4)
                : '—'}
            </span>
          </div>
          <div className="metric-unit" style={{ textAlign: 'right' }}>km</div>
        </div>

        <div>
          <div className="metric-row">
            <span className="metric-name" id="m-tca">Time to TCA</span>
            <span className="metric-val" aria-labelledby="m-tca">
              {tcaMin ?? '—'}
            </span>
          </div>
          <div className="metric-unit" style={{ textAlign: 'right' }}>min from epoch</div>
        </div>

        <div>
          <div className="metric-row">
            <span className="metric-name" id="m-vel">Rel. Velocity</span>
            <span className="metric-val" style={{ fontSize: 14 }} aria-labelledby="m-vel">
              {relVel != null ? relVel.toFixed(3) : '—'}
            </span>
          </div>
          <div className="metric-unit" style={{ textAlign: 'right' }}>
            {relVel != null ? 'km/s' : 'Not provided'}
          </div>
        </div>

        {/* TCA date */}
        <div style={{ paddingTop: 4 }}>
          <div style={{ fontSize: 10, color: 'var(--tx-lo)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 2 }}>
            TCA (UTC)
          </div>
          <div style={{ fontSize: 11, color: 'var(--tx-mid)', fontFamily: 'var(--mono)' }}>
            {tcaDate ?? '—'}
          </div>
        </div>

        {/* Threshold */}
        {is_conjunction && (
          <div style={{
            marginTop: 4, padding: '6px 8px',
            background: 'var(--red-bg)', border: '1px solid var(--red-bdr)',
            borderRadius: 'var(--r-sm)', fontSize: 11, color: 'var(--red)',
          }} role="note">
            Miss distance &lt; {conjunction_threshold_km} km threshold — maneuver review required
          </div>
        )}
      </div>

      <div className="risk-divider" />

      {/* Recommended action */}
      <div className="risk-action">
        <span className="action-label">Recommended Action</span>
        {is_conjunction
          ? <span style={{ color: 'var(--red)', fontWeight: 600, fontSize: 12 }}>
              Review maneuver candidates and select a safe option below.
            </span>
          : <span style={{ color: 'var(--green-hi)', fontSize: 12 }}>
              No action required — monitor for updates.
            </span>
        }
      </div>

      <div className="risk-divider" />

      {/* Basis & covariance */}
      <div style={{ padding: '8px 16px', fontSize: 11, color: 'var(--tx-lo)', lineHeight: 1.6 }}>
        <div style={{ marginBottom: 3 }}>
          <span style={{ color: 'var(--tx-mid)' }}>Basis:</span>{' '}
          {risk_basis_label ?? 'Not provided'}
        </div>
        {/* Covariance availability — explicit machine-readable contract */}
        <div style={{
          marginTop: 4, padding: '5px 8px',
          background: covariance_available ? 'var(--surface)' : 'var(--amber-bg, rgba(217,119,6,0.08))',
          border: `1px solid ${covariance_available ? 'var(--bdr)' : 'var(--amber-bdr, rgba(217,119,6,0.3))'}`,
          borderRadius: 'var(--r-sm)',
          fontSize: 10,
        }}>
          <span style={{ color: covariance_available ? 'var(--tx-mid)' : 'var(--amber)', fontWeight: 600 }}>
            {covariance_available ? 'Covariance: available' : '⚠ Covariance: unavailable'}
          </span>
          {' — '}
          <span style={{ color: 'var(--tx-lo)' }}>
            {covariance_source ?? 'Not provided'}
          </span>
        </div>
        {relative_velocity_km_s != null && (
          <div style={{ marginTop: 4, fontSize: 10 }}>
            <span style={{ color: 'var(--tx-mid)' }}>Rel. velocity basis:</span>{' '}
            <span style={{ fontFamily: 'var(--mono)' }}>
              {relative_velocity_basis ?? `${relative_velocity_frame ?? 'TEME'} frame`}
            </span>
          </div>
        )}
        {covNote && (
          <div style={{ color: 'var(--amber)', fontSize: 10, marginTop: 3 }}>⚠ {covNote}</div>
        )}
        {orbit_element_age_note && (
          <div style={{ marginTop: 3, fontSize: 10 }}>{orbit_element_age_note}</div>
        )}
      </div>

      <div className="risk-divider" />

      {/* Threshold guidance + methodology */}
      <div style={{ padding: '8px 16px' }}>
        <div style={{ fontSize: 10, color: 'var(--tx-lo)', lineHeight: 1.5, marginBottom: 4 }}>
          <strong style={{ color: 'var(--tx-mid)' }}>Guidance</strong> (NASA CARA tiers — reference only, not certified):
          Pc &gt; 10⁻⁴ = high · Pc &lt; 10⁻⁷ = low · between = monitor.
          This prototype does not compute Pc.
        </div>
        <button
          className="disclosure-btn"
          onClick={() => setShowMethod(v => !v)}
          aria-expanded={showMethod}
          aria-controls="method-panel"
        >
          {showMethod ? '▾ Hide methodology' : '▸ Methodology'}
        </button>
        {showMethod && (
          <div id="method-panel" className="disclosure-panel" role="region">
            SGP4 propagation in TEME frame, 24-hour window.
            TCA via 30-second grid sweep + Brent refinement (tol = 0.01 s).
            Conjunction threshold: {conjunction_threshold_km} km.
            Relative velocity: difference of both SGP4 velocity vectors at exact TCA timestamp in TEME.
            No CDM covariance — screening-level estimate only.
          </div>
        )}
      </div>
    </div>
  )
}
