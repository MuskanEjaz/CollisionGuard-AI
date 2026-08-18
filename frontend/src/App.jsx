/**
 * CollisionGuard AI — Phase 7 Dashboard
 *
 * Human-supervised decision-support prototype.
 * Simulation only — not flight software.
 *
 * UI flow:
 *   1. Select scenario
 *   2. Run analysis (POST /analyse — cached after first call)
 *   3. View conjunction metrics, trajectory, maneuver table, Granite advisory
 *   4. Select a candidate
 *   5. Approve -> Confirm -> Simulated execution -> Incident report
 */
import { useState, useCallback } from 'react'
import { apiGet, apiPost, apiDel } from './api/client'
import ConjunctionMetrics  from './components/ConjunctionMetrics'
import ManeuverTable       from './components/ManeuverTable'
import GraniteAdvisory     from './components/GraniteAdvisory'
import ApprovalGate        from './components/ApprovalGate'
import TrajectoryPlot      from './components/TrajectoryPlot'
import './styles.css'

// ---------------------------------------------------------------------------
// Scenario selector
// ---------------------------------------------------------------------------
function ScenarioSelector({ scenarios, selectedId, onSelect, disabled }) {
  if (!scenarios.length) {
    return <div className="state-box">No scenarios loaded</div>
  }
  return (
    <div className="scenario-grid">
      {scenarios.map(s => (
        <button
          key={s.scenario_id}
          className={
            `scenario-btn ${
              selectedId === s.scenario_id
                ? s.scenario_type === 'conjunction' ? 'active-conj' : 'active-safe'
                : ''
            }`
          }
          onClick={() => onSelect(s.scenario_id)}
          disabled={disabled}
        >
          <div className={`sb-type ${s.scenario_type === 'conjunction' ? '' : ''}`}
               style={{ color: s.scenario_type === 'conjunction' ? 'var(--red)' : 'var(--green)' }}>
            {s.scenario_type === 'conjunction' ? 'Critical Conjunction' : 'Safe Pass'}
          </div>
          <div className="sb-id">{s.scenario_id}</div>
          <div className="sb-desc">{s.description}</div>
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Data quality panel
// ---------------------------------------------------------------------------
function DataQualityPanel({ quality }) {
  if (!quality?.length) return null
  return (
    <ul className="dq-list">
      {quality.map((q, i) => (
        <li key={i}>
          <span className="dq-field">{q.field}</span>
          <span>{q.note}</span>
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [scenarios,     setScenarios]     = useState([])
  const [scenariosErr,  setScenariosErr]  = useState('')
  const [scenariosLoad, setScenariosLoad] = useState(false)

  const [selectedScenario, setSelectedScenario] = useState(null)
  const [analysis,         setAnalysis]          = useState(null)
  const [analysisLoading,  setAnalysisLoading]   = useState(false)
  const [analysisErr,      setAnalysisErr]        = useState('')

  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [resetKey,          setResetKey]           = useState(0)

  // Load scenario list on mount
  useState(() => {
    setScenariosLoad(true)
    apiGet('/scenarios')
      .then(d => setScenarios(d.scenarios ?? []))
      .catch(e => setScenariosErr(e.message))
      .finally(() => setScenariosLoad(false))
  }, [])

  const runAnalysis = useCallback(async (scenarioId) => {
    if (!scenarioId) return
    setAnalysisLoading(true)
    setAnalysisErr('')
    setAnalysis(null)
    setSelectedCandidate(null)
    try {
      const result = await apiPost(`/scenarios/${scenarioId}/analyse`)
      setAnalysis(result)
    } catch (e) {
      setAnalysisErr(e.message)
    } finally {
      setAnalysisLoading(false)
    }
  }, [])

  const handleScenarioSelect = (id) => {
    setSelectedScenario(id)
    setAnalysis(null)
    setSelectedCandidate(null)
    setAnalysisErr('')
  }

  const handleInvalidateCache = async () => {
    if (!selectedScenario) return
    await apiDel(`/scenarios/${selectedScenario}/cache`).catch(() => {})
    runAnalysis(selectedScenario)
  }

  const handleReset = () => {
    setSelectedCandidate(null)
    setAnalysis(null)
    setResetKey(k => k + 1)
  }

  const selectedCandidateObj = analysis?.candidates?.find(
    c => c.candidate_id === selectedCandidate
  )

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div>
          <div className="app-title">CollisionGuard AI</div>
          <div className="app-subtitle">
            {analysis?.prototype_label ?? 'Human-supervised decision-support prototype'}
          </div>
        </div>
        <div className="app-disclaimer">
          {analysis?.simulation_label ?? 'Simulation only — not flight software'}
        </div>
      </header>

      <main className="app-body">
        {/* ── 1. Scenario selector ─────────────────────────────── */}
        <div className="card">
          <div className="card-header">
            Scenario Selection
            {analysis?.cached && (
              <span style={{ fontSize: '0.62rem', color: 'var(--green)', fontWeight: 400 }}>
                CACHED &nbsp;
                <button
                  className="btn btn-ghost"
                  style={{ padding: '0.1rem 0.4rem', fontSize: '0.6rem' }}
                  onClick={handleInvalidateCache}
                >
                  Refresh
                </button>
              </span>
            )}
          </div>
          <div className="card-body">
            {scenariosLoad && (
              <div className="state-box"><span className="spinner" />Loading scenarios…</div>
            )}
            {scenariosErr && (
              <div className="state-box error">Failed to load scenarios: {scenariosErr}</div>
            )}
            {!scenariosLoad && !scenariosErr && (
              <>
                <ScenarioSelector
                  scenarios={scenarios}
                  selectedId={selectedScenario}
                  onSelect={handleScenarioSelect}
                  disabled={analysisLoading}
                />
                <div className="action-bar" style={{ marginTop: '0.9rem' }}>
                  <button
                    className="btn btn-primary"
                    disabled={!selectedScenario || analysisLoading}
                    onClick={() => runAnalysis(selectedScenario)}
                  >
                    {analysisLoading
                      ? <><span className="spinner" />Analysing…</>
                      : 'Run Deterministic Analysis'}
                  </button>
                  {analysisLoading && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--muted)' }}>
                      Propagating + evaluating maneuvers + Granite advisory…
                    </span>
                  )}
                </div>
              </>
            )}
            {analysisErr && (
              <div className="state-box error" style={{ marginTop: '0.5rem' }}>
                Analysis failed: {analysisErr}
              </div>
            )}
          </div>
        </div>

        {/* ── 2. Conjunction metrics ───────────────────────────── */}
        {analysis && (
          <div className="card">
            <div className="card-header">
              Conjunction Analysis
              <span style={{ fontSize: '0.62rem', color: 'var(--muted)', fontWeight: 400, textTransform: 'none' }}>
                {new Date(analysis.analysis_timestamp).toUTCString()}
              </span>
            </div>
            <div className="card-body">
              <ConjunctionMetrics analysis={analysis} />
            </div>
          </div>
        )}

        {/* ── 3. Trajectory visualisation ─────────────────────── */}
        {analysis && (
          <div className="card">
            <div className="card-header">
              3D Trajectory — Closest Approach Visualisation
            </div>
            <div className="card-body" style={{ padding: '0.5rem' }}>
              <TrajectoryPlot
                analysis={analysis}
                selectedCandidate={selectedCandidateObj}
              />
            </div>
          </div>
        )}

        {/* ── 4. Maneuver candidates ───────────────────────────── */}
        {analysis && (
          <div className="card">
            <div className="card-header">
              Maneuver Candidates
              <span style={{ fontSize: '0.62rem', color: 'var(--muted)', fontWeight: 400, textTransform: 'none' }}>
                {analysis.safe_count}/{analysis.total_count} safe &nbsp;|&nbsp; click a safe row to select
              </span>
            </div>
            <div className="card-body">
              <ManeuverTable
                analysis={analysis}
                advisory={analysis.advisory}
                selectedId={selectedCandidate}
                onSelect={setSelectedCandidate}
              />
              {analysis.evaluation_note && (
                <div style={{
                  marginTop: '0.75rem',
                  fontSize: '0.62rem',
                  color: 'var(--yellow)',
                  borderLeft: '2px solid rgba(246,224,94,0.3)',
                  paddingLeft: '0.5rem',
                }}>
                  {analysis.evaluation_note}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 5. Granite advisory ──────────────────────────────── */}
        {analysis?.advisory && (
          <div className="card">
            <div className="card-header">
              AI Advisory — Separate from Backend Safety Gate
            </div>
            <div className="card-body">
              <GraniteAdvisory advisory={analysis.advisory} />
            </div>
          </div>
        )}

        {/* ── 6. Data quality ──────────────────────────────────── */}
        {analysis?.data_quality && (
          <div className="card">
            <div className="card-header">Data Quality &amp; Limitations</div>
            <div className="card-body">
              <DataQualityPanel quality={analysis.data_quality} />
            </div>
          </div>
        )}

        {/* ── 7. Approval gate ─────────────────────────────────── */}
        {analysis && (
          <div className="card">
            <div className="card-header">Human Approval Gate — Simulated Execution</div>
            <div className="card-body">
              <ApprovalGate
                key={resetKey}
                scenarioId={selectedScenario}
                selectedId={selectedCandidate}
                analysis={analysis}
                onReset={handleReset}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
