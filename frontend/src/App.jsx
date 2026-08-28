/**
 * CollisionGuard AI — Mission-Control Dashboard
 *
 * Human-supervised decision-support prototype.
 * Simulation only — not flight software.
 *
 * UI flow:
 *   1. Select scenario           → step: analyse
 *   2. Run analysis              → step: review
 *   3. Review metrics + maneuvers → step: approve
 *   4. Approve → Confirm         → step: simulate
 *   5. Simulated execution       → step: verify
 *   6. Verification + report     → step: report
 *
 * Scientific rules:
 *   - Every displayed number comes from an actual backend response.
 *   - "Not provided" is shown for any unavailable field.
 *   - Granite output is clearly labelled and separated from physics values.
 *   - Unsafe candidates cannot be selected or approved.
 *   - Simulated execution cannot occur without explicit human approval.
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { apiGet, apiPost, apiDel } from './api/client'
import ConjunctionMetrics  from './components/ConjunctionMetrics'
import ManeuverTable       from './components/ManeuverTable'
import GraniteAdvisory     from './components/GraniteAdvisory'
import ApprovalGate        from './components/ApprovalGate'
import TrajectoryPlot      from './components/TrajectoryPlot'
import './styles.css'

// ─────────────────────────────────────────────────────────────
// WORKFLOW STEPS
// ─────────────────────────────────────────────────────────────
const STEPS = [
  { id: 'analyse',  label: 'Analyse' },
  { id: 'review',   label: 'Review'  },
  { id: 'approve',  label: 'Approve' },
  { id: 'simulate', label: 'Simulate'},
  { id: 'verify',   label: 'Verify'  },
  { id: 'report',   label: 'Report'  },
]

function WorkflowStepper({ currentStep, completedSteps }) {
  return (
    <nav
      className="workflow-stepper"
      aria-label="Decision workflow steps"
      role="list"
    >
      {STEPS.map((step, idx) => {
        const done   = completedSteps.includes(step.id)
        const active = currentStep === step.id
        const state  = done ? 'done' : active ? 'active' : 'waiting'
        return (
          <div key={step.id} style={{ display: 'contents' }} role="listitem">
            <div className="step" aria-current={active ? 'step' : undefined}>
              <div
                className={`step-circle ${state}`}
                aria-label={`${step.label}: ${done ? 'complete' : active ? 'current' : 'pending'}`}
              >
                {done ? '✓' : idx + 1}
              </div>
              <span className={`step-label ${state}`}>{step.label}</span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`step-connector ${done ? 'done' : ''}`} aria-hidden="true" />
            )}
          </div>
        )
      })}
    </nav>
  )
}

// ─────────────────────────────────────────────────────────────
// HEALTH STATUS (top bar)
// ─────────────────────────────────────────────────────────────
function HealthPill() {
  const [health, setHealth] = useState(null)
  const [err, setErr]       = useState(false)

  useEffect(() => {
    apiGet('/health')
      .then(d => setHealth(d))
      .catch(() => setErr(true))
  }, [])

  const status = health?.status ?? (err ? 'error' : 'checking')
  const dotCls = err ? 'error' : (health?.status === 'ok' ? 'ok' : health?.status === 'degraded' ? 'degraded' : '')
  const label  = err ? 'Backend unreachable' : health ? `API ${health.status} · v${health.version}` : 'Checking API…'

  return (
    <div className="app-health-pill" aria-label={`Backend status: ${label}`}>
      <span className={`health-dot ${dotCls}`} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// SCENARIO SELECTOR
// ─────────────────────────────────────────────────────────────
const SCENARIO_META = {
  conjunction_scenario: {
    source: 'Synthetic TLE (committed fallback)',
    quality: 'Screening-level estimate',
  },
  safe_scenario: {
    source: 'Synthetic TLE (committed fallback)',
    quality: 'Screening-level estimate',
  },
}

function ScenarioSelector({ scenarios, selectedId, onSelect, disabled }) {
  if (!scenarios.length) return null
  return (
    <div className="scenario-grid" role="radiogroup" aria-label="Select a scenario">
      {scenarios.map(s => {
        const isConj  = s.scenario_type === 'conjunction'
        const meta    = SCENARIO_META[s.scenario_id] ?? {}
        const checked = selectedId === s.scenario_id
        return (
          <button
            key={s.scenario_id}
            role="radio"
            aria-checked={checked}
            className={`scenario-btn ${checked ? (isConj ? 'active-conj' : 'active-safe') : ''}`}
            onClick={() => onSelect(s.scenario_id)}
            disabled={disabled}
          >
            <div
              className="sb-type"
              style={{ color: isConj ? 'var(--red)' : 'var(--green)' }}
            >
              {isConj ? '⚠ Critical Conjunction' : '✓ Safe Pass'}
            </div>
            <div className="sb-id">{s.scenario_id}</div>
            <div className="sb-desc">{s.description}</div>
            <div className="sb-meta">
              <div className="sb-meta-row">
                <span>Data source</span>
                <span>{meta.source ?? 'Not provided'}</span>
              </div>
              <div className="sb-meta-row">
                <span>Data quality</span>
                <span>{meta.quality ?? 'Not provided'}</span>
              </div>
              {s.epoch_utc && (
                <div className="sb-meta-row">
                  <span>Epoch (UTC)</span>
                  <span>{s.epoch_utc}</span>
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// DATA QUALITY PANEL
// ─────────────────────────────────────────────────────────────
function DataQualityPanel({ quality }) {
  if (!quality?.length) return null
  return (
    <ul className="dq-list" aria-label="Data quality notes">
      {quality.map((q, i) => (
        <li key={i}>
          <span className="dq-field">{q.field}</span>
          <span>{q.note}</span>
        </li>
      ))}
    </ul>
  )
}

// ─────────────────────────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────────────────────────
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

  // Workflow step tracking
  const [currentStep,    setCurrentStep]    = useState('analyse')
  const [completedSteps, setCompletedSteps] = useState([])

  // Status live region ref for screen-reader announcements
  const liveRef = useRef(null)

  function announce(msg) {
    if (liveRef.current) liveRef.current.textContent = msg
  }

  // ── Load scenario list on mount (useEffect, not useState) ──
  useEffect(() => {
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
    setCurrentStep('analyse')
    setCompletedSteps([])
    announce('Running deterministic analysis…')
    try {
      const result = await apiPost(`/scenarios/${scenarioId}/analyse`)
      setAnalysis(result)
      setCurrentStep('review')
      setCompletedSteps(['analyse'])
      announce(`Analysis complete. Risk level: ${result.risk?.label ?? 'unknown'}`)
    } catch (e) {
      setAnalysisErr(e.message)
      announce(`Analysis failed: ${e.message}`)
    } finally {
      setAnalysisLoading(false)
    }
  }, [])

  const handleScenarioSelect = (id) => {
    setSelectedScenario(id)
    setAnalysis(null)
    setSelectedCandidate(null)
    setAnalysisErr('')
    setCurrentStep('analyse')
    setCompletedSteps([])
  }

  const handleInvalidateCache = async () => {
    if (!selectedScenario) return
    await apiDel(`/scenarios/${selectedScenario}/cache`).catch(() => {})
    runAnalysis(selectedScenario)
  }

  const handleCandidateSelect = (id) => {
    setSelectedCandidate(id)
    if (id) {
      setCurrentStep('approve')
      setCompletedSteps(prev => [...new Set([...prev, 'review'])])
    }
  }

  const handleApprovalStepChange = (step) => {
    // Called by ApprovalGate to advance the stepper
    setCurrentStep(step)
    const stepOrder = ['analyse', 'review', 'approve', 'simulate', 'verify', 'report']
    const idx = stepOrder.indexOf(step)
    if (idx > 0) {
      setCompletedSteps(stepOrder.slice(0, idx))
    }
  }

  const handleReset = () => {
    setSelectedCandidate(null)
    setAnalysis(null)
    setResetKey(k => k + 1)
    setCurrentStep('analyse')
    setCompletedSteps([])
    announce('Workflow reset.')
  }

  const selectedCandidateObj = analysis?.candidates?.find(
    c => c.candidate_id === selectedCandidate
  )

  const activeScenario = scenarios.find(s => s.scenario_id === selectedScenario)

  return (
    <div className="app-shell">
      {/* Skip link */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      {/* Screen-reader live region */}
      <div
        ref={liveRef}
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', overflow: 'hidden' }}
      />

      {/* ── TOP BAR ──────────────────────────────────────── */}
      <header className="app-header" role="banner">
        <div className="app-wordmark">
          <div className="app-title">CollisionGuard AI</div>
          <div className="app-subtitle">LEO Conjunction Decision Support</div>
        </div>

        <div
          className="app-scenario-label"
          aria-label={`Active scenario: ${activeScenario?.scenario_id ?? 'None selected'}`}
        >
          {activeScenario
            ? `Scenario: ${activeScenario.scenario_id}`
            : 'No scenario selected'}
        </div>

        <HealthPill />

        <div className="sim-badge" role="note" aria-label="Simulation only — not flight software">
          SIM ONLY
        </div>
      </header>

      {/* ── WORKFLOW STEPPER ─────────────────────────────── */}
      <WorkflowStepper currentStep={currentStep} completedSteps={completedSteps} />

      {/* ── MAIN CONTENT ─────────────────────────────────── */}
      <main id="main-content" className="app-body">

        {/* 1. SCENARIO CONTROL ────────────────────────────── */}
        <section aria-labelledby="section-scenario">
          <div className="card">
            <div className="card-header" id="section-scenario">
              <span>Scenario Control</span>
              {analysis?.cached && (
                <span style={{ fontSize: '0.6rem', color: 'var(--green)', fontWeight: 600 }}>
                  CACHED
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginLeft: '0.5rem' }}
                    onClick={handleInvalidateCache}
                    aria-label="Invalidate cache and re-run analysis"
                  >
                    Refresh
                  </button>
                </span>
              )}
            </div>
            <div className="card-body">
              {scenariosLoad && (
                <div className="state-box" aria-live="polite">
                  <span className="spinner" aria-hidden="true" /> Loading scenarios…
                </div>
              )}
              {scenariosErr && (
                <div className="state-box error" role="alert">
                  Backend unavailable — failed to load scenarios: {scenariosErr}
                </div>
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
                      aria-disabled={!selectedScenario || analysisLoading}
                      aria-label={
                        !selectedScenario
                          ? 'Select a scenario first'
                          : analysisLoading
                          ? 'Analysis running…'
                          : 'Run deterministic analysis'
                      }
                    >
                      {analysisLoading
                        ? <><span className="spinner" aria-hidden="true" />Analysing…</>
                        : 'Run Deterministic Analysis'}
                    </button>
                    {analysisLoading && (
                      <span className="action-hint" aria-live="polite">
                        Propagating orbits · Evaluating maneuvers · Requesting advisory…
                      </span>
                    )}
                    {!selectedScenario && !analysisLoading && (
                      <span className="action-hint">Select a scenario above to enable analysis.</span>
                    )}
                  </div>
                </>
              )}
              {analysisErr && (
                <div
                  className="state-box error"
                  role="alert"
                  style={{ marginTop: '0.5rem', padding: '0.75rem' }}
                >
                  Analysis failed: {analysisErr}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* 2. MISSION SUMMARY STRIP ───────────────────────── */}
        {analysis && (
          <section aria-labelledby="section-summary">
            <div className="card">
              <div className="card-header">
                <span id="section-summary">Mission Summary</span>
                <span style={{ fontSize: '0.6rem', fontWeight: 400, textTransform: 'none', color: 'var(--muted)' }}>
                  {new Date(analysis.analysis_timestamp).toUTCString()}
                  {analysis.cached && ' · from cache'}
                </span>
              </div>
              <div className="card-body">
                <ConjunctionMetrics analysis={analysis} />
              </div>
            </div>
          </section>
        )}

        {/* 3. PRIMARY VISUALIZATION ───────────────────────── */}
        {analysis && (
          <section aria-labelledby="section-viz">
            <div className="card">
              <div className="card-header">
                <span id="section-viz">3D Trajectory — Closest Approach</span>
                <span style={{ fontSize: '0.6rem', fontWeight: 400, textTransform: 'none', color: 'var(--muted)' }}>
                  Approximate circular orbits · Not to scale
                </span>
              </div>
              <div className="card-body" style={{ padding: '0.6rem' }}>
                <TrajectoryPlot
                  analysis={analysis}
                  selectedCandidate={selectedCandidateObj}
                />
              </div>
            </div>
          </section>
        )}

        {/* 4. MANEUVER COMPARISON ─────────────────────────── */}
        {analysis && (
          <section aria-labelledby="section-maneuvers">
            <div className="card">
              <div className="card-header">
                <span id="section-maneuvers">Maneuver Candidates</span>
                <span style={{ fontSize: '0.6rem', fontWeight: 400, textTransform: 'none', color: 'var(--muted)' }}>
                  {analysis.safe_count}/{analysis.total_count} safe
                  &nbsp;·&nbsp;
                  select a safe candidate to proceed
                </span>
              </div>
              <div className="card-body">
                <ManeuverTable
                  analysis={analysis}
                  advisory={analysis.advisory}
                  selectedId={selectedCandidate}
                  onSelect={handleCandidateSelect}
                />
                {analysis.evaluation_note && (
                  <p
                    style={{
                      marginTop: '0.65rem',
                      fontSize: '0.62rem',
                      color: 'var(--yellow)',
                      borderLeft: '2px solid var(--yellow-border)',
                      paddingLeft: '0.5rem',
                    }}
                    role="note"
                  >
                    {analysis.evaluation_note}
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* 5. GRANITE ADVISORY ────────────────────────────── */}
        {analysis?.advisory && (
          <section aria-labelledby="section-advisory">
            <div className="card">
              <div className="card-header">
                <span id="section-advisory">AI Advisory — Separate from Backend Safety Gate</span>
                <span style={{ fontSize: '0.6rem', fontWeight: 400, textTransform: 'none', color: 'var(--muted)' }}>
                  Backend physics values are authoritative
                </span>
              </div>
              <div className="card-body">
                <GraniteAdvisory advisory={analysis.advisory} />
              </div>
            </div>
          </section>
        )}

        {/* 6. DATA QUALITY ────────────────────────────────── */}
        {analysis?.data_quality && (
          <section aria-labelledby="section-dq">
            <div className="card">
              <div className="card-header">
                <span id="section-dq">Data Quality &amp; Scientific Limitations</span>
              </div>
              <div className="card-body">
                <DataQualityPanel quality={analysis.data_quality} />
              </div>
            </div>
          </section>
        )}

        {/* 7. HUMAN APPROVAL GATE ─────────────────────────── */}
        {analysis && (
          <section aria-labelledby="section-approval">
            <div className="card">
              <div className="card-header">
                <span id="section-approval">Human Approval Gate — Simulated Execution</span>
                <span style={{ fontSize: '0.6rem', fontWeight: 400, textTransform: 'none', color: 'var(--yellow)' }}>
                  Human approval required before execution
                </span>
              </div>
              <div className="card-body">
                <ApprovalGate
                  key={resetKey}
                  scenarioId={selectedScenario}
                  selectedId={selectedCandidate}
                  analysis={analysis}
                  onReset={handleReset}
                  onStepChange={handleApprovalStepChange}
                />
              </div>
            </div>
          </section>
        )}
      </main>

      {/* ── FOOTER ───────────────────────────────────────── */}
      <footer className="app-footer" role="contentinfo">
        Human-supervised decision-support prototype · Simulation only — not flight software ·
        CollisionGuard AI
      </footer>
    </div>
  )
}
