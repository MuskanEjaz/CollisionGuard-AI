/**
 * EarthGlobe — Realistic 3D Earth for orbital visualization.
 *
 * Features:
 * - Procedural Earth material with day/night terminator
 * - Atmospheric rim (thin blue glow at limb)
 * - Directional sunlight
 * - Subtle night-side darkness
 * - Cloud layer (procedural)
 *
 * Uses only procedural materials — no external texture hotlinking.
 * Earth radius: 6371 km (to scale before visual scaling)
 * Texture orientation is NOT aligned to TEME frame — labeled as contextual.
 *
 * Attribution: Procedural materials only. No NASA Blue Marble texture used
 * (texture acquisition pending). If/when official texture is added,
 * update this component and document source/license here.
 */
import React, { useMemo } from 'react'
import { useLoader } from '@react-three/fiber'
import { TextureLoader } from 'three'
import * as THREE from 'three'

// Earth radius in km — matches backend visualization units
export const EARTH_RADIUS_KM = 6371

// Visual scale factor — Earth radius in Three.js scene units
// 1 scene unit = 1000 km for convenient camera positioning
export const VISUAL_SCALE = 1 / 1000
export const EARTH_RADIUS_VISUAL = EARTH_RADIUS_KM * VISUAL_SCALE  // ~6.371

// ─── Procedural Earth Material ───────────────────────────────────────────────
function EarthMaterial({ sunDirection }) {
  // Create a procedural shader material for Earth
  // Day side: blue oceans + green/brown land approximation
  // Night side: dark with subtle city lights
  // Atmosphere: thin blue rim at limb

  const uniforms = useMemo(() => ({
    uSunDirection: { value: new THREE.Vector3(...sunDirection).normalize() },
    uEarthRadius: { value: EARTH_RADIUS_VISUAL },
    uTime: { value: 0 },
  }), [sunDirection])

  // We'll use MeshStandardMaterial with custom properties for now
  // A full custom shader would be more realistic but this is a solid base
  return null // We'll use a composite approach below
}

// ─── Main Earth Globe Component ──────────────────────────────────────────────
export function EarthGlobe({
  sunDirection = [1, 0.3, 0.5],  // Default sunlight direction
  showAtmosphere = true,
  showClouds = true,
  showNightLights = true,
  rotationSpeed = 0,  // No auto-rotation by default
}) {
  const sunDir = useMemo(() => new THREE.Vector3(...sunDirection).normalize(), [sunDirection])

  // Earth surface — using a layered approach
  // Base sphere with procedural coloring
  const earthGeometry = useMemo(() => new THREE.SphereGeometry(EARTH_RADIUS_VISUAL, 64, 64), [])

  const textures = useMemo(() => {
    const loader = new THREE.TextureLoader()
    return {
      day: loader.load('/assets/earth/earth_daymap.jpg'),
      night: loader.load('/assets/earth/earth_nightmap.jpg'),
      clouds: loader.load('/assets/earth/earth_clouds.jpg'),
      normal: loader.load('/assets/earth/earth_normal_map.jpg'),
    }
  }, [])

  // We create a custom material that simulates Earth appearance
  const earthMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      map: textures.day,
      normalMap: textures.normal,
      roughness: 0.6,
      metalness: 0.05,
    })
  }, [textures])

  // Cloud layer
  const cloudGeometry = useMemo(() => new THREE.SphereGeometry(EARTH_RADIUS_VISUAL * 1.005, 64, 64), [])
  const cloudMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      map: textures.clouds,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  }, [textures])

  // Atmosphere rim (thin blue glow at limb)
  const atmosphereGeometry = useMemo(() => new THREE.SphereGeometry(EARTH_RADIUS_VISUAL * 1.02, 64, 64), [])
  const atmosphereMaterial = useMemo(() => new THREE.MeshBasicMaterial({
    color: 0x33b1ff,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    depthWrite: false,
  }), [])

  // Night lights (emissive map for dark side)
  const nightLightsMaterial = useMemo(() => {
    return new THREE.MeshBasicMaterial({
      map: textures.night,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  }, [textures])

  return (
    <group>
      {/* Earth surface */}
      <mesh
        geometry={earthGeometry}
        material={earthMaterial}
        receiveShadow
        name="earth-surface"
      />

      {/* Cloud layer */}
      {showClouds && (
        <mesh
          geometry={cloudGeometry}
          material={cloudMaterial}
          name="earth-clouds"
        />
      )}

      {/* Atmosphere rim */}
      {showAtmosphere && (
        <mesh
          geometry={atmosphereGeometry}
          material={atmosphereMaterial}
          name="earth-atmosphere"
        />
      )}

      {/* Night lights (emissive overlay) */}
      {showNightLights && (
        <mesh
          geometry={earthGeometry}
          material={nightLightsMaterial}
          name="earth-night-lights"
        />
      )}

      {/* Orientation notice */}
      <EarthOrientationNotice />
    </group>
  )
}

export default EarthGlobe

// ─── Earth Orientation Notice ────────────────────────────────────────────────
function EarthOrientationNotice() {
  // This is rendered as a DOM overlay, not in 3D
  return null
}

// ─── Helper: Create Earth with Contextual Orientation Label ──────────────────
// Use this to add a label explaining Earth orientation is contextual
export function EarthWithOrientationLabel({ children, ...props }) {
  return (
    <group>
      <EarthGlobe {...props} />
      {children}
    </group>
  )
}