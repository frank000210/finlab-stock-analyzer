// @ts-check
const { test, expect } = require('@playwright/test')

// E18: installable PWA + offline app shell.
test('PWA manifest 與 service worker 正確設定並成功註冊', async ({ page, request }) => {
  const manifestResp = await request.get('/manifest.webmanifest')
  expect(manifestResp.ok()).toBeTruthy()
  const manifest = await manifestResp.json()
  expect(manifest.name).toBe('FinLab Stock Analyzer')
  expect(manifest.display).toBe('standalone')
  expect(manifest.icons.length).toBeGreaterThanOrEqual(2)

  const swResp = await request.get('/sw.js')
  expect(swResp.ok()).toBeTruthy()

  const faviconResp = await request.get('/favicon.ico')
  expect(faviconResp.ok()).toBeTruthy()

  await page.goto('/')
  const manifestHref = await page.locator('link[rel="manifest"]').getAttribute('href')
  expect(manifestHref).toBe('/manifest.webmanifest')

  const swState = await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) return 'unsupported'
    const reg = await navigator.serviceWorker.ready
    for (let i = 0; i < 20; i++) {
      if (reg.active && reg.active.state === 'activated') return 'activated'
      await new Promise((r) => setTimeout(r, 250))
    }
    return reg.active ? reg.active.state : 'no-active'
  })
  expect(swState).toBe('activated')
})

test('離線時已造訪過的殼層頁面仍可載入', async ({ page, context }) => {
  test.setTimeout(60_000)

  // First load: SW registers + installs + precaches the shell.
  await page.goto('/')
  await page.waitForFunction(() => navigator.serviceWorker.ready.then(() => true), { timeout: 15_000 })

  // Reload while under SW control so the hashed JS/CSS bundle gets
  // opportunistically cached into the runtime cache (cache-first strategy).
  await page.reload()
  await page.waitForLoadState('networkidle')

  await context.setOffline(true)
  try {
    await page.reload()
    // The app shell should still boot from cache — the sidebar brand mark
    // is real app content, not a browser offline-error page.
    await expect(page.getByText('FinLab', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
  } finally {
    await context.setOffline(false)
  }
})
