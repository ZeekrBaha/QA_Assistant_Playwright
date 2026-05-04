export function formatScanSummary(scan) {
  if (!scan) return ''
  const frameworks = scan.frameworks?.length ? scan.frameworks.join(', ') : 'unknown'
  const tests = scan.test_frameworks?.length ? scan.test_frameworks.join(', ') : 'unknown'
  return `Frameworks: ${frameworks}. Test tools: ${tests}. Suggested command: ${scan.suggested_test_command}.`
}

export function canWriteProposal(proposal, approved) {
  return Boolean(approved && proposal?.repo_path && proposal?.relative_path && proposal?.content)
}

export function truncateOutput(value = '', max = 8000) {
  if (value.length <= max) return value
  return `${value.slice(0, max)}\n... output truncated ...`
}
