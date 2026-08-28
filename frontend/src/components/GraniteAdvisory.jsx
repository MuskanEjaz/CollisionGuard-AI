/**
 * GraniteAdvisory — displays Granite/fallback status badge, summary, and notes.
 *
 * Source provenance is always shown:
 *   - "IBM Granite — Live" (if source === 'granite')
 *   - "Deterministic fallback — Granite unavailable" (if source === 'deterministic_fallback')
 *   - "Live Granite unverified" warning always shown when not live
 *
 * Granite is never shown as the source of physics values.
 * Validation warnings are displayed prominently.
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
export default function GraniteAdvisory({ advisory }) {
  if (!advisory) return null

  const isLive = advisory.source === 'granite'

  return (
    <div aria-label="AI Advisory panel">
      {/* Source provenance header */}
      <div className="granite-hd">
        <span
          className={`g-badge ${isLive ? 'live' : 'fallback'}`}
          role="status"
          aria-label={
            isLive
              ? `IBM Granite live — model ${advisory.model_id}`
              : 'Deterministic fallback — Granite unavailable'
          }
        >
          {isLive
            ? `IBM Granite — Live (${advisory.model_id})`
            : 'Deterministic fallback — Granite unavailable'}
        </span>

        {!isLive && (
          <span style={{ fontSize: '10px', color: 'var(--tx-lo)' }}>
            Ranking by backend baseline score
          </span>
        )}

        {/* "Live Granite unverified" notice — always show unless proven live */}
        {!isLive && (
          <span
            className="g-badge unverified"
            role="note"
            aria-label="Live Granite has not been verified in this session"
          >
            Live Granite unverified
          </span>
        )}
      </div>

      {/* Provenance disclaimer */}
      <div
        className="g-prov"
        style={{ marginBottom: 'var(--s4)' }}
        role="note"
      >
        Physics values (miss distance, TCA, fuel, robustness) are computed by the
        deterministic backend. Granite provides ranking and explanation only.
        Granite cannot modify physics values or approve execution.
      </div>

      {/* Advisory summary */}
      <div
        className="g-summary"
        aria-label={`${isLive ? 'IBM Granite' : 'Deterministic fallback'} advisory summary`}
      >
        {advisory.granite_summary ?? 'No advisory available.'}
      </div>

      {/* Advisory note */}
      {advisory.granite_note && (
        <div className="g-note" role="note">
          {advisory.granite_note}
        </div>
      )}

      {/* Validation warnings */}
      {advisory.validation_warnings?.length > 0 && (
        <div
          style={{ marginTop: 'var(--s3)' }}
          role="alert"
          aria-label="Advisory validation warnings"
        >
          {advisory.validation_warnings.map((w, i) => (
            <div key={i} className="g-warning">
              <span aria-hidden="true">⚠</span>
              {w}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
