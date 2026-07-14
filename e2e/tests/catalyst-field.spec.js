// @ts-check
const { test, expect } = require('@playwright/test')

// O2：進場理由/催化劑欄位——NotebookLM「Humbled Trader」盤前選股邏輯強調每筆
// 進場都該有明確理由（不是看盤面隨便進），波段化後改成選填的複盤註記欄位。

test('交易日誌 手動新增交易可填寫進場理由並顯示於清單 (O2)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  await page.locator('.add-form input[placeholder="代碼 2330"]').fill('2330')
  await page.locator('.add-form input[placeholder="進場價"]').fill('100')
  await page.locator('.add-form input[placeholder="停損價"]').fill('90')
  await page.locator('.add-form input[placeholder="張數"]').fill('1')
  await page.locator('.add-form input[placeholder="進場理由/催化劑(選填)"]').fill('季報優於預期')
  await page.getByRole('button', { name: '加入' }).click()

  const row = page.locator('.j-table tbody tr', { hasText: '2330' })
  await expect(row.locator('.catalyst-tag')).toBeVisible()
  await expect(row.locator('.catalyst-tag')).toHaveAttribute('title', /季報優於預期/)

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal[0].catalyst).toBe('季報優於預期')
})

test('作戰台 記錄交易時可填寫進場理由並寫入日誌 (O2)', async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          as_of: '2026-07-14',
          items: [{ symbol: '2882', name: '國泰金', ok: true, price: 65, chg_pct: 1.0, trend: '多頭排列', rsi: 55, stop_dist_pct: 5, vol_ratio: 1.2, range_pos_pct: 60, setup_total: 72, setup_verdict: '進場條件佳', tags: [] }],
        },
      }),
    })
  })
  await page.route('**/api/v1/risk/market-regime', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { regime: 'offense', label: '進攻', risk_mult: 1.0, proxy: '0050', close: 60, ma200: 55, above_ma200: true, ma200_rising: true, mom20_pct: 2.5, as_of: '2026-07-14' } }),
    })
  })

  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    localStorage.removeItem('finlab_trade_journal')
  })
  await page.reload()

  const row = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await row.getByRole('button', { name: '記錄' }).click()
  await page.locator('.catalyst-field input').fill('法人連買 + 突破月線')
  await page.getByRole('button', { name: '確認記錄' }).click()

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal.length).toBe(1)
  expect(journal[0].catalyst).toBe('法人連買 + 突破月線')
})
