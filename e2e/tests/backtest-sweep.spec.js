// @ts-check
const { test, expect } = require('@playwright/test')

// Y8：回測參數掃描/最佳化——固定策略，掃描 1 個參數的範圍，
// 對每組參數各跑一次回測，依指定指標排序找出相對較佳組合。

function fakePerf(fastMa) {
  // fast_ma 越接近 10，年化報酬越高，方便驗證排序正確性
  const annual = 0.3 - Math.abs(fastMa - 10) * 0.02
  return {
    annual_return: annual, max_drawdown: -0.1, sharpe_ratio: 1.0, win_rate: 0.5,
    profit_factor: 1.5, total_trades: 30, avg_holding_days: 10, total_return: annual,
  }
}

test('回測頁：參數掃描模式跑多組參數並依指標排序、匯出 CSV (Y8)', async ({ page }) => {
  await page.route('**/api/v1/backtest/strategies', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          strategies: [
            {
              strategy_id: 'ma_crossover', name: 'MA均線交叉', description: '',
              params_schema: { properties: {
                fast_ma: { type: 'integer', default: 5 },
                slow_ma: { type: 'integer', default: 20 },
              } },
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/backtest/run', async (route) => {
    const body = route.request().postDataJSON()
    const fastMa = body.params.fast_ma
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          backtest_id: `bt_${fastMa}`,
          performance: fakePerf(fastMa),
          equity_curve: [],
          monthly_returns: [],
          costs: {},
          overfit_check: { available: false },
          mfe_mae: { available: false },
        },
      }),
    })
  })

  await page.goto('/stocks/2330/backtest')
  await page.getByText('參數掃描模式').click()

  const fastMaRow = page.locator('.form-group', { has: page.getByText('fast_ma', { exact: true }) })
  await fastMaRow.getByText('掃描這個參數').click()
  await fastMaRow.locator('input[placeholder="最小值"]').fill('6')
  await fastMaRow.locator('input[placeholder="最大值"]').fill('14')
  await fastMaRow.locator('input[placeholder="間距"]').first().fill('4')

  // 6, 10, 14 → 3 組
  await expect(page.getByText('將測試')).toContainText('3')

  const runBtn = page.getByRole('button', { name: /執行參數掃描/ })
  await expect(runBtn).toBeEnabled()
  await runBtn.click()

  await expect(page.getByText(/參數掃描結果（共 3 組/)).toBeVisible({ timeout: 20_000 })
  // fast_ma=10 應該排第一（依預設排序指標年化報酬率，10 最接近理想值）
  const firstRow = page.locator('.data-table tbody tr').first()
  await expect(firstRow).toHaveClass(/best-row/)
  await expect(firstRow.locator('td').first()).toHaveText('10')

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /匯出 CSV/ }).click(),
  ])
  expect(download.suggestedFilename()).toContain('backtest-sweep')
})
