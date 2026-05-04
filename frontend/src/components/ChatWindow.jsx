import ReactMarkdown from 'react-markdown'
import { buildExportFile, downloadTextFile } from '../lib/exporters'

function ChatWindow({ messages, onRegenerate, ticketWorkflow, setTicketWorkflow, onApproveScenarios, isLoading, assistantStage }) {
  if (messages.length === 0) {
    return (
      <section className="chat-window" id="assistant-panel">
        <div className="empty">
          <span className="eyebrow">Assistant context</span>
          <h2>Start with a testing objective</h2>
          <p>Pick an action and output mode below, then ask for a test plan, Gherkin scenarios, locators, or automation code. The backend will route the prompt to the selected LLM provider.</p>
          <div className="instruction-card">
            <strong>Recommended first prompt</strong>
            <span>Generate a Playwright smoke test plan for the repo integration workflow: scan repo, propose file, approve write, and run tests.</span>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="chat-window" id="assistant-panel">
      <div className="chat-header">
        <div>
          <span className="eyebrow">Assistant activity</span>
          <strong>{assistantStage || 'Ready'}</strong>
        </div>
        <span>{messages.length} messages</span>
      </div>
      {ticketWorkflow?.status === 'scenarios_pending_approval' && (
        <div className="workflow-panel">
          <div>
            <strong>Ticket workflow</strong>
            <p>Review the generated scenarios, then approve them to generate an automation skeleton.</p>
          </div>
          <label>
            Automation target
            <select
              aria-label="Automation target"
              value={ticketWorkflow.automationMode}
              disabled={isLoading}
              onChange={(event) => setTicketWorkflow((prev) => ({ ...prev, automationMode: event.target.value }))}
            >
              <option value="playwright">Playwright test</option>
              <option value="selenium">Selenium test</option>
              <option value="cypress">Cypress test</option>
              <option value="page_object">Page Object Model</option>
            </select>
          </label>
          <button type="button" onClick={onApproveScenarios} disabled={isLoading || !ticketWorkflow.scenarios}>
            Approve scenarios and generate skeleton
          </button>
        </div>
      )}
      {messages.map((message, index) => (
        <article className={`message ${message.role}`} key={message.id || index}>
          <div className="message-role">{message.role === 'user' ? 'You' : 'Assistant'}</div>
          <ReactMarkdown>{message.content}</ReactMarkdown>
          {message.role === 'assistant' && index === messages.length - 1 && (
            <div className="message-actions">
              <button type="button" className="secondary" onClick={() => onRegenerate(index)}>
                Regenerate
              </button>
              <button type="button" className="secondary" onClick={() => downloadTextFile(buildExportFile(message.content, message.outputMode || 'test_cases_table', 'native'))}>
                Export native
              </button>
              <button type="button" className="secondary" onClick={() => downloadTextFile(buildExportFile(message.content, message.outputMode || 'test_cases_table', 'markdown'))}>
                Export Markdown
              </button>
              <button type="button" className="secondary" onClick={() => downloadTextFile(buildExportFile(message.content, message.outputMode || 'test_cases_table', 'csv'))}>
                Export CSV
              </button>
            </div>
          )}
        </article>
      ))}
    </section>
  )
}

export default ChatWindow
