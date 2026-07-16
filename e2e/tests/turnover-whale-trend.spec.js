// @ts-check
const { test, expect } = require('@playwright/test')

// Q1+Q2：個股分析頁新增換手率分析＋千張大戶持股趨勢，兩者都要能「發生
// 作用」——不是丟數字，而是依股價方向給出不同解讀，異常時才觸發聯合判讀。

test('分析頁顯示換手率分析區塊，異常放大時給方向性敘事 (Q1)', async ({ page }) => {
  await page.route('**/api/v1/analysis/2330/turnover', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', turnover_pct: 0.85, percentile: 92, sample_days: 60, cap_tier: '大型/中型',
          series: [{ date: '2026-07-15', turnover_pct: 0.85 }],
          as_of: '2026-07-15', shares_as_of: '2026-07-01', source: 'finmind',
        },
      }),
    })
  })

  await page.goto('/stocks/2330')
  const section = page.locator('.turnover-section')
  await expect(section).toBeVisible({ timeout: 60_000 })
  await expect(section).toContainText('0.85%')
  await expect(section).toContainText('近 60 日百分位 92%')
  await expect(section).toContainText('大型/中型股')
  // 換手放大 + 敘事應點出「換手確立趨勢」或「換手不過」其中一種方向性判讀
  await expect(page.locator('.turnover-narrative')).toContainText(/換手/)
})

test('分析頁換手率樣本不足時顯示提示，不硬湊誤導的百分位 (R3)', async ({ page }) => {
  await page.route('**/api/v1/analysis/2330/turnover', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', turnover_pct: 1.2, percentile: null, sample_days: 5, cap_tier: '小型',
          series: [], as_of: '2026-07-15', shares_as_of: '2026-07-01', source: 'finmind',
        },
      }),
    })
  })

  await page.goto('/stocks/2330')
  const section = page.locator('.turnover-section')
  await expect(section).toBeVisible({ timeout: 60_000 })
  await expect(section).toContainText('1.2%')
  await expect(section).toContainText('樣本不足無法計算百分位')
  await expect(section.locator('.turnover-scale')).toHaveCount(0)
})

test('分析頁美股（無已發行股數資料）不顯示換手率區塊 (Q1)', async ({ page }) => {
  await page.route('**/api/v1/analysis/AAPL/turnover', async (route) => {
    await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: '換手率僅支援台股' }) })
  })
  await page.goto('/stocks/AAPL')
  await expect(page.locator('.turnover-section')).toHaveCount(0, { timeout: 30_000 })
})

test('分析頁顯示千張大戶持股趨勢，三重訊號同向時給聯合判讀 (Q2/Q4)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/chip-summary*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', data_date: '20260713',
          mega_pct: 85.5, whale_pct: 88.0, retail_pct: 5.2,
          recent_weeks: [
            { date: '20260706', mega_pct: 84.8, mega_pct_change: 0.2 },
            { date: '20260713', mega_pct: 85.5, mega_pct_change: 0.7 },
          ],
          verdict: '籌碼集中', verdict_description: '大戶持股穩固，籌碼面偏多',
          history_weeks: 3,
        },
      }),
    })
  })
  // 換手率也放大，且股價當日上漲（用固定價格資料讓漲跌方向確定）→ 應觸發三重訊號聯合判讀
  await page.route('**/api/v1/analysis/2330/turnover', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { symbol: '2330', turnover_pct: 0.9, percentile: 88, sample_days: 60, cap_tier: '大型/中型', series: [], as_of: '2026-07-15', shares_as_of: '2026-07-01', source: 'finmind' },
      }),
    })
  })
  await page.route('**/api/v1/stocks/2330/price*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', period: '1d',
          items: [
            { date: '2026-07-14', open: 900, high: 905, low: 895, close: 900, volume: 1000 },
            { date: '2026-07-15', open: 905, high: 915, low: 900, close: 910, volume: 1000 },
          ],
          source: 'finmind', as_of: '2026-07-15',
        },
      }),
    })
  })

  await page.goto('/stocks/2330')
  const trend = page.locator('.whale-trend')
  await expect(trend).toBeVisible({ timeout: 60_000 })
  await expect(trend).toContainText('85.5%')
  await expect(trend).toContainText('+0.7% 週變化')
  await expect(trend).toContainText('大戶持股穩固，籌碼面偏多')
  await expect(page.locator('.whale-trend-link')).toHaveAttribute('href', '/stocks/2330/chip')
  // R4：聯合判讀要標明大戶持股是每週快照，跟今日換手率不是同一天的資料
  await expect(page.locator('.whale-trend-cross')).toContainText('主力進貨訊號較強')
  await expect(page.locator('.whale-trend-cross')).toContainText('每週快照')
})

test('分析頁千張大戶歷史不足一週比較時不顯示趨勢區塊 (Q2)', async ({ page }) => {
  await page.route('**/api/v1/stocks/2330/chip-summary*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          symbol: '2330', data_date: '20260713', mega_pct: 85.5, whale_pct: 88.0, retail_pct: 5.2,
          recent_weeks: [], verdict: '中性', verdict_description: '籌碼結構中性，無明顯方向', history_weeks: 1,
        },
      }),
    })
  })
  await page.goto('/stocks/2330')
  await expect(page.locator('.card.detail-card').filter({ hasText: '籌碼面重點' })).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.whale-trend')).toHaveCount(0)
})
