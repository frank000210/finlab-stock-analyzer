// @ts-check
const { test, expect } = require('@playwright/test')

// S10：3 個原本只測「頁面有載入」的頁面，補上真正的互動流程測試——這些
// 流程如果壞掉（包括 S1 修的訊號規則沒存進 DB 的 bug），只測頁面載入完全
// 抓不到。

test('資料爬蟲頁 新聞可信度檢查表單送出後顯示評分結果 (S10)', async ({ page }) => {
  await page.route('**/api/v1/news/crawled-data*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/news/check-credibility', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.url).toBe('https://example.com/news/123')
    expect(body.title).toBe('台積電法說會展望樂觀')
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          overall_score: 82, verdict: 'CREDIBLE',
          layers: [
            { label: '媒體來源', score: 90 },
            { label: 'Cofacts 查核', score: 75 },
          ],
        },
      }),
    })
  })

  await page.goto('/data-agent')
  await page.getByPlaceholder('https://example.com/news').fill('https://example.com/news/123')
  await page.getByPlaceholder('輸入新聞標題').fill('台積電法說會展望樂觀')
  await page.getByPlaceholder('貼上完整新聞內文').fill('台積電法說會表示下季展望樂觀，維持資本支出計畫。')
  await page.getByRole('button', { name: '檢查可信度' }).click()

  const panel = page.locator('.result-panel')
  await expect(panel).toBeVisible({ timeout: 20_000 })
  await expect(panel).toContainText('82')
  await expect(panel).toContainText('CREDIBLE')
  await expect(panel).toContainText('媒體來源')
})

test('訊號規則頁 新增規則後顯示於清單，刪除後移除 (S10)', async ({ page }) => {
  let rules = []

  await page.route('**/api/v1/signal-rules', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: rules } }) })
    } else if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      rules = [...rules, { id: 'rule-1', name: body.name, description: body.description, script: body.script, is_active: false, is_default: false }]
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: rules[rules.length - 1] }) })
    }
  })
  await page.route('**/api/v1/signal-rules/rule-1', async (route) => {
    if (route.request().method() === 'DELETE') {
      rules = rules.filter(r => r.id !== 'rule-1')
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { deleted: 'rule-1' } }) })
    }
  })

  await page.goto('/signal-rules')
  await page.getByPlaceholder('例如：突破量價策略').fill('測試規則')
  await page.getByPlaceholder('描述規則使用情境').fill('e2e 互動測試用')
  await page.getByRole('button', { name: '建立規則' }).click()

  const ruleCard = page.locator('.rule-card', { hasText: '測試規則' })
  await expect(ruleCard).toBeVisible({ timeout: 20_000 })
  await expect(ruleCard).toContainText('e2e 互動測試用')

  page.once('dialog', (d) => d.accept())
  await ruleCard.getByRole('button', { name: '刪除' }).click()
  await expect(page.locator('.rule-card', { hasText: '測試規則' })).toHaveCount(0)
})

test('觀察股關聯圖頁 套用新的觀察池後寫入本頁專屬 localStorage 並重新載入 (S10, updated for Y1)', async ({ page }) => {
  await page.route('**/api/v1/graph/watchlist/timeline*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { frames: [], symbols: [] } }) })
  })
  await page.route('**/api/v1/graph/watchlist/build', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { frames: [], symbols: [] } }) })
  })
  await page.route('**/api/v1/graph/watchlist/snapshot*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { nodes: [], edges: [] } }) })
  })
  await page.route('**/api/v1/graph/watchlist/alerts*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })

  await page.goto('/graph01')
  await page.evaluate(() => localStorage.setItem('finlab_watchlist', JSON.stringify(['2330', '2317'])))
  await page.evaluate(() => localStorage.removeItem('finlab_graph01_symbols'))
  await page.reload()

  const input = page.locator('input.input').first()
  await expect(input).toBeVisible({ timeout: 20_000 })
  await input.fill('2330,2454,2317,2603')
  await page.getByRole('button', { name: '套用觀察池' }).click()

  // Y1 修正前：套用會把 finlab_watchlist 也覆寫掉；修正後：這頁的組合只存在
  // 本頁專屬的 finlab_graph01_symbols，共用觀察清單維持原樣，重新整理後仍生效。
  const graphSymbols = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_graph01_symbols') || '[]'))
  expect(graphSymbols).toEqual(['2330', '2454', '2317', '2603'])

  const sharedWatchlist = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_watchlist') || '[]'))
  expect(sharedWatchlist).toEqual(['2330', '2317'])

  await page.reload()
  await expect(input).toHaveValue('2330,2454,2317,2603')
})
