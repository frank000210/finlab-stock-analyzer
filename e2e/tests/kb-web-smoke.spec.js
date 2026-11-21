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

const MOCK_ASK_RESPONSE = {
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
}

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

async function setupKbApiMocks(page, captured = {}) {
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
      try {
        captured.lastAskBody = req.postDataJSON()
      } catch {
        captured.lastAskBody = null
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_ASK_RESPONSE),
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

  test('公開模式總覽頁載入正常、顯示知識庫標題與領域卡片、不顯示匯入頁且零錯誤', async ({ page }) => {
    const pageErrors = []
    const consoleErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await setupKbApiMocks(page)
    await page.goto(`${kbUrl}/`, { waitUntil: 'networkidle' })

    await expect(page).toHaveTitle(/知識庫/)
    await expect(page.locator('.brand')).toContainText('知識庫')
    await expect(page.locator('h1')).toContainText('Notebook 總覽')

    // 公開模式權限邊界：不顯示「資料匯入」與「登出」
    await expect(page.locator('header nav a', { hasText: '資料匯入' })).toHaveCount(0)
    await expect(page.locator('.logout-btn')).toHaveCount(0)
    await expect(page.locator('header nav a', { hasText: '問答' })).toBeVisible()

    // 驗證模擬領域／文件卡片正確渲染
    const cards = page.locator('.nb-card')
    await expect(cards).toHaveCount(MOCK_NOTEBOOKS.length)
    await expect(cards.filter({ hasText: 'dev_note' })).toContainText('18')
    await expect(cards.filter({ hasText: 'morning_revival' })).toContainText('12')
    await expect(cards.filter({ hasText: 'patent' })).toContainText('5')

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

  test('問答頁載入正常，送出問題後正確渲染回答與引用來源', async ({ page }) => {
    const pageErrors = []
    const consoleErrors = []
    page.on('pageerror', (err) => pageErrors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    const captured = {}
    await setupKbApiMocks(page, captured)
    await page.goto(`${kbUrl}/`, { waitUntil: 'networkidle' })

    // 透過導覽列進入問答頁
    await page.locator('header nav a', { hasText: '問答' }).click()
    await expect(page.locator('h1')).toContainText('問答')

    const textarea = page.locator('textarea')
    const submitBtn = page.getByRole('button', { name: '提問' })
    await expect(textarea).toBeVisible()
    await expect(submitBtn).toBeDisabled()

    await page.locator('input[placeholder*="patent"]').fill('dev_note')
    await textarea.fill('公開模式的權限邊界是什麼？')
    await expect(submitBtn).toBeEnabled()
    await submitBtn.click()

    // 驗證問答回答、引用來源與搜尋過程正確渲染
    const answerCard = page.locator('.answer-card')
    await expect(answerCard).toBeVisible()
    await expect(answerCard.locator('.answer-question')).toContainText('公開模式的權限邊界是什麼？')
    await expect(answerCard.locator('.answer-text')).toContainText('瀏覽知識庫與 AI 問答皆免登入')
    await expect(answerCard.locator('.answer-text strong')).toContainText('公開模式')

    const chips = answerCard.locator('.citations .chip')
    await expect(chips).toHaveCount(2)
    await expect(chips.nth(0)).toContainText('[1]')
    await expect(chips.nth(0)).toContainText('dev-note-2026-04-10-公開模式權限設計')
    await expect(chips.nth(1)).toContainText('[2]')
    await expect(chips.nth(1)).toContainText('kb-web 匯入端點驗證規格')

    await expect(answerCard.locator('.steps-toggle')).toContainText('搜尋過程（2 步）')
    expect(captured.lastAskBody).toMatchObject({
      question: '公開模式的權限邊界是什麼？',
      domain: 'dev_note',
    })

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
