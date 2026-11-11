// @ts-check
const { test, expect } = require('@playwright/test')

// 全站套用「筆記本＋手繪」外觀，右上角可選 6 組色彩主題（預設手帳米白＋5 組常見配色）。
// 色票定義在 frontend/src/assets/main.css（預設）與 themes.css（其餘）。

const THEMES = [
  { id: 'notebook', name: '手帳米白' },
  { id: 'dark', name: '夜間深色' },
  { id: 'solarized', name: 'Solarized' },
  { id: 'nord', name: 'Nord' },
  { id: 'dracula', name: 'Dracula' },
  { id: 'gruvbox', name: 'Gruvbox' },
]

const lum = (hex) => {
  const h = hex.replace('#', '')
  const c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const contrast = (a, b) => {
  const [la, lb] = [lum(a), lum(b)]
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** 讀出目前主題的基底色（都是 #rrggbb） */
async function readTokens(page) {
  return page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement)
    const names = ['paper', 'side', 'card', 'elev', 'well', 'ink', 'ink-2', 'muted', 'heading', 'blue', 'purple', 'cyan', 'up', 'down', 'warn', 'on-accent', 'desk']
    return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue('--' + n).trim()]))
  })
}

async function openMenu(page) {
  await page.getByTestId('theme-picker-btn').click()
  await expect(page.getByTestId('theme-picker-menu')).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  // 不跳「第一次來」橫幅，版面才穩定
  await page.addInitScript(() => { try { localStorage.setItem('finlab_onboarded', '1') } catch (e) { /* ignore */ } })
})

test('主題選單在頁面右上角，預設是手帳米白', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/settings')
  const btn = page.getByTestId('theme-picker-btn')
  await expect(btn).toBeVisible()
  await expect(btn).toContainText('手帳米白')
  const box = await btn.boundingBox()
  expect(box.y).toBeLessThan(80)
  expect(box.x + box.width).toBeGreaterThan(1280 - 80)
  expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBeNull()
})

test('選單列出 6 組主題（預設＋5 組常見配色），選了就即時套用並記住', async ({ page }) => {
  await page.goto('/settings')
  await openMenu(page)
  const items = page.locator('[data-testid="theme-picker-menu"] [role="option"]')
  await expect(items).toHaveCount(6)
  for (const t of THEMES) await expect(items.filter({ hasText: t.name })).toHaveCount(1)
  await page.keyboard.press('Escape')

  const papers = new Set()
  for (const t of THEMES) {
    await page.getByTestId('theme-picker-btn').click()
    await page.locator(`[data-theme-id="${t.id}"]`).click()
    await expect(page.getByTestId('theme-picker-menu')).toHaveCount(0)
    await expect(page.getByTestId('theme-picker-btn')).toContainText(t.name)
    const attr = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(attr).toBe(t.id === 'notebook' ? null : t.id)
    // 預設主題一開始就是目前的，重選不會寫入；其他主題選了就會記住
    if (t.id !== 'notebook') expect(await page.evaluate(() => localStorage.getItem('finlab.colorTheme.v1'))).toBe(t.id)
    papers.add((await readTokens(page)).paper)
  }
  expect(papers.size).toBe(6) // 每組主題的紙張底色都不同

  // 重新整理後保留最後選的主題（載入前就套用，不會閃回預設）
  await page.reload()
  expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe('gruvbox')
  await expect(page.getByTestId('theme-picker-btn')).toContainText('Gruvbox')
})

test('每組主題的文字對比都 ≥ 4.5:1，漲紅跌綠方向不變', async ({ page }) => {
  await page.goto('/settings')
  for (const t of THEMES) {
    await page.evaluate((id) => {
      if (id === 'notebook') document.documentElement.removeAttribute('data-theme')
      else document.documentElement.setAttribute('data-theme', id)
    }, t.id)
    const k = await readTokens(page)
    const bad = []
    for (const fg of ['ink', 'ink-2', 'muted', 'heading', 'blue', 'purple', 'cyan', 'up', 'down', 'warn']) {
      for (const bg of ['paper', 'side', 'card', 'elev', 'well']) {
        const r = contrast(k[fg], k[bg])
        if (r < 4.5) bad.push(`${fg} 在 ${bg} 上只有 ${r.toFixed(2)}`)
      }
    }
    for (const acc of ['blue', 'up', 'down', 'warn', 'purple']) {
      const r = contrast(k['on-accent'], k[acc])
      if (r < 4.5) bad.push(`按鈕字 on-accent 在 ${acc} 上只有 ${r.toFixed(2)}`)
    }
    expect(bad, `${t.id}：${bad.join('；')}`).toEqual([])

    // 台股慣例：漲＝紅、跌＝綠（每個主題都保留）
    const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
    const [ur, ug] = rgb(k.up)
    const [dr, dg] = rgb(k.down)
    expect(ur, `${t.id} 的 --up 要偏紅`).toBeGreaterThan(ug + 40)
    expect(dg, `${t.id} 的 --down 要偏綠`).toBeGreaterThan(dr)
  }
})

test('套用風格 7＋8：紙張橫線、手繪邊框、標楷體標題', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await expect(page.locator('h1').first()).toBeVisible()
  const h1Font = await page.evaluate(() => getComputedStyle(document.querySelector('h1')).fontFamily)
  await page.goto('/settings')
  await expect(page.locator('.card').first()).toBeVisible()
  const info = await page.evaluate(() => {
    const main = document.querySelector('.main-content')
    const mcs = getComputedStyle(main)
    const card = document.querySelector('.card')
    const before = getComputedStyle(card, '::before')
    return {
      sheetBg: mcs.backgroundImage,
      sheetBefore: getComputedStyle(main, '::before').content,
      cardBeforeFilter: before.filter,
      cardBeforeBorder: before.borderTopStyle,
      filterDefined: !!document.getElementById('sk-rough'),
    }
  })
  expect(info.sheetBg).toContain('repeating-linear-gradient') // 橫線
  expect(info.sheetBefore).not.toBe('none') // 線圈
  expect(info.filterDefined).toBe(true)
  expect(info.cardBeforeFilter).toContain('sk-rough')
  expect(info.cardBeforeBorder).toBe('solid')
  expect(h1Font).toMatch(/標楷體|BiauKai|Kaiti|DFKai/)
})

test('可以關掉手繪線條（卡片邊框不再抖動），選擇會記住', async ({ page }) => {
  await page.goto('/settings')
  await openMenu(page)
  const box = page.getByTestId('theme-rough')
  await expect(box).toBeChecked()
  await box.uncheck()
  expect(await page.evaluate(() => document.documentElement.getAttribute('data-rough'))).toBe('off')
  const f = await page.evaluate(() => getComputedStyle(document.querySelector('.card'), '::before').filter)
  expect(f).toBe('none')
  await page.reload()
  expect(await page.evaluate(() => document.documentElement.getAttribute('data-rough'))).toBe('off')
})

test('換主題會清掉設定頁的底色微調；舊版（v1）設定不會蓋掉新主題', async ({ page }) => {
  // 舊版把「全部欄位連同預設值」存在 finlab_theme_v1：不能再套用，否則新主題會被深色蓋住
  await page.addInitScript(() => {
    try {
      localStorage.setItem('finlab_theme_v1', JSON.stringify({ '--bg-primary': '#000000', '--bg-card': '#131b30' }))
    } catch (e) { /* ignore */ }
  })
  await page.goto('/settings')
  expect(await page.evaluate(() => document.documentElement.style.getPropertyValue('--bg-primary'))).toBe('')
  const paper = (await readTokens(page)).paper
  expect(await page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--bg-primary').trim())).toBeTruthy()

  // 微調（v2）：只存使用者改過的欄位
  await page.evaluate(() => localStorage.setItem('finlab_theme_v2', JSON.stringify({ '--bg-primary': '#123456' })))
  await page.reload()
  expect(await page.evaluate(() => document.documentElement.style.getPropertyValue('--bg-primary'))).toBe('#123456')

  await openMenu(page)
  await page.locator('[data-theme-id="nord"]').click()
  expect(await page.evaluate(() => document.documentElement.style.getPropertyValue('--bg-primary'))).toBe('')
  expect(await page.evaluate(() => localStorage.getItem('finlab_theme_v2'))).toBeNull()
  expect(paper).toMatch(/^#/)
})

test('手機寬度：選單不撐寬頁面、仍可選主題', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 760 })
  await page.goto('/settings')
  await expect(page.getByTestId('theme-picker-btn')).toBeVisible()
  await openMenu(page)
  const m = await page.getByTestId('theme-picker-menu').boundingBox()
  expect(m.x).toBeGreaterThanOrEqual(0)
  expect(m.x + m.width).toBeLessThanOrEqual(375)
  await page.locator('[data-theme-id="dracula"]').click()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})

test('每組主題下頁面都能正常載入，沒有 JS 錯誤', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  for (const t of THEMES) {
    for (const path of ['/settings', '/price-alerts', '/guide']) {
      await page.goto(path)
      await page.evaluate((id) => localStorage.setItem('finlab.colorTheme.v1', id), t.id)
      await page.reload() // 載入前的小腳本會依 localStorage 先套用主題
      expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe(t.id === 'notebook' ? null : t.id)
      await expect(page.getByTestId('theme-picker-btn')).toBeVisible()
      await expect(page.locator('.main-content')).toBeVisible()
    }
  }
  expect(errors).toEqual([])
})

// 圖表函式庫看不懂 color-mix() 算出來的 "color(srgb …)" 寫法（Cannot parse color）：
// 色票要先轉成 rgb()/rgba() 才能交給圖表（見 frontend/src/lib/cssColor.js）。
test('圖表頁在淺色與深色主題下都能畫出來，不會丟「Cannot parse color」', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  for (const id of ['notebook', 'dracula']) {
    await page.goto('/rotation')
    await page.evaluate((v) => localStorage.setItem('finlab.colorTheme.v1', v), id)
    await page.reload()
    await expect(page.locator('main svg').first()).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(1500)
  }
  expect(errors.filter((e) => /Cannot parse color/.test(e))).toEqual([])
})
