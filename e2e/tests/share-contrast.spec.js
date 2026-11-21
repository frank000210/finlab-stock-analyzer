// @ts-check
const { test, expect } = require('@playwright/test')
const http = require('http')
const fs = require('fs')
const path = require('path')

const PORTAL_DIR = path.resolve(__dirname, '../../deploy/portal')
const THEMES = [
  { id: 'notebook', name: '手帳米白' },
  { id: 'dark', name: '夜間深色' },
  { id: 'solarized', name: 'Solarized' },
  { id: 'nord', name: 'Nord' },
  { id: 'dracula', name: 'Dracula' },
  { id: 'gruvbox', name: 'Gruvbox' },
]

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
}

function startStaticServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0])
      let filePath = path.join(rootDir, urlPath)
      if (!filePath.startsWith(rootDir)) {
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
      if (ext === '.html') {
        const html = fs.readFileSync(filePath, 'utf-8').replaceAll('{{env "BASE_HOST"}}', 'example.test')
        res.writeHead(200, { 'Content-Type': MIME[ext] })
        res.end(html)
        return
      }
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
      fs.createReadStream(filePath).pipe(res)
    })
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      resolve({ server, baseUrl: `http://127.0.0.1:${addr.port}` })
    })
  })
}

/** 透過右上角主題選單切換色彩主題 */
async function selectTheme(page, themeId) {
  const btn = page.getByTestId('theme-picker-btn')
  await expect(btn).toBeVisible()
  await btn.click()
  const option = page.locator(`.tp-item[data-theme-id="${themeId}"]`)
  await expect(option).toBeVisible()
  await option.click()
  await expect.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe(themeId)
}

/**
 * 在瀏覽器內用 getComputedStyle 實地量測指定選擇器、全頁可見文字節點與 SVG 心智圖的 WCAG 對比度。
 * @param {import('@playwright/test').Page} page
 * @param {Array<{ label: string, selector: string, checkHighlight?: boolean }>} keyChecks
 */
async function auditPageContrast(page, keyChecks) {
  return page.evaluate((checks) => {
    function parseColor(str) {
      if (!str || str === 'none' || str === 'transparent') return null
      const m = str.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i)
      if (!m) return null
      return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] === undefined ? 1 : Number(m[4])]
    }
    function composite(fg, bg) {
      const a = fg[3]
      return [
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1,
      ]
    }
    function relLum(rgb) {
      const ch = rgb.slice(0, 3).map((v) => {
        const s = v / 255
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
      })
      return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    }
    function contrastRatio(c1, c2) {
      const l1 = relLum(c1)
      const l2 = relLum(c2)
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
    }
    function toHex(rgb) {
      return '#' + rgb.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')
    }
    function getEffectiveBg(el) {
      const layers = []
      let cur = el
      while (cur && cur.nodeType === 1) {
        const bg = parseColor(getComputedStyle(cur).backgroundColor)
        if (bg && bg[3] > 0) {
          layers.push(bg)
          if (bg[3] >= 0.999) break
        }
        cur = cur.parentElement
      }
      let result = [255, 255, 255, 1]
      for (let i = layers.length - 1; i >= 0; i--) {
        result = composite(layers[i], result)
      }
      return result
    }
    function isVisible(el) {
      let cur = el
      while (cur && cur.nodeType === 1) {
        const cs = getComputedStyle(cur)
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false
        if (cur.classList && cur.classList.contains('sr-only')) return false
        if (cur.tagName === 'DETAILS' && !cur.open) {
          if (!el.closest('summary')) return false
        }
        cur = cur.parentElement
      }
      const rect = el.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    }

    const keyResults = []
    const failures = []

    // 1. 重點元件實地量測
    for (const item of checks) {
      const nodes = Array.from(document.querySelectorAll(item.selector)).filter(isVisible)
      if (nodes.length === 0) {
        failures.push(`找不到可見元素：${item.label} (${item.selector})`)
        continue
      }
      let minRatio = Infinity
      let worstSample = null
      for (const node of nodes) {
        const cs = getComputedStyle(node)
        const fg = parseColor(cs.color)
        const bg = getEffectiveBg(node)
        if (!fg) continue
        const blendedFg = fg[3] < 1 ? composite(fg, bg) : fg
        let r = contrastRatio(blendedFg, bg)
        let bgUsed = bg
        if (item.checkHighlight) {
          const hlStr = getComputedStyle(document.documentElement).getPropertyValue('--hl').trim()
          const hlColor = parseColor(hlStr)
          if (hlColor) {
            const hlBg = composite(hlColor, bg)
            const hlRatio = contrastRatio(blendedFg, hlBg)
            if (hlRatio < r) {
              r = hlRatio
              bgUsed = hlBg
            }
          }
        }
        if (r < minRatio) {
          minRatio = r
          worstSample = { fg: toHex(blendedFg), bg: toHex(bgUsed), text: (node.textContent || '').trim().slice(0, 24) }
        }
      }
      keyResults.push({ label: item.label, count: nodes.length, minRatio: Number(minRatio.toFixed(2)), sample: worstSample })
      if (minRatio < 4.5) {
        failures.push(`[KEY] ${item.label}: ${minRatio.toFixed(2)}:1 (${worstSample.fg} on ${worstSample.bg}, "${worstSample.text}")`)
      }
    }

    // 2. 全頁可見文字節點泛掃
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    const seen = new Set()
    let textNode
    while ((textNode = walker.nextNode())) {
      if (!textNode.nodeValue || !textNode.nodeValue.trim()) continue
      const el = textNode.parentElement
      if (!el || seen.has(el)) continue
      seen.add(el)
      if (el.closest('svg')) continue
      if (!isVisible(el)) continue
      const cs = getComputedStyle(el)
      const fg = parseColor(cs.color)
      if (!fg) continue
      const bg = getEffectiveBg(el)
      const blendedFg = fg[3] < 1 ? composite(fg, bg) : fg
      const r = contrastRatio(blendedFg, bg)
      if (r < 4.5) {
        const tag = el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).trim().replace(/\s+/g, '.') : '')
        failures.push(`[DOM] ${tag}: ${r.toFixed(2)}:1 (${toHex(blendedFg)} on ${toHex(bg)}, "${textNode.nodeValue.trim().slice(0, 24)}")`)
      }
    }

    // 3. 心智圖 SVG 節點量測
    const svgNodes = Array.from(document.querySelectorAll('svg.map a'))
    let svgChecked = 0
    for (const link of svgNodes) {
      const rect = link.querySelector('rect')
      if (!rect) continue
      const bg = parseColor(getComputedStyle(rect).fill)
      if (!bg) continue
      for (const t of link.querySelectorAll('text')) {
        const fg = parseColor(getComputedStyle(t).fill)
        if (!fg) continue
        svgChecked += 1
        const r = contrastRatio(fg, bg)
        if (r < 4.5) {
          failures.push(`[SVG] ${link.getAttribute('class') || ''} text.${t.getAttribute('class') || ''}: ${r.toFixed(2)}:1 (${toHex(fg)} on ${toHex(bg)}, "${t.textContent.trim()}")`)
        }
      }
    }

    return { keyResults, svgChecked, failures }
  }, keyChecks)
}

test.describe('知識分享 /share/ 六組主題 WCAG AA 對比度驗證', () => {
  /** @type {{ server: import('http').Server, baseUrl: string }} */
  let srv

  test.beforeAll(async () => {
    srv = await startStaticServer(PORTAL_DIR)
  })

  test.afterAll(async () => {
    if (srv && srv.server) {
      await new Promise((resolve) => srv.server.close(resolve))
    }
  })

  test('HTML 檔案不含 Caddy templates 衝突字元 {{', async () => {
    const files = [
      path.join(PORTAL_DIR, 'share/index.html'),
      path.join(PORTAL_DIR, 'share/math-study-method/index.html'),
    ]
    for (const f of files) {
      const html = fs.readFileSync(f, 'utf-8')
      expect(html, `${path.relative(PORTAL_DIR, f)} 不應含連續兩個左大括號`).not.toContain('{{')
    }
    const portalHtml = fs.readFileSync(path.join(PORTAL_DIR, 'index.html'), 'utf-8')
      .replaceAll('{{env "BASE_HOST"}}', 'example.test')
    expect(portalHtml, 'index.html 除 {{env "BASE_HOST"}} 外不應含連續兩個左大括號').not.toContain('{{')
  })

  test('入口頁 / 在 6 組主題下重測按鈕、異常標籤與所有可見文字皆達 WCAG AA ≥ 4.5:1', async ({ page }) => {
    const pageErrors = []
    page.on('pageerror', (e) => pageErrors.push(String(e)))

    await page.route(/^https?:\/\/(?!127\.0\.0\.1(?::\d+)?\/|localhost(?::\d+)?\/).*/, (route) => route.abort())
    await page.route('https://*.example.test/**', (route) => {
      if (route.request().url().startsWith('https://food.example.test/')) {
        return route.abort()
      }
      return route.fulfill({ status: 200, contentType: 'text/plain; charset=utf-8', body: 'ok' })
    })

    await page.goto(`${srv.baseUrl}/`)
    await expect(page.locator('#retest-btn')).toBeVisible()
    await expect(page.locator('.status-badge:visible')).toHaveCount(1)

    const checks = [
      { label: '便利貼大字 (.sticky .big)', selector: '.sticky .big' },
      { label: '便利貼說明 (.sticky small)', selector: '.sticky small' },
      { label: '便利貼重測按鈕 (.retest-btn)', selector: '.retest-btn' },
      { label: '異常微標籤 (.status-badge)', selector: '.status-badge' },
      { label: '卡片標題 (.card .title)', selector: '.card .title' },
      { label: '卡片描述 (.card .desc)', selector: '.card .desc' },
      { label: '主題選單按鈕 (.tp-btn)', selector: '.tp-btn' },
    ]

    for (const theme of THEMES) {
      await selectTheme(page, theme.id)
      const res = await auditPageContrast(page, checks)
      expect(res.failures, `入口頁 / 主題 ${theme.id} 對比度失敗：\n${res.failures.join('\n')}`).toEqual([])
    }
    expect(pageErrors).toEqual([])
  })

  test('/share/ 目錄頁在 6 組主題下卡片標題與所有文字皆達 WCAG AA ≥ 4.5:1', async ({ page }) => {
    const pageErrors = []
    page.on('pageerror', (e) => pageErrors.push(String(e)))

    await page.goto(`${srv.baseUrl}/share/`)
    await expect(page.locator('.card .title').first()).toBeVisible()

    const checks = [
      { label: '課程卡片標題 (.card .title)', selector: '.card .title' },
      { label: '課程卡片描述 (.card .desc)', selector: '.card .desc' },
      { label: '課程卡片中繼資訊 (.card .meta)', selector: '.card .meta' },
      { label: '分類膠囊 (.pill)', selector: '.pill' },
      { label: '頁面標題 (h1)', selector: 'h1' },
      { label: '麵包屑連結 (.crumbs a)', selector: '.crumbs a' },
      { label: '導言 (.lede)', selector: '.lede' },
      { label: '頁尾 (footer)', selector: 'footer' },
      { label: '主題選單按鈕 (.tp-btn)', selector: '.tp-btn' },
    ]

    for (const theme of THEMES) {
      await selectTheme(page, theme.id)
      const res = await auditPageContrast(page, checks)
      expect(res.failures, `/share/ 主題 ${theme.id} 對比度失敗：\n${res.failures.join('\n')}`).toEqual([])
    }
    expect(pageErrors).toEqual([])
  })

  test('/share/math-study-method/ 數學課在 6 組主題下所有條目標籤、徽章、表格、便利貼與心智圖皆達 ≥ 4.5:1', async ({ page }) => {
    const pageErrors = []
    page.on('pageerror', (e) => pageErrors.push(String(e)))

    await page.goto(`${srv.baseUrl}/share/math-study-method/`)
    await expect(page.locator('h1')).toBeVisible()
    // 展開所有「課本的寫法」折疊區塊，並開啟浮動目錄、顯示「回上一處」按鈕與心智圖滑動提示，確保所有新增元件皆驗證對比度
    await page.evaluate(() => {
      document.querySelectorAll('details').forEach((d) => { d.open = true })
      const backBtn = document.getElementById('read-back')
      if (backBtn) backBtn.hidden = false
      document.querySelectorAll('.map-shell').forEach((s) => s.classList.add('is-scrollable'))
    })
    await page.locator('#read-toc-btn').click()
    await expect(page.locator('#read-toc')).toBeVisible()

    const checks = [
      { label: '定義條目標籤 (.item.def .tag)', selector: '.item.def .tag' },
      { label: '公設條目標籤 (.item.axm .tag)', selector: '.item.axm .tag' },
      { label: '定理條目標籤 (.item.thm .tag)', selector: '.item.thm .tag' },
      { label: '輔助定理條目標籤 (.item.lem .tag)', selector: '.item.lem .tag' },
      { label: '推論條目標籤 (.item.cor .tag)', selector: '.item.cor .tag' },
      { label: '一句話摘要徽章 (.sumtag)', selector: '.sumtag' },
      { label: '重點紅字 (.key)', selector: '.key' },
      { label: '螢光筆標記 (.hl)', selector: '.hl', checkHighlight: true },
      { label: '表格表頭 (th)', selector: 'th' },
      { label: '表格條目標籤 (td .tag)', selector: 'td .tag' },
      { label: '關聯晶片：定義 (a.chip.def)', selector: 'a.chip.def' },
      { label: '關聯晶片：公設 (a.chip.axm)', selector: 'a.chip.axm' },
      { label: '關聯晶片：定理 (a.chip.thm)', selector: 'a.chip.thm' },
      { label: '關聯晶片：輔助定理 (a.chip.lem)', selector: 'a.chip.lem' },
      { label: '關聯晶片：推論 (a.chip.cor)', selector: 'a.chip.cor' },
      { label: '便利貼大字 (.sticky .big)', selector: '.sticky .big' },
      { label: '便利貼說明 (.sticky small)', selector: '.sticky small' },
      { label: '目錄連結 (.toc a)', selector: '.toc a' },
      { label: '提示框 (.note)', selector: '.note' },
      { label: '簡式連接詞 (.kw)', selector: '.kw' },
      { label: '結果編號 (.n.r)', selector: '.n.r' },
      { label: '浮動閱讀按鈕 (.read-btn)', selector: '.read-btn' },
      { label: '浮動回上一處按鈕 (.read-btn-back)', selector: '.read-btn-back' },
      { label: '浮動目錄標題 (.read-toc-head strong)', selector: '.read-toc-head strong' },
      { label: '浮動目錄關閉鈕 (.read-toc-close)', selector: '.read-toc-close' },
      { label: '浮動目錄連結 (.read-toc-list a)', selector: '.read-toc-list a' },
      { label: '浮動目錄目前章節 (.read-toc-list a.active)', selector: '.read-toc-list a.active' },
      { label: '心智圖滑動提示 (.map-hint)', selector: '.map-hint' },
    ]

    for (const theme of THEMES) {
      await selectTheme(page, theme.id)
      // selectTheme 點擊主題按鈕會收起目錄抽屜，這裡重新打開以涵蓋目錄抽屜對比度
      if (await page.locator('#read-toc').isHidden()) {
        await page.locator('#read-toc-btn').click()
        await expect(page.locator('#read-toc')).toBeVisible()
      }
      const res = await auditPageContrast(page, checks)
      expect(res.svgChecked, `主題 ${theme.id} 應驗證 26 個心智圖節點文字`).toBe(52)
      expect(res.failures, `/share/math-study-method/ 主題 ${theme.id} 對比度失敗：\n${res.failures.join('\n')}`).toEqual([])
    }
    expect(pageErrors).toEqual([])
  })
})
