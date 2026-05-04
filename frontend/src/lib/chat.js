export function buildAtlassianRequest(action, text, atlassianConfig) {
  const base = {
    domain: atlassianConfig.domain,
    email: atlassianConfig.email,
    api_token: atlassianConfig.token,
  }

  if (action === 'jira') {
    const issueKey = text.trim().split(/\s+/)[0] || ''
    const extraPrompt = text.slice(issueKey.length).trim() || 'Summarize this.'
    return {
      endpoint: '/api/atlassian/jira',
      body: { ...base, issue_key: issueKey },
      extraPrompt,
    }
  }

  if (action === 'rovo') {
    return {
      endpoint: '/api/atlassian/rovo',
      body: { ...base, jql: text.trim() },
      extraPrompt: 'Summarize these Jira search results and propose QA coverage.',
    }
  }

  throw new Error(`Unsupported Atlassian action: ${action}`)
}

export function buildConversationHistory(messages, options = {}) {
  const excludedIndex = options.excludeIndex
  return messages
    .filter((_, index) => index !== excludedIndex)
    .slice(-10)
    .map((message) => ({ role: message.role, content: message.content }))
}

export function makeRegeneratePayload(messages, assistantIndex) {
  const userMessage = messages[assistantIndex - 1]
  if (!userMessage || userMessage.role !== 'user') return null

  return {
    text: userMessage.content.replace('[Image Uploaded]\n', ''),
    history: buildConversationHistory(messages.slice(0, assistantIndex - 1)),
  }
}
