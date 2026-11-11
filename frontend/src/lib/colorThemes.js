// 色彩主題：預設「手帳米白」+ 5 組常見配色。
// 色票本身在 assets/main.css（預設）與 assets/themes.css（其餘），這裡只負責
// 記住使用者的選擇、把 data-theme 設到 <html>。index.html 有一小段相同邏輯在
// 載入前先套用，避免換頁時閃一下預設色。
import { reactive } from 'vue'

export const THEME_KEY = 'finlab.colorTheme.v1'
export const ROUGH_KEY = 'finlab.roughLines.v1'
export const DEFAULT_THEME_ID = 'notebook'

// swatch：選單上的小色塊（紙、墨、重點色），讓使用者不用切換就能預覽。
export const COLOR_THEMES = [
  { id: 'notebook', name: '手帳米白', hint: '預設・淺色', swatch: ['#FFFDF7', '#2B2B33', '#17807C'] },
  { id: 'dark', name: '夜間深色', hint: '深色', swatch: ['#0d1322', '#e8edf5', '#4fd1c5'] },
  { id: 'solarized', name: 'Solarized', hint: '淺色・低對比', swatch: ['#fdf6e3', '#073642', '#1f7f79'] },
  { id: 'nord', name: 'Nord', hint: '深色・冷灰藍', swatch: ['#2e3440', '#eceff4', '#88c0d0'] },
  { id: 'dracula', name: 'Dracula', hint: '深色・紫粉', swatch: ['#282a36', '#f8f8f2', '#bd93f9'] },
  { id: 'gruvbox', name: 'Gruvbox', hint: '深色・復古暖棕', swatch: ['#282828', '#ebdbb2', '#8ec07c'] },
]

const IDS = COLOR_THEMES.map((t) => t.id)

function read(key) {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key, value) {
  try { localStorage.setItem(key, value) } catch { /* 無痕模式等：這次有效就好 */ }
}

export function normalizeThemeId(id) {
  return IDS.includes(id) ? id : DEFAULT_THEME_ID
}

const state = reactive({
  id: normalizeThemeId(read(THEME_KEY)),
  rough: read(ROUGH_KEY) !== 'off',
})

function applyToDom() {
  const root = document.documentElement
  if (state.id === DEFAULT_THEME_ID) root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', state.id)
  root.setAttribute('data-rough', state.rough ? 'on' : 'off')
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) {
    const bg = getComputedStyle(root).getPropertyValue('--side').trim()
    if (bg) meta.setAttribute('content', bg)
  }
}

// App 啟動時呼叫一次，把上次的選擇套回。
export function applySavedColorTheme() {
  applyToDom()
}

// 主題變了：通知圖表重讀色票、通知頁面重畫（見 App.vue 的 themeTick）。
function announce() {
  window.dispatchEvent(new CustomEvent('finlab:theme-change', { detail: { id: state.id } }))
}

export function useColorTheme() {
  function setTheme(id) {
    const next = normalizeThemeId(id)
    if (next === state.id) return
    state.id = next
    write(THEME_KEY, next)
    applyToDom()
    announce()
  }
  function setRough(on) {
    state.rough = !!on
    write(ROUGH_KEY, state.rough ? 'on' : 'off')
    applyToDom()
  }
  return { state, themes: COLOR_THEMES, setTheme, setRough }
}
