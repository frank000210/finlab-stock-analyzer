// @ts-check
const { test, expect } = require('@playwright/test')

// Trade Journal: record a trade, close it, verify realized R and stats.
test('交易日誌 records a trade, closes it, computes R and stats', async ({ page }) => {
  // 手動新增只填代號 → 名稱由搜尋 API 自動補上（mock）
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '2330', name_zh: '台積電', market: 'twse', industry: '半導體業' }] } }),
    })
  })
  await page.goto('/journal')
  await page.evaluate(() => localStorage.clear())
  await page.reload()

  await expect(page.getByRole('heading', { name: /交易日誌/ })).toBeVisible()

  // Record a long: entry 100, stop 90 (1R = 10), target 130, 1 lot.
  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('100')
  await page.getByPlaceholder('停損價').fill('90')
  await page.getByPlaceholder('目標價(選填)').fill('130')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByPlaceholder('型態(選填)').fill('突破')
  await page.getByRole('button', { name: '加入' }).click()

  await expect(page.getByRole('heading', { name: /進行中/ })).toBeVisible()
  // 代號伴隨股票名稱（背景解析）
  await expect(page.locator('.j-table').first()).toContainText('台積電')

  // Close at 120 -> R = (120-100)/(100-90) = 2.00
  await page.locator('.j-table input[type="number"]').first().fill('120')
  await page.getByRole('button', { name: '平倉' }).click()

  // Realized R in the closed table, and cumulative-R stat card.
  await expect(page.locator('.j-table').first()).toContainText('+2.00R')
  await expect(page.getByText('+2.00 R').first()).toBeVisible()

  // Review analytics: R histogram + per-型態 stats (突破 group).
  await expect(page.getByRole('heading', { name: '複盤分析' })).toBeVisible()
  await expect(page.locator('.rhist-svg')).toBeVisible()
  await expect(page.locator('.analytics-grid')).toContainText('突破')
})

test('交易日誌 複盤教練 gives rule-based coaching insights (E15)', async ({ page }) => {
  const mk = (exit, tag) => ({
    id: 'e15-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag, openDate: '2026-06-01', status: 'closed', exit, exitDate: '2026-06-10',
  })
  const journal = [
    // 4 連續大虧（衝動單，R=-3.0）觸發：連續虧損 + 拖累型態
    mk(70, '衝動單'), mk(70, '衝動單'), mk(70, '衝動單'), mk(70, '衝動單'),
    // 1 小賺（R=+0.3）跟上面湊出「賺一點就跑、賠了拗單」的整體不對稱
    mk(103, '衝動單'),
    // 3 筆突破型態穩定小賺（R=+0.5，勝率100%）觸發「表現最好的型態」——
    // 刻意用小賺而非大賺，避免拉高整體平均獲利、蓋掉上面的不對稱訊號
    mk(105, '突破'), mk(105, '突破'), mk(105, '突破'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(coach).toContainText('賺一點就跑')
  await expect(coach).toContainText('報復性下單')
  await expect(coach).toContainText('衝動單')
  await expect(coach).toContainText('突破')
  await expect(coach).toContainText('只有 8 筆')
  await expect(page.locator('.coach-item.coach-bad').first()).toBeVisible()
  await expect(page.locator('.coach-item.coach-good').first()).toBeVisible()
})

test('交易日誌 匯出 CSV', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    { id: 'x1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: 130, lots: 1, tag: '突破', openDate: '2026-07-01', status: 'closed', exit: 120, exitDate: '2026-07-05' },
  ])))
  await page.reload()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '匯出 CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/trade-journal.*\.csv/)
})
