/**
 * LiveCelestrakPanel — CelesTrak live two-object fetch form.
 *
 * Allows the operator to enter two NORAD catalog IDs, validate them,
 * fetch live OMM elements from CelesTrak, and run the deterministic
 * analysis pipeline.
 *
 * All provenance values (source, format, epoch, age, covariance note,
 * risk basis) are read from the backend response — never hardcoded.
 *
 * Human-supervised decision-support prototype. Simulation only.
 */
import { useState } from 'react'
import { apiPost } from '../api/client'

// ── small helpers ─────────────────────────────────────────────────────────────

function isPositiveInteger(v) {
  return /^\d+$/.test(String(v).trim()) && parseInt(v, 10) > 0
}

function MetaRow({ label, value, mono = false }) {
  return (
    <div className="sb-meta-row">
      <span>{label}</span>
      <span style={mono ? { fontFamily: 'var(--mono)', fontSize: 11 } : undefined}>
        {value ?? 'Not provided'}
      </span>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function LiveCelestrakPanel({ onAnalysis, disabled }) {
  const [protectedId, setProtectedId] = useState('')
  const [threatId,    setThreatId]    = useState('')
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [lastResult,  setLastResult]  = useState(null)

  // ── Validation ─────────────────────────────────────────────────────────────
  const protectedValid = isPositiveInteger(protectedId)
  const threatValid    = isPositiveInteger(threatId)
  const idsMatch       = protectedId.trim() === threatId.trim() &&
                         protectedId.trim() !== ''
  const canFetch       = protectedValid && threatValid && !idsMatch && !loading && !disabled

  function validationMessage() {
    if (protectedId && !protectedValid)
      return 'Protected satellite ID must be a positive integer.'
    if (threatId && !threatValid)
      return 'Threat object ID must be a positive integer.'
    if (idsMatch)
      return 'Protected and threat IDs must differ.'
    return ''
  }

  // ── Fetch & analyse ────────────────────────────────────────────────────────
  async function handleFetch() {
    if (!canFetch) return
    setLoading(true)
    setError('')
    setLastResult(null)

    try {
      const result = await apiPost('/scenarios/live', {
        protected_catalog_id: parseInt(protectedId.trim(), 10),
        threat_catalog_id:    parseInt(threatId.trim(),    10),
      })
      setLastResult(result)
      onAnalysis?.(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const valMsg = validationMessage()

  return (
    <div className="live-panel" aria-label="Live CelesTrak two-object fetch">

      {/* Header */}
      <div className="live-panel-hd">
        <span className="live-badge" aria-label="Live CelesTrak data">● LIVE</span>
        <span>CelesTrak GP Catalog</span>
        <span style={{ fontSize: 10, color: 'var(--tx-lo)', marginLeft: 'auto' }}>
          Public orbital elements · No covariance · Screening-level
        </span>
      </div>

      {/* Input fields */}
      <div className="live-inputs" role="group" aria-label="NORAD catalog ID inputs">
        <div className="live-field">
          <label htmlFor="live-protected-id" className="live-label">
            Protected Satellite — NORAD Cat ID
          </label>
          <input
            id="live-protected-id"
            type="text"
            inputMode="numeric"
            className={`live-input ${protectedId && !protectedValid ? 'live-input-err' : ''}`}
            value={protectedId}
            onChange={e => setProtectedId(e.target.value)}
            placeholder="e.g. 25544"
            disabled={loading || disabled}
            aria-invalid={protectedId && !protectedValid ? 'true' : undefined}
            aria-describedby="live-protected-hint"
            maxLength={10}
          />
          <span id="live-protected-hint" className="live-hint">
            Positive integer NORAD catalog number
          </span>
        </div>

        <div className="live-field">
          <label htmlFor="live-threat-id" className="live-label">
            Threat Object — NORAD Cat ID
          </label>
          <input
            id="live-threat-id"
            type="text"
            inputMode="numeric"
            className={`live-input ${threatId && !threatValid ? 'live-input-err' : ''}`}
            value={threatId}
            onChange={e => setThreatId(e.target.value)}
            placeholder="e.g. 33591"
            disabled={loading || disabled}
            aria-invalid={threatId && !threatValid ? 'true' : undefined}
            aria-describedby="live-threat-hint"
            maxLength={10}
          />
          <span id="live-threat-hint" className="live-hint">
            Must differ from protected satellite ID
          </span>
        </div>
      </div>

      {/* Validation message */}
      {valMsg && (
        <div role="alert" className="live-val-msg" aria-live="polite">
          {valMsg}
        </div>
      )}

      {/* Actions */}
      <div className="action-bar" style={{ marginTop: 'var(--s3)' }}>
        <button
          className="btn btn-primary"
          onClick={handleFetch}
          disabled={!canFetch}
          aria-label={
            !canFetch && valMsg
              ? `Cannot fetch: ${valMsg}`
              : 'Fetch from CelesTrak and run deterministic analysis'
          }
        >
          {loading ? (
            <><span className="spinner" aria-hidden="true" /> Fetching…</>
          ) : 'Fetch &amp; Analyse'}
        </button>
        {(protectedId || threatId) && !loading && (
          <button
            className="btn btn-ghost"
            onClick={() => { setProtectedId(''); setThreatId(''); setError(''); setLastResult(null) }}
            aria-label="Clear inputs"
          >
            Clear
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div role="alert" className="live-error" aria-live="polite">
          <strong>Fetch failed:</strong> {error}
          {error.toLowerCase().includes('timeout') && (
            <div style={{ marginTop: 4, fontSize: 11 }}>
              CelesTrak did not respond within the timeout. Check your internet
              connection or try again.
            </div>
          )}
          {error.toLowerCase().includes('not in leo') && (
            <div style={{ marginTop: 4, fontSize: 11 }}>
              One or both objects are not in Low Earth Orbit. CollisionGuard AI
              supports LEO objects only (mean motion &gt; 11.25 rev/day).
            </div>
          )}
          {error.toLowerCase().includes('not found') && (
            <div style={{ marginTop: 4, fontSize: 11 }}>
              Object not found in CelesTrak catalog. Verify the NORAD catalog ID.
            </div>
          )}
        </div>
      )}

      {/* Source metadata — shown after a successful fetch */}
      {lastResult && (
        <div className="live-meta-panel" role="region" aria-label="CelesTrak source metadata">
          <div className="live-meta-hd">Source Provenance</div>
          <div className="sb-meta">
            <MetaRow label="Provider"        value={lastResult.source_provider} />
            <MetaRow label="Format"          value={lastResult.source_format} />
            <MetaRow label="Retrieved (UTC)" value={lastResult.source_retrieved_at_utc} mono />
            <MetaRow label="Protected"       value={`${lastResult.protected_object_name} (${lastResult.protected_object_catalog_id})`} />
            <MetaRow label="Protected epoch" value={lastResult.protected_element_epoch_utc} mono />
            <MetaRow label="Protected age"   value={`${lastResult.protected_element_age_hours} h`} />
            <MetaRow label="Threat"          value={`${lastResult.threat_object_name} (${lastResult.threat_object_catalog_id})`} />
            <MetaRow label="Threat epoch"    value={lastResult.threat_element_epoch_utc} mono />
            <MetaRow label="Threat age"      value={`${lastResult.threat_element_age_hours} h`} />
          </div>

          {/* Scientific limitations — always shown */}
          <div className="live-disclosures">
            <details>
              <summary className="live-disclosure-summary">
                Covariance &amp; Risk Estimate Basis
              </summary>
              <div className="live-disclosure-body">
                <div className="live-disclosure-item">
                  <span className="live-disclosure-lbl">Covariance source:</span>
                  <span>{lastResult.covariance_source}</span>
                </div>
                <div className="live-disclosure-item">
                  <span className="live-disclosure-lbl">Risk basis:</span>
                  <span>{lastResult.risk_estimate_basis}</span>
                </div>
                <div className="live-disclosure-item">
                  <span className="live-disclosure-lbl">Limitations:</span>
                  <span>{lastResult.data_limitations}</span>
                </div>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  )
}
