// @ts-check
const { test, expect } = require('@playwright/test')

// F7: 風控監控接真實資料 — 原本 /api/v1/risk/status、/equity-curve 是 backend
// risk_manager 用 seeded 亂數產生的模擬權益曲線，跟使用者實際交易完全無關。
// 現在改成直接讀「交易日誌」(localStorage finlab_trade_journal，與 F1-F6/
// 複盤教練同一份資料) 的已平倉紀錄，算出實際回撤(MDD)、實際當日交易筆數，
// 熔斷狀態也隨之反映真實紀律狀況而非隨機噪音。
function closedTrade(over) {
  return {
    id: 'rm-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', target: null, tag: '',
    status: 'closed',
    ...over,
  }
}

test('風控監控 尚無交易日誌紀錄時顯示空狀態與 ACTIVE (F7)', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate(() => {
    localStorage.removeItem('finlab_trade_journal')
    localStorage.removeItem('portfolio_heat_account')
  })
  await page.reload()

  await expect(page.locator('.status-pill')).toHaveClass(/is-active/)
  await expect(page.locator('.status-pill')).toHaveText('ACTIVE')
  await expect(page.locator('.trade-counter strong')).toHaveText('0')
  await expect(page.locator('.gauge-inner strong')).toHaveText('0.00%')
  await expect(page.locator('.empty-state')).toContainText('尚無已平倉交易紀錄')
  await expect(page.locator('.state-body p')).toContainText('尚無已平倉交易紀錄')
})

test('風控監控 依交易日誌已平倉紀錄計算實際回撤 MDD 與權益曲線 (F7)', async ({ page }) => {
  const journal = [
    closedTrade({ entry: 100, stop: 90, exit: 110, lots: 1, openDate: '2026-06-30', exitDate: '2026-07-01' }),
    closedTrade({ entry: 100, stop: 90, exit: 80, lots: 1, openDate: '2026-07-01', exitDate: '2026-07-02' }),
  ]
  await page.goto('/risk-monitor')
  await page.evaluate((j) => {
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_trade_journal', JSON.stringify(j))
  }, journal)
  await page.reload()

  // 權益：1,000,000 -> +10,000 (2026-07-01, 峰值1,010,000) -> -20,000 (2026-07-02, 990,000)
  // 回撤 = (1,010,000-990,000)/1,010,000 ≈ 1.98%
  await expect(page.locator('.gauge-inner strong')).toHaveText('1.98%')
  await expect(page.locator('.status-pill')).toHaveText('ACTIVE')
  await expect(page.locator('.badge-estimated').first()).toContainText('資料來源：交易日誌')
  await expect(page.locator('.chart-area').first()).toBeVisible()
})

test('風控監控 實際回撤達 6% 時顯示 WARNING (F7)', async ({ page }) => {
  const journal = [
    closedTrade({ entry: 100, stop: 90, exit: 90, lots: 6, openDate: '2026-07-01', exitDate: '2026-07-01' }),
  ]
  await page.goto('/risk-monitor')
  await page.evaluate((j) => {
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_trade_journal', JSON.stringify(j))
  }, journal)
  await page.reload()

  // 1,000,000 -> -60,000 = 940,000；回撤 = 60,000/1,000,000 = 6.00%
  await expect(page.locator('.gauge-inner strong')).toHaveText('6.00%')
  await expect(page.locator('.status-pill')).toHaveClass(/is-warning/)
  await expect(page.locator('.status-pill')).toHaveText('WARNING')
})

test('風控監控 實際回撤達 10% 以上時顯示 PAUSED (F7)', async ({ page }) => {
  const journal = [
    closedTrade({ entry: 100, stop: 90, exit: 90, lots: 12, openDate: '2026-07-01', exitDate: '2026-07-01' }),
  ]
  await page.goto('/risk-monitor')
  await page.evaluate((j) => {
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('finlab_trade_journal', JSON.stringify(j))
  }, journal)
  await page.reload()

  // 1,000,000 -> -120,000 = 880,000；回撤 = 120,000/1,000,000 = 12.00%
  await expect(page.locator('.gauge-inner strong')).toHaveText('12.00%')
  await expect(page.locator('.status-pill')).toHaveClass(/is-paused/)
  await expect(page.locator('.status-pill')).toHaveText('PAUSED')
})

test('風控監控 當日交易數達 12 筆時顯示 WARNING，與回撤無關 (F7)', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate(() => {
    const today = new Date().toISOString().slice(0, 10)
    const trades = Array.from({ length: 12 }, (_, i) => ({
      id: 'ot-' + i, symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 1, tag: '', openDate: today, status: 'open', exit: null, exitDate: null,
    }))
    localStorage.setItem('finlab_trade_journal', JSON.stringify(trades))
  })
  await page.reload()

  await expect(page.locator('.trade-counter strong')).toHaveText('12')
  await expect(page.locator('.status-pill')).toHaveClass(/is-warning/)
})

// A2 統一門檻：MDD 圖例/熔斷判定/交易上限過去是三套矛盾的數字，統一成一套
// 可自訂設定（localStorage）——交易數達上限 80% 警戒、達上限即熔斷。
test('風控監控 自訂當日上限 5 筆時第 5 筆即 PAUSED，圖例隨設定變動 (A2)', async ({ page }) => {
  await page.goto('/risk-monitor')
  await page.evaluate(() => {
    const today = new Date().toISOString().slice(0, 10)
    localStorage.setItem('finlab_daily_trade_limit', '5')
    localStorage.setItem('finlab_mdd_warn_pct', '4')
    localStorage.setItem('finlab_mdd_pause_pct', '8')
    const trades = Array.from({ length: 5 }, (_, i) => ({
      id: 'a2-' + i, symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 1, tag: '', openDate: today, status: 'open', exit: null, exitDate: null,
    }))
    localStorage.setItem('finlab_trade_journal', JSON.stringify(trades))
  })
  await page.reload()

  await expect(page.locator('.trade-counter span')).toHaveText('/ 5')
  await expect(page.locator('.status-pill')).toHaveClass(/is-paused/)
  await expect(page.locator('.trades-card .section-header p')).toContainText('達 4 筆警戒、5 筆熔斷')
  await expect(page.locator('.gauge-card .section-header p')).toContainText('綠色 < 4%，黃色 4-8%，紅色 ≥ 8%')
})

// C2 未實現回撤：進行中部位的浮動虧損也要被熔斷看到——凹單中的部位正是
// 風險最高的時刻，不能等平倉才算。
test('風控監控 進行中部位的未實現虧損納入回撤與熔斷 (C2)', async ({ page }) => {
  await page.route('**/api/v1/risk/sizing/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2330', name: '台積電', price: 80, atr: 2, atr_period: 14, atr_pct: 2.5, suggested_stops: [], setup: null, as_of: '2026-07-10', source: 'test' } }),
    })
  })
  await page.goto('/risk-monitor')
  await page.evaluate(() => {
    localStorage.setItem('portfolio_heat_account', '1000000')
    // 昨天開倉、尚未平倉：進場 100、現價 80、10 張 → 未實現 -200,000（-20%）
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 'c2-1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 10, tag: '', openDate: yesterday, status: 'open', exit: null, exitDate: null,
    }]))
  })
  await page.reload()

  await expect(page.locator('.badge-unrealized')).toContainText('含 1 筆未實現損益')
  await expect(page.locator('.gauge-inner strong')).toHaveText('20.00%')
  await expect(page.locator('.status-pill')).toHaveClass(/is-paused/)
})

// B2 跨分頁同步：交易日誌在另一個分頁平倉後，已開著的風控頁靠 storage
// 事件即時更新，不需手動重新整理。
test('風控監控 另一分頁寫入日誌後即時更新 (B2)', async ({ page, context }) => {
  await page.goto('/risk-monitor')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_account', '1000000')
  })
  await page.reload()
  await expect(page.locator('.gauge-inner strong')).toHaveText('0.00%')
  await expect(page.locator('.status-pill')).toHaveText('ACTIVE')

  const page2 = await context.newPage()
  await page2.goto('/journal')
  await page2.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 'b2-1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 6, tag: '', openDate: '2026-07-01', status: 'closed', exit: 90, exitDate: '2026-07-01',
    }]))
  })

  // 第一個分頁完全沒有 reload，靠 storage 事件更新：-60,000 → 6% → WARNING
  await expect(page.locator('.gauge-inner strong')).toHaveText('6.00%')
  await expect(page.locator('.status-pill')).toHaveClass(/is-warning/)
  await page2.close()
})
