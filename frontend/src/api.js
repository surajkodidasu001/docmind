const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
import { parseSSEBuffer } from './lib/sseParser'

async function jsonOrThrow(resp) {
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(text || `${resp.status} ${resp.statusText}`)
  }
  return resp.json()
}

export async function health() {
  return jsonOrThrow(await fetch(`${API_BASE}/health`))
}

export async function supportedFormats() {
  return jsonOrThrow(await fetch(`${API_BASE}/supported-formats`))
}

export async function listTables() {
  return jsonOrThrow(await fetch(`${API_BASE}/tables`))
}

export async function cacheStats() {
  return jsonOrThrow(await fetch(`${API_BASE}/cache/stats`))
}

export async function clearCache() {
  return jsonOrThrow(await fetch(`${API_BASE}/cache/clear`, { method: 'POST' }))
}

export async function resetIndex() {
  return jsonOrThrow(await fetch(`${API_BASE}/reset`, { method: 'POST' }))
}

export async function ingestFile(file, visionFallback = false) {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(
    `${API_BASE}/ingest?vision_fallback=${visionFallback}`,
    { method: 'POST', body: form },
  )
  return jsonOrThrow(resp)
}

export async function deleteDocument(filename) {
  const resp = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  })
  return jsonOrThrow(resp)
}

export async function clearSession(sessionId) {
  return jsonOrThrow(await fetch(`${API_BASE}/session/${sessionId}/clear`, { method: 'POST' }))
}

export async function query(text, sessionId) {
  const resp = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: text, session_id: sessionId }),
  })
  return jsonOrThrow(resp)
}

/**
 * Streams an answer via SSE. Calls onDelta(text) for each token chunk and
 * onFinal(finalEventPayload) once the server sends the closing event.
 * Uses a raw fetch + ReadableStream reader rather than EventSource, because
 * EventSource only supports GET requests and this endpoint is a POST.
 */
export async function queryStream(text, sessionId, { onDelta, onFinal, onError, signal }) {
  try {
    const resp = await fetch(`${API_BASE}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text, session_id: sessionId }),
      signal,
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`Stream request failed: ${resp.status} ${resp.statusText}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const { events, remainder } = parseSSEBuffer(buffer)
      buffer = remainder

      for (const event of events) {
        if (event.type === 'delta') {
          onDelta(event.text)
        } else if (event.type === 'final') {
          onFinal(event)
        }
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') onError?.(err)
  }
}
