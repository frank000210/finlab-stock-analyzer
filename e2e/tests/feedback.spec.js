// @ts-check
const { test, expect } = require('@playwright/test')

test('意見回饋 lists existing feedback and submits a new one', async ({ page }) => {
  const stored = [
    {
      _id: 'f1',
      content: '希望增加台指期資料',
      category: 'feature',
      page: '總覽',
      status: 'resolved',
      response: '已於本次更新加入',
      created_at: '2026-07-01T00:00:00Z',
    },
  ]

  await page.route('**/api/v1/feedback', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: stored }) })
      return
    }
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      stored.unshift({ _id: 'f2', ...body, status: 'open', response: null, created_at: new Date().toISOString() })
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data: stored[0] }) })
      return
    }
    await route.continue()
  })

  await page.goto('/feedback')

  await expect(page.locator('.feedback-item')).toHaveCount(1)
  await expect(page.locator('.feedback-item').first()).toContainText('希望增加台指期資料')
  await expect(page.locator('.feedback-item').first()).toContainText('已於本次更新加入')
  await expect(page.locator('.status-pill').first()).toContainText('已完成')

  await page.locator('textarea.inp').fill('建議把 K 線圖預設改成週線')
  await page.getByRole('button', { name: '送出意見' }).click()

  await expect(page.locator('.success-text')).toBeVisible()
  await expect(page.locator('.feedback-item')).toHaveCount(2)
  await expect(page.locator('.feedback-item').first()).toContainText('建議把 K 線圖預設改成週線')
})
