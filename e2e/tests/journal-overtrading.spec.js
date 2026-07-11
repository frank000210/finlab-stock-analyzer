// @ts-check
const { test, expect } = require('@playwright/test')

// F4: overtrading frequency detector — extends 複盤教練 with a check that's
// independent of win/loss: a single day with a trade-count spike vs your
// typical daily frequency is itself a sign of impulse/revenge trading.
test('交易日誌 複盤教練 偵測單日過度交易 (F4)', async ({ page }) => {
  const mk = (openDate) => ({
    id: 'f4-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate, status: 'closed', exit: 100, exitDate: openDate,
  })
  const journal = [
    // 5 個正常交易日，各 1 筆。
    mk('2026-05-01'), mk('2026-05-02'), mk('2026-05-03'), mk('2026-05-04'), mk('2026-05-05'),
    // 單日爆量：2026-05-10 這天做了 6 筆（是平常中位數 1 筆的 6 倍）。
    mk('2026-05-10'), mk('2026-05-10'), mk('2026-05-10'), mk('2026-05-10'), mk('2026-05-10'), mk('2026-05-10'),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(coach).toContainText('2026-05-10')
  await expect(coach).toContainText('6 筆交易')
  await expect(coach).toContainText('6.0 倍')
  await expect(coach).toContainText('衝動/報復性交易')
})

test('交易日誌 複盤教練 交易頻率平穩時不顯示過度交易提示 (F4)', async ({ page }) => {
  const mk = (openDate) => ({
    id: 'f4b-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate, status: 'closed', exit: 100, exitDate: openDate,
  })
  const journal = [
    '2026-05-01', '2026-05-02', '2026-05-03', '2026-05-04',
    '2026-05-05', '2026-05-06', '2026-05-07', '2026-05-08',
  ].map(mk)

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(page.locator('.coach-list')).not.toContainText('衝動/報復性交易')
})
