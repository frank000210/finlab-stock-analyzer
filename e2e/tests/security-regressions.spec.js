// @ts-check
const { test, expect } = require('@playwright/test')

// JJ2：II 系列修過的兩個最嚴重問題（main.py 的 SPA fallback 路徑遍歷、
// TradingViewChart.vue 的 DOM XSS）當時都只有手動/現場驗證過，沒有留下
// 自動化回歸測試——之後如果 serve_spa() 或 SAFE_SYMBOL 被不小心改壞，
// 不會有任何測試失敗來擋。這裡補上鎖定兩個修復行為的測試。

test('II1 回歸：main.py 的 SPA fallback 路由擋下路徑遍歷', async ({ request }) => {
  // 用 %2e%2e%2f（URL 編碼的 ../）而不是字面上的 ../——一般 HTTP 客戶端
  // （包含瀏覽器的 fetch）會在送出前先把字面上的 ../ 相對路徑解析掉，
  // 編碼過的版本能原封不動送到伺服器，由 Starlette 的路由層解碼後才
  // 交給 serve_spa()，這樣才是真的在測後端的防護，不是被客戶端提前擋掉。
  const resp = await request.get('/%2e%2e%2f%2e%2e%2fbackend/app/config/settings.py')
  expect(resp.status()).toBe(200)
  const body = await resp.text()
  // 修復前：會原樣讀出後端原始碼（含 admin_secret 等欄位定義）。
  // 修復後：一律落回 index.html。
  expect(body).toContain('<!DOCTYPE html>')
  expect(body).not.toContain('admin_secret')
  expect(body).not.toContain('class Settings')
})

test('II1 回歸：一般 SPA 路由與真實靜態資源不受影響', async ({ request }) => {
  const spaRoute = await request.get('/stocks/2330')
  expect(spaRoute.status()).toBe(200)
  expect(await spaRoute.text()).toContain('<!DOCTYPE html>')

  const staticAsset = await request.get('/favicon.ico')
  expect(staticAsset.status()).toBe(200)
})

test('II2 回歸：合法代號在 TradingView 模式下正常顯示 widget', async ({ page }) => {
  await page.goto('/stocks/2330')
  await page.getByRole('button', { name: 'TradingView' }).click()
  await expect(page.locator('.tv-widget')).toHaveCount(1)
  await expect(page.locator('.tv-fallback')).toHaveCount(0)
})

test('II2 回歸：惡意代號透過真實路由送進元件時被白名單擋下，不會執行', async ({ page }) => {
  // 記住 TradingView 模式偏好，讓惡意代號直接命中會呼叫
  // script.innerHTML 的那條渲染路徑，而不是停在內建圖表模式。
  await page.addInitScript(() => localStorage.setItem('finlab_chart_mode', 'tradingview'))
  const payload = '</script><img src=x onerror="window.__xss_executed=true">'
  await page.goto(`/stocks/${encodeURIComponent(payload)}`)

  // 修復前：SAFE_SYMBOL 不存在，這個代號會被塞進 script.innerHTML 組出
  // 的 JSON，注入的 markup 會被當成真實 DOM 插入並執行 onerror。
  // 修復後：白名單擋下，widget 不渲染、改顯示失敗狀態。
  await expect(page.locator('.tv-fallback')).toBeVisible()
  await expect(page.locator('.tv-widget')).toHaveCount(0)
  const xssExecuted = await page.evaluate(() => window.__xss_executed === true)
  expect(xssExecuted).toBe(false)
})
