// @ts-check
const { test, expect } = require('@playwright/test')

// KK7：籌碼分析頁（ChipAnalysisView）先前只有 smoke.spec.js 檢查標題有出現、
// turnover-whale-trend.spec.js 檢查連結有導過去，籌碼健診分數、主力成本、
// 目前股價、融資維持率這些實際算出來的數值從未被斷言過——後端公式算錯
// （例如 chip_signals.compute_margin_ratio、chip_cost.compute_major_cost）
// 只要畫面還「看起來」正常顯示，測試全綠也不會發現。

test('籌碼分析頁：籌碼健診分數與主力成本區顯示真實數值', async ({ page }) => {
  await page.goto('/stocks/2330/chip')
  await expect(page.getByRole('heading', { name: '籌碼分析' })).toBeVisible()

  // 籌碼健診 hero：0-100 分，不應該是 NaN/undefined。
  const healthNum = page.locator('.health-num')
  await expect(healthNum).toBeVisible({ timeout: 15_000 })
  const healthScore = Number((await healthNum.textContent()).trim())
  expect(Number.isFinite(healthScore)).toBeTruthy()
  expect(healthScore).toBeGreaterThanOrEqual(0)
  expect(healthScore).toBeLessThanOrEqual(100)

  // 主力成本區：目前股價一定是正數（即使主力估計成本因資料不足顯示 —）。
  const costSection = page.locator('section.card', { has: page.getByRole('heading', { name: '主力成本區' }) })
  await expect(costSection).toBeVisible()
  const lastCloseText = await costSection.locator('.cost-metric').nth(1).locator('.cm-val').textContent()
  const lastClose = Number(lastCloseText.replace(/,/g, '').trim())
  expect(Number.isFinite(lastClose)).toBeTruthy()
  expect(lastClose).toBeGreaterThan(0)

  // 融資維持率（若該卡片有渲染）：格式須為數字加 %，不是佔位符或 NaN%。
  const marginCard = page.locator('.sig-card', { has: page.getByRole('heading', { name: /融資維持率估算/ }) })
  if (await marginCard.count()) {
    const ratioText = (await marginCard.locator('.mh-val').textContent()).trim()
    expect(ratioText).toMatch(/^-?\d+(\.\d+)?%$/)
  }

  // 短線投機籌碼（當沖／隔日沖）：若渲染，最新當沖比須為合理百分比或 —。
  const dayTradeSection = page.locator('section.card', { has: page.getByRole('heading', { name: /短線投機籌碼/ }) })
  if (await dayTradeSection.count()) {
    const ratioText = (await dayTradeSection.locator('.dt-val').textContent()).trim()
    expect(ratioText === '—' || /^\d+(\.\d+)?%$/.test(ratioText)).toBeTruthy()
  }
})
