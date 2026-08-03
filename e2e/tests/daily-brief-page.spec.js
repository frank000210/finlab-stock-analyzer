// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// E14: dedicated frontend page for the C9 daily brief, so you can read it on
// the web instead of only via Telegram push.
test('盤後日報頁：顯示日報內容並可手動推播', async ({ page }) => {
  test.setTimeout(120_000)

  // LL2：/daily-brief、/daily-brief/send 補上跟其他 LLM 端點一致的
  // check_llm_rate_limit 後，這裡走瀏覽器真實網路請求，來源 IP 沒有特別
  // 指定的話，會跟同一輪套件裡其他真的打到後端的 LLM 呼叫共用同一個「真實
  // IP」的 6 次/10 分鐘額度。比照 daily-brief.spec.js 的作法插入測試 IP。
  const testIp = `203.0.113.${Math.floor(Math.random() * 250) + 1}`
  await page.route('**/api/v1/risk/daily-brief**', async (route) => {
    await route.continue({ headers: { ...route.request().headers(), 'x-forwarded-for': testIp } })
  })

  const token = await getAdminToken(page.request)
  await page.addInitScript(({ adminToken }) => {
    localStorage.setItem('admin_token', adminToken)
    localStorage.setItem('admin_user', JSON.stringify({ is_admin: true, email: 'test@admin', name: 'Test', avatar: '' }))
  }, { adminToken: token })

  await page.request.post('/api/v1/risk/sync-watchlist', {
    data: { symbols: ['2330'] },
    headers: { 'X-Admin-Token': token },
  })

  await page.goto('/daily-brief')
  await expect(page.getByRole('heading', { name: '盤後日報' })).toBeVisible()

  const briefText = page.locator('.brief-text')
  await expect(briefText).toContainText('盤後日報', { timeout: 90_000 })
  await expect(briefText).toContainText('2330')
  await expect(briefText).toContainText('非投資建議')

  await page.getByRole('button', { name: '推播到 Telegram' }).click()
  await expect(page.locator('.small')).toContainText(/已推播|未推播/, { timeout: 30_000 })
})
