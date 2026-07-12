// @ts-check
const { test, expect } = require('@playwright/test')

// 社群熱度分析：PTT + 新聞 + 財經媒體（鉅亨網/MoneyDJ/CMoney）+ 事實查核，
// 外部即時抓取的資料量會變動，測試只驗證結構與格式，不assert確切筆數。
test('社群熱度 API 回傳含發布日期的新聞/財經媒體/PTT資料 (I1/J5)', async ({ request }) => {
  test.setTimeout(120_000)
  const resp = await request.get('/api/v1/stocks/2330/social-buzz', { timeout: 90_000 })
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  expect(body.success).toBeTruthy()
  const data = body.data

  // 新聞/財經媒體文章若有 published 欄位，格式須為 YYYY-MM-DD
  for (const a of data.news.articles) {
    if (a.published) expect(a.published).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  }
  expect(data.finance_news).toBeTruthy()
  expect(Array.isArray(data.finance_news.articles)).toBeTruthy()
  for (const a of data.finance_news.articles) {
    if (a.published) expect(a.published).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  }

  // PTT 貼文日期補完年份後也應該是完整日期格式（不再是裸的 M/D）
  for (const p of data.ptt.posts) {
    if (p.date) expect(p.date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  }

  // trend_baseline 沒有足夠歷史時是 null，有的話至少要有 3 天樣本
  if (data.trend_baseline) {
    expect(data.trend_baseline.sample_days).toBeGreaterThanOrEqual(3)
  }
})

test('社群熱度 歷史走勢 API 回傳陣列 (J3)', async ({ request }) => {
  const resp = await request.get('/api/v1/stocks/2330/social-buzz/history?days=30')
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  expect(body.success).toBeTruthy()
  expect(Array.isArray(body.data)).toBeTruthy()
})

test('社群熱度分析頁 顯示 PTT/新聞/財經媒體/事實查核區塊與趨勢基準說明', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/stocks/2330/social-buzz')

  await expect(page.getByRole('heading', { name: '🔥 社群熱度分析' })).toBeVisible()
  await expect(page.locator('.card', { hasText: 'PTT 股板討論' })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.card', { hasText: '新聞曝光' })).toBeVisible()
  await expect(page.locator('.card', { hasText: '財經媒體' })).toBeVisible()
  await expect(page.locator('.card', { hasText: '事實查核' })).toBeVisible()

  // 趨勢基準說明：有歷史資料時顯示均值，沒有時顯示「尚無足夠歷史資料」
  await expect(page.locator('.trend-baseline')).toContainText(/基準：近 \d+ 天|尚無足夠歷史資料/)
})

test('社群熱度分析頁 日期排序可切換由近至遠/由遠至近 (K1)', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/stocks/2317/social-buzz')

  const newsCard = page.locator('.card', { hasText: '新聞曝光' })
  await expect(newsCard).toBeVisible({ timeout: 30_000 })
  const dates = newsCard.locator('.news-date')
  await expect(dates.first()).toBeVisible()

  const readDates = async () => {
    const count = await dates.count()
    const values = []
    for (let i = 0; i < count; i++) values.push(await dates.nth(i).textContent())
    return values.filter(Boolean)
  }

  const descDates = await readDates()
  expect([...descDates].sort().reverse()).toEqual(descDates)

  await page.locator('.sort-select').selectOption('asc')
  const ascDates = await readDates()
  expect([...ascDates].sort()).toEqual(ascDates)
})
