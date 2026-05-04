import { describe, expect, it } from 'vitest'
import { canWriteProposal, formatScanSummary, truncateOutput } from '../lib/repoIntegration'

describe('repo integration helpers', () => {
  it('formats scan summaries', () => {
    expect(formatScanSummary({
      frameworks: ['react', 'vite'],
      test_frameworks: ['playwright'],
      suggested_test_command: 'npx playwright test',
    })).toBe('Frameworks: react, vite. Test tools: playwright. Suggested command: npx playwright test.')
  })

  it('requires explicit approval and complete proposal before writing', () => {
    const proposal = { repo_path: '/repo', relative_path: 'tests/a.spec.ts', content: 'test' }

    expect(canWriteProposal(proposal, false)).toBe(false)
    expect(canWriteProposal(proposal, true)).toBe(true)
    expect(canWriteProposal({ ...proposal, content: '' }, true)).toBe(false)
  })

  it('truncates long command output', () => {
    expect(truncateOutput('abcdef', 3)).toBe('abc\n... output truncated ...')
  })
})
