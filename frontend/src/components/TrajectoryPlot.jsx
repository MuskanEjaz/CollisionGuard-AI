/**
 * TrajectoryPlot — 3D Plotly visualization of orbital paths and TCA marker.
 *
 * Shows original and post-maneuver paths; marks closest approach.
 *
 * SIMPLIFIED FOR PROTOTYPE: orbit positions are approximated from orbital
 * inclination and RAAN using simple circular-orbit geometry. Not a real
 * ephemeris. SGP4 is used for all physics in the backend.
 *
 * Accessibility: provides a text summary of the visualization state.
 * Reset-view button restores the default camera angle.
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
import React, { useMemo, useState } from 'react'

function circularOrbitPoints(sma_km, inc_deg, raan_deg, n = 120) {
  // SIMPLIFIED FOR PROTOTYPE: circular orbit, no J2, no time progression.
  const inc  = (inc_deg  * Math.PI) / 180
  const raan = (raan_deg * Math.PI) / 180
  const pts  = { x: [], y: [], z: [] }
  for (let i = 0; i <= n; i++) {
    const nu = (2 * Math.PI * i) / n
    const xp = sma_km * Math.cos(nu)
    const yp = sma_km * Math.sin(nu)
    pts.x.push(xp * Math.cos(raan) - yp * Math.cos(inc) * Math.sin(raan))
    pts.y.push(xp * Math.sin(raan) + yp * Math.cos(inc) * Math.cos(raan))
    pts.z.push(yp * Math.sin(inc))
  }
  return pts
}

function earthSphere(r = 6371) {
  const N = 30
  const x = [], y = [], z = []
  for (let i = 0; i <= N; i++) {
    const phi = (Math.PI * i) / N
    for (let j = 0; j <= N; j++) {
      const theta = (2 * Math.PI * j) / N
      x.push(r * Math.sin(phi) * Math.cos(theta))
      y.push(r * Math.sin(phi) * Math.sin(theta))
      z.push(r * Math.cos(phi))
    }
  }
  return { x, y, z }
}

export default function TrajectoryPlot({ analysis, selectedCandidate }) {
  const [PlotComponent, setPlotComponent] = React.useState(null)
  const [cameraRevision, setCameraRevision] = useState(0)

  React.useEffect(() => {
    import('react-plotly.js').then(m => setPlotComponent(() => m.default))
  }, [])

  const traces = useMemo(() => {
    if (!analysis) return []

    const ourInc     = 51.640
    const threatInc  = 51.641
    const ourRaan    = 208.51
    const threatRaan = 208.505
    const ourSMA     = 6778   // ~400 km altitude LEO
    const threatSMA  = 6775

    const ourPath    = circularOrbitPoints(ourSMA,    ourInc,    ourRaan)
    const threatPath = circularOrbitPoints(threatSMA, threatInc, threatRaan)

    // Post-maneuver path: shift SMA based on delta-v
    // SIMPLIFIED FOR PROTOTYPE: delta SMA is approximate, not integrated
    const dv      = selectedCandidate?.delta_v_ms ?? 0
    const dSMA    = dv * 0.2  // rough km shift per m/s prograde
    const postPath = circularOrbitPoints(ourSMA + dSMA, ourInc, ourRaan)

    // TCA marker: approximate position at TCA offset
    const tcaFrac  = (analysis.tca_offset_seconds ?? 0) / 5760  // ~96-min orbit
    const tcaAngle = 2 * Math.PI * tcaFrac
    const tcaX     = ourSMA * Math.cos(tcaAngle)
    const tcaY     = ourSMA * Math.sin(tcaAngle) * Math.cos((ourInc * Math.PI) / 180)
    const tcaZ     = ourSMA * Math.sin(tcaAngle) * Math.sin((ourInc * Math.PI) / 180)

    const earth = earthSphere(6371)

    return [
      // Earth surface
      {
        type: 'surface', opacity: 0.30, showscale: false, hoverinfo: 'skip',
        x: earth.x, y: earth.y, z: earth.z,
        colorscale: [[0, '#0d1e38'], [1, '#1a3a6a']],
        name: 'Earth (approximate)',
      },
      // Our satellite orbit (original)
      {
        type: 'scatter3d', mode: 'lines', name: 'Protected Satellite',
        x: ourPath.x, y: ourPath.y, z: ourPath.z,
        line: { color: '#4589ff', width: 2 },
      },
      // Threat object orbit
      {
        type: 'scatter3d', mode: 'lines', name: 'Threat Object',
        x: threatPath.x, y: threatPath.y, z: threatPath.z,
        line: { color: '#ff7e7e', width: 2, dash: 'dash' },
      },
      // Post-maneuver orbit (only if candidate selected)
      ...(selectedCandidate ? [{
        type: 'scatter3d', mode: 'lines', name: 'Post-Maneuver Path',
        x: postPath.x, y: postPath.y, z: postPath.z,
        line: { color: '#52c07a', width: 2 },
      }] : []),
      // TCA marker
      {
        type: 'scatter3d', mode: 'markers+text',
        name: 'Closest Approach (TCA)',
        x: [tcaX], y: [tcaY], z: [tcaZ],
        text: ['TCA'],
        textposition: 'top center',
        textfont: { color: '#f0c040', size: 9 },
        marker: { size: 8, color: '#f0c040', symbol: 'diamond' },
      },
    ]
  }, [analysis, selectedCandidate])

  // Accessible text summary of the visualization
  const a11ySummary = analysis
    ? [
        `Trajectory visualization: protected satellite (blue) and threat object (red dashed)`,
        `in low Earth orbit (~${6778 - 6371} km altitude).`,
        `Closest approach (TCA) marker shown in yellow.`,
        analysis.tca_offset_seconds != null
          ? `TCA at ${(analysis.tca_offset_seconds / 60).toFixed(1)} min from epoch.`
          : '',
        analysis.nominal_miss_distance_km != null
          ? `Miss distance: ${analysis.nominal_miss_distance_km.toFixed(4)} km.`
          : '',
        selectedCandidate
          ? `Post-maneuver path (green) shown for ${selectedCandidate.label}.`
          : '',
        'SIMPLIFIED: circular orbit approximation. Not a real ephemeris.',
      ].filter(Boolean).join(' ')
    : 'No trajectory data available. Run analysis to view.'

  if (!PlotComponent) {
    return (
      <div className="state-box" style={{ height: 340 }} aria-live="polite">
        <span className="spinner" aria-hidden="true" /> Loading 3D view…
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="state-box" style={{ height: 280 }}>
        Run analysis to view trajectory.
      </div>
    )
  }

  return (
    <div>
      {/* Plot controls */}
      <div className="plot-controls">
        <span className="plot-disclaimer" aria-label="Visualization disclaimer">
          SIMPLIFIED FOR PROTOTYPE: Orbits shown as approximate circular paths.
          Not a real ephemeris. SGP4 is used for all physics in the backend.
        </span>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setCameraRevision(r => r + 1)}
          aria-label="Reset 3D view to default camera angle"
        >
          Reset View
        </button>
      </div>

      {/* 3D plot */}
      <PlotComponent
        key={cameraRevision}
        data={traces}
        layout={{
          paper_bgcolor: 'transparent',
          plot_bgcolor:  'transparent',
          margin: { l: 0, r: 0, t: 0, b: 0 },
          height: 360,
          legend: {
            font:        { color: '#a8bccf', size: 10 },
            bgcolor:     'rgba(15,28,46,0.85)',
            bordercolor: '#243347',
            borderwidth: 1,
          },
          scene: {
            bgcolor: '#060e1a',
            xaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            yaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            zaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            camera: { eye: { x: 1.5, y: 1.5, z: 0.9 } },
          },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        aria-hidden="true"
      />

      {/* Accessible text alternative */}
      <div
        className="plot-a11y-summary"
        aria-label="Text description of the trajectory visualization"
        role="note"
      >
        <strong>Text summary:</strong> {a11ySummary}
      </div>
    </div>
  )
}
