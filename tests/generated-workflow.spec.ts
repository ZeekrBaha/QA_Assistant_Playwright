// Generated proposal for qa-assistant-reliable
// Instruction: Generate a Playwright smoke test for the QA assistant workflow: open the app, verify the repo integration panel is visible, verify the chat input exists, and verify output mode selection is available.


import { test, expect } from '@playwright/test'

const appUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173'

test('QA assistant repo integration smoke test', async ({ page }) => {
  await page.goto(appUrl)

  await expect(page.getByRole('heading', { name: 'Repo Integration' })).toBeVisible()
  await expect(page.getByText('Scan a local repo, preview a generated test file')).toBeVisible()
  await expect(page.getByLabel('Message')).toBeVisible()
  await expect(page.getByLabel('Output mode')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Scan repo' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Propose test file' })).toBeVisible()
})
