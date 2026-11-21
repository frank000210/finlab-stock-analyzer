// @ts-check
const fs = require('fs')
const http = require('http')
const path = require('path')
const { execFileSync, execSync } = require('child_process')
const { test, expect } = require('@playwright/test')

// kb-web 自動化煙霧測試：完全自給自足、零外網／零 MongoDB 依賴。
// 啟動輕量本機 Node HTTP 靜態伺服器託管 kb-web/frontend/dist（若尚未建置則自動建置），
// 並透過 page.route 完整 mock /api/**，不依賴 FinLab 主站 BASE_URL 或正式站外網。

const REPO_ROOT = path.resolve(__dirname, '../..')
const KB_FRONTEND_DIR = path.join(REPO_ROOT, 'kb-web', 'frontend')
const KB_DIST_DIR = path.join(KB_FRONTEND_DIR, 'dist')

const THEMES = [
  { id: 'notebook', name: '手帳米白' },
  { id: 'dark', name: '夜間深色' },
  { id: 'solarized', name: 'Solarized' },
  { id: 'nord', name: 'Nord' },
  { id: 'dracula', name: 'Dracula' },
  { id: 'gruvbox', name: 'Gruvbox' },
]

const MOCK_NOTEBOOKS = [
  {
    domain: 'dev_note',
    doc_count: 18,
    last_updated: '2026-04-12T08:30:00Z',
    quality_failed: 0,
    needs_review: 0,
  },
  {
    domain: 'morning_revival',
    doc_count: 12,
    last_updated: '2026-04-14T06:00:00Z',
    quality_failed: 0,
    needs_review: 1,
  },
  {
    domain: 'patent',
    doc_count: 5,
    last_updated: '2026-04-08T10:15:00Z',
    quality_failed: 1,
    needs_review: 0,
  },
]

const MOCK_ASK_RESPONSES = [
  {
    answer: '在**公開模式**下，瀏覽知識庫與 AI 問答皆免登入 [1]；匯入 API（`/api/import/*`）仍須 `KB_API_TOKEN` 保護 [2]。',
    citations: [
      { index: 1, title: 'dev-note-2026-04-10-公開模式權限設計', source: 'dev_note/public-mode.md' },
      { index: 2, title: 'kb-web 匯入端點驗證規格', source: 'dev_note/import-auth.md' },
    ],
    steps: [
      { type: 'rewrite', query: '公開模式 權限邊界', hits: 0 },
      { type: 'kb', query: 'kb-web 公開模式 匯入 token', hits: 2 },
    ],
    question_id: 'mock-q-001',
  },
  {
    answer: '補充說明：對話串會自動帶入最近 3 輪上下文，方便連續追問 [1]。',
    citations: [
      { index: 1, title: 'PP6 多輪對話設計筆記', source: 'dev_note/chat-history.md' },
    ],
    steps: [
      { type: 'kb', query: '多輪對話 上下文', hits: 1 },
    ],
    question_id: 'mock-q-002',
  },
]

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
}

function getLatestMtime(targetPath) {
  if (!fs.existsSync(targetPath)) return 0
  const stat = fs.statSync(targetPath)
  if (!stat.isDirectory()) return stat.mtimeMs
  let latest = stat.mtimeMs
  for (const entry of fs.readdirSync(targetPath, { withFileTypes: true })) {
    const t = getLatestMtime(path.join(targetPath, entry.name))
    if (t > latest) latest = t
  }
  return latest
}

function ensureKbDist() {
  const indexHtml = path.join(KB_DIST_DIR, 'index.html')
  const sourceTargets = [
    path.join(KB_FRONTEND_DIR, 'index.html'),
    path.join(KB_FRONTEND_DIR, 'package.json'),
    path.join(KB_FRONTEND_DIR, 'vite.config.js'),
    path.join(KB_FRONTEND_DIR, 'src'),
  ]
  const latestSourceMtime = Math.max(...sourceTargets.map(getLatestMtime))

  if (fs.existsSync(indexHtml)) {
    const distMtime = fs.statSync(indexHtml).mtimeMs
    if (distMtime >= latestSourceMtime) return
  }

  const viteBin = path.join(KB_FRONTEND_DIR, 'node_modules', 'vite', 'bin', 'vite.js')
  if (!fs.existsSync(viteBin)) {
    execSync('npm ci --prefer-offline --no-audit --no-fund', {
      cwd: KB_FRONTEND_DIR,
      stdio: 'pipe',
    })
  }

  execFileSync(process.execPath, [viteBin, 'build'], {
    cwd: KB_FRONTEND_DIR,
    stdio: 'pipe',
  })

  if (!fs.existsSync(indexHtml)) {
    throw new Error(`kb-web frontend build did not produce ${indexHtml}`)
  }
}

function startStaticServer(distDir) {
  const indexPath = path.join(distDir, 'index.html')
  const server = http.createServer((req, res) => {
    const rawUrl = (req.url || '/').split('?')[0]
    const safePath = path.normalize(decodeURIComponent(rawUrl)).replace(/^(\.\.[/\\])+/, '')
    const fullPath = path.join(distDir, safePath)

    if (rawUrl === '/favicon.ico' && !fs.existsSync(fullPath)) {
      res.writeHead(204)
      res.end()
      return
    }

    // 靜態檔存在就回傳；非 /assets/ 與 /api/ 路徑一律 SPA fallback 到 index.html
    if (fullPath.startsWith(distDir) && fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
      const ext = path.extname(fullPath).toLowerCase()
      res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' })
      fs.createReadStream(fullPath).pipe(res)
      return
    }

    if (rawUrl.startsWith('/assets/') || rawUrl.startsWith('/api/')) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end('Not found')
      return
    }

    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    fs.createReadStream(indexPath).pipe(res)
  })

  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      resolve({ server, url: `http://127.0.0.1:${addr.port}` })
    })
  })
}

async function setupKbApiMocks(page, captured = {}, options = {}) {
  captured.askBodies = captured.askBodies || []
  let askCount = 0

  await page.route('**/api/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const pathname = url.pathname

    if (pathname === '/api/auth-mode' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ public: true }),
      })
    }

    if (pathname === '/api/notebooks' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_NOTEBOOKS),
      })
    }

    if (pathname === '/api/ask' && req.method() === 'POST') {
      let body = null
      try {
        body = req.postDataJSON()
      } catch {
        body = null
      }
      captured.lastAskBody = body
      captured.askBodies.push(body)

      const idx = Math.min(askCount, MOCK_ASK_RESPONSES.length - 1)
      askCount += 1

      if (options.askDelayMs) {
        await new Promise((r) => setTimeout(r, options.askDelayMs))
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_ASK_RESPONSES[idx]),
      })
    }

    if (pathname === '/api/ask/feedback' && req.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    }

    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: `Unmocked API route: ${pathname}` }),
    })
  })
}

test.describe('kb-web 知識庫自動化煙霧測試', () => {
  /** @type {import('http').Server | null} */
  let server = null
  let kbUrl = ''

  test.beforeAll(async () => {
    ensureKbDist()
    const started = await startStaticServer(KB_DIST_DIR)
    server = started.server
    kbUrl = started.url
  })

  test.afterAll(async () => {
    if (server) {
      await new Promise((resolve) => server.close(() => resolve()))
      server = null
    }
  })

  test('公開模式總覽頁載入正常、寬螢幕置中、回入口導覽、專利下拉選單與卡片直通問答', async ({ page }) => {
    const pageErrors = []
    const consoleErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await page.setViewportSize({ width: 1280, height: 800 })
    await setupKbApiMocks(page)
    await page.goto(`${kbUrl}/`, { waitUntil: 'networkidle' })

    await expect(page).toHaveTitle(/知識庫/)
    await expect(page.locator('h1')).toContainText('Notebook 總覽')

    // 寬螢幕（1280px）下 .page 應水平置中且與 .topnav-inner 對齊
    const layoutMetrics = await page.evaluate(() => {
      const pageEl = document.querySelector('.page')
      const topnavEl = document.querySelector('.topnav-inner')
      const pRect = pageEl.getBoundingClientRect()
      const tRect = topnavEl.getBoundingClientRect()
      return {
        viewportWidth: window.innerWidth,
        pageLeft: pRect.left,
        pageRightGap: window.innerWidth - pRect.right,
        pageCenter: pRect.left + pRect.width / 2,
        topnavCenter: tRect.left + tRect.width / 2,
      }
    })
    expect(Math.abs(layoutMetrics.pageLeft - layoutMetrics.pageRightGap)).toBeLessThanOrEqual(4)
    expect(Math.abs(layoutMetrics.pageCenter - layoutMetrics.topnavCenter)).toBeLessThanOrEqual(4)

    // 「← 入口」與 .brand 回首頁連結
    const portalLink = page.getByTestId('portal-back-link')
    await expect(portalLink).toBeVisible()
    await expect(portalLink).toContainText('← 入口')
    await expect(portalLink).toHaveAttribute('href', 'https://43-133-44-216.sslip.io/')
    await expect(portalLink).toHaveAttribute('title', '回到 Frank 入口頁')

    const brandLink = page.locator('a.brand')
    await expect(brandLink).toBeVisible()
    await expect(brandLink).toContainText('知識庫')
    await expect(brandLink).toHaveAttribute('href', '/')

    // 公開模式權限邊界：不顯示「資料匯入」與「登出」，且頁首說明不提「資料匯入」
    await expect(page.locator('header nav a', { hasText: '資料匯入' })).toHaveCount(0)
    await expect(page.locator('.logout-btn')).toHaveCount(0)
    await expect(page.locator('header nav a', { hasText: '問答' })).toBeVisible()
    await expect(page.locator('.page-header p')).not.toContainText('資料匯入')

    // 專利分析收斂成下拉選單，點擊與鍵盤皆可開關並切換路由
    const patentBtn = page.getByTestId('patent-menu-btn')
    await expect(patentBtn).toBeVisible()
    await expect(patentBtn).toContainText('專利分析')
    await expect(page.getByTestId('patent-menu')).toHaveCount(0)

    await patentBtn.click()
    const patentMenu = page.getByTestId('patent-menu')
    await expect(patentMenu).toBeVisible()
    await expect(patentMenu.locator('a[role="menuitem"]')).toHaveCount(3)
    await expect(patentMenu).toContainText('規劃書')
    await expect(patentMenu).toContainText('示範報告')
    await expect(patentMenu).toContainText('審查備注')

    await page.keyboard.press('Escape')
    await expect(patentMenu).toHaveCount(0)

    await patentBtn.click()
    await patentMenu.locator('a[role="menuitem"]', { hasText: '示範報告' }).click()
    await expect(page).toHaveURL(/\/patent-report$/)
    await expect(patentBtn).toHaveClass(/active/)

    // 點擊 .brand 回到首頁
    await brandLink.click()
    await expect(page).toHaveURL(/\/$/)
    await expect(page.locator('h1')).toContainText('Notebook 總覽')

    // 驗證模擬領域／文件卡片正確渲染，並點擊直通 /ask?domain=dev_note
    const cards = page.locator('a.nb-card')
    await expect(cards).toHaveCount(MOCK_NOTEBOOKS.length)
    const devNoteCard = cards.filter({ hasText: 'dev_note' })
    await expect(devNoteCard).toContainText('18')
    await expect(devNoteCard).toContainText('點擊直接提問')
    await expect(cards.filter({ hasText: 'morning_revival' })).toContainText('12')
    await expect(cards.filter({ hasText: 'patent' })).toContainText('5')

    await devNoteCard.click()
    await expect(page).toHaveURL(/\/ask\?domain=dev_note$/)
    await expect(page.getByTestId('domain-select')).toHaveValue('dev_note')

    // 公開模式直接存取 /import 應導回首頁
    await page.goto(`${kbUrl}/import`, { waitUntil: 'networkidle' })
    expect(new URL(page.url()).pathname).toBe('/')

    expect(pageErrors).toEqual([])
    expect(consoleErrors).toEqual([])
  })

  test('6 組色彩主題可於右上角選單切換、同步 dataset.theme 與 localStorage 並於重整後保留', async ({ page }) => {
    const pageErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))

    await page.setViewportSize({ width: 1280, height: 800 })
    await setupKbApiMocks(page)
    await page.goto(`${kbUrl}/`, { waitUntil: 'networkidle' })

    const pickerBtn = page.getByTestId('theme-picker-btn')
    await expect(pickerBtn).toBeVisible()
    await expect(pickerBtn).toContainText('手帳米白')

    // 選單列出全部 6 組主題
    await pickerBtn.click()
    const menu = page.getByTestId('theme-picker-menu')
    await expect(menu).toBeVisible()
    const options = menu.locator('[role="option"]')
    await expect(options).toHaveCount(6)
    await page.keyboard.press('Escape')
    await expect(menu).toHaveCount(0)

    // 先切換 5 組非預設主題再切回 notebook，確保 6 組皆實際觸發寫入與 DOM 更新
    const order = ['dark', 'solarized', 'nord', 'dracula', 'gruvbox', 'notebook']
    const papers = new Set()

    for (const id of order) {
      const theme = THEMES.find((t) => t.id === id)
      await pickerBtn.click()
      await page.locator(`[data-theme-id="${id}"]`).click()
      await expect(menu).toHaveCount(0)
      await expect(pickerBtn).toContainText(theme.name)

      const state = await page.evaluate(() => ({
        datasetTheme: document.documentElement.dataset.theme,
        savedTheme: localStorage.getItem('finlab.colorTheme.v1'),
        paper: getComputedStyle(document.documentElement).getPropertyValue('--paper').trim(),
      }))

      if (id === 'notebook') {
        expect(state.datasetTheme).toBeUndefined()
      } else {
        expect(state.datasetTheme).toBe(id)
      }
      expect(state.savedTheme).toBe(id)
      papers.add(state.paper)
    }
    expect(papers.size).toBe(6)

    // 切到 dracula 並重新整理，確認 dataset.theme 與 localStorage 皆保留
    await pickerBtn.click()
    await page.locator('[data-theme-id="dracula"]').click()
    await page.reload({ waitUntil: 'networkidle' })

    const afterReload = await page.evaluate(() => ({
      datasetTheme: document.documentElement.dataset.theme,
      savedTheme: localStorage.getItem('finlab.colorTheme.v1'),
    }))
    expect(afterReload.datasetTheme).toBe('dracula')
    expect(afterReload.savedTheme).toBe('dracula')
    await expect(pickerBtn).toContainText('Dracula')

    expect(pageErrors).toEqual([])
  })

  test('問答頁支援領域下拉選單、保留多輪對話串與可展開引用出處', async ({ page }) => {
    const pageErrors = []
    const consoleErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    const captured = {}
    await setupKbApiMocks(page, captured, { askDelayMs: 200 })
    await page.goto(`${kbUrl}/`, { waitUntil: 'networkidle' })

    // 透過導覽列進入問答頁
    await page.locator('header nav a', { hasText: '問答' }).click()
    await expect(page.locator('h1')).toContainText('問答')

    // 驗證領域下拉選單包含「全部領域」與模擬領域
    const domainSelect = page.getByTestId('domain-select')
    await expect(domainSelect).toBeVisible()
    await expect(domainSelect.locator('option')).toHaveCount(MOCK_NOTEBOOKS.length + 1)
    await expect(domainSelect).toHaveValue('')
    await domainSelect.selectOption('dev_note')
    await expect(domainSelect).toHaveValue('dev_note')

    const textarea = page.locator('textarea')
    const submitBtn = page.getByRole('button', { name: '提問' })
    await expect(textarea).toBeVisible()
    await expect(submitBtn).toBeDisabled()

    // 第 1 題以 Ctrl+Enter 送出
    await textarea.fill('公開模式的權限邊界是什麼？')
    await expect(submitBtn).toBeEnabled()
    await textarea.press('Control+Enter')

    // 驗證第 1 輪問答渲染於對話串
    const turns = page.getByTestId('chat-turn')
    await expect(turns).toHaveCount(1)
    const firstTurn = turns.nth(0)
    await expect(firstTurn.getByTestId('user-bubble')).toContainText('公開模式的權限邊界是什麼？')
    await expect(firstTurn.locator('.answer-text')).toContainText('瀏覽知識庫與 AI 問答皆免登入')
    await expect(firstTurn.locator('.answer-text strong')).toContainText('公開模式')

    // 引用來源 chip 可點擊展開完整出處預覽卡片，再點一次可收合
    const chips = firstTurn.locator('.citations .chip')
    await expect(chips).toHaveCount(2)
    await expect(chips.nth(0)).toContainText('[1]')
    await expect(chips.nth(0)).toContainText('dev-note-2026-04-10-公開模式權限設計')
    await expect(chips.nth(1)).toContainText('[2]')
    await expect(chips.nth(1)).toContainText('kb-web 匯入端點驗證規格')

    await chips.nth(0).click()
    const detailCard = firstTurn.getByTestId('citation-detail')
    await expect(detailCard).toBeVisible()
    await expect(detailCard).toContainText('dev_note/public-mode.md')
    await chips.nth(0).click()
    await expect(detailCard).toHaveCount(0)

    await expect(firstTurn.locator('.steps-toggle')).toContainText('搜尋過程（2 步）')
    expect(captured.askBodies[0]).toMatchObject({
      question: '公開模式的權限邊界是什麼？',
      domain: 'dev_note',
      history: [],
    })

    // 送出第 2 題：確認載入中第 1 題不會被洗白，且底部出現「思考中…」氣泡
    await textarea.fill('追問：多輪對話怎麼運作？')
    await submitBtn.click()

    await expect(turns).toHaveCount(2)
    await expect(firstTurn.locator('.answer-text')).toContainText('瀏覽知識庫與 AI 問答皆免登入')
    await expect(turns.nth(1).getByTestId('user-bubble')).toContainText('追問：多輪對話怎麼運作？')
    await expect(turns.nth(1).getByTestId('thinking-bubble')).toContainText('思考中…')

    // 等待第 2 題完成，確認兩輪問答完整保留且帶入前 1 輪 history
    await expect(turns.nth(1).locator('.answer-text')).toContainText('自動帶入最近 3 輪上下文')
    await expect(firstTurn.locator('.answer-text')).toContainText('瀏覽知識庫與 AI 問答皆免登入')
    expect(captured.askBodies[1].history).toHaveLength(2)
    expect(captured.askBodies[1].history[0]).toMatchObject({
      role: 'user',
      content: '公開模式的權限邊界是什麼？',
    })

    // 點擊「清除對話」清空對話串
    await page.getByTestId('clear-chat-btn').click()
    await expect(page.getByTestId('chat-thread')).toHaveCount(0)

    expect(pageErrors).toEqual([])
    expect(consoleErrors).toEqual([])
  })

  test('手機寬度（390×844）不超出水平捲動寬度', async ({ page }) => {
    const pageErrors = []
    const consoleErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await setupKbApiMocks(page)

    for (const routePath of ['/', '/ask']) {
      await page.goto(`${kbUrl}${routePath}`, { waitUntil: 'networkidle' })
      await expect(page.locator('.page')).toBeVisible()
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      expect(
        metrics.scrollWidth,
        `${routePath} 在 390×844 下不應超出水平寬度（scrollWidth=${metrics.scrollWidth}, clientWidth=${metrics.clientWidth}）`,
      ).toBeLessThanOrEqual(metrics.clientWidth)
    }

    // 確認手機寬度下展開專利下拉選單仍在視窗內且不撐開水平寬度
    await page.getByTestId('patent-menu-btn').click()
    const patentMenuBox = await page.getByTestId('patent-menu').boundingBox()
    expect(patentMenuBox).not.toBeNull()
    expect(patentMenuBox.x).toBeGreaterThanOrEqual(0)
    expect(patentMenuBox.x + patentMenuBox.width).toBeLessThanOrEqual(390)
    await page.keyboard.press('Escape')

    // 確認手機寬度下問答展開引用詳情卡片也不會撐破寬度
    await page.locator('textarea').fill('手機測試問題')
    await page.getByRole('button', { name: '提問' }).click()
    const firstChip = page.locator('.citations .chip').first()
    await expect(firstChip).toBeVisible()
    await firstChip.click()
    await expect(page.getByTestId('citation-detail')).toBeVisible()

    const askMetrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(askMetrics.scrollWidth).toBeLessThanOrEqual(askMetrics.clientWidth)

    // 確認手機寬度下右上角主題選單按鈕與展開選單都在畫面內
    const pickerBtn = page.getByTestId('theme-picker-btn')
    await expect(pickerBtn).toBeVisible()
    const btnBox = await pickerBtn.boundingBox()
    expect(btnBox).not.toBeNull()
    expect(btnBox.x).toBeGreaterThanOrEqual(0)
    expect(btnBox.x + btnBox.width).toBeLessThanOrEqual(390)

    await pickerBtn.click()
    const menuBox = await page.getByTestId('theme-picker-menu').boundingBox()
    expect(menuBox).not.toBeNull()
    expect(menuBox.x).toBeGreaterThanOrEqual(0)
    expect(menuBox.x + menuBox.width).toBeLessThanOrEqual(390)

    expect(pageErrors).toEqual([])
    expect(consoleErrors).toEqual([])
  })
})
