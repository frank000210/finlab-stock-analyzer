// @ts-check
const { test, expect } = require('@playwright/test')

test('新手上路 guide renders the full flow with deep links', async ({ page }) => {
  await page.goto('/guide')
  await expect(page.getByRole('heading', { name: /新手上路/ })).toBeVisible()
  await expect(page.locator('.steps .step')).toHaveCount(8)
  await expect(page.locator('.step-go').first()).toBeVisible()
  await expect(page.locator('.flow-strip')).toContainText('複盤')
})

test('first-visit onboarding banner shows on home and dismisses', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => localStorage.removeItem('finlab_onboarded'))
  await page.reload()

  await expect(page.locator('.onboard-banner')).toBeVisible()
  await page.locator('.onboard-banner .ob-x').click()
  await expect(page.locator('.onboard-banner')).toBeHidden()

  const flag = await page.evaluate(() => localStorage.getItem('finlab_onboarded'))
  expect(flag).toBe('1')
})
