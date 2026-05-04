import { getOutputMode } from './workflow'

export function buildExportFile(content, modeId, format = 'native') {
  const mode = getOutputMode(modeId)
  if (format === 'csv') {
    return {
      filename: `qa-test-plan-${Date.now()}.csv`,
      mimeType: 'text/csv',
      content: markdownTableToCsv(content),
    }
  }

  const extension = format === 'markdown' ? 'md' : mode.extension
  return {
    filename: `qa-output-${Date.now()}.${extension}`,
    mimeType: extension === 'csv' ? 'text/csv' : 'text/plain',
    content,
  }
}

export function downloadTextFile({ filename, mimeType, content }) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function markdownTableToCsv(markdown) {
  const tableLines = markdown
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('|') && line.endsWith('|'))
    .filter((line) => !/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line))

  if (tableLines.length === 0) return markdown

  return tableLines
    .map((line) => line
      .slice(1, -1)
      .split('|')
      .map((cell) => csvEscape(cell.trim()))
      .join(','))
    .join('\n')
}

function csvEscape(value) {
  if (!/[",\n]/.test(value)) return value
  return `"${value.replaceAll('"', '""')}"`
}
