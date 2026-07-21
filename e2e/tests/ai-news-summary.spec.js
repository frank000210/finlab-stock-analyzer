// @ts-check
const { test, expect } = require('@playwright/test')

// W4：社群熱度頁的 AI 輿情摘要——只總結已抓到的標題清單，使用者主動觸發。

const BUZZ = {
  symbol: '2327', stock_name: '國巨', buzz_score: 62, buzz_level: '偏熱',
  sentiment: 0.1, sentiment_label: '中性偏多', trend: 'up', trend_label: '上升',
  ptt: { post_count: 5, posts: [], sentiment: 0.2, bullish_count: 3, bearish_count: 2, trend: 'up', source: 'ptt' },
  news: { article_count: 8, articles: [{ title: '國巨法說會上修展望', published: '2026-07-20', source: 'cnyes' }], trend: 'up', source: 'news' },
  finance_news: { article_count: 3, articles: [], trend: 'flat', source: 'finance' },
  fact_check: { check_count: 0, items: [], source: '', source_url: '' },
  volume_attention: { attention_score: 40, volume_ratio: 1.2, volume_surge: false, vol_increasing: true, avg_volume_20d: 1000, avg_volume_5d: 1200 },
  trend_baseline: { sample_days: 30, avg_posts: 4.2, avg_articles: 6.1 }, updated_at: '2026-07-20T00:00:00',
}

test('社群熱度頁 AI 輿情摘要需手動觸發並正確渲染 (W4)', async ({ page }) => {
  await page.route('**/api/v1/stocks/ai/status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { configured: true } }) })
  })
  await page.route('**/api/v1/stocks/2327/social-buzz', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: BUZZ }) })
  })
  await page.route('**/api/v1/stocks/2327/social-buzz/history*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: [] }) })
  })
  let called = 0
  await page.route('**/api/v1/stocks/2327/social-buzz/ai-summary', async (route) => {
    called += 1
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2327', summary: '**焦點**：法說會上修展望帶動討論。\n**輿情傾向**：偏多', as_of: '2026-07-20', cached: false } }),
    })
  })

  await page.goto('/stocks/2327/social-buzz')
  const section = page.locator('.ai-news-section')
  await expect(section).toBeVisible({ timeout: 30_000 })
  expect(called).toBe(0)

  await section.getByRole('button', { name: '產生輿情摘要' }).click()
  await expect(section.locator('.ai-text')).toBeVisible({ timeout: 30_000 })
  expect(called).toBe(1)
  await expect(section.locator('.ai-text')).toContainText('法說會上修展望')
})
