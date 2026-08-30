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
  const groupRef = React.useRef(null)
  const active = highlighted || pinned

  useFrame((state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08
    }
  })

  return (
    <group
      ref={groupRef}
      position={position}
      scale={scale * 0.32}
      rotation={[0.18, 0.35, -0.12]}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
      name="protected-satellite"
    >
      {/* Larger invisible target preserves reliable hover interaction. */}
      <mesh visible={false} name="protected-satellite-hit">
        <sphereGeometry args={[2.2, 12, 12]} />
        <meshBasicMaterial visible={false} />
      </mesh>

      {/* Compact metallic spacecraft bus. */}
      <mesh castShadow receiveShadow name="satellite-bus">
        <boxGeometry args={[1.05, 0.72, 0.82]} />
        <meshStandardMaterial
          color={active ? '#90d5ff' : '#d0dce8'}
          emissive={active ? '#0d6b9c' : '#142a40'}
          emissiveIntensity={active ? 0.6 : 0.25}
          metalness={0.82}
          roughness={0.3}
        />
      </mesh>

      {/* Gold thermal face gives the model a recognizable spacecraft body. */}
      <mesh position={[0, 0, 0.416]} name="thermal-panel">
        <boxGeometry args={[0.78, 0.48, 0.035]} />
        <meshStandardMaterial
          color="#c9952e"
          emissive="#3a2605"
          emissiveIntensity={0.18}
          metalness={0.5}
          roughness={0.34}
        />
      </mesh>

      {/* Horizontal solar wings: compact and readable at global scale. */}
      <group name="solar-array">
        <mesh position={[1.18, 0, 0]} castShadow name="solar-panel-right">
          <boxGeometry args={[1.25, 0.07, 0.7]} />
          <meshStandardMaterial
            color={active ? '#1c66b8' : '#0f3875'}
            emissive={active ? '#0a4278' : '#041738'}
            emissiveIntensity={active ? 0.45 : 0.2}
            metalness={0.5}
            roughness={0.3}
          />
        </mesh>

        <mesh position={[-1.18, 0, 0]} castShadow name="solar-panel-left">
          <boxGeometry args={[1.25, 0.07, 0.7]} />
          <meshStandardMaterial
            color={active ? '#1c66b8' : '#0f3875'}
            emissive={active ? '#0a4278' : '#041738'}
            emissiveIntensity={active ? 0.45 : 0.2}
            metalness={0.5}
            roughness={0.3}
          />
        </mesh>

        {/* Slim silver booms connect panels to the bus. */}
        <mesh position={[0.72, 0, 0]}>
          <boxGeometry args={[0.42, 0.05, 0.08]} />
          <meshStandardMaterial color="#9aa8b6" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[-0.72, 0, 0]}>
          <boxGeometry args={[0.42, 0.05, 0.08]} />
          <meshStandardMaterial color="#9aa8b6" metalness={0.8} roughness={0.25} />
        </mesh>
      </group>

      {/* Small communications antenna. */}
      <group position={[0.15, 0.42, 0]} name="antenna">
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.025, 0.025, 0.42, 8]} />
          <meshStandardMaterial color="#aeb8c2" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0.48, 0]} rotation={[0, 0, Math.PI]}>
          <coneGeometry args={[0.18, 0.16, 20]} />
          <meshStandardMaterial color="#d6dde5" metalness={0.75} roughness={0.22} />
        </mesh>
      </group>

      {/* Central bright cyan beacon light */}
      <mesh name="satellite-beacon">
        <sphereGeometry args={[0.15, 16, 16]} />
        <meshBasicMaterial color="#00e5ff" />
      </mesh>

      {/* Visible blue glow aura */}
      <mesh name="satellite-glow">
        <sphereGeometry args={[1.85, 24, 24]} />
        <meshBasicMaterial
          color="#33b1ff"
          transparent
          opacity={active ? 0.35 : 0.22}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>
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

  const baseColor = highlighted || pinned ? '#fa4d56' : '#3a3f4a'
  const emissiveColor = highlighted || pinned ? '#fa4d56' : '#221414'
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
          metalness: 0.8,
          roughness: 0.4,
          flatShading: true,
        }), [baseColor, emissiveColor, emissiveIntensity])}
        castShadow
        receiveShadow
        name="debris-body"
      />

      {/* Central glowing red hazard hotspot */}
      <mesh name="debris-core">
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshBasicMaterial color="#ff3b30" />
      </mesh>

      {/* Visible red danger glow aura */}
      <mesh name="debris-glow">
        <sphereGeometry args={[2.0, 24, 24]} />
        <meshBasicMaterial
          color="#fa4d56"
          transparent
          opacity={highlighted || pinned ? 0.35 : 0.22}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>
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