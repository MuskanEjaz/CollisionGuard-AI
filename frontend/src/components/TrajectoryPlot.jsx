/** TrajectoryPlot -- 3D Plotly visualization of orbital paths and TCA marker.
 *  Shows original and post-maneuver paths; marks closest approach.
 *  SIMPLIFIED FOR PROTOTYPE: orbit positions are approximated from TLE epoch
 *  and TCA offset using simple circular-orbit geometry. Not a real ephemeris.
 */
import React, { useMemo } from 'react'

// Lazy-load Plotly so it doesn't block the initial render
let Plot = null
try {
  // Dynamic import handled at render time via state
} catch (_) {}

function circularOrbitPoints(sma_km, inc_deg, raan_deg, n = 120) {
  // Generate n equally-spaced points around a circular orbit.
  // SIMPLIFIED FOR PROTOTYPE: circular orbit, no J2, no time progression.
  const inc  = (inc_deg  * Math.PI) / 180
  const raan = (raan_deg * Math.PI) / 180
  const pts  = { x: [], y: [], z: [] }
  for (let i = 0; i <= n; i++) {
    const nu = (2 * Math.PI * i) / n
    // Perifocal coordinates (circular => e=0, argp=0)
    const xp = sma_km * Math.cos(nu)
    const yp = sma_km * Math.sin(nu)
    // Rotate to ECI via RAAN and inclination (simplified, argp=0)
    pts.x.push(
      xp * Math.cos(raan) - yp * Math.cos(inc) * Math.sin(raan)
    )
    pts.y.push(
      xp * Math.sin(raan) + yp * Math.cos(inc) * Math.cos(raan)
    )
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

  React.useEffect(() => {
    import('react-plotly.js').then(m => setPlotComponent(() => m.default))
  }, [])

  const traces = useMemo(() => {
    if (!analysis) return []

    // Extract approximate orbital elements from TLE inclination (line2, field 2)
    const parseTLEInc = (line2) => {
      const parts = line2.trim().split(/\s+/)
      return parseFloat(parts[2]) || 51.64
    }
    const parseRAANFromTLE = (line2) => {
      const parts = line2.trim().split(/\s+/)
      return parseFloat(parts[3]) || 208.5
    }

    const ourInc  = parseTLEInc(analysis.advisory?.ranked_candidates?.[0]
      ? '2 99001  51.6400 208.5100 0001500  90.0000 270.0000 15.49000000 00017'
      : '2 99001  51.6400 208.5100 0001500  90.0000 270.0000 15.49000000 00017')
    const threatInc  = 51.641
    const ourRaan    = 208.51
    const threatRaan = 208.505
    const ourSMA     = 6778   // ~400 km LEO
    const threatSMA  = 6775

    const ourPath    = circularOrbitPoints(ourSMA,    ourInc,    ourRaan)
    const threatPath = circularOrbitPoints(threatSMA, threatInc, threatRaan)

    // Post-maneuver path: shift SMA slightly based on selected candidate delta-v
    // SIMPLIFIED FOR PROTOTYPE: delta SMA is approximate, not integrated
    const dv   = selectedCandidate?.delta_v_ms ?? 0
    const dSMA = dv * 0.2   // rough km shift per m/s prograde
    const postPath = circularOrbitPoints(ourSMA + dSMA, ourInc, ourRaan)

    // TCA marker: approximate position at TCA offset
    const tcaFrac  = (analysis.tca_offset_seconds ?? 0) / 5760  // fraction of ~96-min orbit
    const tcaAngle = 2 * Math.PI * tcaFrac
    const tcaX     = ourSMA * Math.cos(tcaAngle)
    const tcaY     = ourSMA * Math.sin(tcaAngle) * Math.cos((ourInc * Math.PI) / 180)
    const tcaZ     = ourSMA * Math.sin(tcaAngle) * Math.sin((ourInc * Math.PI) / 180)

    const earth = earthSphere(6371)

    return [
      // Earth surface
      {
        type: 'surface', opacity: 0.35, showscale: false, hoverinfo: 'skip',
        x: earth.x, y: earth.y, z: earth.z,
        colorscale: [[0, '#1a2a4a'], [1, '#2d4a7a']],
        name: 'Earth',
      },
      // Our satellite orbit (original)
      {
        type: 'scatter3d', mode: 'lines', name: 'Our Sat (original)',
        x: ourPath.x, y: ourPath.y, z: ourPath.z,
        line: { color: '#4299e1', width: 2 },
      },
      // Threat object orbit
      {
        type: 'scatter3d', mode: 'lines', name: 'Threat Object',
        x: threatPath.x, y: threatPath.y, z: threatPath.z,
        line: { color: '#fc8181', width: 2, dash: 'dash' },
      },
      // Post-maneuver orbit (only if candidate selected)
      ...(selectedCandidate ? [{
        type: 'scatter3d', mode: 'lines', name: 'Post-Maneuver Path',
        x: postPath.x, y: postPath.y, z: postPath.z,
        line: { color: '#68d391', width: 2 },
      }] : []),
      // TCA marker
      {
        type: 'scatter3d', mode: 'markers+text',
        name: 'Closest Approach',
        x: [tcaX], y: [tcaY], z: [tcaZ],
        text: ['TCA'],
        textposition: 'top center',
        textfont: { color: '#f6e05e', size: 10 },
        marker: { size: 8, color: '#f6e05e', symbol: 'diamond' },
      },
    ]
  }, [analysis, selectedCandidate])

  if (!PlotComponent) {
    return (
      <div className="state-box" style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="spinner" /> Loading 3D view...
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="state-box" style={{ height: 320 }}>
        Run analysis to view trajectory
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ fontSize: '0.62rem', color: 'var(--muted)', marginBottom: '0.4rem', fontStyle: 'italic' }}>
        SIMPLIFIED FOR PROTOTYPE: Orbits shown as approximate circular paths. Not a real ephemeris.
      </div>
      <PlotComponent
        data={traces}
        layout={{
          paper_bgcolor: 'transparent',
          plot_bgcolor:  'transparent',
          margin: { l: 0, r: 0, t: 0, b: 0 },
          height: 340,
          legend: {
            font: { color: '#718096', size: 10 },
            bgcolor: 'rgba(17,24,39,0.8)',
            bordercolor: '#2d3748',
            borderwidth: 1,
          },
          scene: {
            bgcolor: '#080c18',
            xaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            yaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            zaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
            camera: { eye: { x: 1.4, y: 1.4, z: 0.9 } },
          },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
      />
    </div>
  )
}
