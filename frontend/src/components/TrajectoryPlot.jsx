/**
 * TrajectoryPlot — Main integration component for orbital trajectory visualization.
 *
 * Replaces the old Plotly-based implementation with a real Three.js/WebGL scene.
 * Maintains the same public API for compatibility with existing imports.
 *
 * Features:
 * - Realistic 3D Earth (procedural, no texture hotlinking)
 * - Protected satellite & threat debris 3D objects
 * - Backend-propagated trajectory lines (not frontend circularOrbit)
 * - TCA geometry with markers, connector, midpoint
 * - Hover-to-highlight, click-to-pin interactions
 * - Interactive legend with keyboard support
 * - Global/Local conjunction views
 * - Camera presets: Global, Focus Protected, Focus Threat, Focus TCA, Reset
 * - Accessible text summary and keyboard controls
 * - WebGL fallback detection
 *
 * Scientific Integrity:
 * - All trajectory geometry from backend visualization data contract
 * - No frontend circularOrbit() or TLE propagation
 * - Coordinate frame: TEME, Units: km
 * - Post-maneuver path only when evaluated coordinates exist
 */
import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { OrbitalSceneWrapper } from './OrbitalScene'
import { useWebGLSupport } from './OrbitalScene'
import { SizeDisclosure } from './SpaceObject'

// ─── Legend Button Subcomponent ──────────────────────────────────────────────
function LegendBtn({
  role,
  active,
  pinned,
  onHover,
  onUnhover,
  onClick,
  lineStyle,
  label,
  dashStyle,
  isMarker,
  markerColor,
}) {
  return (
    <button
      className={`legend-btn ${active ? 'legend-btn-active' : ''} ${pinned ? 'legend-btn-pinned' : ''}`}
      aria-pressed={pinned}
      aria-label={`${label} trajectory${pinned ? ' — pinned' : ''}`}
      onMouseEnter={() => onHover(role)}
      onMouseLeave={onUnhover}
      onClick={() => onClick(role)}
      onFocus={() => onHover(role)}
      onBlur={onUnhover}
    >
      {isMarker ? (
        <span className="legend-diamond" style={{ background: markerColor }} aria-hidden="true" />
      ) : (
        <span
          className="legend-line"
          style={lineStyle}
          aria-hidden="true"
          title={dashStyle ? 'Dashed line (threat)' : 'Solid line'}
        />
      )}
      <span>{label}</span>
      {pinned && <span className="legend-pin-dot" aria-hidden="true">●</span>}
    </button>
  )
}

// ─── Accessible Description ──────────────────────────────────────────────────
function AccessibleDescription({ analysis, selectedCandidate, activeRole }) {
  const desc = useMemo(() => {
    if (!analysis) return 'No trajectory data. Select a scenario and run analysis.'
    const parts = [
      'Orbital visualization: protected satellite (cyan solid line) and threat object (red dashed line) in LEO.',
      analysis.tca_offset_seconds != null
        ? `TCA at ${(analysis.tca_offset_seconds / 60).toFixed(1)} min from epoch.`
        : '',
      analysis.nominal_miss_distance_km != null
        ? `Miss distance: ${analysis.nominal_miss_distance_km.toFixed(4)} km.`
        : '',
      selectedCandidate
        ? `Post-maneuver path (green solid line) shown for ${selectedCandidate.label}.`
        : '',
      activeRole === 'protected' ? 'Protected trajectory selected.' : '',
      activeRole === 'threat' ? 'Threat trajectory selected.' : '',
      activeRole === 'post' ? 'Post-maneuver trajectory selected.' : '',
      activeRole === 'tca' ? 'Closest approach selected.' : '',
      'Backend SGP4 propagation — not a frontend approximation.',
    ]
    return parts.filter(Boolean).join(' ')
  }, [analysis, selectedCandidate, activeRole])

  return <p className="sr-only" aria-live="polite">{desc}</p>
}

// ─── Status Bar ──────────────────────────────────────────────────────────────
function TrajStatus({ pinnedRole, label }) {
  if (!pinnedRole) return null
  return (
    <div className="traj-status" role="status" aria-live="polite">
      {label}
      <span className="traj-status-hint">· Click again or press Esc to unpin</span>
    </div>
  )
}

// ─── Keyboard Controls (Outside Canvas) ──────────────────────────────────────
function KeyboardControls({
  pinned,
  selectedCandidate,
  focusOur,
  focusThr,
  focusTCA,
  focusPost,
  clearSel,
}) {
  return (
    <div className="traj-kbd-controls" role="group" aria-label="Trajectory keyboard controls">
      <button
        className={`traj-kbd-btn ${pinned === 'protected' ? 'active' : ''}`}
        onClick={focusOur}
        aria-pressed={pinned === 'protected'}
        title="Focus protected satellite trajectory"
      >
        Protected
      </button>
      <button
        className={`traj-kbd-btn ${pinned === 'threat' ? 'active' : ''}`}
        onClick={focusThr}
        aria-pressed={pinned === 'threat'}
        title="Focus threat trajectory"
      >
        Threat
      </button>
      <button
        className={`traj-kbd-btn ${pinned === 'tca' ? 'active' : ''}`}
        onClick={focusTCA}
        aria-pressed={pinned === 'tca'}
        title="Focus closest approach"
      >
        TCA
      </button>
      {selectedCandidate && (
        <button
          className={`traj-kbd-btn ${pinned === 'post' ? 'active' : ''}`}
          onClick={focusPost}
          aria-pressed={pinned === 'post'}
          title="Focus post-maneuver trajectory"
        >
          Maneuver
        </button>
      )}
      {pinned && (
        <button
          className="traj-kbd-btn traj-kbd-clear"
          onClick={clearSel}
          title="Clear selection (Escape)"
        >
          ✕ Clear
        </button>
      )}
    </div>
  )
}

// ─── Main TrajectoryPlot Component ───────────────────────────────────────────
export default function TrajectoryPlot({ analysis, selectedCandidate, loading }) {
  const webglSupported = useWebGLSupport()
  const [focus, setFocus] = useState(null)       // 'protected'|'threat'|'post'|'tca'|null
  const [pinned, setPinned] = useState(null)     // same
  const [cameraMode, setCameraMode] = useState('global') // 'global'|'tca'|'protected'|'threat'
  const [vizError, setVizError] = useState(null)

  const activeRole = pinned ?? focus
  const isPinned = !!pinned

  // Extract visualization data from analysis response
  const visualization = useMemo(() => analysis?.visualization ?? null, [analysis])

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === 'Escape') setPinned(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Pin status label
  const pinnedLabel = pinned === 'protected' ? 'Protected trajectory selected'
    : pinned === 'threat' ? 'Threat trajectory selected'
    : pinned === 'post' ? 'Post-maneuver trajectory selected'
    : pinned === 'tca' ? 'Closest approach selected'
    : ''

  // Legend handlers
  const handleLegendHover = useCallback((role) => setFocus(role), [])
  const handleLegendUnhover = useCallback(() => setFocus(null), [])
  const handleLegendClick = useCallback((role) => {
    setPinned(prev => (prev === role ? null : role))
  }, [])

  // Camera view handlers
  const focusTCA = useCallback(() => {
    setCameraMode('tca')
    setPinned('tca')
    setFocus(null)
  }, [])

  const resetView = useCallback(() => {
    setCameraMode('global')
    setPinned(null)
    setFocus(null)
  }, [])

  const focusOur = useCallback(() => { setPinned('protected'); setFocus(null) }, [])
  const focusThr = useCallback(() => { setPinned('threat'); setFocus(null) }, [])
  const focusTCA_ = useCallback(() => { setPinned('tca'); setFocus(null) }, [])
  const focusPost = useCallback(() => { if (selectedCandidate) { setPinned('post'); setFocus(null) } }, [selectedCandidate])
  const clearSel = useCallback(() => setPinned(null), [])

  // Emphasis handlers for 3D scene
  const handleEmphasisChange = useCallback((role) => setFocus(role), [])
  const handlePinChange = useCallback((role) => {
    setPinned(prev => (prev === role ? null : role))
  }, [])

  // Loading state
  if (loading) {
    return (
      <div className="viz-panel" aria-labelledby="viz-title">
        <div className="viz-toolbar">
          <span className="viz-title" id="viz-title">Orbital Trajectories — Closest Approach</span>
        </div>
        <div className="viz-empty" style={{ height: 560 }}>
          <span className="spinner" aria-hidden="true" />
          <span>Computing trajectories…</span>
        </div>
      </div>
    )
  }

  // No analysis data
  if (!analysis) {
    return (
      <div className="viz-panel" aria-labelledby="viz-title">
        <div className="viz-toolbar">
          <span className="viz-title" id="viz-title">Orbital Trajectories — Closest Approach</span>
        </div>
        <div className="viz-empty" style={{ height: 560 }}>
          <span style={{ fontSize: 32, opacity: 0.3 }}>◎</span>
          <span>Select a scenario and run analysis to view orbital trajectories.</span>
        </div>
      </div>
    )
  }

  // WebGL not supported
  if (!webglSupported) {
    return (
      <div className="viz-panel" aria-labelledby="viz-title" role="alert">
        <div className="viz-toolbar">
          <span className="viz-title" id="viz-title">Orbital Trajectories — Closest Approach</span>
        </div>
        <div className="viz-empty" style={{ height: 560, padding: 24, textAlign: 'center' }}>
          <h3>WebGL Not Available</h3>
          <p>This visualization requires WebGL support.</p>
          <p className="error-fallback">
            Please enable hardware acceleration in your browser settings,
            or use a browser with WebGL support.
          </p>
          <AccessibleDescription analysis={analysis} selectedCandidate={selectedCandidate} activeRole={activeRole} />
        </div>
      </div>
    )
  }

  // Visualization data not available (backend contract not fulfilled)
  if (!visualization) {
    return (
      <div className="viz-panel" aria-labelledby="viz-title" role="alert">
        <div className="viz-toolbar">
          <span className="viz-title" id="viz-title">Orbital Trajectories — Closest Approach</span>
        </div>
        <div className="viz-empty" style={{ height: 560, padding: 24, textAlign: 'center' }}>
          <h3>Visualization Data Unavailable</h3>
          <p>The backend did not return trajectory visualization data.</p>
          <p className="error-fallback">
            This may indicate a backend version mismatch. Please re-run analysis.
          </p>
          <AccessibleDescription analysis={analysis} selectedCandidate={selectedCandidate} activeRole={activeRole} />
        </div>
      </div>
    )
  }

  return (
    <div className="viz-panel" aria-labelledby="viz-title">
      {/* ── Toolbar ──────────────────────────────────────────────── */}
      <div className="viz-toolbar">
        <span className="viz-title" id="viz-title">Orbital Trajectories — Closest Approach</span>

        {/* ── Interactive Legend ───────────────────────────────── */}
        <div className="viz-legend" role="group" aria-label="Trajectory legend — click to pin">
          <LegendBtn
            role="protected"
            active={activeRole === 'protected'}
            pinned={pinned === 'protected'}
            onHover={handleLegendHover}
            onUnhover={handleLegendUnhover}
            onClick={handleLegendClick}
            lineStyle={{ background: '#33b1ff' }}
            label="Protected Sat"
            dashStyle={false}
          />
          <LegendBtn
            role="threat"
            active={activeRole === 'threat'}
            pinned={pinned === 'threat'}
            onHover={handleLegendHover}
            onUnhover={handleLegendUnhover}
            onClick={handleLegendClick}
            lineStyle={{ background: `repeating-linear-gradient(90deg, #fa4d56 0, #fa4d56 4px, transparent 4px, transparent 7px)` }}
            label="Threat Object"
            dashStyle={true}
          />
          {selectedCandidate && (
            <LegendBtn
              role="post"
              active={activeRole === 'post'}
              pinned={pinned === 'post'}
              onHover={handleLegendHover}
              onUnhover={handleLegendUnhover}
              onClick={handleLegendClick}
              lineStyle={{ background: '#42be65' }}
              label="Post-Maneuver"
              dashStyle={false}
            />
          )}
          <LegendBtn
            role="tca"
            active={activeRole === 'tca'}
            pinned={pinned === 'tca'}
            onHover={handleLegendHover}
            onUnhover={handleLegendUnhover}
            onClick={handleLegendClick}
            isMarker={true}
            markerColor="#f1c21b"
            label="TCA"
          />
        </div>

        {/* ── Toolbar Actions ──────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="viz-schematic-chip" aria-label="Backend-derived visualization — accurate to scale">
            Backend SGP4 · TEME Frame · To Scale
          </span>
          {cameraMode === 'tca' ? (
            <button
              className="btn btn-ghost btn-sm"
              onClick={resetView}
              aria-label="Return to global orbital view"
            >
              ↩ Global View
            </button>
          ) : (
            <button
              className="btn btn-ghost btn-sm"
              onClick={focusTCA}
              aria-label="Focus camera on closest approach region"
              title="Focus Closest Approach"
            >
              ⊙ Focus TCA
            </button>
          )}
          <button
            className="btn btn-ghost btn-sm"
            onClick={resetView}
            aria-label="Reset 3D camera to default angle and clear selection"
          >
            Reset View
          </button>
        </div>
      </div>

      {/* ── Keyboard Controls (Outside Canvas) ───────────────── */}
      <KeyboardControls
        pinned={pinned}
        selectedCandidate={selectedCandidate}
        focusOur={focusOur}
        focusThr={focusThr}
        focusTCA={focusTCA_}
        focusPost={focusPost}
        clearSel={clearSel}
      />

      {/* ── Status Bar ──────────────────────────────────────────── */}
      <TrajStatus pinnedRole={pinned} label={pinnedLabel} />

      {/* ── Accessible Description ─────────────────────────────── */}
      <AccessibleDescription analysis={analysis} selectedCandidate={selectedCandidate} activeRole={activeRole} />

      {/* ── 3D Orbital Scene ───────────────────────────────────── */}
      <div className="viz-body">
        <OrbitalSceneWrapper
          visualization={visualization}
          analysis={analysis}
          selectedCandidate={selectedCandidate}
          emphasizedRole={focus}
          pinnedRole={pinned}
          onEmphasisChange={handleEmphasisChange}
          onPinChange={handlePinChange}
          cameraMode={cameraMode}
          onCameraModeChange={setCameraMode}
          loading={false}
          error={vizError}
          style={{ width: '100%', height: '100%' }}
        />
      </div>
    </div>
  )
}