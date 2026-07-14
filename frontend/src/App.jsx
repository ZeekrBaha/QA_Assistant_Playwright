import { useCallback, useEffect, useState } from 'react'
import ChatInput from './components/ChatInput'
import ChatWindow from './components/ChatWindow'
import RepoIntegration from './components/RepoIntegration'
import Sidebar from './components/Sidebar'
import { API_BASE } from './lib/config'
import { apiJson, buildHeaders, readStreamResponse } from './lib/api'
import { getDefaultModel, getSelectedModel, loadModelPreferences, loadTemperature } from './lib/config'
import { buildAtlassianRequest, buildConversationHistory, makeRegeneratePayload } from './lib/chat'
import { analyzeLocatorConfidence } from './lib/locatorConfidence'
import { loadApiKeys, loadAtlassianConfig, loadBackendToken, saveApiKeys, saveAtlassianConfig, saveBackendToken } from './lib/sensitiveStorage'
import { buildAutomationSkeletonPrompt, buildStructuredPrompt, buildTicketScenarioPrompt } from './lib/workflow'

function loadJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback))
  } catch {
    return fallback
  }
}

function App() {
  const [messages, setMessages] = useState(() => loadJson('qa_messages', []))
  const [provider, setProvider] = useState(() => localStorage.getItem('qa_provider') || 'openai')
  const [apiKeys, setApiKeys] = useState(() => loadApiKeys())
  const [temperature, setTemperature] = useState(() => loadTemperature())
  const [modelPreferences, setModelPreferences] = useState(() => loadModelPreferences())
  const [selectedModel, setSelectedModel] = useState(() => getSelectedModel(localStorage.getItem('qa_provider') || 'openai', loadModelPreferences()))
  const [streamingEnabled, setStreamingEnabled] = useState(() => localStorage.getItem('qa_streaming') === 'true')
  const [action, setAction] = useState('text')
  const [outputMode, setOutputMode] = useState(() => localStorage.getItem('qa_output_mode') || 'test_cases_table')
  const [isLoading, setIsLoading] = useState(false)
  const [atlassianConfig, setAtlassianConfig] = useState(() => loadAtlassianConfig())
  const [backendStatus, setBackendStatus] = useState('checking')
  const [backendToken, setBackendToken] = useState(() => loadBackendToken())
  const [ticketWorkflow, setTicketWorkflow] = useState(null)
  const [assistantStage, setAssistantStage] = useState('Ready for a prompt')

  useEffect(() => localStorage.setItem('qa_messages', JSON.stringify(messages)), [messages])
  useEffect(() => localStorage.setItem('qa_provider', provider), [provider])
  useEffect(() => saveApiKeys(apiKeys), [apiKeys])
  useEffect(() => localStorage.setItem('qa_temperature', String(temperature)), [temperature])
  useEffect(() => localStorage.setItem('qa_model_preferences', JSON.stringify(modelPreferences)), [modelPreferences])
  useEffect(() => localStorage.setItem('qa_streaming', String(streamingEnabled)), [streamingEnabled])
  useEffect(() => localStorage.setItem('qa_output_mode', outputMode), [outputMode])
  useEffect(() => saveAtlassianConfig(atlassianConfig), [atlassianConfig])
  useEffect(() => saveBackendToken(backendToken), [backendToken])

  useEffect(() => {
    let cancelled = false
    apiJson('/api/health')
      .then(() => !cancelled && setBackendStatus('online'))
      .catch(() => !cancelled && setBackendStatus('offline'))
    return () => {
      cancelled = true
    }
  }, [])

  const sendToAssistant = useCallback(async ({ text, sendAction, requestedOutputMode, historyOverride }) => {
    let finalMessage = text
    const isLocatorMode = sendAction === 'locator_gen'
    const activeOutputMode = requestedOutputMode || outputMode

    if (sendAction === 'jira' || sendAction === 'rovo') {
      setAssistantStage('Fetching Atlassian context')
      if (!atlassianConfig.domain || !atlassianConfig.email || !atlassianConfig.token) {
        throw new Error('Configure Atlassian domain, email, and token first.')
      }
      const request = buildAtlassianRequest(sendAction, text, atlassianConfig)
      const atlassianData = await apiJson(request.endpoint, {
        method: 'POST',
        body: JSON.stringify(request.body),
      })
      if (atlassianData.error) throw new Error(atlassianData.content)
      if (sendAction === 'jira') {
        setTicketWorkflow({
          status: 'scenarios_pending_approval',
          ticketContext: atlassianData.content,
          scenarioMode: activeOutputMode,
          automationMode: 'playwright',
          scenarios: '',
        })
        finalMessage = buildTicketScenarioPrompt(atlassianData.content, activeOutputMode)
      } else {
        finalMessage = buildStructuredPrompt(`Context from Atlassian:\n\n${atlassianData.content}\n\nUser instructions: ${request.extraPrompt}`, activeOutputMode)
      }
    }

    if (sendAction === 'web_search') {
      setAssistantStage('Collecting web search context')
      const searchData = await apiJson('/api/web_search', {
        method: 'POST',
        body: JSON.stringify({ query: text }),
      })
      if (searchData.error) throw new Error(searchData.content)
      finalMessage = buildStructuredPrompt(`Use these search results as context:\n\n${searchData.content}\n\nUser question: ${text}`, activeOutputMode)
    }

    if (sendAction === 'image') {
      setAssistantStage(`Calling ${provider} image generation`)
      const imageData = await apiJson('/api/generate_image', {
        method: 'POST',
        body: JSON.stringify({
          prompt: text,
          provider,
          api_key: apiKeys[provider] || '',
          model_name: selectedModel,
        }),
      })
      return imageData.response
    }

    const requestBody = {
      provider,
      message: finalMessage,
      api_key: apiKeys[provider] || '',
      temperature,
      model_name: selectedModel || getDefaultModel(provider),
      is_locator_mode: isLocatorMode,
      conversation_history: historyOverride || buildConversationHistory(messages),
    }

    if (!streamingEnabled) {
      setAssistantStage(`Calling ${provider} / ${selectedModel || getDefaultModel(provider)}`)
      const data = await apiJson('/api/generate', {
        method: 'POST',
        body: JSON.stringify(requestBody),
      })
      setAssistantStage('Response received')
      return appendDomMeta(data.response, data, isLocatorMode)
    }

    setAssistantStage(`Streaming from ${provider} / ${selectedModel || getDefaultModel(provider)}`)
    const response = await fetch(`${API_BASE}/api/stream`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(requestBody),
    })

    let content = ''
    let meta = {}
    await readStreamResponse(response, (event) => {
      if (event.type === 'meta') meta = event
      if (event.type === 'token') content += event.content
      if (event.type === 'error') content += `\n\n${event.content}`
    })
    setAssistantStage('Stream completed')
    return appendDomMeta(content, meta, isLocatorMode)
  }, [apiKeys, atlassianConfig, messages, outputMode, provider, selectedModel, streamingEnabled, temperature])

  const handleSend = useCallback(async ({ text, action: sendAction = action, outputMode: requestedOutputMode = outputMode, historyOverride = null }) => {
    if (!text.trim() || isLoading) return
    const userMessage = { role: 'user', content: text, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    setAssistantStage('Preparing prompt')
    try {
      const promptText = ['text', 'locator_gen'].includes(sendAction)
        ? buildStructuredPrompt(text, requestedOutputMode)
        : text
      const response = await sendToAssistant({ text: promptText, sendAction, requestedOutputMode, historyOverride })
      setMessages((prev) => [...prev, { role: 'assistant', content: response, timestamp: new Date().toISOString(), outputMode: requestedOutputMode }])
      if (sendAction === 'jira') {
        setTicketWorkflow((prev) => prev ? { ...prev, scenarios: response } : prev)
      }
    } catch (error) {
      setAssistantStage('Request failed')
      setMessages((prev) => [...prev, { role: 'assistant', content: `**Error:** ${error.message}`, timestamp: new Date().toISOString() }])
    } finally {
      setIsLoading(false)
    }
  }, [action, isLoading, outputMode, sendToAssistant])

  const handleRegenerate = useCallback((assistantIndex) => {
    const payload = makeRegeneratePayload(messages, assistantIndex)
    if (!payload) return
    setMessages((prev) => prev.filter((_, index) => index !== assistantIndex))
    handleSend({ text: payload.text, action, outputMode, historyOverride: payload.history })
  }, [action, handleSend, messages, outputMode])

  const handleApproveScenarios = useCallback(async () => {
    if (!ticketWorkflow?.scenarios || isLoading) return
    setIsLoading(true)
    setAssistantStage('Generating approved automation skeleton')
    try {
      const prompt = buildAutomationSkeletonPrompt(ticketWorkflow.ticketContext, ticketWorkflow.scenarios, ticketWorkflow.automationMode)
      const response = await sendToAssistant({
        text: prompt,
        sendAction: 'text',
        requestedOutputMode: ticketWorkflow.automationMode,
        historyOverride: buildConversationHistory(messages),
      })
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: response,
        timestamp: new Date().toISOString(),
        outputMode: ticketWorkflow.automationMode,
      }])
      setTicketWorkflow((prev) => prev ? { ...prev, status: 'automation_generated' } : prev)
    } catch (error) {
      setAssistantStage('Request failed')
      setMessages((prev) => [...prev, { role: 'assistant', content: `**Error:** ${error.message}`, timestamp: new Date().toISOString() }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, messages, sendToAssistant, ticketWorkflow])

  return (
    <div className="app">
      <Sidebar
        provider={provider}
        setProvider={setProvider}
        apiKeys={apiKeys}
        setApiKeys={setApiKeys}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        modelPreferences={modelPreferences}
        setModelPreferences={setModelPreferences}
        temperature={temperature}
        setTemperature={setTemperature}
        streamingEnabled={streamingEnabled}
        setStreamingEnabled={setStreamingEnabled}
        atlassianConfig={atlassianConfig}
        setAtlassianConfig={setAtlassianConfig}
        backendToken={backendToken}
        setBackendToken={setBackendToken}
        onClearChat={() => setMessages([])}
      />
      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">QA operations console</span>
            <h2>Generate, review, and run automation safely</h2>
          </div>
          <div className="topbar-actions">
            <span className={`status-pill ${backendStatus}`}>Backend {backendStatus}</span>
            <span className="status-pill">{provider} / {selectedModel}</span>
          </div>
        </header>
        <section className="overview-strip" aria-label="Workflow overview">
          <div className="overview-card">
            <span>1. Generate</span>
            <strong>Ask AI</strong>
            <p>Use OpenAI or another provider for test plans, locators, and code.</p>
          </div>
          <div className="overview-card">
            <span>2. Review</span>
            <strong>Approve output</strong>
            <p>Inspect scenarios, locators, or diffs before any file write.</p>
          </div>
          <div className="overview-card">
            <span>3. Run</span>
            <strong>Verify safely</strong>
            <p>Write approved files, then run an allowlisted command.</p>
          </div>
        </section>
        <section className="guidance-strip" aria-label="Current workflow guidance">
          <strong>{assistantStage}</strong>
          <span>Tip: leave the provider API key blank when the backend has the key in `.env`; otherwise paste a temporary key in the sidebar for that provider.</span>
        </section>
        <section className="workspace-grid">
          <RepoIntegration />
          <ChatWindow
            messages={messages}
            onRegenerate={handleRegenerate}
            ticketWorkflow={ticketWorkflow}
            setTicketWorkflow={setTicketWorkflow}
            onApproveScenarios={handleApproveScenarios}
            isLoading={isLoading}
            assistantStage={assistantStage}
          />
        </section>
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          action={action}
          setAction={setAction}
          outputMode={outputMode}
          setOutputMode={setOutputMode}
        />
      </main>
    </div>
  )
}

function appendDomMeta(content, data, isLocatorMode) {
  let finalContent = data.dom_warning ? `> DOM Fetch Warning: ${data.dom_warning}\n\n${content}` : content
  if (isLocatorMode && data.distilled_dom) {
    const confidence = analyzeLocatorConfidence(data.distilled_dom)
    const confidenceTable = confidence.length
      ? `\n\nLocator confidence:\n\n| Element | Strategy | Selector | Stability | Confidence |\n| --- | --- | --- | --- | --- |\n${confidence.map((item) => `| ${escapeTable(item.tag + (item.text ? `: ${item.text}` : ''))} | ${item.strategy} | \`${escapeTable(item.selector)}\` | ${item.stability} | ${item.confidence} |`).join('\n')}`
      : ''
    finalContent += `\n\n---\n\nDistilled DOM:\n\n\`\`\`html\n${data.distilled_dom.slice(0, 3000)}\n\`\`\``
    finalContent += confidenceTable
  }
  return finalContent
}

function escapeTable(value) {
  return String(value).replaceAll('|', '\\|').replaceAll('\n', ' ')
}

export default App
