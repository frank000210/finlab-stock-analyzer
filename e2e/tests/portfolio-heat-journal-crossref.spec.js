// @ts-check
const { test, expect } = require('@playwright/test')

// E1: 投組風險頁的「總風險熱度」過去只讀手動記錄的 portfolio_heat_positions，
// 交易日誌裡的進行中部位（若沒有重複記錄在這頁）完全不計入，會低估真實曝
// 險。同代碼去重：手動記錄視為權威版本，日誌只補它沒有的部位。
test('投組風險 交易日誌進行中部位併入總風險熱度並唯讀列出 (E1)', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_account', '1000000')
    // 手動記錄 2330（100,000 風險），交易日誌另外開了 2454（60,000 風險，
    // 未在這頁記錄）與一筆已平倉（不該計入）。
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2330', name: '台積電', industry: '半導體業', entry: 500, stop: 400, lots: 1, price: 500 },
    ]))
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { id: 'j1', symbol: '2454', name: '聯發科', side: 'long', entry: 100, stop: 90, target: null, lots: 6, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
      { id: 'j2', symbol: '2317', name: '鴻海', side: 'long', entry: 50, stop: 45, target: null, lots: 1, tag: '', openDate: '2026-06-01', status: 'closed', exit: 55, exitDate: '2026-06-10' },
    ]))
  })
  await page.reload()

  // 手動：100,000/1,000,000=10%；日誌 2454：60,000/1,000,000=6%；合計 16%（已平倉的 2317 不計入）
  await expect(page.locator('.scard.heat .sval')).toHaveText('16.00%')
  await expect(page.locator('.scard.heat')).toContainText('含交易日誌 1 檔進行中部位（6.00%）')

  const journalTable = page.locator('.journal-positions')
  await expect(journalTable).toBeVisible()
  await expect(journalTable).toContainText('2454')
  await expect(journalTable).not.toContainText('2317')
  // 手動記錄的 2330 不會在唯讀清單重複出現
  await expect(journalTable).not.toContainText('2330')
})

// F3: 交易日誌在另一分頁變動時，開著的投組風險頁靠 storage 事件即時更新，
// 不需手動重新整理（跟風控監控頁 B2 同一套模式）。
test('投組風險 另一分頁寫入日誌後總風險熱度即時更新 (F3)', async ({ page, context }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_account', '1000000')
  })
  await page.reload()
  await expect(page.locator('.scard.heat .sval')).toHaveText('0.00%')

  const page2 = await context.newPage()
  await page2.goto('/journal')
  await page2.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 'f3-1', symbol: '2454', name: '聯發科', side: 'long', entry: 100, stop: 90, target: null,
      lots: 6, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null,
    }]))
  })

  // 第一個分頁完全沒有 reload：60,000/1,000,000 = 6%
  await expect(page.locator('.scard.heat .sval')).toHaveText('6.00%')
  await expect(page.locator('.journal-positions')).toContainText('2454')
  await page2.close()
})

test('投組風險 手動記錄與交易日誌同代碼時不重複計入 (E1)', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('portfolio_heat_account', '1000000')
    localStorage.setItem('portfolio_heat_positions', JSON.stringify([
      { symbol: '2330', name: '台積電', industry: '半導體業', entry: 500, stop: 400, lots: 1, price: 500 },
    ]))
    // 交易日誌也開了 2330（不同進出場價），視為同一檔部位，不應該疊加。
    localStorage.setItem('finlab_trade_journal', JSON.stringify([
      { id: 'j1', symbol: '2330', name: '台積電', side: 'long', entry: 480, stop: 470, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
    ]))
  })
  await page.reload()

  await expect(page.locator('.scard.heat .sval')).toHaveText('10.00%')
  await expect(page.locator('.journal-positions')).toHaveCount(0)
})
