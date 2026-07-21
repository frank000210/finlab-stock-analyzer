// @ts-check
const { test, expect } = require('@playwright/test')

// Y7：回測策略並列比較——同股票/同區間，勾選 2~4 個策略跑並列比較，
// 顯示績效表格（含最佳指標標示）與疊加權益曲線，並可匯出 CSV。

function equityCurve(startVal, drift) {
  const items = []
  let v = startVal
  for (let i = 0; i < 6; i++) {
    items.push({ date: `2025-01-0${i + 1}`, portfolio_value: v })
    v = v * (1 + drift)
  }
  return items
}

function fakePerf(overrides) {
  return {
    annual_return: 0.12, max_drawdown: -0.08, sharpe_ratio: 1.1, win_rate: 0.55,
    profit_factor: 1.8, total_trades: 40, avg_holding_days: 12, total_return: 0.3,
    ...overrides,
  }
}

test('回測頁：策略並列比較模式顯示績效表格、疊加權益曲線、匯出 CSV (Y7)', async ({ page }) => {
  await page.route('**/api/v1/backtest/strategies', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          strategies: [
            { strategy_id: 'ma_crossover', name: 'MA均線交叉', description: '', params_schema: { properties: { fast_ma: { type: 'integer', default: 5 }, slow_ma: { type: 'integer', default: 20 } } } },
            { strategy_id: 'macd_trend', name: 'MACD趨勢', description: '', params_schema: { properties: {} } },
            { strategy_id: 'bollinger_breakout', name: '布林通道突破', description: '', params_schema: { properties: {} } },
            { strategy_id: 'rsi_reversion', name: 'RSI反轉', description: '', params_schema: { properties: {} } },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/backtest/run', async (route) => {
    const body = route.request().postDataJSON()
    const sid = body.strategy_id
    const perfBySid = {
      ma_crossover: fakePerf({ annual_return: 0.20, max_drawdown: -0.05 }),
      macd_trend: fakePerf({ annual_return: 0.08, max_drawdown: -0.15 }),
    }
    const perf = perfBySid[sid] || fakePerf()
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          backtest_id: `bt_${sid}`,
          performance: perf,
          equity_curve: equityCurve(1_000_000, sid === 'ma_crossover' ? 0.01 : 0.003),
          monthly_returns: [],
          costs: {},
          overfit_check: { available: false },
          mfe_mae: { available: false },
        },
      }),
    })
  })

  await page.goto('/stocks/2330/backtest')
  await page.getByText('策略並列比較模式').click()

  // 預設會勾選前兩個策略（MA均線交叉、MACD趨勢）
  await expect(page.locator('.compare-strategy-item input:checked')).toHaveCount(2)

  const runBtn = page.getByRole('button', { name: /執行比較回測/ })
  await expect(runBtn).toBeEnabled()
  await runBtn.click()

  await expect(page.getByText('策略績效並列比較')).toBeVisible({ timeout: 20_000 })
  const table = page.locator('.data-table table')
  await expect(table.locator('thead th')).toHaveCount(3) // 指標 + 2策略
  await expect(page.locator('.best-cell').first()).toBeVisible()

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /匯出 CSV/ }).click(),
  ])
  expect(download.suggestedFilename()).toContain('backtest-compare')
})

test('回測頁：關閉比較模式後恢復單一策略表單', async ({ page }) => {
  await page.route('**/api/v1/backtest/strategies', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { strategies: [{ strategy_id: 'ma_crossover', name: 'MA均線交叉', description: '', params_schema: { properties: { fast_ma: { type: 'integer', default: 5 } } } }] },
      }),
    })
  })
  await page.goto('/stocks/2330/backtest')
  const toggle = page.getByText('策略並列比較模式')
  await toggle.click()
  await expect(page.locator('.compare-strategy-list')).toBeVisible()
  await toggle.click()
  await expect(page.locator('.compare-strategy-list')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '🚀 執行回測' })).toBeVisible()
})
