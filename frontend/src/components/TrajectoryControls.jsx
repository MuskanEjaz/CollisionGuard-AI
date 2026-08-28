/**
 * TrajectoryControls — Camera and view controls for orbital visualization.
 *
 * Provides:
 * - OrbitControls with bounded distance (prevents camera entering Earth)
 * - Preset camera views: Global, Focus Protected, Focus Threat, Focus TCA, Reset
 * - Smooth transitions between views
 * - Keyboard accessible controls outside canvas
 */
import React, { useMemo, useCallback, useEffect } from 'react'
import { useThree, useFrame } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { EARTH_RADIUS_VISUAL, VISUAL_SCALE } from './EarthGlobe'

// ─── Camera Presets ──────────────────────────────────────────────────────────
export const CAMERA_PRESETS = {
  global: {
    position: new THREE.Vector3(24, 18, 16),
    target: new THREE.Vector3(0, 0, 0),
    name: 'Global View',
    description: 'Full orbital context with Earth, both trajectories, and TCA region',
  },
  protected: {
    position: null,  // Computed dynamically based on satellite position
    target: null,
    name: 'Focus Protected',
    description: 'Camera follows protected satellite',
  },
  threat: {
    position: null,  // Computed dynamically based on threat position
    target: null,
    name: 'Focus Threat',
    description: 'Camera follows threat object',
  },
  tca: {
    position: null,  // Computed dynamically based on TCA midpoint
    target: null,
    name: 'Focus TCA',
    description: 'Close-up view of closest approach geometry',
  },
  reset: {
    position: new THREE.Vector3(24, 18, 16),
    target: new THREE.Vector3(0, 0, 0),
    name: 'Reset View',
    description: 'Return to default global orbital view',
  },
}

// ─── Main Controls Component ─────────────────────────────────────────────────
export function TrajectoryControls({
  enabled = true,
  enableDamping = true,
  dampingFactor = 0.05,
  minDistance = EARTH_RADIUS_VISUAL * 1.2,  // Prevent camera entering Earth
  maxDistance = 50,
  onViewChange,
  children,
}) {
  const { camera, gl } = useThree()
  const controlsRef = React.useRef()

  // Configure OrbitControls
  useFrame(() => {
    if (controlsRef.current) {
      controlsRef.current.minDistance = minDistance
      controlsRef.current.maxDistance = maxDistance
      controlsRef.current.enableDamping = enableDamping
      controlsRef.current.dampingFactor = dampingFactor
      // Prevent camera from going below Earth surface
      controlsRef.current.minPolarAngle = 0
      controlsRef.current.maxPolarAngle = Math.PI
    }
  })

  // Smooth camera transition helper
  const transitionTo = useCallback((targetPosition, targetTarget, duration = 1000) => {
    if (!controlsRef.current) return

    const startPosition = camera.position.clone()
    const startTarget = controlsRef.current.target.clone()
    const startTime = performance.now()

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)

      camera.position.lerpVectors(startPosition, targetPosition, eased)
      controlsRef.current.target.lerpVectors(startTarget, targetTarget, eased)

      if (progress < 1) {
        requestAnimationFrame(animate)
      } else if (onViewChange) {
        onViewChange()
      }
    }

    requestAnimationFrame(animate)
  }, [camera, onViewChange])

  // View functions
  const focusGlobal = useCallback(() => {
    const preset = CAMERA_PRESETS.global
    transitionTo(preset.position, preset.target)
  }, [transitionTo])

  const focusProtected = useCallback((satellitePosition) => {
    if (!satellitePosition) return
    const target = new THREE.Vector3(...satellitePosition).multiplyScalar(VISUAL_SCALE)
    const pos = target.clone().multiplyScalar(1.5)
    transitionTo(pos, target)
  }, [transitionTo])

  const focusThreat = useCallback((threatPosition) => {
    if (!threatPosition) return
    const target = new THREE.Vector3(...threatPosition).multiplyScalar(VISUAL_SCALE)
    const pos = target.clone().multiplyScalar(1.5)
    transitionTo(pos, target)
  }, [transitionTo])

  const focusTCA = useCallback((protectedPos, threatPos) => {
    if (!protectedPos || !threatPos) return
    const midpoint = new THREE.Vector3(
      (protectedPos[0] + threatPos[0]) / 2,
      (protectedPos[1] + threatPos[1]) / 2,
      (protectedPos[2] + threatPos[2]) / 2
    ).multiplyScalar(VISUAL_SCALE)
    const pos = midpoint.clone().multiplyScalar(3)  // Close zoom
    transitionTo(pos, midpoint, 800)
  }, [transitionTo])

  const resetView = useCallback(() => {
    const preset = CAMERA_PRESETS.reset
    transitionTo(preset.position, preset.target)
  }, [transitionTo])

  return (
    <>
      <OrbitControls
        ref={controlsRef}
        makeDefault
        enableDamping={enableDamping}
        dampingFactor={dampingFactor}
        minDistance={minDistance}
        maxDistance={maxDistance}
        minPolarAngle={0}
        maxPolarAngle={Math.PI}
        enablePan={true}
        enableZoom={true}
        enableRotate={enabled}
      />
      <ControlsAPI
        focusGlobal={focusGlobal}
        focusProtected={focusProtected}
        focusThreat={focusThreat}
        focusTCA={focusTCA}
        resetView={resetView}
      >
        {children}
      </ControlsAPI>
    </>
  )
}

// ─── Controls API Context (for external keyboard buttons) ────────────────────
const ControlsContext = React.createContext(null)

export function ControlsAPI({ children, ...api }) {
  return (
    <ControlsContext.Provider value={api}>
      {children}
    </ControlsContext.Provider>
  )
}

export function useTrajectoryControls() {
  const context = React.useContext(ControlsContext)
  if (!context) {
    throw new Error('useTrajectoryControls must be used within TrajectoryControls')
  }
  return context
}

// ─── Keyboard-Accessible Control Buttons (DOM overlay) ───────────────────────
export function TrajectoryControlButtons({
  protectedPosition,
  threatPosition,
  tcaProtectedPosition,
  tcaThreatPosition,
  focusGlobal,
  focusProtected,
  focusThreat,
  focusTCA,
  resetView,
}) {
  return (
    <div className="trajectory-control-buttons" role="group" aria-label="Camera view controls">
      <button
        className="traj-control-btn"
        onClick={focusGlobal}
        title="Global orbital view (G)"
        aria-label="Global orbital view"
      >
        🌍 Global
      </button>
      <button
        className="traj-control-btn"
        onClick={() => focusProtected(protectedPosition)}
        disabled={!protectedPosition}
        title="Focus protected satellite (P)"
        aria-label="Focus protected satellite"
      >
        🛰 Protected
      </button>
      <button
        className="traj-control-btn"
        onClick={() => focusThreat(threatPosition)}
        disabled={!threatPosition}
        title="Focus threat object (T)"
        aria-label="Focus threat object"
      >
        ☄ Threat
      </button>
      <button
        className="traj-control-btn"
        onClick={() => focusTCA(tcaProtectedPosition, tcaThreatPosition)}
        disabled={!tcaProtectedPosition || !tcaThreatPosition}
        title="Focus closest approach (C)"
        aria-label="Focus closest approach"
      >
        ⊙ TCA
      </button>
      <button
        className="traj-control-btn traj-control-reset"
        onClick={resetView}
        title="Reset camera to default view (R)"
        aria-label="Reset camera view"
      >
        ↩ Reset
      </button>
    </div>
  )
}

export function TrajectoryControlOverlay(props) {
  const controls = useTrajectoryControls()

  useTrajectoryKeyboardShortcuts({
    ...controls,
    protectedPosition: props.protectedPosition,
    threatPosition: props.threatPosition,
    tcaProtectedPosition: props.tcaProtectedPosition,
    tcaThreatPosition: props.tcaThreatPosition,
  })

  return (
    <Html
      fullscreen
      prepend
      wrapperClass="orbital-html-overlay"
    >
      <TrajectoryControlButtons {...props} {...controls} />
    </Html>
  )
}

// ─── Keyboard Shortcuts Hook ─────────────────────────────────────────────────
export function useTrajectoryKeyboardShortcuts({
  focusGlobal,
  focusProtected,
  focusThreat,
  focusTCA,
  resetView,
  protectedPosition,
  threatPosition,
  tcaProtectedPosition,
  tcaThreatPosition,
}) {
  useEffect(() => {
    function handleKeyDown(e) {
      // Only trigger if not typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      switch (e.key.toLowerCase()) {
        case 'g':
          focusGlobal()
          break
        case 'p':
          if (protectedPosition) focusProtected(protectedPosition)
          break
        case 't':
          if (threatPosition) focusThreat(threatPosition)
          break
        case 'c':
          if (tcaProtectedPosition && tcaThreatPosition) focusTCA(tcaProtectedPosition, tcaThreatPosition)
          break
        case 'r':
        case 'escape':
          resetView()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [focusGlobal, focusProtected, focusThreat, focusTCA, resetView,
      protectedPosition, threatPosition, tcaProtectedPosition, tcaThreatPosition])
}