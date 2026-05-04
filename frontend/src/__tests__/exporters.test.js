import { describe, expect, it } from 'vitest'
import { buildExportFile, markdownTableToCsv } from '../lib/exporters'

describe('exporters', () => {
  it('creates native filenames from output modes', () => {
    const file = buildExportFile('test code', 'playwright', 'native')

    expect(file.filename).toMatch(/qa-output-\d+\.spec\.ts/)
    expect(file.content).toBe('test code')
  })

  it('converts markdown test tables to CSV', () => {
    const csv = markdownTableToCsv(`
| ID | Title |
| --- | --- |
| TC-1 | Checkout, success |
`)

    expect(csv).toBe('ID,Title\nTC-1,"Checkout, success"')
  })
})
