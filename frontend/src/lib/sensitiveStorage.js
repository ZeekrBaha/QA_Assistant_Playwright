const API_KEYS_KEY = 'qa_api_keys'
const BACKEND_TOKEN_KEY = 'qa_backend_token'
const ATLASSIAN_KEY = 'qa_atlassian'
const EMPTY_ATLASSIAN = { domain: '', email: '', token: '' }

function loadJson(key, fallback, storage = window.sessionStorage) {
  try {
    return JSON.parse(storage.getItem(key) || JSON.stringify(fallback))
  } catch {
    return fallback
  }
}

function saveJson(key, value, storage = window.sessionStorage) {
  storage.setItem(key, JSON.stringify(value))
  window.localStorage.removeItem(key)
}

export function loadApiKeys(storage = window.sessionStorage) {
  return loadJson(API_KEYS_KEY, {}, storage)
}

export function saveApiKeys(apiKeys, storage = window.sessionStorage) {
  saveJson(API_KEYS_KEY, apiKeys, storage)
}

export function loadBackendToken(storage = window.sessionStorage) {
  return storage.getItem(BACKEND_TOKEN_KEY) || ''
}

export function saveBackendToken(token, storage = window.sessionStorage) {
  storage.setItem(BACKEND_TOKEN_KEY, token)
  window.localStorage.removeItem(BACKEND_TOKEN_KEY)
}

export function loadAtlassianConfig(storage = window.sessionStorage) {
  return loadJson(ATLASSIAN_KEY, EMPTY_ATLASSIAN, storage)
}

export function saveAtlassianConfig(config, storage = window.sessionStorage) {
  saveJson(ATLASSIAN_KEY, config, storage)
}
