/**
 * SpaceObject — Procedural 3D models for satellites and debris objects.
 *
 * Protected Satellite:
 * - Central bus (cuboid)
 * - Two solar panel wings
 * - Small antenna/dish
 * - Metallic materials with cyan accent
 *
 * Threat/Debris Object:
 * - Irregular dark metallic mesh (tumbling appearance)
 * - Red/amber accent
 * - Not weapon-like
 *
 * Visual size exaggeration: Objects are enlarged for visibility.
 * Disclosure: "Object sizes enlarged for visibility."
 * Trajectory distances are NOT scaled inconsistently.
 */
import React, { useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// ─── Protected Satellite ─────────────────────────────────────────────────────
export function ProtectedSatellite({
  position = [0, 0, 0],
  scale = 1,
  highlighted = false,
  pinned = false,
  onPointerOver,
  onPointerOut,
  onClick,
}) {
  const meshRef = useReactThreeFiberRef()
  const groupRef = React.useRef(null)

  // Subtle rotation for visual interest (solar panels facing sun)
  useFrame((state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05
    }
  })

  // Emphasis colors
  const baseColor = highlighted || pinned ? '#33b1ff' : '#66ccff'
  const emissiveColor = highlighted || pinned ? '#33b1ff' : '#004466'
  const emissiveIntensity = highlighted || pinned ? 0.4 : 0.15

  return (
    <group
      ref={groupRef}
      position={position}
      scale={scale}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
      name="protected-satellite"
    >
      {/* Invisible hit target for easier hovering (slightly larger than visual) */}
      <mesh
        visible={false}
        geometry={useMemo(() => new THREE.BoxGeometry(4, 4, 4), [])}
        material={useMemo(() => new THREE.MeshBasicMaterial({ visible: false }), [])}
        onPointerOver={onPointerOver}
        onPointerOut={onPointerOut}
        onClick={onClick}
        name="protected-satellite-hit"
      />

      {/* Central bus */}
      <mesh
        ref={meshRef}
        geometry={useMemo(() => new THREE.BoxGeometry(1.2, 0.8, 1.0), [])}
        material={useMemo(() => new THREE.MeshStandardMaterial({
          color: baseColor,
          emissive: emissiveColor,
          emissiveIntensity,
          metalness: 0.7,
          roughness: 0.3,
        }), [baseColor, emissiveColor, emissiveIntensity])}
        castShadow
        receiveShadow
        name="satellite-bus"
      >
        <meshStandardMaterial attach="material" />
      </mesh>

      {/* Solar panel +Y wing */}
      <group position={[0, 0, 0]} name="solar-wing-positive-y">
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.1, 3.5, 2.0), [])}
          material={useMemo(() => new THREE.MeshStandardMaterial({
            color: 0x1a1a2e,
            emissive: highlighted || pinned ? '#0a2a4a' : '#000',
            emissiveIntensity: highlighted || pinned ? 0.3 : 0.1,
            metalness: 0.5,
            roughness: 0.2,
          }), [highlighted, pinned])}
          castShadow
          receiveShadow
          position={[0, 2.0, 0]}
          name="solar-panel-plus-y"
        />
        {/* Panel detail lines */}
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.12, 3.5, 0.15), [])}
          material={useMemo(() => new THREE.MeshBasicMaterial({ color: 0x0a0a1a }), [])}
          position={[0, 2.0, 0.9]}
        />
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.12, 3.5, 0.15), [])}
          material={useMemo(() => new THREE.MeshBasicMaterial({ color: 0x0a0a1a }), [])}
          position={[0, 2.0, -0.9]}
        />
      </group>

      {/* Solar panel -Y wing */}
      <group position={[0, 0, 0]} name="solar-wing-negative-y">
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.1, 3.5, 2.0), [])}
          material={useMemo(() => new THREE.MeshStandardMaterial({
            color: 0x1a1a2e,
            emissive: highlighted || pinned ? '#0a2a4a' : '#000',
            emissiveIntensity: highlighted || pinned ? 0.3 : 0.1,
            metalness: 0.5,
            roughness: 0.2,
          }), [highlighted, pinned])}
          castShadow
          receiveShadow
          position={[0, -2.0, 0]}
          name="solar-panel-minus-y"
        />
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.12, 3.5, 0.15), [])}
          material={useMemo(() => new THREE.MeshBasicMaterial({ color: 0x0a0a1a }), [])}
          position={[0, -2.0, 0.9]}
        />
        <mesh
          geometry={useMemo(() => new THREE.BoxGeometry(0.12, 3.5, 0.15), [])}
          material={useMemo(() => new THREE.MeshBasicMaterial({ color: 0x0a0a1a }), [])}
          position={[0, -2.0, -0.9]}
        />
      </group>

      {/* Antenna/dish */}
      <group position={[0.7, 0, 0.2]} name="antenna">
        <mesh
          geometry={useMemo(() => new THREE.CylinderGeometry(0.04, 0.04, 0.6, 8), [])}
          material={useMemo(() => new THREE.MeshStandardMaterial({
            color: 0x555566,
            metalness: 0.8,
            roughness: 0.2,
          }), [])}
          position={[0.3, 0, 0]}
          rotation={[0, 0, Math.PI / 2]}
          name="antenna-boom"
        />
        <mesh
          geometry={useMemo(() => new THREE.ConeGeometry(0.35, 0.4, 16), [])}
          material={useMemo(() => new THREE.MeshStandardMaterial({
            color: 0x888899,
            metalness: 0.9,
            roughness: 0.1,
          }), [])}
          position={[0.6, 0, 0]}
          rotation={[0, 0, Math.PI / 2]}
          name="antenna-dish"
        />
      </group>

      {/* Cyan accent glow when highlighted/pinned */}
      {(highlighted || pinned) && (
        <mesh name="satellite-glow">
          <sphereGeometry args={[1.5, 16, 16]} />
          <meshBasicMaterial
            color="#33b1ff"
            transparent
            opacity={0.12}
            depthWrite={false}
            side={THREE.BackSide}
          />
        </mesh>
      )}
    </group>
  )
}

// ─── Threat/Debris Object ────────────────────────────────────────────────────
export function ThreatObject({
  position = [0, 0, 0],
  scale = 1,
  highlighted = false,
  pinned = false,
  onPointerOver,
  onPointerOut,
  onClick,
}) {
  const groupRef = React.useRef(null)

  // Tumbling rotation for debris appearance
  useFrame((state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.x += delta * 0.15
      groupRef.current.rotation.y += delta * 0.22
      groupRef.current.rotation.z += delta * 0.08
    }
  })

  const baseColor = highlighted || pinned ? '#fa4d56' : '#aa3338'
  const emissiveColor = highlighted || pinned ? '#fa4d56' : '#441111'
  const emissiveIntensity = highlighted || pinned ? 0.4 : 0.15

  // Generate irregular debris shape (same seed for consistency)
  const debrisGeometry = useMemo(() => {
    const geom = new THREE.IcosahedronGeometry(1, 1)
    const positions = geom.attributes.position
    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i)
      const y = positions.getY(i)
      const z = positions.getZ(i)
      // Add controlled irregularity
      const noise = (Math.sin(x * 10) + Math.cos(y * 10) + Math.sin(z * 10)) * 0.15
      const len = Math.sqrt(x * x + y * y + z * z)
      positions.setXYZ(i, x + x * noise, y + y * noise, z + z * noise)
    }
    geom.computeVertexNormals()
    return geom
  }, [])

  return (
    <group
      ref={groupRef}
      position={position}
      scale={scale}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
      name="threat-object"
    >
      {/* Invisible hit target for easier hovering */}
      <mesh
        visible={false}
        geometry={useMemo(() => new THREE.SphereGeometry(1.8, 16, 16), [])}
        material={useMemo(() => new THREE.MeshBasicMaterial({ visible: false }), [])}
        onPointerOver={onPointerOver}
        onPointerOut={onPointerOut}
        onClick={onClick}
        name="threat-object-hit"
      />

      {/* Main debris body */}
      <mesh
        geometry={debrisGeometry}
        material={useMemo(() => new THREE.MeshStandardMaterial({
          color: baseColor,
          emissive: emissiveColor,
          emissiveIntensity,
          metalness: 0.6,
          roughness: 0.5,
          flatShading: true,
        }), [baseColor, emissiveColor, emissiveIntensity])}
        castShadow
        receiveShadow
        name="debris-body"
      />

      {/* Red accent glow when highlighted/pinned */}
      {(highlighted || pinned) && (
        <mesh name="debris-glow">
          <sphereGeometry args={[2.0, 16, 16]} />
          <meshBasicMaterial
            color="#fa4d56"
            transparent
            opacity={0.12}
            depthWrite={false}
            side={THREE.BackSide}
          />
        </mesh>
      )}
    </group>
  )
}

// ─── Size Disclosure Component ───────────────────────────────────────────────
export function SizeDisclosure() {
  return (
    <div className="size-disclosure" role="note" aria-live="polite">
      Object sizes enlarged for visibility. Trajectory distances to scale.
    </div>
  )
}

// ─── Helper hook for R3F ref ─────────────────────────────────────────────────
function useReactThreeFiberRef() {
  const ref = React.useRef()
  return ref
}