// @ts-check
const { test, expect } = require('@playwright/test')

// KK10：資料爬蟲頁（DataAgentView）的「已爬取資料」來源分頁籤（ALL/TWSE/PTT/
// NEWS）先前完全沒有測試覆蓋，只有同頁的新聞可信度檢查表單被測過
// （interaction-depth.spec.js）。分頁籤切換沒有對應覆蓋——若哪天
// selectedSource 的 watch() 或 loadCrawledData() 壞掉，不會有任何測試發現。

test('資料爬蟲頁：已爬取資料來源分頁籤可切換且正常載入', async ({ page }) => {
  await page.goto('/data-agent')
  await expect(page.getByRole('heading', { name: '已爬取資料' })).toBeVisible()

  const tabs = ['ALL', 'TWSE', 'PTT', 'NEWS']
  for (const tab of tabs) {
    await page.getByRole('button', { name: tab, exact: true }).click()
    await expect(page.getByRole('button', { name: tab, exact: true })).toHaveClass(/active/)
    // 不論該來源有沒有資料，畫面只會是清單或「目前沒有爬蟲資料」，不會整頁當機。
    await expect(page.locator('.crawl-list, .empty-state').first()).toBeVisible({ timeout: 15_000 })
  }
})
