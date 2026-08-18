/**
 * API client for the CollisionGuard AI backend.
 *
 * Base URL is read from the VITE_API_BASE_URL environment variable so that
 * the dev server, staging, and any future deployment targets can each use a
 * different URL without a code change.
 *
 * Usage:
 *   import { apiGet } from './api/client'
 *   const health = await apiGet('/health')
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * Perform a GET request against the backend API.
 *
 * @param {string} path  - Endpoint path, e.g. '/health' or '/scenarios'
 * @returns {Promise<unknown>}  Parsed JSON response body
 * @throws {Error}  On non-2xx HTTP status or network failure
 */
export async function apiGet(path) {
  const url = `${BASE_URL}${path}`
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`API error ${response.status} on GET ${path}`)
  }

  return response.json()
}
