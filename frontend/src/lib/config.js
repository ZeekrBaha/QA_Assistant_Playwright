export const API_BASE = ''

export const PROVIDER_MODELS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'o4-mini', 'o3', 'o3-mini'],
  claude: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5', 'claude-sonnet-4-5', 'claude-3-7-sonnet', 'claude-3-5-sonnet'],
  gemini: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite', 'gemini-3.1-pro-preview', 'gemini-3-flash-preview'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  mistral: ['mistral-large-latest', 'mistral-small-latest'],
  kimi: ['kimi-k2.6', 'kimi-k2.5'],
  groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'llama-4-scout-17b', 'qwen3-32b', 'gemma2-9b-it'],
  ollama: ['llama3.2'],
}

export const PROVIDERS = Object.keys(PROVIDER_MODELS)

export function getDefaultModel(provider) {
  return PROVIDER_MODELS[provider]?.[0] || ''
}

export function loadTemperature(storage = window.localStorage) {
  const saved = storage.getItem('qa_temperature')
  if (saved === null || saved === '') return 0.6
  const parsed = Number.parseFloat(saved)
  return Number.isNaN(parsed) || parsed < 0 || parsed > 1 ? 0.6 : parsed
}

export function loadModelPreferences(storage = window.localStorage) {
  try {
    return JSON.parse(storage.getItem('qa_model_preferences') || '{}')
  } catch {
    return {}
  }
}

export function getSelectedModel(provider, modelPreferences) {
  return modelPreferences[provider] || getDefaultModel(provider)
}
