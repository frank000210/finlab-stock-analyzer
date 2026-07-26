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

// 大戶成本「問問AI」：公式說明 + 逐步試算 + 5 日可能情境（教育性質，非預測）。
// 真實 LLM 呼叫要 15~40 秒且每次都有成本，這裡 mock AI 端點只驗前端契約，
// 同 ai-summary.spec.js 的作法；chip-analysis 本身走真後端，確保按鈕出現的
// 前提條件（cost.cost !== null）跟真實資料一致。

const EXPLAIN = {
  symbol: '2330',
  explanation:
    '**① 大戶成本怎麼算**：把法人買超那幾天的收盤價，用買超股數當權重平均起來。\n\n' +
    '**② 這檔股票的實際試算過程**：買超金額合計 ÷ 買超股數合計 = 大戶估計成本。\n\n' +
    '**③ 股價之後可能的情境（僅供參考，非預測）**：現價貼近成本區，市場上常見的解讀是多空拉鋸，實際走勢可能因各種原因而不同，不構成投資建議。',
  as_of: '2026-07-27',
  model_note: '由 AI 依網站已計算好的大戶成本數據生成說明；所有數字均來自網站計算結果，AI 僅負責解讀與教學，不構成投資建議。',
  cached: false,
}

async function mockAiConfigured(page, configured = true) {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { configured } }),
    })
  })
}

test('籌碼分析頁：主力成本區「問問AI」需手動觸發，點擊後顯示公式與試算說明', async ({ page }) => {
  await mockAiConfigured(page)
  let called = 0
  await page.route('**/api/v1/stocks/2330/major-cost/ai-explain**', async (route) => {
    called += 1
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: EXPLAIN }),
    })
  })

  await page.goto('/stocks/2330/chip')
  const costSection = page.locator('section.card', { has: page.getByRole('heading', { name: '主力成本區' }) })
  await expect(costSection).toBeVisible({ timeout: 15_000 })

  const aiButton = costSection.getByRole('button', { name: '🤖 問問AI' })
  await expect(aiButton).toBeVisible()
  // 關鍵行為：頁面載入時「不」自動呼叫 AI（有成本且慢）。
  expect(called).toBe(0)

  await aiButton.click()
  await expect(costSection.locator('.ai-text')).toBeVisible({ timeout: 30_000 })
  expect(called).toBe(1)

  await expect(costSection.locator('.ai-text')).toContainText('大戶成本怎麼算')
  await expect(costSection.locator('.ai-text')).toContainText('僅供參考，非預測')
  // markdown 粗體有被渲染成 <strong>
  await expect(costSection.locator('.ai-text strong').first()).toContainText('大戶成本怎麼算')
  await expect(costSection).toContainText('不構成投資建議')
})

test('籌碼分析頁：AI 服務未設定時「問問AI」按鈕不顯示', async ({ page }) => {
  await mockAiConfigured(page, false)

  await page.goto('/stocks/2330/chip')
  const costSection = page.locator('section.card', { has: page.getByRole('heading', { name: '主力成本區' }) })
  await expect(costSection).toBeVisible({ timeout: 15_000 })
  await expect(costSection.getByRole('button', { name: '🤖 問問AI' })).toHaveCount(0)
})

test('籌碼分析頁：AI 說明產生失敗時顯示錯誤訊息，不影響其他區塊', async ({ page }) => {
  await mockAiConfigured(page)
  await page.route('**/api/v1/stocks/2330/major-cost/ai-explain**', async (route) => {
    await route.fulfill({
      status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: 'AI 服務尚未設定' }),
    })
  })

  await page.goto('/stocks/2330/chip')
  const costSection = page.locator('section.card', { has: page.getByRole('heading', { name: '主力成本區' }) })
  await expect(costSection).toBeVisible({ timeout: 15_000 })
  await costSection.getByRole('button', { name: '🤖 問問AI' }).click()

  await expect(costSection.locator('.error-text')).toContainText('AI 服務尚未設定', { timeout: 15_000 })
  await expect(page.getByRole('heading', { name: '籌碼分析' })).toBeVisible()
})
