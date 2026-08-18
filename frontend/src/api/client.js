/**
 * API client -- Phase 7.
 * All calls go through apiGet / apiPost; base URL from VITE_API_BASE_URL.
 * Never hardcodes computed results. Never calls simulated execution "real".
 */
const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function _request(method, path, body) {
  const opts = {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const r = await fetch(`${BASE}${path}`, opts)
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try { detail = (await r.json()).detail ?? detail } catch (_) {}
    throw new Error(detail)
  }
  return r.json()
}

export const apiGet  = (path)        => _request('GET',    path)
export const apiPost = (path, body)  => _request('POST',   path, body)
export const apiDel  = (path)        => _request('DELETE', path)
