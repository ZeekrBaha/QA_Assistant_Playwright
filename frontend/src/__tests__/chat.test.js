import { describe, expect, it } from 'vitest'
import { buildAtlassianRequest, buildConversationHistory, makeRegeneratePayload } from '../lib/chat'

describe('chat helpers', () => {
  it('sends the full Rovo JQL query instead of only the first token', () => {
    const request = buildAtlassianRequest(
      'rovo',
      "project=PROJ AND status='To Do'",
      { domain: 'company.atlassian.net', email: 'qa@example.com', token: 'secret' },
    )

    expect(request.endpoint).toBe('/api/atlassian/rovo')
    expect(request.body.jql).toBe("project=PROJ AND status='To Do'")
  })

  it('keeps Jira issue key parsing separate from extra instructions', () => {
    const request = buildAtlassianRequest(
      'jira',
      'PROJ-123 generate regression cases',
      { domain: 'company.atlassian.net', email: 'qa@example.com', token: 'secret' },
    )

    expect(request.body.issue_key).toBe('PROJ-123')
    expect(request.extraPrompt).toBe('generate regression cases')
  })

  it('excludes stale assistant output from regenerate history', () => {
    const messages = [
      { role: 'user', content: 'first' },
      { role: 'assistant', content: 'old first answer' },
      { role: 'user', content: 'second' },
      { role: 'assistant', content: 'stale answer to regenerate' },
    ]

    const payload = makeRegeneratePayload(messages, 3)

    expect(payload.text).toBe('second')
    expect(payload.history).toEqual([
      { role: 'user', content: 'first' },
      { role: 'assistant', content: 'old first answer' },
    ])
    expect(buildConversationHistory(messages, { excludeIndex: 3 })).not.toContainEqual({
      role: 'assistant',
      content: 'stale answer to regenerate',
    })
  })
})
