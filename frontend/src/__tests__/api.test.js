import { describe, expect, it } from 'vitest'
import { buildHeaders, parseSseEvents } from '../lib/api'

describe('api helpers', () => {
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

  it('adds backend token header when configured', () => {
    window.localStorage.setItem('qa_backend_token', 'secret-token')

    expect(buildHeaders()).toMatchObject({
      'Content-Type': 'application/json',
      'X-Backend-Token': 'secret-token',
    })
  })
})
