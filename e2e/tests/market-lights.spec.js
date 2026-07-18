// @ts-check
const { test, expect } = require('@playwright/test')

// V1-V3：大盤多空三燈儀表板（規格經五輪資深投顧審查凍結）。核心行為：
// 訊號矛盾時明示「僵持」而非假中性；每燈標實證等級；B 級燈失效時降級顯示。

const TREND = {
  regime: 'offense', label: '進攻', risk_mult: 1.0, proxy: '0050',
  close: 100.15, ma200: 78.19, above_ma200: true, ma200_rising: true,
  mom20_pct: -5.52, as_of: '2026-07-17', evidence: 'A', tone: 'good',
}
const FOREIGN = {
  status: 'extreme_short', tone: 'bad', net_amount_yi: -7345.3,
  rolling_percentile: 4.8, chg5_yi: 33.9, settlement_week: false,
  narrative: '外資淨空單金額 7,345 億，比過去一年 95% 的時間都更空——屬偏空訊號；但極端空單同時是未來回補的燃料。',
  history: [{ date: '2026-07-16', value: -7718.7 }, { date: '2026-07-17', value: -7345.3 }],
  as_of: '2026-07-17', evidence: 'B', publish_note: '期交所每交易日約 15:00 後公布',
}
const MARGIN = {
  status: 'sharp_decline', tone: 'warn', balance_yi: 5879.6, d1_pct: -4.49, d20_pct: 0.7,
  narrative: '融資餘額單日 -4.49%，屬急減——去槓桿壓力進行中，等止穩。',
  history: [{ date: '2026-07-16', value: 6156 }, { date: '2026-07-17', value: 5879.6 }],
  as_of: '2026-07-17', evidence: 'B', publish_note: '交易所每交易日約 21:00 後公布',
}
const NOTE = '籌碼燈閾值為兩年分布之描述統計校準；文獻實證的是指標類別，非本組參數之回測績效保證。'

test('大盤多空 訊號矛盾時顯示僵持，三燈與實證等級齊備 (V2)', async ({ page }) => {
  await page.route('**/api/v1/market/lights', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          combined: { regime: 'stalemate', label: '僵持', confidence: 'low', narrative: '趨勢燈偏多，但外資期貨極端淨空、融資斷頭/急減進行中與其矛盾——長線結構未壞、短線籌碼激烈換手中。' },
          lights: { trend: TREND, foreign_futures: FOREIGN, margin: MARGIN },
          errors: null, calibration_note: NOTE,
        },
      }),
    })
  })

  await page.goto('/market-lights')
  const banner = page.locator('.combined-banner')
  await expect(banner).toBeVisible({ timeout: 30_000 })
  await expect(banner).toHaveClass(/regime-stalemate/)
  await expect(banner).toContainText('僵持')
  await expect(banner).toContainText('訊號矛盾中')
  await expect(banner).toContainText('長線結構未壞')

  // 三燈卡片與實證等級標籤
  await expect(page.locator('.light-card')).toHaveCount(3)
  await expect(page.locator('.evidence-badge.a')).toHaveCount(1)
  await expect(page.locator('.evidence-badge.b')).toHaveCount(2)

  // 外資燈：雙向敘事（偏空訊號＋回補燃料都要講）
  const foreign = page.locator('.light-card', { hasText: '外資期貨燈' })
  await expect(foreign).toContainText('極端淨空')
  await expect(foreign).toContainText('回補的燃料')
  await expect(foreign).toContainText('近一年百分位：4.8%')

  // 融資燈：急減狀態
  const margin = page.locator('.light-card', { hasText: '融資燈' })
  await expect(margin).toContainText('急減（去槓桿進行中）')
  await expect(margin).toContainText('-4.49%')

  // 校準誠信註記
  await expect(page.locator('.disclaimer')).toContainText('非本組參數之回測績效保證')
})

test('大盤多空 三燈同向時顯示多方與高信心 (V2)', async ({ page }) => {
  await page.route('**/api/v1/market/lights', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          combined: { regime: 'bull', label: '多方', confidence: 'high', narrative: '趨勢燈偏多，且外資期貨部位轉多同向確認。體制為狀態描述，非漲跌預測。' },
          lights: {
            trend: TREND,
            foreign_futures: { ...FOREIGN, status: 'bullish_shift', tone: 'good', rolling_percentile: 85.0, narrative: '外資淨部位升至過去一年第 85 百分位——相對自身常態明顯轉多。' },
            margin: { ...MARGIN, status: 'normal', tone: 'flat', d1_pct: 0.3, narrative: '融資餘額無異常。' },
          },
          errors: null, calibration_note: NOTE,
        },
      }),
    })
  })

  await page.goto('/market-lights')
  const banner = page.locator('.combined-banner')
  await expect(banner).toBeVisible({ timeout: 30_000 })
  await expect(banner).toHaveClass(/regime-bull/)
  await expect(banner).toContainText('多方')
  await expect(banner).toContainText('高（三燈同向）')
})

test('大盤多空 B級燈失效時降級顯示，不裝死也不假裝有資料 (V2)', async ({ page }) => {
  await page.route('**/api/v1/market/lights', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          combined: { regime: 'bull', label: '多方', confidence: 'medium', narrative: '趨勢燈偏多，籌碼燈無矛盾訊號。' },
          lights: { trend: TREND, foreign_futures: null, margin: MARGIN },
          errors: { foreign_futures: '查無台指期法人資料' }, calibration_note: NOTE,
        },
      }),
    })
  })

  await page.goto('/market-lights')
  await expect(page.locator('.combined-banner')).toBeVisible({ timeout: 30_000 })
  const failed = page.locator('.light-card.light-failed')
  await expect(failed).toHaveCount(1)
  await expect(failed).toContainText('外資期貨燈')
  await expect(failed).toContainText('資料暫時無法取得')
})
