import { beforeEach, describe, expect, it } from 'vitest'
import {
  loadApiKeys,
  loadAtlassianConfig,
  loadBackendToken,
  saveApiKeys,
  saveAtlassianConfig,
  saveBackendToken,
} from '../lib/sensitiveStorage'

describe('sensitive storage helpers', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('keeps provider keys, backend token, and Atlassian credentials out of localStorage', () => {
    saveApiKeys({ openai: 'sk-test' })
    saveBackendToken('backend-secret')
    saveAtlassianConfig({ domain: 'company.atlassian.net', email: 'qa@example.com', token: 'atlassian-secret' })

    expect(loadApiKeys()).toEqual({ openai: 'sk-test' })
    expect(loadBackendToken()).toBe('backend-secret')
    expect(loadAtlassianConfig()).toEqual({ domain: 'company.atlassian.net', email: 'qa@example.com', token: 'atlassian-secret' })
    expect(window.localStorage.getItem('qa_api_keys')).toBeNull()
    expect(window.localStorage.getItem('qa_backend_token')).toBeNull()
    expect(window.localStorage.getItem('qa_atlassian')).toBeNull()
  })
})
