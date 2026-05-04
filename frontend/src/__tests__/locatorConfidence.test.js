import { describe, expect, it } from 'vitest'
import { analyzeLocatorConfidence } from '../lib/locatorConfidence'

describe('locator confidence', () => {
  it('prefers role, label, test-id, id, then text/css style selectors', () => {
    const result = analyzeLocatorConfidence(`
      <button role="button">Save</button>
      <input aria-label="Email" />
      <button data-testid="submit">Submit</button>
      <a id="settings">Settings</a>
      <button>Plain text</button>
    `)

    expect(result.map((item) => item.strategy)).toEqual(['role', 'label', 'test-id', 'id', 'text'])
    expect(result[0].confidence).toBe('high')
    expect(result[4].stability).toBe('brittle')
  })
})
