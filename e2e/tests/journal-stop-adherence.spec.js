// @ts-check
const { test, expect } = require('@playwright/test')

// F5: stop-loss adherence — a distinct execution-fidelity check from
// F1-F4 (size, frequency, trend): did losing trades actually exit near the
// planned stop, or did the trader let the loss run past it ("凹單")?
test('交易日誌 複盤教練 偵測停損未照計畫執行（凹單超過停損）(F5)', async ({ page }) => {
  const mk = (exit, day) => ({
    id: 'f5-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate: day, status: 'closed', exit, exitDate: day,
  })
  const journal = [
    // 2 筆照計畫在停損價出場（R=-1.00）。
    mk(90, '2026-05-01'), mk(90, '2026-05-02'),
    // 3 筆凹單超過停損，實際出場比停損還差 10 元（R=-2.00）。
    mk(80, '2026-05-03'), mk(80, '2026-05-04'), mk(80, '2026-05-05'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(coach).toContainText('3 筆')
  await expect(coach).toContainText('60%')
  await expect(coach).toContainText('凹單')
  await expect(coach).toContainText('-2.00R')
})

test('交易日誌 複盤教練 停損都有照計畫執行時不顯示該項提示 (F5)', async ({ page }) => {
  const mk = (exit, day) => ({
    id: 'f5b-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate: day, status: 'closed', exit, exitDate: day,
  })
  // 5 筆虧損交易，全部都在停損價附近出場（沒有凹單）。
  const journal = [
    mk(90, '2026-05-01'), mk(89, '2026-05-02'), mk(90, '2026-05-03'),
    mk(89, '2026-05-04'), mk(90, '2026-05-05'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(page.locator('.coach-list')).not.toContainText('凹單')
})
