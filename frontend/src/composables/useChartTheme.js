// 圖表配色統一入口:第一次呼叫才讀一次 getComputedStyle,之後所有圖表共用同一份響應式快取,
// 避免每個 view 各自寫死 hex,換主題只需要改 main.css / themes.css 的 --chart-* token。
// 同時監聽 finlab:theme-change 與 <html data-theme/style> 變化，遞增 themeVersion，
// 讓圖表元件可以直接用記憶體中的資料原地重繪，不必重掛 router-view 或重打 API。
import { reactive, ref } from 'vue'
import { resolveCssColor } from '../lib/cssColor.js'

let cached = null
export const themeVersion = ref(0)

// token 現在多半是 color-mix()/var() 推導出來的，getPropertyValue 回傳的是原文字串，
// 圖表函式庫（lightweight-charts / d3）不一定認得；統一請瀏覽器算成 rgb()/rgba()（見 lib/cssColor.js）。
const resolveColor = (raw, fallback) => resolveCssColor(raw) || fallback

function readTokens() {
  if (typeof document === 'undefined') {
    return {
      up: '#C03936', upStrong: '#C03936', down: '#1C6E3B', downStrong: '#1C6E3B',
      warn: '#985105', blue: '#2A62C4', blueSoft: 'rgba(42,98,196,0.12)',
      purple: '#7454C2', cyan: '#12706C', neutral: '#666674',
      text: '#2B2B33', textSoft: '#4A4A56', muted: '#666674',
      well: '#FAF6ED', grid: 'rgba(43,43,51,0.11)', border: 'rgba(43,43,51,0.24)',
      upSoft: 'rgba(192,57,54,0.14)', downSoft: 'rgba(28,110,59,0.14)',
      negative: '#C03936', negativeSoft: 'rgba(192,57,54,0.14)',
    }
  }
  const cs = getComputedStyle(document.documentElement)
  const v = (name, fallback) => resolveColor(cs.getPropertyValue(name).trim(), fallback)
  return {
    up: v('--chart-up', '#10b981'),
    upStrong: v('--chart-up-strong', '#34d399'),
    down: v('--chart-down', '#ef4444'),
    downStrong: v('--chart-down-strong', '#f87171'),
    warn: v('--chart-warn', '#f59e0b'),
    blue: v('--chart-blue', '#3b82f6'),
    blueSoft: v('--blue-soft', 'rgba(59,130,246,0.15)'),
    purple: v('--chart-purple', '#8b5cf6'),
    cyan: v('--chart-cyan', '#06b6d4'),
    neutral: v('--chart-neutral', '#94a3b8'),
    text: v('--chart-text', '#f1f5f9'),
    textSoft: v('--chart-text-soft', '#cbd5e1'),
    muted: v('--chart-muted', '#5b6b84'),
    well: v('--bg-well', '#0f172a'), // 圖表畫布底色（跟著主題）
    grid: v('--chart-grid', 'rgba(148,163,184,0.06)'),
    border: v('--chart-border', 'rgba(148,163,184,0.14)'),
    upSoft: v('--chart-up-soft', 'rgba(239,68,68,0.12)'),
    downSoft: v('--chart-down-soft', 'rgba(16,185,129,0.12)'),
    // 相關係數負向色（恆紅，不隨漲紅跌綠翻轉）— 關聯圖/領先落後圖用
    negative: v('--chart-negative', '#ef4444'),
    negativeSoft: v('--chart-negative-soft', 'rgba(239,68,68,0.12)'),
  }
}

function syncThemeTokens(forceBump = false) {
  const next = readTokens()
  if (!cached) {
    cached = reactive(next)
    if (forceBump) themeVersion.value += 1
    return
  }
  let changed = false
  for (const key of Object.keys(next)) {
    if (cached[key] !== next[key]) {
      cached[key] = next[key]
      changed = true
    }
  }
  if (changed || forceBump) {
    themeVersion.value += 1
  }
}

export function useChartTheme() {
  if (!cached) cached = reactive(readTokens())
  return cached
}

export function getChartTheme() {
  return useChartTheme()
}

// 換色彩主題或改動 <html data-theme / style> 時原地更新快取並遞增 themeVersion，
// 讓各圖表元件監聽 themeVersion 原地重繪（零 API 重打）。
if (typeof window !== 'undefined') {
  window.addEventListener('finlab:theme-change', () => {
    syncThemeTokens(true)
  })
  if (typeof MutationObserver !== 'undefined' && document.documentElement) {
    const observer = new MutationObserver(() => {
      syncThemeTokens(false)
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'style'],
    })
  }
}
