/**
 * CollisionGuard AI — Mission-Console Dashboard
 *
 * Layout: sticky command-bar + stepper → split workspace (viz left, risk right)
 * → lower sections (maneuvers, advisory, approval)
 *
 * Human-supervised decision-support prototype. Simulation only — not flight software.
 * All displayed values come from actual backend API responses.
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { apiGet, apiPost, apiDel } from './api/client'
import TrajectoryPlot      from './components/TrajectoryPlot'
import ConjunctionMetrics  from './components/ConjunctionMetrics'
import ManeuverTable       from './components/ManeuverTable'
import GraniteAdvisory     from './components/GraniteAdvisory'
import ApprovalGate        from './components/ApprovalGate'
import LiveCelestrakPanel  from './components/LiveCelestrakPanel'
import './styles.css'

// ─── STEPS ───────────────────────────────────────────────────────
const STEPS = [
  { id: 'analyse',  label: 'Analyse'  },
  { id: 'review',   label: 'Review'   },
  { id: 'approve',  label: 'Approve'  },
  { id: 'simulate', label: 'Simulate' },
  { id: 'verify',   label: 'Verify'   },
  { id: 'report',   label: 'Report'   },
]

function Stepper({ currentStep, completedSteps }) {
  return (
    <nav className="stepper" aria-label="Decision workflow" role="list">
      {STEPS.map((s, i) => {
        const done   = completedSteps.includes(s.id)
        const active = currentStep === s.id
        const state  = done ? 'done' : active ? 'active' : 'waiting'
        return (
          <div key={s.id} style={{ display: 'contents' }} role="listitem">
            <div className="step" aria-current={active ? 'step' : undefined}>
              <div className={`step-node ${state}`}
                   aria-label={`${s.label}: ${done ? 'complete' : active ? 'current' : 'pending'}`}>
                {done ? '✓' : i + 1}
              </div>
              <span className={`step-lbl ${state}`}>{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`step-connector ${done ? 'done' : ''}`} aria-hidden="true" />
            )}
          </div>
        )
      })}
    </nav>
  )
}

// ─── HEALTH PILL ─────────────────────────────────────────────────
function HealthPill() {
  const [health, setHealth] = useState(null)
  const [err,    setErr]    = useState(false)
  useEffect(() => {
    apiGet('/health').then(setHealth).catch(() => setErr(true))
  }, [])
  const dotCls = err ? 'error' : health?.status === 'ok' ? 'ok' : health ? 'degraded' : ''
  const label  = err
    ? 'Backend unreachable'
    : health ? `API ${health.status} · v${health.version}` : 'Checking…'
  return (
    <div className="health-pill" aria-label={`Backend status: ${label}`}>
      <span className={`health-dot ${dotCls}`} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

// ─── SCENARIO BUTTONS ────────────────────────────────────────────
const SCENARIO_META = {
  conjunction_scenario: { source: 'Synthetic TLE', quality: 'Screening-level' },
  safe_scenario:        { source: 'Synthetic TLE', quality: 'Screening-level' },
}

function ScenarioGrid({ scenarios, selectedId, onSelect, disabled }) {
  if (!scenarios.length) return null
  return (
    <div className="scenario-grid" role="radiogroup" aria-label="Select scenario">
      {scenarios.map(s => {
        const conj    = s.scenario_type === 'conjunction'
        const checked = selectedId === s.scenario_id
        const meta    = SCENARIO_META[s.scenario_id] ?? {}
        return (
          <button
            key={s.scenario_id}
            role="radio"
            aria-checked={checked}
            className={`scenario-btn ${checked ? (conj ? 'active-conj' : 'active-safe') : ''}`}
            onClick={() => onSelect(s.scenario_id)}
            disabled={disabled}
          >
            <div className="sb-type" style={{ color: conj ? 'var(--red)' : 'var(--green-hi)' }}>
              {conj ? '⚠ Critical Conjunction' : '✓ Safe Pass'}
            </div>
            <div className="sb-id">{s.scenario_id}</div>
            <div className="sb-desc">{s.description}</div>
            <div className="sb-meta">
              <div className="sb-meta-row">
                <span>Source</span>
                <span>{meta.source ?? 'Not provided'}</span>
              </div>
              <div className="sb-meta-row">
                <span>Quality</span>
                <span>{meta.quality ?? 'Not provided'}</span>
              </div>
              {s.epoch_utc && (
                <div className="sb-meta-row">
                  <span>Epoch</span>
                  <span style={{ fontFamily: 'var(--mono)' }}>{s.epoch_utc}</span>
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// ─── DATA QUALITY ─────────────────────────────────────────────────
function DataQuality({ quality }) {
  if (!quality?.length) return null
  return (
    <ul className="dq-list" aria-label="Data quality notes">
      {quality.map((q, i) => (
        <li key={i} className="dq-item">
          <span className="dq-field">{q.field}</span>
          <span>{q.note}</span>
        </li>
      ))}
    </ul>
  )
}

// ─── MAIN APP ────────────────────────────────────────────────────
// ─── SCENARIO MODE ───────────────────────────────────────────────
// 'synthetic' = committed JSON scenarios; 'live' = live CelesTrak fetch
const SCENARIO_MODES = [
  { id: 'synthetic', label: 'Synthetic Demo'   },
  { id: 'live',      label: '● Live CelesTrak' },
]

export default function App() {
  const [scenarios,      setScenarios]      = useState([])
  const [scenariosErr,   setScenariosErr]   = useState('')
  const [scenariosLoad,  setScenariosLoad]  = useState(false)
  const [selectedScenario, setSelectedScenario] = useState(null)
  const [scenarioMode,   setScenarioMode]   = useState('synthetic')  // 'synthetic' | 'live'
  const [liveResult,     setLiveResult]     = useState(null)         // LiveAnalysisResponse
  const [analysis,       setAnalysis]       = useState(null)
  const [analysisLoading,setAnalysisLoading]= useState(false)
  const [analysisErr,    setAnalysisErr]    = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [resetKey,       setResetKey]       = useState(0)
  const [currentStep,    setCurrentStep]    = useState('analyse')
  const [completedSteps, setCompletedSteps] = useState([])
  const liveRef = useRef(null)

  function announce(msg) {
    if (liveRef.current) liveRef.current.textContent = msg
  }

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
      announce(`Analysis complete. Risk: ${result.risk?.label ?? 'unknown'}`)
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
    setCurrentStep(step)
    const order = ['analyse','review','approve','simulate','verify','report']
    const idx   = order.indexOf(step)
    if (idx > 0) setCompletedSteps(order.slice(0, idx))
  }

  // Handle live CelesTrak analysis and guarantee trajectory visualization.
  // The live endpoint may return its initial scientific analysis without the
  // sampled visualization contract. In that case, automatically request the
  // registered scenario's full analysis — no second user click is required.
  const handleLiveAnalysis = useCallback(async (liveAnalysisResponse) => {
    setLiveResult(liveAnalysisResponse)

    const initialAnalysis = liveAnalysisResponse?.analysis
    if (!initialAnalysis?.scenario_id) {
      setAnalysisErr('Live analysis response did not include a scenario ID.')
      return
    }

    setAnalysisLoading(true)
    setAnalysisErr('')
    setSelectedCandidate(null)
    setCurrentStep('analyse')
    announce('Preparing live trajectory visualization…')

    try {
      let completeAnalysis = initialAnalysis

      if (!initialAnalysis.visualization) {
        completeAnalysis = await apiPost(
          `/scenarios/${initialAnalysis.scenario_id}/analyse`
        )
      }

      if (!completeAnalysis?.visualization) {
        throw new Error(
          'Backend analysis completed but did not return trajectory visualization data.'
        )
      }

      setAnalysis(completeAnalysis)
      setSelectedScenario(completeAnalysis.scenario_id)
      setCurrentStep('review')
      setCompletedSteps(['analyse'])

      announce(
        `Live analysis complete. Risk: ${
          completeAnalysis.risk?.label ?? 'unknown'
        }. Trajectory visualization ready.`
      )
    } catch (error) {
      setAnalysis(null)
      setSelectedScenario(initialAnalysis.scenario_id)
      setAnalysisErr(error.message)
      announce(`Live trajectory visualization failed: ${error.message}`)
    } finally {
      setAnalysisLoading(false)
    }
  }, [])
  const handleModeChange = (mode) => {
    setScenarioMode(mode)
    // Reset analysis state when switching modes
    setAnalysis(null)
    setSelectedScenario(null)
    setSelectedCandidate(null)
    setLiveResult(null)
    setAnalysisErr('')
    setCurrentStep('analyse')
    setCompletedSteps([])
  }

  const handleReset = () => {
    setSelectedCandidate(null)
    setAnalysis(null)
    setLiveResult(null)
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
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      {/* Skip link */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      {/* Live region */}
      <div ref={liveRef} aria-live="polite" aria-atomic="true"
           style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, overflow: 'hidden' }} />

      {/* ── COMMAND BAR ─────────────────────────────────── */}
      <header className="cmd-bar" role="banner">
        <div className="cmd-brand">
          <span className="cmd-title">CollisionGuard AI</span>
          <span className="cmd-sub">LEO Conjunction Decision Support</span>
        </div>

        <div className="cmd-divider" aria-hidden="true" />

        <div className="cmd-scenario-chip" aria-label={`Active scenario: ${activeScenario?.scenario_id ?? 'none'}`}>
          {activeScenario ? activeScenario.scenario_id : 'No scenario selected'}
        </div>

        <div className="cmd-spacer" />

        <div className="cmd-actions">
          <HealthPill />
          <div className="cmd-divider" aria-hidden="true" />
          {selectedScenario && !analysisLoading && (
            <button
              className="btn btn-primary"
              onClick={() => runAnalysis(selectedScenario)}
              aria-label="Run or re-run deterministic analysis"
            >
              {analysis ? 'Re-analyse' : 'Analyse'}
            </button>
          )}
          {analysisLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--tx-lo)' }}>
              <span className="spinner" aria-hidden="true" />
              Analysing…
            </div>
          )}
          {analysis?.cached && (
            <button className="btn btn-ghost btn-sm" onClick={handleInvalidateCache}
                    aria-label="Invalidate cache and re-run">
              Refresh Cache
            </button>
          )}
          <div className="sim-chip" role="note" aria-label="Simulation only — not flight software">
            SIM ONLY
          </div>
        </div>
      </header>

      {/* ── STEPPER ─────────────────────────────────────── */}
      <Stepper currentStep={currentStep} completedSteps={completedSteps} />

      {/* ── SCENARIO CONTROL ─────────────────────────────── */}
      <section className="scenario-control" aria-labelledby="scen-hd">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 id="scen-hd" style={{ fontSize: 12, fontWeight: 700, color: 'var(--tx-lo)',
                                    textTransform: 'uppercase', letterSpacing: '.07em' }}>
            Scenario Selection
          </h2>
          {analysisErr && (
            <span style={{ fontSize: 11, color: 'var(--red)' }} role="alert">
              Analysis failed: {analysisErr}
            </span>
          )}
        </div>

        {/* Mode tabs: Synthetic Demo | Live CelesTrak */}
        <div className="scenario-tabs" role="tablist" aria-label="Scenario source mode">
          {SCENARIO_MODES.map(m => (
            <button
              key={m.id}
              role="tab"
              aria-selected={scenarioMode === m.id}
              className={`scenario-tab ${scenarioMode === m.id ? (m.id === 'live' ? 'active-live' : 'active') : ''}`}
              onClick={() => handleModeChange(m.id)}
              disabled={analysisLoading}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Synthetic scenarios */}
        {scenarioMode === 'synthetic' && (
          <>
            {scenariosLoad && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--tx-lo)' }}>
                <span className="spinner" aria-hidden="true" /> Loading scenarios…
              </div>
            )}
            {scenariosErr && (
              <div role="alert" style={{ fontSize: 12, color: 'var(--red)' }}>
                Backend unavailable — cannot load scenarios: {scenariosErr}
              </div>
            )}
            {!scenariosLoad && !scenariosErr && (
              <>
                <ScenarioGrid
                  scenarios={scenarios}
                  selectedId={selectedScenario}
                  onSelect={handleScenarioSelect}
                  disabled={analysisLoading}
                />
                {!selectedScenario && (
                  <p style={{ fontSize: 11, color: 'var(--tx-lo)', marginTop: 8 }}>
                    Select a scenario above, then click Analyse in the command bar.
                  </p>
                )}
              </>
            )}
          </>
        )}

        {/* Live CelesTrak mode */}
        {scenarioMode === 'live' && (
          <LiveCelestrakPanel
            onAnalysis={handleLiveAnalysis}
            disabled={analysisLoading}
          />
        )}
      </section>

      {/* ── CONTEXT STRIP ─────────────────────────────────── */}
      {analysis && (
        <div className="ctx-strip" aria-label="Analysis context">
          <div className="ctx-item">
            <span className="ctx-label">Scenario</span>
            <span className="ctx-value">{analysis.scenario_id}</span>
          </div>
          <div className="ctx-item">
            <span className="ctx-label">Analysed</span>
            <span className="ctx-value">{new Date(analysis.analysis_timestamp).toUTCString()}</span>
          </div>
          <div className="ctx-item">
            <span className="ctx-label">Cache</span>
            <span className="ctx-value">{analysis.cached ? 'HIT' : 'MISS'}</span>
          </div>
          <div className="ctx-item">
            <span className="ctx-label">Threshold</span>
            <span className="ctx-value">{analysis.conjunction_threshold_km} km</span>
          </div>
          <div className="ctx-item">
            <span className="ctx-label">Candidates</span>
            <span className="ctx-value">{analysis.safe_count}/{analysis.total_count} safe</span>
          </div>
        </div>
      )}

      {/* ── MAIN WORKSPACE ────────────────────────────────── */}
      <main id="main-content">
        {/* above-the-fold split: viz left, risk right */}
        <div className="workspace">
          {/* LEFT — Trajectory Visualization */}
          <div aria-labelledby="viz-title">
            <TrajectoryPlot
              analysis={analysis}
              selectedCandidate={selectedCandidateObj}
              loading={analysisLoading}
            />
          </div>

          {/* RIGHT — Risk Panel */}
          <div className="risk-panel" aria-label="Risk status panel">
            {!analysis && !analysisLoading && (
              <div style={{ fontSize: 12, color: 'var(--tx-lo)', paddingTop: 16, lineHeight: 1.6 }}>
                Run analysis to see risk metrics, miss distance, and time to closest approach.
              </div>
            )}
            {analysisLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--tx-lo)' }}>
                <span className="spinner" aria-hidden="true" />
                Computing propagation and maneuver evaluation…
              </div>
            )}
            {analysis && <ConjunctionMetrics analysis={analysis} />}
          </div>
        </div>

        {/* ── BELOW FOLD ──────────────────────────────────── */}
        {analysis && (
          <div className="lower-body">

            {/* Maneuver candidates */}
            <section aria-labelledby="maneuverhd">
              <div className="card">
                <div className="card-hd">
                  <span id="maneuverhd">Maneuver Candidates</span>
                  <span className="card-hd-sub">
                    {analysis.safe_count}/{analysis.total_count} safe · select a safe row to proceed
                  </span>
                </div>
                <div className="card-bd">
                  <ManeuverTable
                    analysis={analysis}
                    advisory={analysis.advisory}
                    selectedId={selectedCandidate}
                    onSelect={handleCandidateSelect}
                  />
                  {analysis.evaluation_note && (
                    <p style={{ marginTop: 10, fontSize: 11, color: 'var(--amber)',
                                borderLeft: '2px solid var(--amber-bdr)', paddingLeft: 8 }}>
                      {analysis.evaluation_note}
                    </p>
                  )}
                </div>
              </div>
            </section>

            {/* Granite advisory */}
            {analysis.advisory && (
              <section aria-labelledby="advisoryhd">
                <div className="card">
                  <div className="card-hd">
                    <span id="advisoryhd">AI Advisory</span>
                    <span className="card-hd-sub">Backend physics values are authoritative</span>
                  </div>
                  <div className="card-bd">
                    <GraniteAdvisory advisory={analysis.advisory} />
                  </div>
                </div>
              </section>
            )}

            {/* Data quality */}
            {analysis.data_quality && (
              <section aria-labelledby="dqhd">
                <div className="card">
                  <div className="card-hd"><span id="dqhd">Data Quality &amp; Limitations</span></div>
                  <div className="card-bd">
                    <DataQuality quality={analysis.data_quality} />
                  </div>
                </div>
              </section>
            )}

            {/* Human approval gate */}
            <section aria-labelledby="approvalhd">
              <div className="card">
                <div className="card-hd">
                  <span id="approvalhd">Human Approval Gate — Simulated Execution</span>
                  <span className="card-hd-sub" style={{ color: 'var(--amber)' }}>
                    Human approval required
                  </span>
                </div>
                <div className="card-bd">
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
          </div>
        )}
      </main>

      {/* ── FOOTER ──────────────────────────────────────── */}
      <footer className="app-footer" role="contentinfo">
        Human-supervised decision-support prototype · Simulation only — not flight software · CollisionGuard AI
      </footer>
    </div>
  )
}
