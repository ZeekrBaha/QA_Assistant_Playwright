export const OUTPUT_MODES = [
  { id: 'test_cases_table', label: 'Test cases table', extension: 'md' },
  { id: 'gherkin', label: 'Gherkin scenarios', extension: 'feature' },
  { id: 'playwright', label: 'Playwright test', extension: 'spec.ts' },
  { id: 'selenium', label: 'Selenium test', extension: 'java' },
  { id: 'cypress', label: 'Cypress test', extension: 'cy.js' },
  { id: 'page_object', label: 'Page Object Model', extension: 'ts' },
  { id: 'api_test_plan', label: 'API test plan', extension: 'md' },
]

const MODE_INSTRUCTIONS = {
  test_cases_table: [
    'Return a markdown table with columns: ID, Title, Preconditions, Steps, Expected Result, Priority, Type.',
    'Include positive, negative, boundary, and regression coverage where relevant.',
  ],
  gherkin: [
    'Return valid Gherkin only, grouped by Feature and Scenario/Scenario Outline.',
    'Use Given/When/Then steps and include acceptance criteria traceability tags when possible.',
  ],
  playwright: [
    'Return a Playwright TypeScript spec.',
    'Use role/label/test-id locators where possible, avoid arbitrary waits, and include assertions.',
  ],
  selenium: [
    'Return a Selenium Java test with explicit waits.',
    'Use stable By locators and avoid Thread.sleep.',
  ],
  cypress: [
    'Return a Cypress JavaScript spec.',
    'Use data-testid, contains, intercepts, and assertion chains where appropriate.',
  ],
  page_object: [
    'Return a Page Object Model class plus brief usage example.',
    'Separate locators from actions and assertions.',
  ],
  api_test_plan: [
    'Return an API test plan with endpoint coverage, request data, assertions, negative cases, contract checks, and performance/security notes.',
  ],
}

export function getOutputMode(modeId) {
  return OUTPUT_MODES.find((mode) => mode.id === modeId) || OUTPUT_MODES[0]
}

export function buildStructuredPrompt(userText, modeId) {
  const mode = getOutputMode(modeId)
  const instructions = MODE_INSTRUCTIONS[mode.id].map((item) => `- ${item}`).join('\n')
  return `Structured QA output mode: ${mode.label}

Instructions:
${instructions}

User request:
${userText}`
}

export function buildTicketScenarioPrompt(ticketContext, modeId = 'test_cases_table') {
  const mode = getOutputMode(modeId)
  return `Ticket to test plan workflow: scenario draft

Output mode: ${mode.label}

From the Jira ticket context below:
1. Extract acceptance criteria and explicit business rules.
2. Identify assumptions and missing information.
3. Generate test scenarios for user approval.
4. Do not generate automation code yet.

Jira ticket context:
${ticketContext}`
}

export function buildAutomationSkeletonPrompt(ticketContext, approvedScenarios, modeId = 'playwright') {
  const mode = getOutputMode(modeId)
  return `Ticket to test plan workflow: automation skeleton

Output mode: ${mode.label}

Use the approved scenarios below to generate an automation skeleton.
Keep TODOs for data, environment, and selectors that are unknown.

Jira ticket context:
${ticketContext}

Approved scenarios:
${approvedScenarios}`
}
