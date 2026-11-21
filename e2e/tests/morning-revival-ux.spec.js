// @ts-check
const { test, expect } = require('@playwright/test')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')

const PORTAL_ROOT = path.resolve(__dirname, '../../deploy/portal')
const BASE_HOST = 'example.test'
const THEMES = ['notebook', 'dark', 'solarized', 'nord', 'dracula', 'gruvbox']
const MOBILE_VIEWPORT = { width: 390, height: 844 }

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
}

const MOCK_VERSES = Array.from({ length: 60 }, (_, idx) => ({
  segment_code: idx + 1,
  content: `測試經文第 ${idx + 1} 節內容。`,
}))

function createPortalServer() {
  return http.createServer((req, res) => {
    try {
      const reqUrl = new URL(req.url || '/', 'http://127.0.0.1')
      const relPath = decodeURIComponent(reqUrl.pathname).replace(/^\/+/, '')
      let filePath = path.resolve(PORTAL_ROOT, relPath)
      const relCheck = path.relative(PORTAL_ROOT, filePath)
      if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) {
        res.writeHead(403)
        res.end('Forbidden')
        return
      }
      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        filePath = path.join(filePath, 'index.html')
      }
      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404)
        res.end('Not Found')
        return
      }
      const ext = path.extname(filePath).toLowerCase()
      const contentType = MIME_TYPES[ext] || 'application/octet-stream'
      if (ext === '.html') {
        const html = fs.readFileSync(filePath, 'utf8').replaceAll('{{env "BASE_HOST"}}', BASE_HOST)
        res.writeHead(200, { 'Content-Type': contentType, 'Cache-Control': 'no-store' })
        res.end(html)
        return
      }
      res.writeHead(200, { 'Content-Type': contentType, 'Cache-Control': 'no-store' })
      res.end(fs.readFileSync(filePath))
    } catch (err) {
      res.writeHead(500)
      res.end(String(err))
    }
  })
}

async function setupRoutes(page, verseHandler) {
  await page.route(/^https?:\/\/(?!127\.0\.0\.1(?::\d+)?\/|localhost(?::\d+)?\/).*/, (route) =>
    route.abort(),
  )
  await page.route('https://www.recoveryversion.com.tw/api/getVerses**', (route) => {
    if (verseHandler) return verseHandler(route)
    return route.fulfill({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify(MOCK_VERSES),
    })
  })
}

async function waitRevivalReady(page) {
  await expect(page.locator('#menu a[data-id]').first()).toBeAttached()
  await expect(page.locator('#content h2.week-title')).toBeVisible()
}

test.describe('晨興聖言 UI/UX 增強驗證（T-023）', () => {
  /** @type {http.Server} */
  let server
  let baseUrl = ''
  /** @type {{ latest: string, trainings: Array<{ weeks: Array<{ id: string, no: string, title: string }> }> }} */
  let weeksJson
  /** @type {Array<{ id: string, no: string, title: string }>} */
  let allWeeks

  test.beforeAll(async () => {
    weeksJson = JSON.parse(
      fs.readFileSync(path.join(PORTAL_ROOT, 'morning-revival', 'weeks.json'), 'utf8'),
    )
    allWeeks = weeksJson.trainings.flatMap((t) => t.weeks)
    server = createPortalServer()
    await new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(0, '127.0.0.1', resolve)
    })
    const addr = server.address()
    if (!addr || typeof addr === 'string') throw new Error('無法取得測試伺服器連接埠')
    baseUrl = `http://127.0.0.1:${addr.port}`
  })

  test.afterAll(async () => {
    if (!server) return
    await new Promise((resolve) => server.close(resolve))
  })

  test('無效 Hash 安全回退 data.latest（不誤跳 mt15），並支援週次+章節與純章節錨點', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupRoutes(page)

    // 1. 無效週次 Hash -> 安全回退到 data.latest
    await page.goto(`${baseUrl}/morning-revival/#nonexistent-week-999`)
    await waitRevivalReady(page)
    await expect(page.locator(`#menu a[data-id="${weeksJson.latest}"]`)).toHaveAttribute('aria-current', 'page')
    await expect(page.locator('#menu a[data-id="mt15"]')).not.toHaveAttribute('aria-current', 'page')

    // 2. 點擊黏性工具列的「生活應用」-> 更新 Hash 為 #<weekId>/apply 並標記作用中
    const applyJump = page.locator('.mr-toolbar .jump a[data-section="apply"]')
    await expect(applyJump).toBeVisible()
    await applyJump.click()
    await expect(page).toHaveURL(new RegExp(`#${weeksJson.latest}/apply$`))
    await expect(applyJump).toHaveClass(/is-active/)

    // 3. 週次＋章節格式 #2026-09-w04/apply 直接開啟
    await page.goto(`${baseUrl}/morning-revival/#2026-09-w04/apply`)
    await waitRevivalReady(page)
    await expect(page.locator('#menu a[data-id="2026-09-w04"]')).toHaveAttribute('aria-current', 'page')
    await expect(page.locator('.mr-toolbar .jump a[data-section="apply"]')).toHaveClass(/is-active/)

    // 4. 在 2026-09-w04 上切換純章節錨點 #overview -> 保留 2026-09-w04，不重跳 latest
    await page.evaluate(() => { location.hash = '#overview' })
    await expect(page.locator('#menu a[data-id="2026-09-w04"]')).toHaveAttribute('aria-current', 'page')
    await expect(page.locator('.mr-toolbar .jump a[data-section="overview"]')).toHaveClass(/is-active/)

    expect(errors).toEqual([])
  })

  test('黏性工具列與精簡／展開經文開關可持久化至 localStorage', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupRoutes(page)

    await page.goto(`${baseUrl}/morning-revival/`)
    await waitRevivalReady(page)

    const toolbar = page.locator('.mr-toolbar')
    await expect(toolbar).toBeVisible()
    const pos = await toolbar.evaluate((el) => getComputedStyle(el).position)
    expect(pos).toBe('sticky')

    const toggleBtn = page.locator('#verseToggle')
    await expect(toggleBtn).toBeVisible()
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'false')
    await expect(page.locator('#content .verse-text').first()).toBeVisible()

    // 切換為精簡模式
    await toggleBtn.click()
    await expect(toggleBtn).toHaveAttribute('aria-pressed', 'true')
    await expect(toggleBtn).toContainText('顯示經文')
    await expect(page.locator('#content')).toHaveClass(/verses-compact/)
    await expect(page.locator('#content .verse-text').first()).toBeHidden()
    expect(await page.evaluate(() => localStorage.getItem('mr.compactVerses'))).toBe('1')

    // 重整後保持精簡模式
    await page.reload()
    await waitRevivalReady(page)
    await expect(page.locator('#content')).toHaveClass(/verses-compact/)
    await expect(page.locator('#verseToggle')).toHaveAttribute('aria-pressed', 'true')

    // 展開後載入經文全文
    await page.locator('#verseToggle').click()
    await expect(page.locator('#content')).not.toHaveClass(/verses-compact/)
    await expect(page.locator('#content .verse-text').first()).toContainText('測試經文')
    expect(await page.evaluate(() => localStorage.getItem('mr.compactVerses'))).toBe('0')

    expect(errors).toEqual([])
  })

  test('經文 API 失敗顯示重試鈕，單獨點擊可重新抓取該節經文', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))

    let shouldFail = true
    await setupRoutes(page, (route) => {
      if (shouldFail) {
        return route.fulfill({ status: 500, body: 'upstream error' })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify(MOCK_VERSES),
      })
    })

    await page.goto(`${baseUrl}/morning-revival/`)
    await waitRevivalReady(page)

    const firstVerseItem = page.locator('#content ul.verses li[data-ref]').first()
    const retryBtn = firstVerseItem.locator('.verse-retry')
    await expect(retryBtn).toBeVisible()
    await expect(retryBtn).toContainText('重試')

    // 恢復 API 並僅點擊該條目重試鈕
    shouldFail = false
    await retryBtn.click()
    await expect(firstVerseItem.locator('.verse-text')).toContainText('測試經文')
    await expect(firstVerseItem.locator('.verse-retry')).toHaveCount(0)

    expect(errors).toEqual([])
  })

  test('文末上一週／下一週／回頂部導覽與 6 主題、手機版無水平溢位', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupRoutes(page)

    await page.goto(`${baseUrl}/morning-revival/`)
    await waitRevivalReady(page)

    const latestIdx = allWeeks.findIndex((w) => w.id === weeksJson.latest)
    expect(latestIdx).toBeGreaterThan(0)
    const expectedPrev = allWeeks[latestIdx - 1]

    const prevLink = page.locator('.week-nav a.prev')
    await expect(prevLink).toBeVisible()
    await expect(prevLink).toHaveAttribute('href', `#${expectedPrev.id}`)

    // 捲動到底部並點擊回頂部
    await page.locator('.week-nav .top').scrollIntoViewIfNeeded()
    await page.locator('.week-nav .top').click()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThanOrEqual(5)

    // 點擊上一週切換
    await prevLink.click()
    await expect(page.locator(`#menu a[data-id="${expectedPrev.id}"]`)).toHaveAttribute('aria-current', 'page')

    // 第一篇（mt15）的上一週應為停用狀態
    await page.goto(`${baseUrl}/morning-revival/#${allWeeks[0].id}`)
    await waitRevivalReady(page)
    await expect(page.locator('.week-nav .prev.is-disabled')).toHaveAttribute('aria-disabled', 'true')

    // 手機寬度 390×844 且切 6 主題皆無水平溢位與 pageerror
    await page.setViewportSize(MOBILE_VIEWPORT)
    await page.goto(`${baseUrl}/morning-revival/`)
    await waitRevivalReady(page)

    for (const themeId of THEMES) {
      await page.evaluate((t) => { document.documentElement.dataset.theme = t }, themeId)
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      expect(metrics.scrollWidth, `主題 ${themeId} 手機版溢位`).toBeLessThanOrEqual(metrics.clientWidth)
    }

    expect(errors).toEqual([])
  })
})
