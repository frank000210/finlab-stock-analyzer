// @ts-check
const { test, expect } = require('@playwright/test')

// F2: position-sizing consistency — extends 複盤教練 (E15) with a check for
// "bets sized well above your usual risk perform worse than normal-sized
// ones", a concrete revenge-sizing detector built from real closed trades.
test('交易日誌 複盤教練 偵測部位大小不一致（加碼的單反而更差）(F2)', async ({ page }) => {
  const mk = (exit, lots) => ({
    id: 'f2-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots, tag: '', openDate: '2026-06-01', status: 'closed', exit, exitDate: '2026-06-10',
  })
  const journal = [
    // 7 筆正常大小（1 張，風險金額 10,000）：4 賺(R=+1) + 3 小賠(R=-0.5) -> 平均 +0.36R
    mk(110, 1), mk(110, 1), mk(110, 1), mk(110, 1),
    mk(95, 1), mk(95, 1), mk(95, 1),
    // 3 筆明顯加碼（5 張，風險金額 50,000，是中位數的 5 倍）：全部大賠 R=-3.0
    mk(70, 5), mk(70, 5), mk(70, 5),
  ]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  const coach = page.locator('.coach-list')
  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(coach).toContainText('押注明顯偏大')
  await expect(coach).toContainText('-3.00R')
  await expect(coach).toContainText('0.36R')
})

test('交易日誌 複盤教練 部位大小一致時不顯示該項提示 (F2)', async ({ page }) => {
  const mk = (exit) => ({
    id: 'f2b-' + Math.random().toString(36).slice(2),
    symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
    lots: 1, tag: '', openDate: '2026-06-01', status: 'closed', exit, exitDate: '2026-06-10',
  })
  // 全部同樣大小（1 張），沒有加碼可言。
  const journal = [mk(110), mk(110), mk(95), mk(105), mk(95), mk(110), mk(105), mk(95)]

  await page.goto('/journal')
  await page.evaluate((j) => localStorage.setItem('finlab_trade_journal', JSON.stringify(j)), journal)
  await page.reload()

  await expect(page.getByRole('heading', { name: '🎓 複盤教練' })).toBeVisible()
  await expect(page.locator('.coach-list')).not.toContainText('押注明顯偏大')
})
