// @ts-check
const { test, expect } = require('@playwright/test')

// App-shell hygiene: page tracking must never fire the malformed
// /pageviews// (page='/') request that polluted analytics + logged 404s.
test('page counter never tracks the pre-resolution "/" page', async ({ page }) => {
  const pageviewCalls = []
  page.on('request', (req) => {
    if (req.url().includes('/api/v1/analytics/pageview')) pageviewCalls.push(req.url())
  })

  await page.goto('/')
  // The legit tracking for the resolved route ('home') must arrive…
  await expect.poll(() => pageviewCalls.some(u => u.includes('/pageviews/home')), { timeout: 20_000 }).toBe(true)
  // …and no malformed page='/' call may ever be made.
  const bad = pageviewCalls.filter(u => u.includes('pageviews//') || u.includes('pageviews/%2F'))
  expect(bad).toEqual([])
})

// Global error net: component errors surface as a dismissable toast
// (main.js errorHandler dispatches finlab:app-error; App.vue renders it).
test('global error toast appears and dismisses', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('finlab:app-error', { detail: '測試錯誤' }))
  })

  const toast = page.locator('.error-toast')
  await expect(toast).toBeVisible()
  await expect(toast).toContainText('測試錯誤')

  await toast.locator('.et-x').click()
  await expect(toast).toBeHidden()
})
