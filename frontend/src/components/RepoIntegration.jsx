import { useState } from 'react'
import { apiJson } from '../lib/api'
import { canWriteProposal, formatScanSummary, truncateOutput } from '../lib/repoIntegration'

function RepoIntegration() {
  const [repoPath, setRepoPath] = useState('')
  const [instruction, setInstruction] = useState('')
  const [outputMode, setOutputMode] = useState('playwright')
  const [scan, setScan] = useState(null)
  const [proposal, setProposal] = useState(null)
  const [approved, setApproved] = useState(false)
  const [allowOverwrite, setAllowOverwrite] = useState(false)
  const [testCommand, setTestCommand] = useState('')
  const [testResult, setTestResult] = useState(null)
  const [status, setStatus] = useState('')
  const [notice, setNotice] = useState(null)
  const [writtenFile, setWrittenFile] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleScan = async () => {
    setBusy(true)
    setStatus('')
    setNotice(null)
    try {
      const data = await apiJson('/api/repo/scan', {
        method: 'POST',
        body: JSON.stringify({ repo_path: repoPath }),
      })
      setScan(data)
      setTestCommand(data.suggested_test_command || '')
      setStatus('Repo scanned.')
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  const handlePropose = async () => {
    setBusy(true)
    setStatus('')
    setNotice(null)
    setWrittenFile(null)
    setApproved(false)
    try {
      const data = await apiJson('/api/repo/propose', {
        method: 'POST',
        body: JSON.stringify({ repo_path: repoPath, instruction, output_mode: outputMode }),
      })
      setProposal(data)
      setScan(data.scan)
      setTestCommand(data.scan?.suggested_test_command || testCommand)
      setStatus('Proposal ready for review.')
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  const handleWrite = async () => {
    setBusy(true)
    setStatus('')
    setNotice(null)
    try {
      const data = await apiJson('/api/repo/write', {
        method: 'POST',
        body: JSON.stringify({
          repo_path: proposal.repo_path,
          relative_path: proposal.relative_path,
          content: proposal.content,
          approved,
          allow_overwrite: allowOverwrite,
        }),
      })
      setStatus(`Wrote ${data.relative_path}`)
      setWrittenFile(data)
      setNotice({
        type: 'success',
        title: 'File written',
        message: `${data.relative_path} was written successfully.`,
      })
    } catch (error) {
      setStatus(error.message)
      setNotice({
        type: 'error',
        title: 'Write failed',
        message: error.message,
      })
    } finally {
      setBusy(false)
    }
  }

  const handleRunTests = async () => {
    setBusy(true)
    setStatus('')
    setNotice(null)
    try {
      const data = await apiJson('/api/repo/test', {
        method: 'POST',
        body: JSON.stringify({ repo_path: repoPath, command: testCommand }),
      })
      setTestResult(data)
      setStatus(`Test command exited with ${data.exit_code}.`)
      setNotice({
        type: data.exit_code === 0 ? 'success' : 'error',
        title: data.exit_code === 0 ? 'Tests passed' : 'Tests failed',
        message: `Command exited with ${data.exit_code}.`,
      })
    } catch (error) {
      setStatus(error.message)
      setNotice({
        type: 'error',
        title: 'Test run failed',
        message: error.message,
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="repo-panel" id="repo-workbench">
      <div className="repo-panel-header">
        <div>
          <span className="eyebrow">Controlled file changes</span>
          <h3>Repo Integration</h3>
          <p>Scan a local repo, preview a generated test file, approve the write, then run an allowlisted test command.</p>
          <div className="instruction-card compact">
            <strong>How to use this panel</strong>
            <span>Start with Scan repo. Then propose a test file, review the diff, check approval, write it, and run tests. Each step updates the status below.</span>
          </div>
        </div>
        <div className="repo-stepper" aria-label="Repo workflow steps">
          <span className={scan ? 'active' : ''}>Scan</span>
          <span className={proposal ? 'active' : ''}>Propose</span>
          <span className={writtenFile ? 'active' : ''}>Write</span>
          <span className={testResult ? 'active' : ''}>Run</span>
        </div>
      </div>

      {notice && (
        <div className={`repo-notice ${notice.type}`} role="status" aria-live="polite">
          <strong>{notice.title}</strong>
          <span>{notice.message}</span>
        </div>
      )}

      <div className="repo-grid">
        <label>
          Repo path
          <input value={repoPath} onChange={(event) => setRepoPath(event.target.value)} placeholder="/absolute/path/to/repo" />
        </label>
        <label>
          Output target
          <select value={outputMode} onChange={(event) => setOutputMode(event.target.value)}>
            <option value="playwright">Playwright</option>
            <option value="selenium">Selenium</option>
            <option value="cypress">Cypress</option>
            <option value="gherkin">Gherkin</option>
          </select>
        </label>
      </div>

      <label className="repo-block">
        Test objective / approved scenario
        <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Generate coverage for checkout happy path and failed payment validation." />
      </label>

      <div className="repo-actions">
        <button type="button" onClick={handleScan} disabled={busy || !repoPath.trim()}>Scan repo</button>
        <button type="button" onClick={handlePropose} disabled={busy || !repoPath.trim() || !instruction.trim()}>Propose test file</button>
      </div>

      <div className="repo-lanes">
        <div>

      {scan && (
        <div className="repo-card">
          <strong>Scan summary</strong>
          <p>{formatScanSummary(scan)}</p>
          <p>{scan.summary}</p>
        </div>
      )}

      {proposal && (
        <div className="repo-card">
          <div className="repo-card-title">
            <strong>Proposed file: {proposal.relative_path}</strong>
            {writtenFile?.relative_path === proposal.relative_path && <span className="written-badge">Written</span>}
          </div>
          {proposal.exists && <p className="warning">This file already exists. Enable overwrite only if you reviewed the diff.</p>}
          {writtenFile?.relative_path === proposal.relative_path && (
            <p className="success-text">Saved to {writtenFile.path}</p>
          )}
          <pre className="diff-preview">{proposal.diff || proposal.content}</pre>
          <label className="check-row">
            <input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} />
            I reviewed this proposal and approve writing it.
          </label>
          <label className="check-row">
            <input type="checkbox" checked={allowOverwrite} onChange={(event) => setAllowOverwrite(event.target.checked)} />
            Allow overwrite if the target exists.
          </label>
          <button type="button" onClick={handleWrite} disabled={busy || !canWriteProposal(proposal, approved)}>Write approved file</button>
        </div>
      )}
        </div>

      <div className="repo-card">
        <label>
          Test command
          <input value={testCommand} onChange={(event) => setTestCommand(event.target.value)} placeholder="npm test" />
        </label>
        <button type="button" onClick={handleRunTests} disabled={busy || !repoPath.trim() || !testCommand.trim()}>Run tests</button>
        {testResult && (
          <pre className="diff-preview">{truncateOutput(`$ ${testResult.command}\nexit ${testResult.exit_code}\n\nSTDOUT:\n${testResult.stdout}\n\nSTDERR:\n${testResult.stderr}`)}</pre>
        )}
      </div>
      </div>

      {status && <p className="repo-status">{status}</p>}
    </section>
  )
}

export default RepoIntegration
