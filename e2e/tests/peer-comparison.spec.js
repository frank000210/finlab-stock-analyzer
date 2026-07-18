// @ts-check
const { test, expect } = require('@playwright/test')

// U1-U3：同業比較——把單股數字放進參照系。含產業預設/自訂群組、目標股
// 高亮、相對定位敘事、同業編輯與 AI 協助（貼回解析）流程。

const COMPARISON = {
  success: true,
  data: {
    symbol: '2330', industry: '半導體業', group_source: 'industry',
    target: {
      symbol: '2330', name: '台積電', source: 'target', price: 1015,
      pe: 72.4, revenue_yoy_avg: 54.5, eps: 6.54, eps_yoy_pct: 347.9,
      gross_margin: 29.0, mom20_pct: -33.0, above_ma200: true,
      market_cap: 94788240435, cap_tier: '大型/中型',
    },
    peers: [
      { symbol: '1519', name: '華城', source: 'industry', pe: 45.0, revenue_yoy_avg: -9.6, eps: 3.29, eps_yoy_pct: 9.7, gross_margin: 43.6, mom20_pct: -18.4, above_ma200: false },
      { symbol: '1590', name: '亞德客-KY', source: 'industry', pe: 27.7, revenue_yoy_avg: 36.8, eps: 13.35, eps_yoy_pct: 37.9, gross_margin: 48.0, mom20_pct: -4.2, above_ma200: true },
      { symbol: '1504', name: '東元', source: 'industry', pe: 29.7, revenue_yoy_avg: 8.1, eps: 0.51, eps_yoy_pct: -5.6, gross_margin: 23.5, mom20_pct: -2.8, above_ma200: true },
    ],
    as_of: '2026-07-18',
  },
}

test('分析頁顯示同業比較表，目標股高亮且給出相對定位敘事 (U2)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/peer-comparison', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(COMPARISON) })
  })

  await page.goto('/stocks/2330')
  const section = page.locator('.peer-section')
  await expect(section).toBeVisible({ timeout: 60_000 })
  await expect(section.locator('.peer-source-badge')).toContainText('產業預設（半導體業）')

  // 目標股置頂高亮
  const rows = section.locator('.peer-table tbody tr')
  await expect(rows).toHaveCount(4)
  await expect(rows.first()).toHaveClass(/peer-target/)
  await expect(rows.first()).toContainText('台積電')
  await expect(rows.first()).toContainText('72.4')

  // 相對定位敘事：PE 最高（第 4 低）＋營收成長第 1 高 → 給出風險提醒
  await expect(section.locator('.peer-narrative')).toContainText('排第 4 低')
  await expect(section.locator('.peer-narrative')).toContainText('營收成長排第 1 高')
  await expect(section.locator('.peer-narrative')).toContainText('若成長降溫')
})

test('同業編輯：手動加入同業並儲存，PUT 內容正確 (U2)', async ({ page }) => {
  let putBody = null
  await page.route('**/api/v1/stocks/2330/peer-comparison', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(COMPARISON) })
  })
  await page.route('**/api/v1/stocks/search*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [{ symbol: '3017', name_zh: '奇鋐' }] } }),
    })
  })
  await page.route('**/api/v1/stocks/2330/peers', async (route) => {
    putBody = route.request().postDataJSON()
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { symbol: '2330', industry: '半導體業', group_source: 'custom', peers: [] } }),
    })
  })

  await page.goto('/stocks/2330')
  await expect(page.locator('.peer-section')).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: '編輯同業' }).click()

  await page.getByLabel('加入同業代碼').fill('3017')
  await page.getByRole('button', { name: '加入', exact: true }).click()
  await expect(page.locator('.peer-chip', { hasText: '3017' })).toContainText('奇鋐')

  await page.getByRole('button', { name: '儲存群組' }).click()
  await expect.poll(() => putBody).not.toBeNull()
  expect(putBody.peers.some(p => p.symbol === '3017' && p.source === 'manual')).toBe(true)
})

test('AI 協助：貼回 AI 回答後解析代碼、驗證並以 ai 來源加入 (U2)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/peer-comparison', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(COMPARISON) })
  })
  // 3324 查得到（有效）、9999 查不到（無效，不可勾選）
  await page.route('**/api/v1/stocks/search*', async (route) => {
    const q = new URL(route.request().url()).searchParams.get('q')
    const items = q === '3324' ? [{ symbol: '3324', name_zh: '雙鴻' }] : []
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items } }) })
  })

  await page.goto('/stocks/2330')
  await expect(page.locator('.peer-section')).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: '編輯同業' }).click()

  await page.getByLabel('貼上 AI 回答').fill('依業務相似度建議：3324 雙鴻：水冷散熱。另 9999 不存在公司。')
  await page.getByRole('button', { name: '解析代碼' }).click()

  const cands = page.locator('.ai-cand')
  await expect(cands).toHaveCount(2)
  await expect(cands.filter({ hasText: '3324' })).toContainText('雙鴻')
  await expect(cands.filter({ hasText: '9999' })).toContainText('查無此代碼')
  await expect(cands.filter({ hasText: '9999' }).locator('input')).toBeDisabled()

  await page.getByRole('button', { name: '加入勾選的同業' }).click()
  const chip = page.locator('.peer-chip', { hasText: '3324' })
  await expect(chip).toBeVisible()
  await expect(chip.locator('.peer-tag')).toContainText('AI') // 來源標記
})

test('同業不足時顯示空狀態引導，不硬湊 (U2)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/peer-comparison', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { symbol: '2330', industry: '其他', group_source: 'industry', target: COMPARISON.data.target, peers: [], as_of: '2026-07-18' },
      }),
    })
  })
  await page.goto('/stocks/2330')
  const section = page.locator('.peer-section')
  await expect(section).toBeVisible({ timeout: 60_000 })
  await expect(section).toContainText('目前沒有可比較的同業')
  await expect(section.locator('.peer-table')).toHaveCount(0)
})
