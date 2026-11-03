// @ts-check
const { test, expect } = require('@playwright/test')

// 建站教學（/build-guide）：給非 IT 人員看的「申請 GitHub → 申請主機 → 上線」說明。
// 純前端靜態頁、不需登入；進度勾選只存 localStorage。

const DONE_KEY = 'finlab.buildGuide.done'

test.beforeEach(async ({ page }) => {
  // 預設不顯示首頁導覽橫幅，也不帶任何登入資訊（驗證「不用登入即可看」）
  await page.addInitScript(() => { try { localStorage.setItem('finlab_onboarded', '1') } catch {} })
})

test('不用登入即可看：標題、30 秒摘要、八個章節與各區塊都在', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', e => pageErrors.push(e.message))

  await page.goto('/build-guide')
  await expect(page).toHaveURL(/\/build-guide$/)
  await expect(page.getByRole('heading', { level: 1, name: /做出一個自己的網站/ })).toBeVisible()
  await expect(page.getByTestId('quick-summary')).toContainText('你負責')
  await expect(page.getByTestId('toc-link')).toHaveCount(8)
  await expect(page.getByTestId('flow-step')).toHaveCount(6)
  await expect(page.getByTestId('glossary-card')).toHaveCount(8)
  await expect(page.locator('#github').getByTestId('guide-step')).toHaveCount(5)
  await expect(page.locator('#hosting').getByTestId('guide-step')).toHaveCount(6)
  await expect(page.getByTestId('route-table')).toContainText('託管平台')
  await expect(page.getByTestId('role-human')).toContainText('開帳號')
  await expect(page.getByTestId('role-ai')).toContainText('寫程式')
  await expect(page.getByTestId('gate')).toHaveCount(3)
  await expect(page.getByTestId('cycle-step')).toHaveCount(7)
  await expect(page.getByTestId('after-card')).toHaveCount(6)
  await expect(page.getByTestId('checklist-item')).toHaveCount(8)
  await expect(page.getByTestId('faq-item')).toHaveCount(6)
  expect(pageErrors).toEqual([])
})

test('側邊欄「建站教學」在目錄最下方，點了會進到本頁', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/')
  const items = page.locator('.app-sidebar .nav-item')
  await expect(items.last()).toContainText('建站教學')
  await items.last().scrollIntoViewIfNeeded()
  await items.last().click()
  await expect(page).toHaveURL(/\/build-guide$/)
  await expect(page.getByTestId('guide-hero')).toBeVisible()
})

test('Ctrl+K 快速切換搜得到「建站教學」並可直接前往', async ({ page }) => {
  await page.goto('/overview')
  await page.keyboard.press('Control+k')
  await page.locator('.qs-input').fill('建站')
  await expect(page.locator('.qs-item', { hasText: '建站教學' })).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/build-guide$/)
})

// 等捲動停下來（點目錄是平滑捲動，toBeInViewport 一碰到就算過，動畫其實還在跑）
async function scrollSettled(page) {
  await expect.poll(async () => {
    const a = await page.evaluate(() => window.scrollY)
    await page.waitForTimeout(120)
    return a === await page.evaluate(() => window.scrollY)
  }).toBe(true)
}

test('章節目錄：點擊會捲到該章並標示目前章節', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 900 })
  await page.goto('/build-guide')
  await expect(page.getByTestId('toc')).toBeVisible()

  const hosting = page.getByTestId('toc').locator('a[href="#hosting"]')
  await hosting.click()
  await expect(page.locator('#hosting-h')).toBeInViewport()
  await expect(hosting).toHaveAttribute('aria-current', 'true')
  await expect(page).toHaveURL(/#hosting$/)
})

test('網址帶 #章節 會直達；同一頁改網址的 # 與瀏覽器上一頁也會捲過去', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 900 })
  await page.goto('/build-guide#roles')
  await expect(page.locator('#roles-h')).toBeInViewport()
  await scrollSettled(page)

  // 同一份文件內只改 #（手動改網址、書籤）
  await page.evaluate(() => { location.hash = '#after' })
  await expect(page.locator('#after-h')).toBeInViewport()
  await scrollSettled(page)

  // 點目錄捲走後再改回去，不會被舊的平滑捲動拉回原處
  await page.getByTestId('toc').locator('a[href="#hosting"]').click()
  await expect(page.locator('#hosting-h')).toBeInViewport()
  await page.evaluate(() => { location.hash = '#roles' })
  await expect(page.locator('#roles-h')).toBeInViewport()
  await scrollSettled(page)
  await expect(page.locator('#roles-h')).toBeInViewport()
})

test('完成進度：勾選後重新整理仍在，可清除；不會因未知代號壞掉', async ({ page }) => {
  await page.goto('/build-guide')
  const progress = page.getByTestId('overall-progress')
  await expect(progress).toContainText('0 / 19')

  await page.getByTestId('check-g-prepare').check()
  await page.getByTestId('check-h-account').check()
  await page.getByTestId('check-c-2fa').check()
  await expect(progress).toContainText('3 / 19')
  await expect(page.getByTestId('toc').locator('a[href="#github"]')).toContainText('1/5')

  await page.reload()
  await expect(page.getByTestId('check-g-prepare')).toBeChecked()
  await expect(page.getByTestId('overall-progress')).toContainText('3 / 19')

  await page.getByTestId('reset-progress').click()
  await expect(page.getByTestId('overall-progress')).toContainText('0 / 19')
  await expect(page.getByTestId('check-g-prepare')).not.toBeChecked()

  // 舊版或被改壞的資料：未知代號直接忽略、非陣列整個忽略
  await page.evaluate((k) => localStorage.setItem(k, JSON.stringify(['g-signup', 'no-such-step'])), DONE_KEY)
  await page.reload()
  await expect(page.getByTestId('overall-progress')).toContainText('1 / 19')
  await page.evaluate((k) => localStorage.setItem(k, '{"oops":1}'), DONE_KEY)
  await page.reload()
  await expect(page.getByTestId('overall-progress')).toContainText('0 / 19')
})

test('外部連結都用新分頁並帶 noopener；資料來源列出查證日期', async ({ page }) => {
  await page.goto('/build-guide')
  const signup = page.locator('#g-signup a[href="https://github.com/signup"]')
  await expect(signup).toHaveAttribute('target', '_blank')
  await expect(signup).toHaveAttribute('rel', /noopener/)

  const sources = page.getByTestId('sources')
  await expect(sources).toContainText('查證日期 2026-11-02')
  const hrefs = await sources.locator('a').evaluateAll(els => els.map(a => a.getAttribute('href')))
  expect(hrefs.length).toBeGreaterThanOrEqual(6)
  for (const h of hrefs) expect(h).toMatch(/^https:\/\//)
})

test('常見問題可展開；頁面不含機密或主機 IP', async ({ page }) => {
  await page.goto('/build-guide')
  const first = page.getByTestId('faq-item').first()
  await expect(first).not.toHaveAttribute('open', '')
  await first.locator('summary').click()
  await expect(first).toHaveAttribute('open', '')

  // 公開頁面不放金鑰、token、私鑰與正式主機的真實 IP
  const text = await page.locator('.bg-view').innerText()
  expect(text).not.toMatch(/43\.133\.44\.216|43-133-44-216/)
  expect(text).not.toMatch(/ghp_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY/)
})

test('手機：不橫向捲動，章節收成按鈕，點章節後收起並捲到該章', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/build-guide')
  await expect(page.getByTestId('guide-hero')).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)

  const toggle = page.getByRole('button', { name: /章節與進度/ })
  const links = page.getByTestId('toc').locator('a[href="#cycle"]')
  await expect(links).toBeHidden()
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await links.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('#cycle-h')).toBeInViewport()

  // 比較表放在自己的捲動容器裡，不撐寬整頁
  const wrapScrolls = await page.getByTestId('route-table').evaluate(el => el.scrollWidth > el.clientWidth)
  expect(wrapScrolls).toBe(true)
  await expect(page.locator('.table-hint')).toBeVisible()
})

// 示意圖（FigureLabs 產生）：各章要有對應的圖，且圖要有替代文字、圖說、確實載入
const FIGURES = {
  overview: 'overview',
  words: 'words',
  hosting: 'hosting',
  cycle: 'cycle',
}

test('示意圖：各章都有對應的圖，有替代文字與「示意圖」圖說，滑到畫面內後確實載入', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/build-guide')
  await expect(page.getByTestId('guide-figure')).toHaveCount(Object.keys(FIGURES).length)

  for (const [chapter, id] of Object.entries(FIGURES)) {
    const fig = page.locator(`#${chapter} [data-testid="guide-figure"][data-fig="${id}"]`)
    await fig.scrollIntoViewIfNeeded()
    const img = fig.locator('.gfig-frame img')
    // 替代文字要寫成一段完整說明，不是檔名或「圖片」
    await expect(img).toHaveAttribute('alt', /.{30,}/)
    await expect(fig.locator('figcaption')).toContainText('示意圖')
    await expect.poll(() => img.evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true)
  }
})

test('點圖放大：開啟對話框、Esc 關閉；手機版也能開關', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/build-guide')
  const fig = page.locator('#overview [data-testid="guide-figure"]')
  const dialog = fig.getByTestId('guide-figure-dialog')
  await fig.scrollIntoViewIfNeeded()
  await expect(dialog).toBeHidden()

  await fig.locator('.gfig-frame').click()
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('img')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()

  await page.setViewportSize({ width: 390, height: 844 })
  await fig.locator('.gfig-frame').click()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: /關閉放大圖片/ }).click()
  await expect(dialog).toBeHidden()
})

test('示意圖檔案大小：每張不超過 300KB（手機與慢網路也載得動）', async ({ page }) => {
  await page.goto('/build-guide')
  const srcs = await page.locator('.gfig-frame img').evaluateAll(els => els.map(e => e.getAttribute('src')))
  expect(srcs.length).toBeGreaterThanOrEqual(Object.keys(FIGURES).length)
  for (const src of srcs) {
    // 很小的圖會被打包工具直接內嵌成 data: 網址，這時量字串長度即可
    if (src.startsWith('data:')) { expect(src.length, 'inline image').toBeLessThan(300 * 1024); continue }
    const res = await page.request.get(new URL(src, page.url()).toString())
    expect(res.ok(), src).toBe(true)
    expect((await res.body()).length, src).toBeLessThan(300 * 1024)
  }
})

test('列印：隱藏側邊欄與章節，並自動展開常見問題', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/build-guide')
  // 路由元件是 load 之後才載入；先等頁面掛好（beforeprint 監聽在掛載時才註冊），
  // 否則在較慢的環境（正式站）事件會比監聽先發出，永遠數到 0 個展開
  await expect(page.getByTestId('guide-hero')).toBeVisible()
  await expect(page.getByTestId('toc')).toBeVisible()
  await page.emulateMedia({ media: 'print' })
  await expect(page.locator('.app-sidebar')).toBeHidden()
  await expect(page.getByTestId('toc')).toBeHidden()

  await page.emulateMedia({ media: 'screen' })
  await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')))
  await expect(page.locator('.faq-item[open]')).toHaveCount(6)
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
  await expect(page.locator('.faq-item[open]')).toHaveCount(0)
})
