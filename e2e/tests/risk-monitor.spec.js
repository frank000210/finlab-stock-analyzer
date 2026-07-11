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
  await expect(page.locator('.gauge-inner strong')).toHaveText('0.00%')
  await expect(page.locator('.status-pill')).toHaveClass(/is-warning/)
})
