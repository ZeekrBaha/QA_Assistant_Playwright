import { useState } from 'react'
import { OUTPUT_MODES } from '../lib/workflow'

const ACTIONS = [
  { id: 'text', label: 'Text / Code' },
  { id: 'locator_gen', label: 'DOM Locator Gen' },
  { id: 'web_search', label: 'Web Search' },
  { id: 'image', label: 'Generate Image' },
  { id: 'jira', label: 'Query Jira' },
  { id: 'rovo', label: 'Rovo / JQL Search' },
]

function ChatInput({ onSend, isLoading, action, setAction, outputMode, setOutputMode }) {
  const [text, setText] = useState('')

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!text.trim() || isLoading) return
    onSend({ text, action, outputMode })
    setText('')
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-note">
        <strong>Next step</strong>
        <span>Choose what you want generated, describe the workflow, then send it to the selected LLM.</span>
      </div>
      <select
        aria-label="Chat action"
        value={action}
        disabled={isLoading}
        onChange={(event) => setAction(event.target.value)}
      >
        {ACTIONS.map((item) => (
          <option key={item.id} value={item.id}>{item.label}</option>
        ))}
      </select>
      <select
        aria-label="Output mode"
        value={outputMode}
        disabled={isLoading}
        onChange={(event) => setOutputMode(event.target.value)}
      >
        {OUTPUT_MODES.map((item) => (
          <option key={item.id} value={item.id}>{item.label}</option>
        ))}
      </select>
      <textarea
        aria-label="Message"
        value={text}
        disabled={isLoading}
        onChange={(event) => setText(event.target.value)}
        placeholder={
          action === 'rovo'
            ? "Enter full JQL, e.g. project=PROJ AND status='To Do'"
            : action === 'jira'
              ? 'Enter Jira ID plus optional instructions'
              : action === 'locator_gen'
                ? 'Paste HTML or URL'
                : 'Ask for test cases, locators, or automation code'
        }
      />
      <button type="submit" disabled={isLoading || !text.trim()}>
        {isLoading ? 'Working...' : 'Send'}
      </button>
    </form>
  )
}

export default ChatInput
