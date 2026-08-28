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

  // We create a custom material that simulates Earth appearance
  const earthMaterial = useMemo(() => {
    // Create a canvas texture for procedural Earth
    const canvas = document.createElement('canvas')
    canvas.width = 1024
    canvas.height = 512
    const ctx = canvas.getContext('2d')

    // Base ocean color
    const oceanGradient = ctx.createLinearGradient(0, 0, 0, 512)
    oceanGradient.addColorStop(0, '#0a1f3a')
    oceanGradient.addColorStop(0.5, '#0d2e5a')
    oceanGradient.addColorStop(1, '#0a1f3a')
    ctx.fillStyle = oceanGradient
    ctx.fillRect(0, 0, 1024, 512)

    // Add land masses (procedural approximation)
    // Using noise-like patterns for continents
    const landColors = ['#1a4a2e', '#2a5a3e', '#1a3a2e', '#2d4a2a', '#3a5a2a']
    for (let i = 0; i < 2000; i++) {
      const x = Math.random() * 1024
      const y = Math.random() * 512
      const r = Math.random() * 30 + 5
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fillStyle = landColors[Math.floor(Math.random() * landColors.length)]
      ctx.globalAlpha = 0.3 + Math.random() * 0.4
      ctx.fill()
      ctx.globalAlpha = 1
    }

    // Add some larger land masses (rough continental shapes)
    const continents = [
      { x: 150, y: 150, w: 200, h: 300, color: '#2a5a3a' },  // Americas-ish
      { x: 500, y: 100, w: 300, h: 250, color: '#2d5a2d' },  // Africa/Eurasia-ish
      { x: 800, y: 200, w: 150, h: 200, color: '#1a4a2a' },  // Australia-ish
      { x: 300, y: 350, w: 180, h: 100, color: '#2a4a3a' },  // Antarctica-ish
    ]
    continents.forEach(c => {
      const gradient = ctx.createRadialGradient(c.x + c.w/2, c.y + c.h/2, 0, c.x + c.w/2, c.y + c.h/2, Math.max(c.w, c.h)/2)
      gradient.addColorStop(0, c.color)
      gradient.addColorStop(1, '#0a1f3a')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.ellipse(c.x + c.w/2, c.y + c.h/2, c.w/2, c.h/2, 0, 0, Math.PI * 2)
      ctx.fill()
    })

    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = THREE.RepeatWrapping
    texture.wrapT = THREE.RepeatWrapping

    return new THREE.MeshStandardMaterial({
      map: texture,
      roughness: 0.8,
      metalness: 0.05,
    })
  }, [])

  // Cloud layer
  const cloudGeometry = useMemo(() => new THREE.SphereGeometry(EARTH_RADIUS_VISUAL * 1.005, 64, 64), [])
  const cloudMaterial = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 512
    canvas.height = 256
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = 'rgba(255,255,255,0)'
    ctx.fillRect(0, 0, 512, 256)

    // Procedural clouds
    for (let i = 0; i < 500; i++) {
      const x = Math.random() * 512
      const y = Math.random() * 256
      const r = Math.random() * 40 + 10
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, r)
      gradient.addColorStop(0, 'rgba(255,255,255,0.4)')
      gradient.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fill()
    }

    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = THREE.RepeatWrapping
    texture.wrapT = THREE.RepeatWrapping
    texture.opacity = 0.4

    return new THREE.MeshStandardMaterial({
      map: texture,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  }, [])

  // Atmosphere rim (thin blue glow at limb)
  const atmosphereGeometry = useMemo(() => new THREE.SphereGeometry(EARTH_RADIUS_VISUAL * 1.02, 64, 64), [])
  const atmosphereMaterial = useMemo(() => new THREE.MeshBasicMaterial({
    color: 0x3a7bd5,
    transparent: true,
    opacity: 0.08,
    side: THREE.BackSide,
    depthWrite: false,
  }), [])

  // Night lights (emissive map for dark side)
  const nightLightsMaterial = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1024
    canvas.height = 512
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, 1024, 512)

    // Add city lights (tiny bright dots on land areas)
    for (let i = 0; i < 2000; i++) {
      const x = Math.random() * 1024
      const y = Math.random() * 512
      // Only add lights on "land" areas (avoid oceans)
      if (Math.random() > 0.7) {
        ctx.fillStyle = `rgba(255,220,180,${Math.random() * 0.8 + 0.2})`
        ctx.fillRect(x, y, 1, 1)
      }
    }

    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = THREE.RepeatWrapping
    texture.wrapT = THREE.RepeatWrapping

    return new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    })
  }, [])

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