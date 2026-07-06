// 圖表配色統一入口:第一次呼叫才讀一次 getComputedStyle,之後所有圖表共用同一份快取,
// 避免每個 view 各自寫死 hex,換主題只需要改 main.css 的 --chart-* token。
let cached = null

export function useChartTheme() {
  if (cached) return cached
  const cs = getComputedStyle(document.documentElement)
  const v = (name, fallback) => cs.getPropertyValue(name).trim() || fallback
  cached = {
    up: v('--chart-up', '#10b981'),
    upStrong: v('--chart-up-strong', '#34d399'),
    down: v('--chart-down', '#ef4444'),
    downStrong: v('--chart-down-strong', '#f87171'),
    warn: v('--chart-warn', '#f59e0b'),
    blue: v('--chart-blue', '#3b82f6'),
    purple: v('--chart-purple', '#8b5cf6'),
    cyan: v('--chart-cyan', '#06b6d4'),
    neutral: v('--chart-neutral', '#94a3b8'),
    text: v('--chart-text', '#f1f5f9'),
    textSoft: v('--chart-text-soft', '#cbd5e1'),
    muted: v('--chart-muted', '#5b6b84'),
    grid: v('--chart-grid', 'rgba(148,163,184,0.06)'),
    border: v('--chart-border', 'rgba(148,163,184,0.14)'),
    upSoft: v('--chart-up-soft', 'rgba(239,68,68,0.12)'),
    downSoft: v('--chart-down-soft', 'rgba(16,185,129,0.12)'),
    // 相關係數負向色（恆紅，不隨漲紅跌綠翻轉）— 關聯圖/領先落後圖用
    negative: v('--chart-negative', '#ef4444'),
    negativeSoft: v('--chart-negative-soft', 'rgba(239,68,68,0.12)'),
  }
  return cached
}
