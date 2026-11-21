// @ts-check
const { test, expect } = require('@playwright/test')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')

const PORTAL_ROOT = path.resolve(__dirname, '../../deploy/portal')
const BASE_HOST = 'example.test'
const THEME_KEY = 'finlab.colorTheme.v1'
const THEMES = ['notebook', 'dark', 'solarized', 'nord', 'dracula', 'gruvbox']
const MOBILE_VIEWPORT = { width: 390, height: 844 }

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
}

const CORE_PAGES = [
  { name: '入口頁', path: '/' },
  { name: '知識分享目錄', path: '/share/' },
  { name: '數學讀書法課程頁', path: '/share/math-study-method/' },
  { name: '晨興聖言', path: '/morning-revival/' },
]

/** 建立自給自足的暫時靜態伺服器，模擬 Caddy templates 替換 {{env "BASE_HOST"}} */
function createPortalServer() {
  return http.createServer((req, res) => {
    try {
      const reqUrl = new URL(req.url || '/', 'http://127.0.0.1')
      const relPath = decodeURIComponent(reqUrl.pathname).replace(/^\/+/, '')
      let filePath = path.resolve(PORTAL_ROOT, relPath)

      const relCheck = path.relative(PORTAL_ROOT, filePath)
      if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' })
        res.end('Forbidden')
        return
      }

      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        filePath = path.join(filePath, 'index.html')
      }

      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
        res.end('Not Found')
        return
      }

      const ext = path.extname(filePath).toLowerCase()
      const contentType = MIME_TYPES[ext] || 'application/octet-stream'

      if (ext === '.html') {
        const html = fs.readFileSync(filePath, 'utf8')
          .replaceAll('{{env "BASE_HOST"}}', BASE_HOST)
        res.writeHead(200, { 'Content-Type': contentType, 'Cache-Control': 'no-store' })
        res.end(html)
        return
      }

      const data = fs.readFileSync(filePath)
      res.writeHead(200, { 'Content-Type': contentType, 'Cache-Control': 'no-store' })
      res.end(data)
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end(String(err))
    }
  })
}

const MOCK_VERSES = Array.from({ length: 60 }, (_, idx) => ({
  segment_code: idx + 1,
  content: `測試經文第 ${idx + 1} 節內容。`,
}))

/** 攔截所有外部請求，確保煙霧測試完全離線、不依賴外網 */
async function setupOfflineRoutes(page) {
  // 兜底：阻擋所有非本機請求（Playwright route 採後註冊優先，故先註冊兜底）
  await page.route(/^https?:\/\/(?!127\.0\.0\.1(?::\d+)?\/|localhost(?::\d+)?\/).*/, (route) =>
    route.abort(),
  )

  // 數學讀書法外部 KaTeX CDN：回空 200 避免依賴外網
  await page.route('https://cdn.jsdelivr.net/**', (route) => {
    const isCss = route.request().url().endsWith('.css')
    return route.fulfill({
      status: 200,
      contentType: isCss ? 'text/css; charset=utf-8' : 'application/javascript; charset=utf-8',
      body: '',
    })
  })

  // 入口頁服務健康檢查：回 200 模擬所有跨子網域服務正常
  await page.route(`https://*.${BASE_HOST}/**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/plain; charset=utf-8',
      body: 'ok',
    }),
  )

  // 晨興聖言恢復本經文 API：回模擬 JSON，避免打外網
  await page.route('https://www.recoveryversion.com.tw/api/getVerses**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify(MOCK_VERSES),
    }),
  )
}

/** 等待各頁面主要內容渲染完成 */
async function waitPageReady(page, pagePath) {
  await expect(page.getByTestId('theme-picker-btn')).toBeVisible()
  if (pagePath === '/morning-revival/') {
    await expect(page.locator('#menu a[data-id]').first()).toBeAttached()
    await expect(page.locator('#content h2.week-title')).toBeVisible()
  }
}

test.describe('入口頁與靜態子站煙霧測試', () => {
  /** @type {http.Server} */
  let server
  let baseUrl = ''

  test.beforeAll(async () => {
    server = createPortalServer()
    await new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(0, '127.0.0.1', resolve)
    })
    const addr = server.address()
    if (!addr || typeof addr === 'string') {
      throw new Error('無法取得暫時靜態伺服器連接埠')
    }
    baseUrl = `http://127.0.0.1:${addr.port}`
  })

  test.afterAll(async () => {
    if (!server) return
    await new Promise((resolve) => server.close(resolve))
  })

  test('入口頁 /：所有服務卡片存在、不殘留模板字面、健康檢查離線通過', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupOfflineRoutes(page)

    await page.goto(`${baseUrl}/`)
    await waitPageReady(page, '/')

    // 不殘留任何 Caddy 模板雙左大括號
    const html = await page.content()
    expect(html).not.toContain('{{')

    // 驗證全部 10 張服務卡片皆存在且連結已正確替換 BASE_HOST
    const expectedCards = [
      { title: 'FinLab 選股分析', href: `https://finlab.${BASE_HOST}/` },
      { title: 'FinLab 後台', href: `https://finlab.${BASE_HOST}/admin` },
      { title: '學習中心', href: `https://finlab.${BASE_HOST}/learn` },
      { title: '建站教學', href: `https://finlab.${BASE_HOST}/build-guide` },
      { title: '知識分享', href: '/share/' },
      { title: '晨興聖言', href: '/morning-revival/' },
      { title: '知識庫 kb-web', href: `https://kb.${BASE_HOST}/` },
      { title: 'Agent 工作儀表板', href: `https://dashboard.${BASE_HOST}/` },
      { title: '訂餐前台', href: `https://food.${BASE_HOST}/` },
      { title: '訂餐後台', href: `https://food-admin.${BASE_HOST}/admin/` },
    ]

    const cards = page.locator('a.card')
    await expect(cards).toHaveCount(expectedCards.length)

    for (const item of expectedCards) {
      const card = page.locator(`a.card[href="${item.href}"]`)
      await expect(card).toBeVisible()
      await expect(card).toContainText(item.title)
    }

    // 健康檢查攔截回 200 後，全部狀態點變正常、移除 aria-hidden 盲點、提供無障礙文字
    await expect(page.locator('a.card .dot[aria-hidden="true"]')).toHaveCount(0)
    await expect(page.locator('a.card .dot.ok')).toHaveCount(expectedCards.length)
    await expect(page.locator('a.card .dot .sr-only')).toHaveCount(expectedCards.length)
    await expect(page.locator('a.card .dot .sr-only').first()).toHaveText('運作正常')
    await expect(page.locator('a.card .status-badge:visible')).toHaveCount(0)
    await expect(page.locator('#up-count')).toHaveText(`${expectedCards.length} / ${expectedCards.length}`)
    await expect(page.locator('#up-label')).toHaveText('全部服務正常')

    // 模擬單一服務異常，點擊便利貼「↻ 重測」驗證三重編碼（菱形＋紅字標籤＋無障礙文字）
    const retestBtn = page.locator('#retest-btn')
    await expect(retestBtn).toBeVisible()
    await expect(retestBtn).toContainText('重測')

    let failFood = true
    await page.route(`https://food.${BASE_HOST}/**`, (route) => {
      if (failFood) return route.abort()
      return route.fulfill({ status: 200, contentType: 'text/plain; charset=utf-8', body: 'ok' })
    })

    await retestBtn.click()
    const foodCard = page.locator(`a.card[href="https://food.${BASE_HOST}/"]`)
    await expect(foodCard.locator('.dot.down')).toBeVisible()
    await expect(foodCard.locator('.dot .sr-only')).toHaveText('暫時連不上')
    await expect(foodCard.locator('.status-badge')).toBeVisible()
    await expect(foodCard.locator('.status-badge')).toHaveText('連不上')
    await expect(page.locator('#up-count')).toHaveText(`${expectedCards.length - 1} / ${expectedCards.length}`)
    await expect(page.locator('#up-label')).toHaveText('1 個服務連不上')

    const downShape = await foodCard.locator('.dot.down').evaluate((el) => {
      const cs = getComputedStyle(el)
      return { transform: cs.transform, borderRadius: cs.borderRadius }
    })
    expect(downShape.transform).not.toBe('none')
    expect(downShape.borderRadius).not.toBe('50%')

    // 恢復正常後再次重測，所有燈號與摘要應恢復全部正常
    failFood = false
    await retestBtn.click()
    await expect(page.locator('a.card .dot.ok')).toHaveCount(expectedCards.length)
    await expect(page.locator('a.card .status-badge:visible')).toHaveCount(0)
    await expect(page.locator('#up-count')).toHaveText(`${expectedCards.length} / ${expectedCards.length}`)
    await expect(page.locator('#up-label')).toHaveText('全部服務正常')

    expect(errors).toEqual([])
  })

  test('知識分享目錄 /share/：目錄卡片與返回入口連結正常渲染，多行標題不壓住摘要', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupOfflineRoutes(page)

    await page.goto(`${baseUrl}/share/`)
    await waitPageReady(page, '/share/')

    expect(await page.content()).not.toContain('{{')
    await expect(page.locator('h1')).toHaveText('知識分享')
    await expect(page.locator('nav.crumbs a[href="/"]')).toBeVisible()

    const courseCard = page.locator('a.card[href="/share/math-study-method/"]')
    await expect(courseCard).toBeVisible()
    await expect(courseCard).toContainText('讀書方法分享 — 高等數學')

    // 模擬窄螢幕下 3 行長標題，驗證標題底部絕對不重疊下方摘要頂部
    await page.setViewportSize(MOBILE_VIEWPORT)
    const overlapCheck = await page.evaluate(() => {
      const title = document.querySelector('.card .title')
      const desc = document.querySelector('.card .desc')
      if (!title || !desc) return null
      title.textContent = '超長課程標題測試：微積分、高等微積分、線性代數與實數完備性系統化讀書與筆記整理方法完整示範'
      const tRect = title.getBoundingClientRect()
      const dRect = desc.getBoundingClientRect()
      return {
        titleHeight: tRect.height,
        titleBottom: tRect.bottom,
        descTop: dRect.top,
      }
    })
    expect(overlapCheck).not.toBeNull()
    expect(overlapCheck.titleHeight).toBeGreaterThan(50)
    expect(overlapCheck.titleBottom).toBeLessThanOrEqual(overlapCheck.descTop)

    expect(errors).toEqual([])
  })

  test('數學讀書法課程頁 /share/math-study-method/：目錄、便利貼、條目、浮動閱讀列與心智圖滑動提示', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupOfflineRoutes(page)

    await page.goto(`${baseUrl}/share/math-study-method/`)
    await waitPageReady(page, '/share/math-study-method/')

    expect(await page.content()).not.toContain('{{')
    await expect(page.locator('h1')).toHaveText('讀書方法分享 — 高等數學')
    await expect(page.locator('aside.sticky')).toBeVisible()
    await expect(page.locator('nav.toc a')).toHaveCount(6)
    expect(await page.locator('article.item').count()).toBeGreaterThanOrEqual(10)
    expect(await page.locator('.mapwrap svg').count()).toBeGreaterThanOrEqual(2)

    // 浮動閱讀列：預設顯示「目錄」「回頂部」，隱藏「回上一處」
    const tocBtn = page.locator('#read-toc-btn')
    const topBtn = page.locator('#read-top')
    const backBtn = page.locator('#read-back')
    const tocPanel = page.locator('#read-toc')
    await expect(tocBtn).toBeVisible()
    await expect(topBtn).toBeVisible()
    await expect(backBtn).toBeHidden()
    await expect(tocPanel).toBeHidden()

    // 點擊目錄開啟抽屜，驗證自動收集 6 個章節並可跳轉
    await tocBtn.click()
    await expect(tocPanel).toBeVisible()
    await expect(tocBtn).toHaveAttribute('aria-expanded', 'true')
    await expect(page.locator('#read-toc-list a')).toHaveCount(6)
    await page.locator('#read-toc-list a[href="#practice"]').click()
    await expect(tocPanel).toBeHidden()
    await expect(backBtn).toBeVisible()

    // 模擬閱讀條目 T4 時點擊前置晶片 T3，驗證「↩ 回上一處」捲回原閱讀位置並自動收起
    await page.locator('#a-t4').scrollIntoViewIfNeeded()
    await page.waitForTimeout(150)
    const beforeChipY = await page.evaluate(() => window.scrollY)
    expect(beforeChipY).toBeGreaterThan(200)

    await page.locator('#a-t4 a.chip[href="#a-t3"]').click()
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    await expect(backBtn).toBeHidden()
    await expect.poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - beforeChipY)).toBeLessThan(80)

    // 從心智圖 SVG 節點跳轉去看前置定義，也應浮現「↩ 回上一處」並可返回
    const firstMapNode = page.locator('svg.map a[href="#a-d1"]').first()
    await firstMapNode.scrollIntoViewIfNeeded()
    await page.waitForTimeout(150)
    const beforeMapY = await page.evaluate(() => window.scrollY)
    await firstMapNode.click()
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    await expect(backBtn).toBeHidden()
    await expect.poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - beforeMapY)).toBeLessThan(80)

    // 點擊「↑ 回頂部」應回到頁面最上方
    await topBtn.click()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(20)

    // 手機寬度下驗證心智圖容器顯示水平滑動提示，滑動後淡出
    await page.setViewportSize(MOBILE_VIEWPORT)
    const firstShell = page.locator('.map-shell').first()
    const firstHint = firstShell.locator('.map-hint')
    await firstShell.scrollIntoViewIfNeeded()
    await expect(firstShell).toHaveClass(/is-scrollable/)
    await expect(firstHint).toBeVisible()
    await expect(firstHint).toContainText('左右滑動')

    await firstShell.locator('.mapwrap').evaluate((el) => {
      el.scrollLeft = 80
      el.dispatchEvent(new Event('scroll'))
    })
    await expect(firstShell).toHaveClass(/is-scrolled/)

    expect(errors).toEqual([])
  })

  test('晨興聖言 /morning-revival/：weeks.json 載入、攔截經文 API 與切換週次正常渲染', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await setupOfflineRoutes(page)

    const weeksJson = JSON.parse(
      fs.readFileSync(path.join(PORTAL_ROOT, 'morning-revival', 'weeks.json'), 'utf8'),
    )
    const allWeeks = weeksJson.trainings.flatMap((t) => t.weeks)
    const latestWeek = allWeeks.find((w) => w.id === weeksJson.latest) || allWeeks[0]
    const otherWeek =
      allWeeks.find((w) => w.id !== latestWeek.id && /^20\d\d-/.test(w.id)) ||
      allWeeks.find((w) => w.id !== latestWeek.id)
    expect(otherWeek, 'weeks.json 至少需有兩週可供切換測試').toBeTruthy()
    const normalizeHeading = (title) => title.replace(/（[^）]*）$/, '').trim()

    await page.goto(`${baseUrl}/morning-revival/`)
    await waitPageReady(page, '/morning-revival/')

    expect(await page.content()).not.toContain('{{')

    // 確認選單依照 weeks.json 載入
    await expect(page.locator('#menu details.group')).toHaveCount(weeksJson.trainings.length)
    await expect(page.locator('#menu a[data-id]')).toHaveCount(allWeeks.length)

    // 預設載入最新一週並正確填入模擬經文
    const latestLink = page.locator(`#menu a[data-id="${latestWeek.id}"]`)
    await expect(latestLink).toHaveAttribute('aria-current', 'page')
    await expect(page.locator('#content h2.week-title')).toContainText(normalizeHeading(latestWeek.title))
    await expect(page.locator('#content')).not.toContainText('載入失敗')
    const firstVerse = page.locator('#content .verse-text').first()
    if (await firstVerse.count() > 0) {
      await expect(firstVerse).toContainText('測試經文')
      await expect(page.locator('#content .verse-text.failed')).toHaveCount(0)
    }

    // 點擊另一週切換並驗證畫面與標題更新
    const otherLink = page.locator(`#menu a[data-id="${otherWeek.id}"]`)
    await otherLink.click()

    await expect(otherLink).toHaveAttribute('aria-current', 'page')
    await expect(latestLink).not.toHaveAttribute('aria-current', 'page')
    await expect(page).toHaveURL(new RegExp(`#${otherWeek.id}$`))
    await expect(page.locator('#content h2.week-title')).toContainText(normalizeHeading(otherWeek.title))
    await expect(page.locator('#content')).not.toContainText('載入失敗')
    expect(await page.title()).toContain(otherWeek.title)

    expect(errors).toEqual([])
  })

  for (const target of CORE_PAGES) {
    test(`${target.name}（${target.path}）：切換 6 組色彩主題、重整記住偏好且 0 pageerror`, async ({ page }) => {
      const errors = []
      page.on('pageerror', (e) => errors.push(String(e)))
      await setupOfflineRoutes(page)

      await page.goto(`${baseUrl}${target.path}`)
      await waitPageReady(page, target.path)

      const pickerBtn = page.getByTestId('theme-picker-btn')
      const menu = page.locator('.tp-menu[role="listbox"]')
      await expect(pickerBtn).toBeVisible()

      for (const themeId of THEMES) {
        await pickerBtn.click()
        await expect(menu).toBeVisible()
        await page.locator(`.tp-item[data-theme-id="${themeId}"]`).click()
        await expect(menu).toBeHidden()

        const applied = await page.evaluate(() => document.documentElement.dataset.theme)
        expect(applied).toBe(themeId)

        const stored = await page.evaluate((k) => localStorage.getItem(k), THEME_KEY)
        expect(stored).toBe(themeId)
      }

      // 重新整理後仍保留最後切換的主題（gruvbox）
      await page.reload()
      await waitPageReady(page, target.path)
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe('gruvbox')
      expect(await page.evaluate((k) => localStorage.getItem(k), THEME_KEY)).toBe('gruvbox')

      expect(errors).toEqual([])
    })

    test(`${target.name}（${target.path}）：手機寬度 390×844 無水平捲動溢位且 0 pageerror`, async ({ page }) => {
      const errors = []
      page.on('pageerror', (e) => errors.push(String(e)))
      await setupOfflineRoutes(page)
      await page.setViewportSize(MOBILE_VIEWPORT)

      await page.goto(`${baseUrl}${target.path}`)
      await waitPageReady(page, target.path)

      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      expect(
        metrics.scrollWidth,
        `${target.path} 在 390×844 水平溢位：scrollWidth=${metrics.scrollWidth}, clientWidth=${metrics.clientWidth}`,
      ).toBeLessThanOrEqual(metrics.clientWidth)

      expect(errors).toEqual([])
    })
  }
})
