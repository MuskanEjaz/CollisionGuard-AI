/**
 * ClosestApproach — TCA geometry visualization.
 *
 * Shows at TCA:
 * - Protected satellite position (amber diamond marker)
 * - Threat object position (amber diamond marker)
 * - Line connecting the two points (miss distance connector)
 * - Midpoint indicator
 * - Tooltip with TCA timestamp, miss distance, relative velocity, frame, basis
 *
 * Provides both Global and Local Conjunction views.
 * Local view magnifies separation with visible label:
 * "Local conjunction view — separation magnified for visibility."
 */
import React, { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { VISUAL_SCALE } from './EarthGlobe'

// ─── TCA Markers ─────────────────────────────────────────────────────────────
export function TCAMarkers({
  protectedPosition,
  threatPosition,
  emphasized = false,
  visible = true,
  size = 0.15,
}) {
  const markerRef = useRef()

  const protectedPos = useMemo(() => {
    if (!protectedPosition) return [0, 0, 0]
    return protectedPosition.map(value => value * VISUAL_SCALE)
  }, [protectedPosition])

  const threatPos = useMemo(() => {
    if (!threatPosition) return [0, 0, 0]
    return threatPosition.map(value => value * VISUAL_SCALE)
  }, [threatPosition])

  const markerSize = emphasized ? size * 1.5 : size
  const markerOpacity = emphasized ? 1.0 : 0.8

  if (!visible) return null

  return (
    <group name="tca-markers">
      <mesh
        ref={markerRef}
        position={protectedPos}
        name="tca-protected"
      >
        <octahedronGeometry args={[markerSize, 0]} />
        <meshBasicMaterial
          color={0xf1c21b}
          transparent
          opacity={markerOpacity}
          depthTest
          depthWrite={false}
        />

        {emphasized && (
          <mesh name="tca-protected-glow">
            <sphereGeometry args={[markerSize * 2, 16, 16]} />
            <meshBasicMaterial
              color={0xf1c21b}
              transparent
              opacity={0.15}
              depthWrite={false}
              side={THREE.BackSide}
            />
          </mesh>
        )}
      </mesh>

      <mesh
        position={threatPos}
        name="tca-threat"
      >
        <octahedronGeometry args={[markerSize, 0]} />
        <meshBasicMaterial
          color={0xf1c21b}
          transparent
          opacity={markerOpacity}
          depthTest
          depthWrite={false}
        />

        {emphasized && (
          <mesh name="tca-threat-glow">
            <sphereGeometry args={[markerSize * 2, 16, 16]} />
            <meshBasicMaterial
              color={0xf1c21b}
              transparent
              opacity={0.15}
              depthWrite={false}
              side={THREE.BackSide}
            />
          </mesh>
        )}
      </mesh>
    </group>
  )
}
// ─── TCA Connector Line (Miss Distance) ──────────────────────────────────────
export function TCAConnector({
  protectedPosition,
  threatPosition,
  emphasized = false,
  visible = true,
}) {
  const positions = useMemo(() => {
    if (!protectedPosition || !threatPosition) return null
    return new Float32Array([
      protectedPosition[0] * VISUAL_SCALE, protectedPosition[1] * VISUAL_SCALE, protectedPosition[2] * VISUAL_SCALE,
      threatPosition[0] * VISUAL_SCALE, threatPosition[1] * VISUAL_SCALE, threatPosition[2] * VISUAL_SCALE,
    ])
  }, [protectedPosition, threatPosition])

  const geometry = useMemo(() => {
    if (!positions) return null
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return geom
  }, [positions])

  const material = useMemo(() => new THREE.LineBasicMaterial({
    color: 0xf1c21b,
    opacity: emphasized ? 1.0 : 0.7,
    transparent: true,
    depthTest: true,
    depthWrite: false,
  }), [emphasized])

  if (!geometry || !visible) return null

  return (
    <line
      geometry={geometry}
      material={material}
      name="tca-connector"
    />
  )
}

// ─── TCA Midpoint Indicator ──────────────────────────────────────────────────
export function TCAMidpoint({
  protectedPosition,
  threatPosition,
  emphasized = false,
  visible = true,
}) {
  const midpoint = useMemo(() => {
    if (!protectedPosition || !threatPosition) return [0, 0, 0]

    return [
      ((protectedPosition[0] + threatPosition[0]) / 2) * VISUAL_SCALE,
      ((protectedPosition[1] + threatPosition[1]) / 2) * VISUAL_SCALE,
      ((protectedPosition[2] + threatPosition[2]) / 2) * VISUAL_SCALE,
    ]
  }, [protectedPosition, threatPosition])

  if (!visible) return null

  return (
    <mesh position={midpoint} name="tca-midpoint">
      <sphereGeometry args={[emphasized ? 0.08 : 0.05, 16, 16]} />
      <meshBasicMaterial
        color={0xf1c21b}
        transparent
        opacity={emphasized ? 1.0 : 0.6}
        depthWrite={false}
      />
    </mesh>
  )
}
// ─── TCA Tooltip Data Display ────────────────────────────────────────────────
export function TCATooltipData({
  tcaData,
  emphasized = false,
}) {
  if (!tcaData || !emphasized) return null

  const missDistance = tcaData.miss_distance_km?.toFixed(4) ?? '—'
  const relVelocity = tcaData.relative_velocity_km_s?.toFixed(4) ?? '—'
  const timestamp = tcaData.timestamp_utc
    ? new Date(tcaData.timestamp_utc).toUTCString()
    : 'Not provided'
  const frame = tcaData.coordinate_frame ?? 'TEME'

  // This is rendered as a DOM overlay, not in 3D
  return (
    <div className="tca-tooltip" role="tooltip" aria-label={`TCA details: miss distance ${missDistance} km`}>
      <div className="tca-tooltip-title">Closest Approach (TCA)</div>
      <div className="tca-tooltip-row">
        <span className="tca-tooltip-label">Time:</span>
        <span className="tca-tooltip-value">{timestamp}</span>
      </div>
      <div className="tca-tooltip-row">
        <span className="tca-tooltip-label">Miss Distance:</span>
        <span className="tca-tooltip-value">{missDistance} km</span>
      </div>
      <div className="tca-tooltip-row">
        <span className="tca-tooltip-label">Relative Velocity:</span>
        <span className="tca-tooltip-value">{relVelocity} km/s</span>
      </div>
      <div className="tca-tooltip-row">
        <span className="tca-tooltip-label">Frame:</span>
        <span className="tca-tooltip-value">{frame}</span>
      </div>
      <div className="tca-tooltip-row">
        <span className="tca-tooltip-label">Basis:</span>
        <span className="tca-tooltip-value">SGP4 propagation, same frame & timestamp</span>
      </div>
    </div>
  )
}

// ─── Complete TCA Visualization Group ────────────────────────────────────────
export function ClosestApproach({
  tcaData,           // VisualizationTCA from backend
  emphasized = false,
  visible = true,
  onPointerOver,
  onPointerOut,
  onClick,
}) {
  if (!tcaData) return null

  const protectedPos = tcaData.protected_position_km
  const threatPos = tcaData.threat_position_km

  return (
    <group
      name="closest-approach"
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
    >
      <TCAMarkers
        protectedPosition={protectedPos}
        threatPosition={threatPos}
        emphasized={emphasized}
        visible={visible}
      />
      <TCAConnector
        protectedPosition={protectedPos}
        threatPosition={threatPos}
        emphasized={emphasized}
        visible={visible}
      />
      <TCAMidpoint
        protectedPosition={protectedPos}
        threatPosition={threatPos}
        emphasized={emphasized}
        visible={visible}
      />
    </group>
  )
}

// ─── Local Conjunction View Indicator ────────────────────────────────────────
export function LocalViewNotice({ visible = false }) {
  if (!visible) return null

  return (
    <div className="local-view-notice" role="note" aria-live="polite">
      Local conjunction view — separation magnified for visibility
    </div>
  )
}