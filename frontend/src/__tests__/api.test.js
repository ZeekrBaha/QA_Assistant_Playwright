import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiJson, buildHeaders, parseSseEvents } from '../lib/api'

describe('api helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses SSE token, meta, and done events', () => {
    const events = parseSseEvents([
      'data: {"type":"meta","source_url":"https://example.com"}',
      '',
      'data: {"type":"token","content":"hello"}',
      '',
      'data: [DONE]',
      '',
    ].join('\n'))

    expect(events).toEqual([
      { type: 'meta', source_url: 'https://example.com' },
      { type: 'token', content: 'hello' },
      { type: 'done' },
    ])
  })

  it('adds backend token header from session storage only', () => {
    window.localStorage.setItem('qa_backend_token', 'stale-local-token')
    window.sessionStorage.setItem('qa_backend_token', 'secret-token')

    expect(buildHeaders()).toMatchObject({
      'Content-Type': 'application/json',
      'X-Backend-Token': 'secret-token',
    })
  })

  it('keeps authentication headers when a request adds custom headers', async () => {
    window.sessionStorage.setItem('qa_backend_token', 'secret-token')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'ok' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await apiJson('/api/health', { headers: { 'X-Request-Id': 'request-123' } })

    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.objectContaining({
      headers: {
        'Content-Type': 'application/json',
        'X-Backend-Token': 'secret-token',
        'X-Request-Id': 'request-123',
      },
    }))
  })
})
