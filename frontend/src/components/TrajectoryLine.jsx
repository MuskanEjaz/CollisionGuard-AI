/**
 * TrajectoryLine — Renders orbital trajectory from backend samples.
 *
 * Uses standard Three.js line primitives so the scene remains compatible with
 * the React 18 + @react-three/fiber 8 stack without the removed fat-line package.
 */
import React, { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { VISUAL_SCALE } from './EarthGlobe'

function createTrajectoryGeometry(positions) {
  if (!positions || positions.length < 2) return null

  const positionArray = new Float32Array(positions.length * 3)
  positions.forEach((pos, i) => {
    positionArray[i * 3] = pos[0] * VISUAL_SCALE
    positionArray[i * 3 + 1] = pos[1] * VISUAL_SCALE
    positionArray[i * 3 + 2] = pos[2] * VISUAL_SCALE
  })

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positionArray, 3))
  return geometry
}

function useStyledLineMaterial({ color, opacity, visible, dashed = false, lineWidth = 2 }) {
  return useMemo(() => {
    const MaterialClass = dashed
      ? THREE.LineDashedMaterial
      : THREE.LineBasicMaterial

    return new MaterialClass({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      depthTest: true,
      ...(dashed
        ? {
            dashSize: 0.14,
            gapSize: 0.09,
            scale: 1,
          }
        : {}),
    })
  }, [color, opacity, dashed])
}

// ─── Protected Satellite Trajectory ──────────────────────────────────────────
export function ProtectedTrajectory({
  samples,
  emphasized = false,
  dimmed = false,
  visible = true,
  opacity = 0.5,
}) {
  const lineRef = useRef()

  const geometry = useMemo(() => {
    if (!samples || samples.length < 2) return null
    return createTrajectoryGeometry(samples.map(sample => sample.protected_position_km))
  }, [samples])

  const material = useStyledLineMaterial({
    color: 0x33b1ff,
    opacity: dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity),
    visible,
    lineWidth: emphasized ? 3.5 : (dimmed ? 1.0 : 2.0),
  })

  useFrame(() => {
    if (lineRef.current && lineRef.current.material) {
      lineRef.current.material.opacity = dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity)
    }
  })

  if (!geometry || !visible) return null

  return (
    <line ref={lineRef} geometry={geometry} material={material} name="protected-trajectory" />
  )
}

// ─── Threat Object Trajectory ────────────────────────────────────────────────
export function ThreatTrajectory({
  samples,
  emphasized = false,
  dimmed = false,
  visible = true,
  opacity = 0.55,
}) {
  const lineRef = useRef()

  const geometry = useMemo(() => {
    if (!samples || samples.length < 2) return null
    return createTrajectoryGeometry(samples.map(sample => sample.threat_position_km))
  }, [samples])

  const material = useStyledLineMaterial({
    color: 0xfa4d56,
    opacity: dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity),
    visible,
    dashed: true,
    lineWidth: emphasized ? 3.5 : (dimmed ? 1.0 : 2.0),
  })

  React.useEffect(() => {
    if (lineRef.current) {
      lineRef.current.computeLineDistances()
    }
  }, [geometry])

  useFrame(() => {
    if (lineRef.current && lineRef.current.material) {
      lineRef.current.material.opacity = dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity)
    }
  })

  if (!geometry || !visible) return null

  return (
    <line ref={lineRef} geometry={geometry} material={material} name="threat-trajectory" />
  )
}

// ─── Post-Maneuver Trajectory ────────────────────────────────────────────────
export function PostManeuverTrajectory({
  positions,
  timestamps,
  emphasized = false,
  dimmed = false,
  visible = true,
  opacity = 0.55,
}) {
  const lineRef = useRef()

  const geometry = useMemo(() => createTrajectoryGeometry(positions), [positions])

  const material = useStyledLineMaterial({
    color: 0x42be65,
    opacity: dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity),
    visible,
    lineWidth: emphasized ? 3.5 : (dimmed ? 1.0 : 2.0),
  })

  useFrame(() => {
    if (lineRef.current && lineRef.current.material) {
      lineRef.current.material.opacity = dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity)
    }
  })

  if (!geometry || !visible) return null

  return (
    <line ref={lineRef} geometry={geometry} material={material} name="post-maneuver-trajectory" />
  )
}

// ─── Generic Trajectory Line (for reuse) ─────────────────────────────────────
export function TrajectoryLine({
  positions,
  color = 0x33b1ff,
  emphasized = false,
  dimmed = false,
  visible = true,
  opacity = 0.5,
  dashed = false,
  lineWidth = 2.0,
}) {
  const lineRef = useRef()

  const geometry = useMemo(() => createTrajectoryGeometry(positions), [positions])

  const material = useStyledLineMaterial({
    color,
    opacity: dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity),
    visible,
    dashed,
    lineWidth: emphasized ? lineWidth * 1.75 : (dimmed ? lineWidth * 0.5 : lineWidth),
  })

  React.useEffect(() => {
    if (dashed && lineRef.current) {
      lineRef.current.computeLineDistances()
    }
  }, [geometry, dashed])

  useFrame(() => {
    if (lineRef.current && lineRef.current.material) {
      lineRef.current.material.opacity = dimmed ? opacity * 0.3 : (emphasized ? 0.95 : opacity)
    }
  })

  if (!geometry || !visible) return null

  return (
    <line ref={lineRef} geometry={geometry} material={material} name="trajectory-line" />
  )
}