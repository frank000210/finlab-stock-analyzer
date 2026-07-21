// @ts-check
const { test, expect } = require('@playwright/test')

// Y2：警報類型擴充（成交量異常/RSI 極端值）+ 修復設定頁假通知勾選框。
// Y3：警報觸發歷史中心。

test('價格警報頁 可新增成交量異常/RSI極端值警報，類型受設定頁通知偏好控制 (Y2)', async ({ page }) => {
  let createdBody = null
  await page.route('**/api/v1/risk/alerts', async (route) => {
    if (route.request().method() === 'POST') {
      createdBody = route.request().postDataJSON()
      await route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { id: 'a1', symbol: '2330', ...createdBody, active: true, triggered: false, last_price: null } }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/risk/alerts/history*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })

  await page.goto('/price-alerts')
  const typeSelect = page.locator('select').first()
  await expect(typeSelect).toBeVisible({ timeout: 20_000 })
  await expect(typeSelect.locator('option')).toHaveCount(3) // 預設全部通知偏好開啟：價格/成交量異常/RSI

  await page.locator('input[placeholder="代碼 2330"]').fill('2330')
  await typeSelect.selectOption('rsi_extreme')
  await page.getByRole('button', { name: '加入' }).click()

  expect(createdBody.alert_type).toBe('rsi_extreme')
  expect(createdBody.target_price).toBeNull()
})

test('設定頁 通知偏好持久化，關閉技術訊號通知後價格警報頁隱藏對應選項 (Y2 dead-checkbox fix)', async ({ page }) => {
  await page.goto('/settings')
  const signalCheckbox = page.getByRole('checkbox', { name: /技術訊號通知/ })
  await expect(signalCheckbox).toBeVisible({ timeout: 20_000 })
  await expect(signalCheckbox).toBeChecked()
  await signalCheckbox.uncheck()

  // 修正前：這個勾選框從未存到任何地方，重整就消失；修正後：寫進 localStorage
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_notification_prefs') || '{}'))
  expect(stored.signal).toBe(false)

  await page.route('**/api/v1/risk/alerts', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/risk/alerts/history*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.goto('/price-alerts')
  const typeSelect = page.locator('select').first()
  await expect(typeSelect).toBeVisible({ timeout: 20_000 })
  // 技術訊號通知關閉後，成交量異常/RSI 極端值選項應該消失，只剩「價格」
  await expect(typeSelect.locator('option')).toHaveCount(1)
  await expect(typeSelect.locator('option')).toHaveText('價格')
})

test('價格警報頁 觸發歷史中心顯示過去觸發紀錄 (Y3)', async ({ page }) => {
  await page.route('**/api/v1/risk/alerts', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: { items: [] } }) })
  })
  await page.route('**/api/v1/risk/alerts/history*', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: [
            { id: 'h1', symbol: '2330', alert_type: 'rsi_extreme', direction: 'above', price: 1050, rsi: 72.3, vol_ratio: null, note: '', triggered_at: '2026-07-20T06:15:00', date: '2026-07-20' },
            { id: 'h2', symbol: '2317', alert_type: 'volume_spike', direction: 'above', price: 210, rsi: null, vol_ratio: 2.1, note: '追蹤新聞', triggered_at: '2026-07-19T05:40:00', date: '2026-07-19' },
          ],
        },
      }),
    })
  })

  await page.goto('/price-alerts')
  const historySection = page.locator('.section-block', { hasText: '觸發歷史' })
  await expect(historySection).toBeVisible({ timeout: 20_000 })
  await expect(historySection).toContainText('2330')
  await expect(historySection).toContainText('RSI 72.3')
  await expect(historySection).toContainText('2317')
  await expect(historySection).toContainText('2.1× 均量')
  await expect(historySection).toContainText('追蹤新聞')
})
