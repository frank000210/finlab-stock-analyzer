// @ts-check
const { test, expect } = require('@playwright/test')

// W2：AI 摘要試點。全部走 mock——真實 LLM 呼叫要 15~40 秒且每次都有成本，
// 不適合放進每次 push 都跑的測試套件。這裡驗的是前端契約與降級行為。

const SUMMARY = {
  symbol: '2327',
  summary:
    '**現況**：股價近期重挫，但營收與毛利率仍在成長。\n\n' +
    '**值得注意**：\n- EPS 與營收走勢明顯矛盾\n- 換手率偏低，買盤縮手\n\n' +
    '**待查證**：\n- EPS 驟降的原因',
  as_of: '2026-07-20',
  model_note: '由 AI 依網站既有數據生成；所有數字均來自網站計算結果，AI 僅負責解讀。',
  cached: false,
}

async function mockConfigured(page, configured = true) {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { configured } }),
    })
  })
}

test('分析頁 AI 摘要需手動觸發，點擊後顯示解讀內容 (W2)', async ({ page }) => {
  await mockConfigured(page)
  let called = 0
  await page.route('**/api/v1/stocks/2327/ai-summary', async (route) => {
    called += 1
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: SUMMARY }),
    })
  })

  await page.goto('/stocks/2327')
  const section = page.locator('.ai-summary-section')
  await expect(section).toBeVisible({ timeout: 60_000 })

  // 關鍵行為：頁面載入時「不」自動呼叫 AI（有成本且慢）
  await expect(section).toContainText('點右上按鈕')
  expect(called).toBe(0)

  await section.getByRole('button', { name: '產生 AI 摘要' }).click()
  await expect(section.locator('.ai-text')).toBeVisible({ timeout: 30_000 })
  expect(called).toBe(1)

  await expect(section.locator('.ai-text')).toContainText('EPS 與營收走勢明顯矛盾')
  // markdown 粗體有被渲染成 <strong>
  await expect(section.locator('.ai-text strong').first()).toContainText('現況')
  // 資料來源聲明（AI 只解讀、不產生數字）
  await expect(section).toContainText('AI 僅負責解讀')
})

test('分析頁 AI 服務未設定時整區隱藏，不影響其他區塊 (W2)', async ({ page }) => {
  await mockConfigured(page, false)

  await page.goto('/stocks/2327')
  // 其他區塊照常運作
  await expect(page.getByText('多因子技術圖表')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.ai-summary-section')).toHaveCount(0)
})

test('分析頁 AI 服務不可用時顯示錯誤，不影響其他區塊 (W2)', async ({ page }) => {
  await mockConfigured(page)
  await page.route('**/api/v1/stocks/2327/ai-summary', async (route) => {
    await route.fulfill({
      status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: '今日 AI 呼叫次數已達上限（200 次），請明日再試。' }),
    })
  })

  await page.goto('/stocks/2327')
  const section = page.locator('.ai-summary-section')
  await expect(section).toBeVisible({ timeout: 60_000 })
  await section.getByRole('button', { name: '產生 AI 摘要' }).click()

  await expect(section.locator('.error-text')).toContainText('已達上限', { timeout: 30_000 })
  await expect(page.getByText('多因子技術圖表')).toBeVisible()
})
