/** ManeuverTable -- displays 3-5 evaluated candidates with safety + Granite rank */
export default function ManeuverTable({
  analysis, advisory, selectedId, onSelect,
}) {
  if (!analysis?.candidates?.length) return null

  // Build a rank map from advisory
  const rankMap = {}
  advisory?.ranked_candidates?.forEach(r => {
    rankMap[r.candidate_id] = { rank: r.rank, explanation: r.explanation }
  })

  return (
    <div>
      {/* Column legend */}
      <div style={{ fontSize: '0.62rem', color: 'var(--muted)', marginBottom: '0.5rem' }}>
        <span style={{ color: 'var(--accent)' }}>Backend values</span>
        {' '}are authoritative.{' '}
        <span style={{ color: 'var(--muted)' }}>Granite ranks</span>
        {' '}are advisory only — human operator decides.
      </div>
      <table className="cand-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Maneuver</th>
            <th>Δv (m/s)</th>
            <th>Post-miss (km)</th>
            <th>Fuel (kg)</th>
            <th>Score</th>
            <th>Safety</th>
            <th>Granite Rank</th>
          </tr>
        </thead>
        <tbody>
          {analysis.candidates.map(c => {
            const r = rankMap[c.candidate_id]
            const isSelected = selectedId === c.candidate_id
            return (
              <tr
                key={c.candidate_id}
                className={
                  isSelected ? 'selected' : !c.is_safe ? 'unsafe' : ''
                }
                style={{ cursor: c.is_safe ? 'pointer' : 'default' }}
                onClick={() => c.is_safe && onSelect(c.candidate_id)}
              >
                <td style={{ color: 'var(--accent)' }}>{c.candidate_id}</td>
                <td>{c.label}</td>
                <td>{c.delta_v_ms.toFixed(2)}</td>
                <td>
                  {c.post_maneuver_miss_distance_km != null
                    ? c.post_maneuver_miss_distance_km.toFixed(3)
                    : '—'}
                </td>
                <td>
                  {c.fuel_cost_kg != null
                    ? c.fuel_cost_kg.toFixed(4)
                    : '—'}
                </td>
                <td>
                  {c.baseline_score != null
                    ? c.baseline_score.toFixed(4)
                    : '—'}
                </td>
                <td>
                  {c.is_safe
                    ? <span className="safe-tag">SAFE</span>
                    : (
                      <span className="unsafe-tag" title={c.safety_rejection_reason}>
                        REJECTED
                      </span>
                    )
                  }
                </td>
                <td>
                  {r
                    ? <span className="rank-tag">#{r.rank}</span>
                    : <span style={{ color: 'var(--muted)' }}>—</span>
                  }
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Selected candidate explanation */}
      {selectedId && rankMap[selectedId] && (
        <div style={{
          marginTop: '0.75rem',
          padding: '0.5rem 0.75rem',
          background: 'rgba(66,153,225,0.07)',
          border: '1px solid rgba(66,153,225,0.25)',
          borderRadius: '4px',
          fontSize: '0.7rem',
          color: 'var(--muted)',
        }}>
          <strong style={{ color: 'var(--accent)' }}>Granite explanation for {selectedId}:</strong>{' '}
          {rankMap[selectedId].explanation}
          <div style={{ marginTop: '0.3rem', fontSize: '0.62rem', fontStyle: 'italic' }}>
            Advisory only — human operator approval required before execution.
          </div>
        </div>
      )}
    </div>
  )
}
