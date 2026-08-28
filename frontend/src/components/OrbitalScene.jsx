/**
 * OrbitalScene — Main Three.js scene composition for orbital visualization.
 *
 * Composes:
 * - EarthGlobe (realistic 3D Earth)
 * - ProtectedSatellite & ThreatObject (3D models at actual backend positions)
 * - ProtectedTrajectory & ThreatTrajectory (backend-propagated paths)
 * - ClosestApproach (TCA geometry with markers, connector, midpoint)
 * - TrajectoryControls (camera with preset views)
 * - Starfield background
 * - Directional lighting (sun)
 *
 * All positions from backend visualization data contract.
 * No frontend orbit approximation — only backend SGP4 samples.
 */
import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, Stars, Html, ContactShadows } from '@react-three/drei'
import * as THREE from 'three'

import { EarthGlobe, EARTH_RADIUS_VISUAL, VISUAL_SCALE } from './EarthGlobe'
import { ProtectedSatellite, ThreatObject, SizeDisclosure } from './SpaceObject'
import { ProtectedTrajectory, ThreatTrajectory, PostManeuverTrajectory } from './TrajectoryLine'
import { ClosestApproach, LocalViewNotice } from './ClosestApproach'
import { TrajectoryControls, TrajectoryControlOverlay } from './TrajectoryControls'
import { TrajectoryTooltip, getTooltipContent, useTrajectoryTooltip } from './TrajectoryTooltip'

// ─── Scene Configuration ─────────────────────────────────────────────────────
const SCENE_CONFIG = {
  // Camera
  initialCamera: { position: [24, 18, 16], target: [0, 0, 0], fov: 45 },
  // Lighting
  sunDirection: [1, 0.3, 0.5],
  sunIntensity: 1.5,
  ambientIntensity: 0.4,
  // Performance
  pixelRatio: [1, 1.5],  // Cap at 1.5 for performance
  // Starfield
  starCount: 3000,
  starRadius: 100,
}

// ─── Main Orbital Scene (3D Canvas) ──────────────────────────────────────────
export function OrbitalScene({
  visualization,       // VisualizationData from backend
  analysis,            // FullAnalysisResponse (for metadata)
  selectedCandidate,   // Selected maneuver candidate (if any)
  emphasizedRole,      // Currently emphasized: 'protected'|'threat'|'post'|'tca'|null
  pinnedRole,          // Currently pinned: same values
  onEmphasisChange,    // Callback when emphasis changes (hover)
  onPinChange,         // Callback when pin changes (click)
  cameraMode,          // 'global' | 'tca' | 'protected' | 'threat'
  onCameraModeChange,
  className,
  style,
}) {
  // Extract data from visualization contract
  const samples = visualization?.samples ?? []
  const tcaData = visualization?.tca ?? null

  // Current positions (latest sample = epoch position)
  const latestSample = samples[samples.length - 1]
  const protectedPosition = latestSample?.protected_position_km ?? null
  const threatPosition = latestSample?.threat_position_km ?? null

  // TCA positions
  const tcaProtectedPos = tcaData?.protected_position_km ?? null
  const tcaThreatPos = tcaData?.threat_position_km ?? null

  // Sun direction (normalized)
  const sunDir = useMemo(() => new THREE.Vector3(...SCENE_CONFIG.sunDirection).normalize(), [])

  // Emphasis states
  const protectedEmphasized = emphasizedRole === 'protected' || pinnedRole === 'protected'
  const threatEmphasized = emphasizedRole === 'threat' || pinnedRole === 'threat'
  const postEmphasized = emphasizedRole === 'post' || pinnedRole === 'post'
  const tcaEmphasized = emphasizedRole === 'tca' || pinnedRole === 'tca'

  const protectedDimmed = (emphasizedRole === 'threat' || emphasizedRole === 'post' || emphasizedRole === 'tca') && !pinnedRole
  const threatDimmed = (emphasizedRole === 'protected' || emphasizedRole === 'post' || emphasizedRole === 'tca') && !pinnedRole
  const postDimmed = (emphasizedRole === 'protected' || emphasizedRole === 'threat' || emphasizedRole === 'tca') && !pinnedRole

  // Post-maneuver data (only if evaluated candidate exists with actual coordinates)
  const postManeuverPositions = selectedCandidate?.post_maneuver_positions_km ?? null
  const postManeuverTimestamps = selectedCandidate?.post_maneuver_timestamps_utc ?? null
  const hasPostManeuver = !!(postManeuverPositions && postManeuverPositions.length > 1)

  // Tooltip management
  const { tooltip, pinned, position, showTooltip, hideTooltip, pinTooltip, unpinTooltip } = useTrajectoryTooltip()

  // Handle pointer events on 3D objects
  const handleObjectPointerOver = useCallback((role, e) => {
    const content = getTooltipContent(role, analysis, selectedCandidate, tcaData)
    if (content) showTooltip(content, { x: e.clientX, y: e.clientY })
    onEmphasisChange?.(role)
  }, [analysis, selectedCandidate, tcaData, showTooltip, onEmphasisChange])

  const handleObjectPointerOut = useCallback(() => {
    hideTooltip()
    onEmphasisChange?.(null)
  }, [hideTooltip, onEmphasisChange])

  const handleObjectClick = useCallback((role, e) => {
    e.stopPropagation()
    if (pinnedRole === role) {
      onPinChange?.(null)
      unpinTooltip()
    } else {
      const content = getTooltipContent(role, analysis, selectedCandidate, tcaData)
      if (content) {
        pinTooltip(content, { x: e.clientX, y: e.clientY })
        onPinChange?.(role)
      }
    }
  }, [pinnedRole, analysis, selectedCandidate, tcaData, onPinChange, pinTooltip, unpinTooltip])

  // Click empty space to clear
  const handleSceneClick = useCallback((e) => {
    if (pinnedRole) {
      onPinChange?.(null)
      unpinTooltip()
    }
  }, [pinnedRole, onPinChange, unpinTooltip])

  return (
    <div className={`orbital-scene ${className ?? ''}`} style={style} onClick={handleSceneClick}>
      <Canvas
        camera={SCENE_CONFIG.initialCamera}
        gl={{ preserveDrawingBuffer: true, antialias: true, alpha: true }}
        dpr={SCENE_CONFIG.pixelRatio}
        onCreated={({ gl }) => {
          gl.setClearColor(0x040a14, 1)
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.0
        }}
      >
        <scene background={new THREE.Color(0x040a14)}>
          {/* ── Lighting ───────────────────────────────────────────────── */}
          <ambientLight intensity={SCENE_CONFIG.ambientIntensity} color="#88aacc" />
          <directionalLight
            position={[sunDir.x * 100, sunDir.y * 100, sunDir.z * 100]}
            intensity={SCENE_CONFIG.sunIntensity}
            color="#fff8e7"
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-camera-near={1}
            shadow-camera-far={200}
            shadow-camera-left={-50}
            shadow-camera-right={50}
            shadow-camera-top={50}
            shadow-camera-bottom={-50}
            shadow-bias={-0.001}
          />

          {/* ── Starfield ───────────────────────────────────────────────── */}
          <Stars
            radius={SCENE_CONFIG.starRadius}
            depth={100}
            count={SCENE_CONFIG.starCount}
            factor={1.5}
            saturation={0.1}
            fade={true}
            style={{
              color: '#ffffff',
              sizeAttenuation: true,
            }}
          />

          {/* ── Earth Globe ─────────────────────────────────────────────── */}
          <EarthGlobe
            sunDirection={SCENE_CONFIG.sunDirection}
            showAtmosphere={true}
            showClouds={true}
            showNightLights={true}
          />

          {/* ── Trajectories (rendered first so they appear behind objects) ───── */}
          <ProtectedTrajectory
            samples={samples}
            emphasized={protectedEmphasized}
            dimmed={protectedDimmed}
            visible={true}
            opacity={0.5}
          />
          <ThreatTrajectory
            samples={samples}
            emphasized={threatEmphasized}
            dimmed={threatDimmed}
            visible={true}
            opacity={0.55}
          />
          {hasPostManeuver && (
            <PostManeuverTrajectory
              positions={postManeuverPositions}
              timestamps={postManeuverTimestamps}
              emphasized={postEmphasized}
              dimmed={postDimmed}
              visible={true}
              opacity={0.55}
            />
          )}

          {/* ── Space Objects ───────────────────────────────────────────── */}
          {protectedPosition && (
            <ProtectedSatellite
              position={protectedPosition.map(v => v * VISUAL_SCALE)}
              scale={0.8}
              highlighted={protectedEmphasized}
              pinned={pinnedRole === 'protected'}
              onPointerOver={(e) => handleObjectPointerOver('protected', e)}
              onPointerOut={handleObjectPointerOut}
              onClick={(e) => handleObjectClick('protected', e)}
            />
          )}

          {threatPosition && (
            <ThreatObject
              position={threatPosition.map(v => v * VISUAL_SCALE)}
              scale={0.6}
              highlighted={threatEmphasized}
              pinned={pinnedRole === 'threat'}
              onPointerOver={(e) => handleObjectPointerOver('threat', e)}
              onPointerOut={handleObjectPointerOut}
              onClick={(e) => handleObjectClick('threat', e)}
            />
          )}

          {/* ── TCA Geometry ─────────────────────────────────────────────── */}
          {tcaData && (
            <ClosestApproach
              tcaData={tcaData}
              emphasized={tcaEmphasized}
              visible={true}
              onPointerOver={(e) => handleObjectPointerOver('tca', e)}
              onPointerOut={handleObjectPointerOut}
              onClick={(e) => handleObjectClick('tca', e)}
            />
          )}

          {/* ── Camera Controls ──────────────────────────────────────────── */}
          <TrajectoryControls
            protectedPosition={protectedPosition}
            threatPosition={threatPosition}
            tcaProtectedPosition={tcaProtectedPos}
            tcaThreatPosition={tcaThreatPos}
            onViewChange={onCameraModeChange}
          >
            <TrajectoryControlOverlay
              protectedPosition={protectedPosition}
              threatPosition={threatPosition}
              tcaProtectedPosition={tcaProtectedPos}
              tcaThreatPosition={tcaThreatPos}
            />
          </TrajectoryControls>

          {/* ── Contact Shadows ──────────────────────────────────────────── */}
          <ContactShadows
            opacity={0.15}
            scale={20}
            blur={2}
            far={50}
            position={[0, -EARTH_RADIUS_VISUAL * 1.1, 0]}
          />
        </scene>

        {/* ── HTML Overlays ──────────────────────────────────────────────── */}
        <Html
          fullscreen
          prepend
          wrapperClass="orbital-html-overlay"
        >
          {/* Size disclosure */}
          <SizeDisclosure />

          {/* Local view notice */}
          <LocalViewNotice visible={cameraMode === 'tca'} />

          {/* Tooltip */}
          <TrajectoryTooltip
            content={tooltip}
            pinned={pinned}
            position={position}
            onClose={unpinTooltip}
          />

        </Html>
      </Canvas>
    </div>
  )
}

// ─── Wrapper with Error Boundary & Loading ───────────────────────────────────
export function OrbitalSceneWrapper({
  visualization,
  analysis,
  selectedCandidate,
  emphasizedRole,
  pinnedRole,
  onEmphasisChange,
  onPinChange,
  cameraMode,
  onCameraModeChange,
  loading,
  error,
  className,
  style,
}) {
  if (loading) {
    return (
      <div className="orbital-scene-loading" style={style}>
        <div className="loading-spinner" aria-hidden="true" />
        <span>Loading orbital visualization…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="orbital-scene-error" style={style} role="alert">
        <h3>Visualization Unavailable</h3>
        <p>{error}</p>
        <p className="error-fallback">WebGL may not be supported in this browser.</p>
      </div>
    )
  }

  if (!visualization) {
    return (
      <div className="orbital-scene-empty" style={style}>
        <span style={{ fontSize: 48, opacity: 0.3 }}>◎</span>
        <p>Run analysis to view orbital trajectories.</p>
      </div>
    )
  }

  return (
    <OrbitalScene
      visualization={visualization}
      analysis={analysis}
      selectedCandidate={selectedCandidate}
      emphasizedRole={emphasizedRole}
      pinnedRole={pinnedRole}
      onEmphasisChange={onEmphasisChange}
      onPinChange={onPinChange}
      cameraMode={cameraMode}
      onCameraModeChange={onCameraModeChange}
      className={className}
      style={style}
    />
  )
}

// ─── WebGL Fallback Detection ────────────────────────────────────────────────
export function useWebGLSupport() {
  const [supported, setSupported] = useState(true)

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
      setSupported(!!gl)
    } catch {
      setSupported(false)
    }
  }, [])

  return supported
}