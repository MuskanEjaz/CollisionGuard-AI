/**
 * TrajectoryTooltip — Hover/pin tooltips for orbital visualization.
 *
 * Features:
 * - Shows on hover of satellite, debris, trajectory, or TCA
 * - Pinned state persists tooltip when clicked
 * - Accessible: ARIA live region, keyboard dismissible
 * - Content varies by object type
 * - "Hover changes presentation only — no computation triggered" disclosure
 */
import React, { useMemo } from 'react'

// ─── Main Tooltip Component ──────────────────────────────────────────────────
export function TrajectoryTooltip({
  content,           // Tooltip content object from getTooltipContent()
  pinned = false,    // Whether tooltip is pinned (clicked)
  position,          // { x, y } screen position for tooltip
  onClose,           // Callback to close/unpin
}) {
  if (!content) return null

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose?.()
    }
  }

  return (
    <div
      className={`traj-tooltip ${pinned ? 'traj-tooltip-pinned' : ''}`}
      role="tooltip"
      aria-live="polite"
      aria-label={`Trajectory info: ${content.title}`}
      style={{
        left: position?.x ?? 0,
        top: position?.y ?? 0,
        transform: position ? 'translate(-50%, -100%)' : undefined,
      }}
      onKeyDown={handleKeyDown}
      tabIndex={pinned ? 0 : -1}
    >
      <div className="traj-tooltip-header">
        <h4 className="traj-tooltip-title">{content.title}</h4>
        {pinned && (
          <button
            className="traj-tooltip-pin-btn"
            onClick={onClose}
            aria-label="Unpin tooltip"
            title="Click to unpin (or press Escape)"
          >
            ✕
          </button>
        )}
      </div>

      {content.rows && content.rows.map(([label, value], i) => (
        <div key={i} className="traj-tooltip-row">
          <span className="traj-tooltip-label">{label}</span>
          <span className="traj-tooltip-value">{value}</span>
        </div>
      ))}

      <div className="traj-tooltip-footer">
        Hover changes presentation only · No computation triggered
      </div>
    </div>
  )
}

// ─── Tooltip Content Generators ──────────────────────────────────────────────
export function getTooltipContent(role, analysis, selectedCandidate, tcaData) {
  if (!role) return null

  // Protected satellite tooltip
  if (role === 'protected' || role === 'our') {
    const src = analysis?.data_quality?.[0]?.note ?? 'Not provided'
    const epoch = analysis?.tca_utc
      ? 'Backend-computed TCA: ' + new Date(analysis.tca_utc).toUTCString()
      : null
    const missDist = analysis?.nominal_miss_distance_km != null
      ? `${analysis.nominal_miss_distance_km.toFixed(4)} km`
      : 'Not provided'
    const risk = analysis?.risk?.label ?? 'Not provided'

    return {
      title: analysis?.scenario_id
        ? `Protected Satellite · ${analysis.scenario_id}`
        : 'Protected Satellite',
      rows: [
        ['Role', 'Protected satellite (primary)'],
        ['Trajectory', 'Backend-propagated SGP4 trajectory (TEME frame)'],
        ['Risk Level', risk],
        ['Nominal Miss Distance', missDist],
        ['Data Source', src],
        epoch && ['TCA Time', epoch],
        ['Frame', 'TEME (backend propagation frame)'],
        ['Units', 'km'],
      ].filter(Boolean),
    }
  }

  // Threat object tooltip
  if (role === 'threat' || role === 'thr') {
    const src = analysis?.data_quality?.[0]?.note ?? 'Not provided'
    const epochNote = analysis?.orbit_element_age_note ?? 'Not provided'
    const risk = analysis?.risk?.label ?? 'Not provided'
    const missDist = analysis?.nominal_miss_distance_km != null
      ? `${analysis.nominal_miss_distance_km.toFixed(4)} km`
      : 'Not provided'

    return {
      title: 'Threat Object (Debris)',
      rows: [
        ['Role', 'Threat object (secondary)'],
        ['Trajectory', 'Backend-propagated SGP4 trajectory (TEME frame)'],
        ['Risk Level', risk],
        ['Nominal Miss Distance', missDist],
        ['Data Source', src],
        ['Epoch Note', epochNote],
        ['Frame', 'TEME (backend propagation frame)'],
        ['Units', 'km'],
      ],
    }
  }

  // Post-maneuver tooltip
  if (role === 'post' || role === 'maneuver') {
    const c = selectedCandidate
    if (!c) {
      return {
        title: 'Post-Maneuver Path',
        rows: [['Status', 'No candidate selected']],
      }
    }

    return {
      title: `Post-Maneuver · ${c.label}`,
      rows: [
        ['Maneuver', c.label],
        ['Delta-v', c.delta_v_ms != null ? `${c.delta_v_ms.toFixed(2)} m/s` : 'Not provided'],
        ['Direction', c.direction ?? 'Not provided'],
        ['Post-Maneuver Miss Distance', c.post_maneuver_miss_distance_km != null
          ? `${c.post_maneuver_miss_distance_km.toFixed(3)} km`
          : 'Not provided'],
        ['Fuel Cost', c.fuel_cost_kg != null ? `${c.fuel_cost_kg.toFixed(4)} kg` : 'Not provided'],
        ['Safety Status', c.is_safe ? '✓ Safe (backend verified)' : '✗ Rejected'],
        ['Baseline Score', c.baseline_score != null ? c.baseline_score.toFixed(4) : 'Not provided'],
        ['Note', 'Trajectory shown only when actual evaluated coordinates exist'],
      ],
    }
  }

  // TCA tooltip
  if (role === 'tca' || role === 'closest-approach') {
    const timestamp = analysis?.tca_utc
      ? new Date(analysis.tca_utc).toUTCString()
      : 'Not provided'
    const missDist = analysis?.nominal_miss_distance_km != null
      ? `${analysis.nominal_miss_distance_km.toFixed(4)} km`
      : 'Not provided'
    const tcaOffset = analysis?.tca_offset_seconds != null
      ? `${(analysis.tca_offset_seconds / 60).toFixed(1)} min from epoch`
      : 'Not provided'
    const riskLevel = analysis?.risk?.level ?? 'Not provided'
    const relVel = analysis?.relative_velocity_km_s != null
      ? `${analysis.relative_velocity_km_s.toFixed(4)} km/s`
      : 'Not available'
    const basis = analysis?.risk_basis_label
      ? analysis.risk_basis_label.slice(0, 100) + '…'
      : 'Screening-level estimate'

    return {
      title: 'Closest Approach (TCA)',
      rows: [
        ['TCA Time (UTC)', timestamp],
        ['Miss Distance', missDist],
        ['TCA Offset', tcaOffset],
        ['Relative Velocity', relVel],
        ['Risk Tier', riskLevel],
        ['Coordinate Frame', 'TEME'],
        ['Estimate Basis', basis],
        ['Geometry', 'Both positions from backend SGP4 at identical TCA timestamp'],
      ],
    }
  }

  // Trajectory line tooltip (generic)
  if (role === 'trajectory-protected') {
    return {
      title: 'Protected Satellite Trajectory',
      rows: [
        ['Type', 'Backend-propagated trajectory samples'],
        ['Frame', 'TEME'],
        ['Units', 'km'],
        ['Sample Count', analysis?.visualization?.samples?.length ?? '~360'],
        ['Window', '±3 hours around TCA'],
      ],
    }
  }

  if (role === 'trajectory-threat') {
    return {
      title: 'Threat Object Trajectory',
      rows: [
        ['Type', 'Backend-propagated trajectory samples'],
        ['Frame', 'TEME'],
        ['Units', 'km'],
        ['Sample Count', analysis?.visualization?.samples?.length ?? '~360'],
        ['Window', '±3 hours around TCA'],
      ],
    }
  }

  return null
}

// ─── Hover State Manager Hook ────────────────────────────────────────────────
export function useTrajectoryTooltip() {
  const [tooltip, setTooltip] = React.useState(null)
  const [pinned, setPinned] = React.useState(false)
  const [position, setPosition] = React.useState({ x: 0, y: 0 })

  const showTooltip = React.useCallback((content, pos) => {
    if (!pinned) {
      setTooltip(content)
      if (pos) setPosition(pos)
    }
  }, [pinned])

  const hideTooltip = React.useCallback(() => {
    if (!pinned) {
      setTooltip(null)
    }
  }, [pinned])

  const pinTooltip = React.useCallback((content, pos) => {
    setTooltip(content)
    setPinned(true)
    if (pos) setPosition(pos)
  }, [])

  const unpinTooltip = React.useCallback(() => {
    setPinned(false)
    setTooltip(null)
  }, [])

  return {
    tooltip,
    pinned,
    position,
    showTooltip,
    hideTooltip,
    pinTooltip,
    unpinTooltip,
  }
}

// ─── Tooltip Trigger Wrapper (for 3D objects) ────────────────────────────────
export function TooltipTrigger({
  children,
  role,
  analysis,
  selectedCandidate,
  tcaData,
  onPin,
  onUnpin,
}) {
  const { showTooltip, hideTooltip, pinTooltip, unpinTooltip, tooltip, pinned, position } = useTrajectoryTooltip()

  // This would be connected to 3D object pointer events
  // For now, return children with event handlers attached
  return React.cloneElement(children, {
    onPointerOver: (e) => {
      const content = getTooltipContent(role, analysis, selectedCandidate, tcaData)
      if (content) showTooltip(content, { x: e.clientX, y: e.clientY })
    },
    onPointerOut: hideTooltip,
    onClick: (e) => {
      e.stopPropagation()
      if (pinned) {
        unpinTooltip()
        onUnpin?.(role)
      } else {
        const content = getTooltipContent(role, analysis, selectedCandidate, tcaData)
        if (content) {
          pinTooltip(content, { x: e.clientX, y: e.clientY })
          onPin?.(role)
        }
      }
    },
  })
}