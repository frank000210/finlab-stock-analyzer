// @ts-check
const { test, expect } = require('@playwright/test')

// LL10：季節性分析頁、公開資訊頁先前只有 smoke/a11y/layout 測試檢查標題有
// 出現，從未斷言過實際算出來的數值——公式算錯或 DD8 那種欄位對應漏掉的
// 回歸，只要畫面還「看起來」正常顯示，測試全綠也不會發現。

test('季節性分析頁：年度合計欄位是各月報酬率加總，不是佔位值', async ({ page }) => {
  await page.goto('/stocks/2330/seasonal')
  await expect(page.getByRole('heading', { name: /季節性分析/ })).toBeVisible()
  await expect(page.locator('.heatmap-table tbody tr').first()).toBeVisible({ timeout: 20_000 })

  const firstRow = page.locator('.heatmap-table tbody tr').first()
  const monthCells = firstRow.locator('.heat-cell')
  expect(await monthCells.count()).toBe(12)

  let expectedTotal = 0
  const count = await monthCells.count()
  for (let i = 0; i < count; i++) {
    const text = (await monthCells.nth(i).textContent()).trim()
    if (text !== '–') expectedTotal += Number(text)
  }

  const totalText = (await firstRow.locator('.year-total').textContent()).trim()
  const actualTotal = Number(totalText.replace('%', ''))
  expect(Number.isFinite(actualTotal)).toBeTruthy()
  // yearTotal() 加總的是原始未捨入的月報酬，畫面上每月已先各自 toFixed(1)
  // 才顯示——用捨入後的月值反推加總會有些微捨入誤差，容忍到 1（抓的是
  // 公式錯誤如正負號顛倒/漏乘，不是抓小數點誤差）。
  expect(Math.abs(actualTotal - expectedTotal)).toBeLessThan(1)

  // 各月統計：勝率必須是 0-100 的合理數字，不是 NaN/undefined。
  const winRateText = await page.locator('.month-stat-card').first().locator('.stat-meta').textContent()
  const winRate = Number(winRateText.replace('勝率', '').replace('%', '').trim())
  expect(Number.isFinite(winRate)).toBeTruthy()
  expect(winRate).toBeGreaterThanOrEqual(0)
  expect(winRate).toBeLessThanOrEqual(100)
})

test('公開資訊頁：財務摘要不會洩漏物件字串或原始英文欄位名（DD8 回歸）', async ({ page }) => {
  await page.goto('/stocks/2330/public-data')
  await expect(page.getByRole('heading', { name: /公開資訊/ })).toBeVisible()

  const finSection = page.locator('section.card', { has: page.getByRole('heading', { name: /最新財務摘要/ }) })
  await expect(finSection).toBeVisible({ timeout: 20_000 })

  const items = finSection.locator('.fin-item')
  const count = await items.count()
  expect(count).toBeGreaterThan(0)

  for (let i = 0; i < count; i++) {
    const label = (await items.nth(i).locator('.fin-label').textContent()).trim()
    const value = (await items.nth(i).locator('.fin-value').textContent()).trim()
    // DD8 修復前：latest_financial_announcement 是物件，會被顯示成這個字串。
    expect(value).not.toContain('[object Object]')
    // DD8 修復前：對不上 labelMap 的欄位會直接顯示原始 snake_case 英文 key。
    expect(label).not.toMatch(/^[a-z_]+$/)
  }
})
