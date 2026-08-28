/**
 * ManeuverTable — displays 3–5 evaluated candidates with safety + Granite rank.
 *
 * Uses backend-returned fields only. Unsafe candidates are visibly rejected
 * and cannot be selected. Shows mobile card fallback on small screens.
 * Granite rank is purple to distinguish it from backend physics values.
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
export default function ManeuverTable({ analysis, advisory, selectedId, onSelect }) {
  if (!analysis?.candidates?.length) return null

  // Build a rank map from advisory (safe candidates only)
  const rankMap = {}
  advisory?.ranked_candidates?.forEach(r => {
    rankMap[r.candidate_id] = { rank: r.rank, explanation: r.explanation }
  })

  function fmt(v, decimals) {
    return v != null ? v.toFixed(decimals) : '—'
  }

  return (
    <div>
      {/* Legend */}
      <p style={{ fontSize: '11px', color: 'var(--tx-lo)', marginBottom: 'var(--s3)' }}>
        <span style={{ color: 'var(--cyan)' }}>Backend values</span>
        {' '}are authoritative.{' '}
        <span style={{ color: 'var(--violet-hi)' }}>Granite ranks</span>
        {' '}are advisory only — human operator decides.
      </p>

      {/* ── Desktop table ───────────────────────────────── */}
      <div className="cand-table-wrap" role="region" aria-label="Maneuver candidates table">
        <table
          className="cand-table"
          aria-label="Maneuver candidates comparison"
          aria-describedby="cand-table-legend"
        >
          <caption id="cand-table-legend" style={{ display: 'none' }}>
            Maneuver candidates evaluated by the deterministic backend safety gate.
            Click a safe row to select it for the approval workflow.
            Unsafe candidates are shown dimmed and cannot be selected.
          </caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Direction / Label</th>
              <th scope="col">Δv (m/s)</th>
              <th scope="col">Post-miss (km)</th>
              <th scope="col">Fuel (kg)</th>
              <th scope="col">Score</th>
              <th scope="col">Safety</th>
              <th scope="col" style={{ color: 'var(--violet-hi)' }}>Granite Rank</th>
            </tr>
          </thead>
          <tbody>
            {analysis.candidates.map(c => {
              const r         = rankMap[c.candidate_id]
              const isSelected = selectedId === c.candidate_id
              const rowClass   = isSelected
                ? 'row-selected'
                : !c.is_safe
                ? 'row-unsafe'
                : 'row-safe'
              return (
                <tr
                  key={c.candidate_id}
                  className={rowClass}
                  tabIndex={c.is_safe ? 0 : undefined}
                  role="row"
                  aria-selected={isSelected}
                  aria-disabled={!c.is_safe}
                  onClick={() => c.is_safe && onSelect(c.candidate_id)}
                  onKeyDown={e => {
                    if (c.is_safe && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault()
                      onSelect(c.candidate_id)
                    }
                  }}
                  title={!c.is_safe ? `Rejected: ${c.safety_rejection_reason ?? 'unsafe'}` : undefined}
                >
                  <td style={{ color: 'var(--cyan)', fontFamily: 'var(--mono)' }}>
                    {c.candidate_id}
                  </td>
                  <td>{c.label}</td>
                  <td style={{ fontFamily: 'var(--mono)' }}>{fmt(c.delta_v_ms, 2)}</td>
                  <td style={{ fontFamily: 'var(--mono)' }}>
                    {fmt(c.post_maneuver_miss_distance_km, 3)}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)' }}>
                    {fmt(c.fuel_cost_kg, 4)}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)' }}>
                    {fmt(c.baseline_score, 4)}
                  </td>
                  <td>
                    {c.is_safe
                      ? <span className="safe-chip" aria-label="Safe">✓ SAFE</span>
                      : (
                        <span
                          className="unsafe-chip"
                          aria-label={`Rejected: ${c.safety_rejection_reason ?? 'unsafe'}`}
                          title={c.safety_rejection_reason}
                        >
                          ✗ REJECTED
                        </span>
                      )
                    }
                  </td>
                  <td>
                    {r
                      ? <span className="rank-chip" aria-label={`Granite rank ${r.rank}`}>#{r.rank}</span>
                      : <span style={{ color: 'var(--tx-lo)' }}>—</span>
                    }
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ── Mobile card fallback ─────────────────────────── */}
      <div className="cand-cards" aria-label="Maneuver candidates">
        {analysis.candidates.map(c => {
          const r          = rankMap[c.candidate_id]
          const isSelected = selectedId === c.candidate_id
          return (
            <div
              key={c.candidate_id}
              className={`cand-card ${isSelected ? 'selected' : ''} ${!c.is_safe ? 'unsafe' : ''}`}
              onClick={() => c.is_safe && onSelect(c.candidate_id)}
              tabIndex={c.is_safe ? 0 : undefined}
              role="button"
              aria-pressed={isSelected}
              aria-disabled={!c.is_safe}
              onKeyDown={e => {
                if (c.is_safe && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  onSelect(c.candidate_id)
                }
              }}
            >
              <div className="cand-card-header">
                <span className="cand-card-id">{c.candidate_id}</span>
                <span>
                  {c.is_safe
                    ? <span className="safe-chip">✓ SAFE</span>
                    : <span className="unsafe-chip">✗ REJECTED</span>
                  }
                </span>
              </div>
              <div className="cand-card-label">{c.label}</div>
              <div className="cand-card-meta" style={{ marginTop: 'var(--s2)' }}>
                <div className="cand-meta-kv">
                  <span className="k">Δv</span>
                  <span className="v">{fmt(c.delta_v_ms, 2)} m/s</span>
                </div>
                <div className="cand-meta-kv">
                  <span className="k">Post-miss</span>
                  <span className="v">{fmt(c.post_maneuver_miss_distance_km, 3)} km</span>
                </div>
                <div className="cand-meta-kv">
                  <span className="k">Fuel</span>
                  <span className="v">{fmt(c.fuel_cost_kg, 4)} kg</span>
                </div>
                <div className="cand-meta-kv">
                  <span className="k">Score</span>
                  <span className="v">{fmt(c.baseline_score, 4)}</span>
                </div>
                {r && (
                  <div className="cand-meta-kv">
                    <span className="k">Granite</span>
                    <span className="v" style={{ color: 'var(--violet-hi)' }}>#{r.rank}</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Selected candidate Granite explanation */}
      {selectedId && rankMap[selectedId] && (
        <div className="cand-explain" role="region" aria-label="Granite explanation for selected candidate">
          <strong>Granite explanation for {selectedId}:</strong>{' '}
          {rankMap[selectedId].explanation}
          <div style={{ marginTop: 'var(--s2)', fontSize: '10px', fontStyle: 'italic', color: 'var(--tx-lo)' }}>
            Advisory only — human operator approval required before execution.
          </div>
        </div>
      )}
    </div>
  )
}
