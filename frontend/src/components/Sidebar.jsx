import { PROVIDERS, PROVIDER_MODELS, getSelectedModel } from '../lib/config'

function Sidebar({
  provider,
  setProvider,
  apiKeys,
  setApiKeys,
  selectedModel,
  setSelectedModel,
  modelPreferences,
  setModelPreferences,
  temperature,
  setTemperature,
  streamingEnabled,
  setStreamingEnabled,
  atlassianConfig,
  setAtlassianConfig,
  backendToken,
  setBackendToken,
  onClearChat,
}) {
  const models = PROVIDER_MODELS[provider] || []

  const handleProviderChange = (event) => {
    const nextProvider = event.target.value
    setProvider(nextProvider)
    setSelectedModel(getSelectedModel(nextProvider, modelPreferences))
  }

  const handleModelChange = (event) => {
    const nextModel = event.target.value
    setSelectedModel(nextModel)
    setModelPreferences((prev) => ({ ...prev, [provider]: nextModel }))
  }

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-mark">QA</div>
        <div>
          <h1>QA Assistant Reliable</h1>
          <p>Test generation workbench</p>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Primary workflow">
        <a href="#repo-workbench">Repo workbench</a>
        <a href="#assistant-panel">Assistant</a>
        <a href="#configuration">Configuration</a>
      </nav>

      <div className="sidebar-section" id="configuration">
        <h2>Configuration</h2>

      <label className="field">
        <span>Provider</span>
        <select aria-label="Provider" value={provider} onChange={handleProviderChange}>
          {PROVIDERS.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Model</span>
        <select aria-label="Model" value={selectedModel} onChange={handleModelChange}>
          {models.map((model) => (
            <option key={model} value={model}>{model}</option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>API Key</span>
        <input
          aria-label="API Key"
          type="password"
          value={apiKeys[provider] || ''}
          onChange={(event) => setApiKeys((prev) => ({ ...prev, [provider]: event.target.value }))}
          placeholder={`${provider} key`}
        />
      </label>

      <label className="field">
        <span>Temperature: {temperature.toFixed(1)}</span>
        <input
          aria-label="Temperature"
          type="range"
          min="0"
          max="1"
          step="0.1"
          value={temperature}
          onChange={(event) => setTemperature(Number.parseFloat(event.target.value))}
        />
      </label>

      <label className="field">
        <span>Streaming</span>
        <select
          aria-label="Streaming"
          value={streamingEnabled ? 'on' : 'off'}
          onChange={(event) => setStreamingEnabled(event.target.value === 'on')}
        >
          <option value="off">Off</option>
          <option value="on">On</option>
        </select>
      </label>
      </div>

      <div className="sidebar-section">
        <h2>Integrations</h2>

      <label className="field">
        <span>Backend Access Token</span>
        <input
          aria-label="Backend Access Token"
          type="password"
          value={backendToken}
          onChange={(event) => setBackendToken(event.target.value)}
          placeholder="Required when backend auth is enabled"
        />
      </label>

      <label className="field">
        <span>Atlassian Domain</span>
        <input
          value={atlassianConfig.domain}
          onChange={(event) => setAtlassianConfig((prev) => ({ ...prev, domain: event.target.value }))}
          placeholder="company.atlassian.net"
        />
      </label>
      <label className="field">
        <span>Atlassian Email</span>
        <input
          value={atlassianConfig.email}
          onChange={(event) => setAtlassianConfig((prev) => ({ ...prev, email: event.target.value }))}
          placeholder="you@example.com"
        />
      </label>
      <label className="field">
        <span>Atlassian Token</span>
        <input
          type="password"
          value={atlassianConfig.token}
          onChange={(event) => setAtlassianConfig((prev) => ({ ...prev, token: event.target.value }))}
          placeholder="API token"
        />
      </label>
      </div>

      <button className="secondary" type="button" onClick={onClearChat}>Clear Chat</button>
    </aside>
  )
}

export default Sidebar
