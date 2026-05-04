import { describe, expect, it } from 'vitest'
import { buildAutomationSkeletonPrompt, buildStructuredPrompt, buildTicketScenarioPrompt, getOutputMode } from '../lib/workflow'

describe('workflow helpers', () => {
  it('builds structured prompts for specific output modes', () => {
    const prompt = buildStructuredPrompt('checkout should succeed', 'gherkin')

    expect(prompt).toContain('Structured QA output mode: Gherkin scenarios')
    expect(prompt).toContain('Return valid Gherkin only')
    expect(prompt).toContain('checkout should succeed')
  })

  it('builds ticket scenario and automation prompts for approval workflow', () => {
    const scenarioPrompt = buildTicketScenarioPrompt('Summary: Checkout', 'test_cases_table')
    const automationPrompt = buildAutomationSkeletonPrompt('Summary: Checkout', '| ID | Title |', 'playwright')

    expect(scenarioPrompt).toContain('scenario draft')
    expect(scenarioPrompt).toContain('Do not generate automation code yet')
    expect(automationPrompt).toContain('automation skeleton')
    expect(automationPrompt).toContain('Approved scenarios')
  })

  it('returns native extensions for export modes', () => {
    expect(getOutputMode('playwright').extension).toBe('spec.ts')
    expect(getOutputMode('gherkin').extension).toBe('feature')
  })
})
