import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ChatInput from '../components/ChatInput'

describe('ChatInput', () => {
  it('lets users select the Rovo action and submit full JQL text', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    let action = 'text'
    let outputMode = 'test_cases_table'
    const setAction = vi.fn((next) => {
      action = next
    })
    const setOutputMode = vi.fn((next) => {
      outputMode = next
    })

    const { rerender } = render(
      <ChatInput onSend={onSend} isLoading={false} action={action} setAction={setAction} outputMode={outputMode} setOutputMode={setOutputMode} />,
    )

    await user.selectOptions(screen.getByLabelText('Chat action'), 'rovo')
    expect(setAction).toHaveBeenCalledWith('rovo')

    rerender(<ChatInput onSend={onSend} isLoading={false} action={action} setAction={setAction} outputMode={outputMode} setOutputMode={setOutputMode} />)

    await user.selectOptions(screen.getByLabelText('Output mode'), 'gherkin')
    expect(setOutputMode).toHaveBeenCalledWith('gherkin')
    outputMode = 'gherkin'
    rerender(<ChatInput onSend={onSend} isLoading={false} action={action} setAction={setAction} outputMode={outputMode} setOutputMode={setOutputMode} />)
    await user.type(screen.getByLabelText('Message'), "project=PROJ AND status='To Do'")
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(onSend).toHaveBeenCalledWith({
      text: "project=PROJ AND status='To Do'",
      action: 'rovo',
      outputMode: 'gherkin',
    })
  })
})
