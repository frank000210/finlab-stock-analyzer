// @ts-check
const { test, expect } = require('@playwright/test')

// F3: rolling expectancy trend — extends 複盤教練 with an edge-decay check:
// compare the most recent closed trades against the earlier baseline, sorted
// by exitDate (not insertion order), and flag when recent performance has
// dropped meaningfully from a previously-positive edge.
test('交易日誌 複盤教練 偵測期望值邊際衰退（近期比先前明顯轉差）(F3)', async ({ page }) => {
  const mk = (exit, exitDate) => ({
    id: 'f3-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate: exitDate, status: 'closed', exit, exitDate,
  })
  const journal = [
    // 15 筆較早的交易，R=+1.00（穩定正期望值基準）
    ...Array.from({ length: 15 }, (_, i) => mk(110, `2026-05-${String(i + 1).padStart(2, '0')}`)),
    // 最近 10 筆全部虧損，R=-0.50——期望值明顯轉差
    ...Array.from({ length: 10 }, (_, i) => mk(95, `2026-06-${String(i + 1).padStart(2, '0')}`)),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(coach).toContainText('明顯轉差')
  await expect(coach).toContainText('-0.50R')
  await expect(coach).toContainText('1.00R')
})

test('交易日誌 複盤教練 表現穩定時不顯示邊際衰退提示 (F3)', async ({ page }) => {
  const mk = (exit, exitDate) => ({
    id: 'f3b-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate: exitDate, status: 'closed', exit, exitDate,
  })
  // 25 筆全部一致地小賺，沒有轉差可言。
  const journal = Array.from({ length: 25 }, (_, i) => mk(105, `2026-05-${String((i % 28) + 1).padStart(2, '0')}`))

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(page.locator('.coach-list')).not.toContainText('明顯轉差')
})
