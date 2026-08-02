// @ts-check
const { test, expect } = require('@playwright/test')

// F8: holding-period disposition effect — a distinct angle from F1-F5.
// Not about exit price vs stop (F5), not about size/frequency/trend/asymmetry.
// It asks: does the trader cut winners fast but hold losers far longer
// (處置效應 / disposition effect)? Measured purely from openDate→exitDate.
test('交易日誌 複盤教練 偵測處置效應（砍贏單、凹輸單）(F8)', async ({ page }) => {
  // entry 100 / stop 90 (risk = 10 per share).
  const mk = (exit, openDate, exitDate) => ({
    id: 'f8-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate, status: 'closed', exit, exitDate,
  })
  const journal = [
    // 3 筆獲利，各只抱 1 天就了結（exit 106 → R = +0.6）。
    mk(106, '2026-05-01', '2026-05-02'),
    mk(106, '2026-05-05', '2026-05-06'),
    mk(106, '2026-05-08', '2026-05-09'),
    // 3 筆虧損，各抱 12 天才出場（exit 96 → R = -0.4）。凹輸單。
    mk(96, '2026-05-01', '2026-05-13'),
    mk(96, '2026-05-05', '2026-05-17'),
    mk(96, '2026-05-08', '2026-05-20'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  // 虧損平均持有 12 天、獲利平均持有 1 天，比值 12 >= 1.5 → 應觸發。
  await expect(coach).toContainText('處置效應')
  await expect(coach).toContainText('砍贏單')
  await expect(coach).toContainText('12 天')
  await expect(coach).toContainText('1 天')
})

test('交易日誌 複盤教練 贏賠抱單時間相當時不顯示處置效應提示 (F8)', async ({ page }) => {
  const mk = (exit, openDate, exitDate) => ({
    id: 'f8b-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate, status: 'closed', exit, exitDate,
  })
  // 贏單與輸單都抱約 5 天（比值 ~1.0 < 1.5）→ 不得觸發。
  const journal = [
    mk(106, '2026-05-01', '2026-05-06'), mk(106, '2026-05-08', '2026-05-13'),
    mk(106, '2026-05-15', '2026-05-20'),
    mk(96, '2026-05-01', '2026-05-06'), mk(96, '2026-05-08', '2026-05-13'),
    mk(96, '2026-05-15', '2026-05-20'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(page.locator('.coach-list')).not.toContainText('處置效應')
})
