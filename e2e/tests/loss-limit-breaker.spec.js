// @ts-check
const { test, expect } = require('@playwright/test')

// F1: daily/weekly loss-limit circuit breaker — autonomous risk-discipline
// addition. Real closed-trade R-multiples from 交易日誌 feed a status strip
// and a hard check in the E17 pre-trade gate, so "stop after N losses" is
// enforced instead of just advised (as it already was in 複盤教練/E15).
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/risk/watchlist-signals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          as_of: '2026-07-11',
          items: [
            { symbol: '2882', name: '國泰金', ok: true, price: 65, chg_pct: 1.0, trend: '多頭排列', rsi: 55, stop_dist_pct: 5, vol_ratio: 1.2, range_pos_pct: 60, setup_total: 72, setup_verdict: '進場條件佳', tags: [{ t: '多頭排列', tone: 'up' }] },
          ],
        },
      }),
    })
  })
  await page.route('**/api/v1/risk/market-regime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { regime: 'offense', label: '進攻', risk_mult: 1.0, proxy: '0050', close: 60, ma200: 55, above_ma200: true, ma200_rising: true, mom20_pct: 2.5, as_of: '2026-07-10' } }),
    })
  })
})

test('作戰台 單日虧損達上限時顯示熔斷並擋在紀律檢查裡 (F1)', async ({ page }) => {
  await page.goto('/command')
  await page.evaluate(() => {
    // F1: 用本地日曆日（跟 tradeMath.js 的 localDateStr() 同邏輯），不是
    // toISOString() 的 UTC 日期——兩者在日期邊界附近的時區會不一致。
    const now = new Date()
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    // 2 筆今日已平倉、各 -2R -> 今日合計 -4R，低於預設單日上限 -3R。
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 80, exitDate: today },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 80, exitDate: today },
    ]))
  })
  await page.reload()

  const strip = page.locator('.loss-limit-strip')
  await expect(strip).toHaveClass(/ll-danger/)
  await expect(strip).toContainText('-4.0R')
  await expect(strip).toContainText('已達停手門檻')

  const row = page.locator('.cmd-table tbody tr', { hasText: '2882' })
  await row.getByRole('button', { name: '記錄' }).click()
  await expect(page.locator('.trade-gate')).toBeVisible()
  await expect(page.locator('.trade-gate')).toContainText('單日虧損上限')
  await expect(page.locator('.gate-list li.bad')).toContainText('已達今日停手門檻')
})

test('作戰台 未達上限時熔斷條顯示安全狀態 (F1)', async ({ page }) => {
  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    localStorage.removeItem('finlab_trade_journal')
  })
  await page.reload()

  const strip = page.locator('.loss-limit-strip')
  await expect(strip).toHaveClass(/ll-safe/)
  await expect(strip).toContainText('+0.0R')
  await expect(page.locator('.ll-tag')).toHaveCount(0)
})

// G1：作戰台的虧損上限熔斷過去只在頁面載入當下讀一次交易日誌，之後不會再
// 更新——如果在另一分頁把交易平倉，這頁的熔斷條會顯示過時的安全狀態，直到
// 手動重新整理。這是熔斷（安全機制）的資料新鮮度問題，補上跟風控監控頁
// B2 同一套 storage 事件監聽。
test('作戰台 另一分頁把交易平倉後熔斷條即時更新 (G1)', async ({ page, context }) => {
  await page.goto('/command')
  await page.evaluate(() => {
    localStorage.setItem('finlab_watchlist', JSON.stringify(['2882']))
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_risk_pct', '1')
    localStorage.removeItem('finlab_trade_journal')
  })
  await page.reload()

  const strip = page.locator('.loss-limit-strip')
  await expect(strip).toHaveClass(/ll-safe/)

  const page2 = await context.newPage()
  await page2.goto('/journal')
  await page2.evaluate(() => {
    const now = new Date()
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    // 2 筆今日已平倉、各 -2R -> 今日合計 -4R，低於預設單日上限 -3R。
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 80, exitDate: today },
      { status: 'closed', side: 'long', entry: 100, stop: 90, exit: 80, exitDate: today },
    ]))
  })

  // 第一個分頁完全沒有 reload。
  await expect(strip).toHaveClass(/ll-danger/)
  await expect(strip).toContainText('-4.0R')
  await page2.close()
})

// 同一分頁記錄新單後，作戰台自己的熔斷/半凱利也要立即反映（過去只寫
// localStorage，沒同步更新本頁的本地資料，"記錄" 完之後同頁看不到變化）。
test('作戰台 記錄新單後同分頁的交易日誌統計立即同步 (G1)', async ({ page }) => {
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
  await page.locator('.gate-actions button', { hasText: '確認記錄' }).click()

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal).toHaveLength(1)
  expect(journal[0].symbol).toBe('2882')
})
