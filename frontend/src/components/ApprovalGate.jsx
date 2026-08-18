/** ApprovalGate -- approval confirmation and execution flow */
import { useState } from 'react'
import { apiPost } from '../api/client'

export default function ApprovalGate({
  scenarioId, selectedId, analysis, onReset,
}) {
  const [phase, setPhase]     = useState('idle')   // idle | confirming | approved | executing | done | rejected | error
  const [execResult, setExecResult] = useState(null)
  const [report, setReport]   = useState(null)
  const [err, setErr]         = useState('')

  const candidate = analysis?.candidates?.find(c => c.candidate_id === selectedId)
  if (!candidate) return null

  async function handleApprove() {
    setPhase('confirming')
  }

  async function handleConfirm() {
    setErr('')
    try {
      setPhase('approved')
      const res = await apiPost(`/scenarios/${scenarioId}/approve`, {
        scenario_id: scenarioId,
        candidate_id: selectedId,
        operator_id: 'OPERATOR',
      })
      if (!res.safety_gate_passed) {
        setPhase('rejected')
        setErr(res.rejection_reason ?? 'Safety gate rejected this candidate.')
        return
      }
      setPhase('executing')
      const execRes = await apiPost(`/scenarios/${scenarioId}/execute`, {
        scenario_id: scenarioId,
        candidate_id: selectedId,
        operator_id: 'OPERATOR',
      })
      setExecResult(execRes)
      setPhase('done')
      // Request incident report
      try {
        const rep = await apiPost(`/scenarios/${scenarioId}/incident-report`, {
          scenario_id: scenarioId,
          candidate_id: selectedId,
          operator_id: 'OPERATOR',
        })
        setReport(rep)
      } catch (_) { /* non-fatal */ }
    } catch (e) {
      setErr(e.message)
      setPhase('error')
    }
  }

  function handleCancel() { setPhase('idle') }

  function handleReset() {
    setPhase('idle')
    setExecResult(null)
    setReport(null)
    setErr('')
    onReset()
  }

  // Safety: never allow executing without explicit backend approval
  const canApprove = candidate?.is_safe === true && phase === 'idle'

  return (
    <div>
      {phase === 'idle' && (
        <div className="action-bar">
          <button
            className="btn btn-warn"
            disabled={!canApprove}
            onClick={handleApprove}
            title={!canApprove ? 'Select a safe candidate first' : undefined}
          >
            Request Simulated Execution
          </button>
          <button className="btn btn-ghost" onClick={handleReset}>Reset</button>
          <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>
            {!canApprove && 'Select a safe candidate to enable approval.'}
          </span>
        </div>
      )}

      {phase === 'confirming' && (
        <div className="confirm-overlay">
          <h3>Confirm Simulated Execution</h3>
          <p>
            You are about to approve <strong>{candidate.label}</strong> ({selectedId})
            for <strong>simulated execution</strong>.<br />
            Delta-v: {candidate.delta_v_ms.toFixed(2)} m/s &nbsp;|&nbsp;
            Est. fuel: {candidate.fuel_cost_kg?.toFixed(4)} kg &nbsp;|&nbsp;
            Post-maneuver miss: {candidate.post_maneuver_miss_distance_km?.toFixed(3)} km
            <br /><br />
            <span style={{ color: 'var(--yellow)', fontWeight: 700 }}>
              This is SIMULATION ONLY — not flight software. No spacecraft will be commanded.
            </span>
          </p>
          <div className="action-bar">
            <button className="btn btn-danger" onClick={handleConfirm}>
              Confirm — Simulate Execution
            </button>
            <button className="btn btn-ghost" onClick={handleCancel}>Cancel</button>
          </div>
        </div>
      )}

      {(phase === 'approved' || phase === 'executing') && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--muted)', fontSize: '0.8rem' }}>
          <span className="spinner" />
          {phase === 'approved' ? 'Submitting approval…' : 'Simulating execution…'}
        </div>
      )}

      {phase === 'done' && execResult && (
        <div>
          <div className="exec-result">
            <h3>Simulated Execution Complete</h3>
            <div className="exec-kv"><span className="k">Status</span><span>{execResult.status}</span></div>
            <div className="exec-kv"><span className="k">Candidate</span><span>{execResult.candidate_id}</span></div>
            <div className="exec-kv"><span className="k">Delta-v applied</span><span>{execResult.delta_v_applied_ms?.toFixed(2)} m/s</span></div>
            <div className="exec-kv"><span className="k">Fuel consumed</span><span>{execResult.fuel_consumed_kg?.toFixed(4)} kg</span></div>
            <div className="exec-kv"><span className="k">Post-maneuver miss</span><span>{execResult.post_maneuver_miss_distance_km?.toFixed(3)} km</span></div>
            <div className="exec-kv"><span className="k">Executed at</span><span>{execResult.executed_at ? new Date(execResult.executed_at).toUTCString() : '—'}</span></div>
            <div style={{ marginTop: '0.6rem', fontSize: '0.62rem', color: 'var(--yellow)' }}>
              {execResult.execution_label}
            </div>
          </div>

          {report && (
            <div style={{ marginTop: '1rem' }}>
              <div className="card-header" style={{ fontSize: '0.62rem' }}>
                Incident Report
                <span style={{ color: 'var(--muted)', textTransform: 'none', fontWeight: 400 }}>
                  Generated by: {report.generated_by}
                </span>
              </div>
              <pre className="incident-report">{report.report_text}</pre>
            </div>
          )}

          <div className="action-bar" style={{ marginTop: '0.75rem' }}>
            <button className="btn btn-ghost" onClick={handleReset}>New Analysis</button>
          </div>
        </div>
      )}

      {phase === 'rejected' && (
        <div className="exec-result rejected">
          <h3>Safety Gate: Execution Rejected</h3>
          <p style={{ fontSize: '0.72rem', marginTop: '0.4rem', color: 'var(--red)' }}>{err}</p>
          <div className="action-bar" style={{ marginTop: '0.75rem' }}>
            <button className="btn btn-ghost" onClick={handleReset}>Reset</button>
          </div>
        </div>
      )}

      {phase === 'error' && (
        <div className="exec-result rejected">
          <h3>Error</h3>
          <p style={{ fontSize: '0.72rem', marginTop: '0.4rem' }}>{err}</p>
          <div className="action-bar" style={{ marginTop: '0.75rem' }}>
            <button className="btn btn-ghost" onClick={() => setPhase('idle')}>Retry</button>
            <button className="btn btn-ghost" onClick={handleReset}>Reset</button>
          </div>
        </div>
      )}
    </div>
  )
}
