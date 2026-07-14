import { API_BASE } from './config'
import { loadBackendToken } from './sensitiveStorage'

export async function apiJson(path, options = {}) {
  const { headers, ...requestOptions } = options
  const response = await fetch(`${API_BASE}${path}`, {
    ...requestOptions,
    headers: buildHeaders(headers),
  })

  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    const detail = contentType.includes('application/json') ? JSON.stringify(await response.json()) : await response.text()
    throw new Error(`Request failed (${response.status}) ${detail}`)
  }

  if (!contentType.includes('application/json')) {
    throw new Error(`Expected JSON response from ${path}`)
  }

  return response.json()
}

export function buildHeaders(headers = {}) {
  const token = loadBackendToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'X-Backend-Token': token } : {}),
    ...headers,
  }
}

export function parseSseEvents(text) {
  return text
    .split('\n')
    .filter((line) => line.startsWith('data: '))
    .map((line) => line.slice(6).trim())
    .filter(Boolean)
    .map((payload) => (payload === '[DONE]' ? { type: 'done' } : JSON.parse(payload)))
}

export async function readStreamResponse(response, onEvent) {
  if (!response.ok) {
    throw new Error(`Stream request failed (${response.status}) ${await response.text()}`)
  }
  if (!response.body) {
    throw new Error('Streaming response did not include a body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()

    for (const line of lines) {
      dispatchSseLine(line, onEvent)
    }
  }

  buffer += decoder.decode()
  dispatchSseLine(buffer, onEvent)
}

function dispatchSseLine(line, onEvent) {
  if (!line.startsWith('data: ')) return
  const payload = line.slice(6).trim()
  if (!payload) return
  onEvent(payload === '[DONE]' ? { type: 'done' } : JSON.parse(payload))
}
