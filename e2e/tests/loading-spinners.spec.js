// @ts-check
const { test, expect } = require('@playwright/test')

// Loading feedback on the other compute-heavy pages (mirrors graph-spinner).

test('重算輪動 shows a loading spinner while computing', async ({ page }) => {
  await page.route('**/api/v1/rotation/timeline*', async (route) => {
    await new Promise((r) => setTimeout(r, 2000))
    await route.continue()
  })

  await page.goto('/rotation')

  const recalc = page.getByRole('button', { name: '重算輪動', exact: true })
  await expect(recalc).toBeVisible({ timeout: 90_000 })
  await expect(recalc).toBeEnabled({ timeout: 90_000 }) // wait for initial load to settle

  await recalc.click()
  await expect(page.locator('.canvas-loading')).toBeVisible()
  await expect(page.getByText(/重算輪動中/)).toBeVisible()
  await expect(page.locator('.canvas-loading')).toBeHidden({ timeout: 90_000 })
})

test('執行回測 shows a loading state while running', async ({ page }) => {
  await page.route('**/api/v1/backtest/run', async (route) => {
    await new Promise((r) => setTimeout(r, 2000))
    await route.continue()
  })

  await page.goto('/stocks/2330/backtest')

  const runBtn = page.getByRole('button', { name: /執行回測/ })
  await expect(runBtn).toBeVisible({ timeout: 60_000 })

  await runBtn.click()
  await expect(page.getByText('回測運算中…')).toBeVisible()
  await expect(page.getByRole('button', { name: /回測中/ })).toBeVisible()
})
