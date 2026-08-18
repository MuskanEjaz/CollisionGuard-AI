/** GraniteAdvisory -- displays Granite status badge, summary, and note */
export default function GraniteAdvisory({ advisory }) {
  if (!advisory) return null

  const isLive = advisory.source === 'granite'

  return (
    <div>
      <div className="granite-header">
        <span className={`granite-badge ${isLive ? 'live' : 'fallback'}`}>
          {isLive
            ? `IBM Granite — Live (${advisory.model_id})`
            : 'Deterministic fallback — Granite unavailable'}
        </span>
        {!isLive && (
          <span style={{ fontSize: '0.62rem', color: 'var(--muted)' }}>
            Ranking by backend baseline score
          </span>
        )}
      </div>

      <div className="granite-summary">{advisory.granite_summary}</div>
      <div className="granite-note">{advisory.granite_note}</div>

      {advisory.validation_warnings?.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          {advisory.validation_warnings.map((w, i) => (
            <div key={i} style={{
              fontSize: '0.62rem',
              color: 'var(--yellow)',
              padding: '0.2rem 0',
            }}>
              ⚠ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
