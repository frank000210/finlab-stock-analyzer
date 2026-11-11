// 把任何 CSS 顏色（#hex、rgb()、color-mix()、var() 展開後的字串…）請瀏覽器算成 rgb()/rgba() 字串。
// 為什麼要這一層：主題的衍生色多半是 color-mix()，getPropertyValue 回傳的是原文字；而
// getComputedStyle().color 遇到帶透明度的 color-mix 會回傳 "color(srgb 0.75 0.22 0.21 / 0.14)"，
// lightweight-charts 與 d3 都不認得這種寫法（會丟 Cannot parse color）。這裡統一轉成 rgb()/rgba()。
let probe = null

export function resolveCssColor(raw) {
  if (!raw || typeof document === 'undefined') return null
  if (!probe) {
    probe = document.createElement('span')
    probe.style.cssText = 'position:absolute;width:0;height:0;visibility:hidden;pointer-events:none'
    document.body.appendChild(probe)
  }
  probe.style.color = ''
  probe.style.color = raw
  if (!probe.style.color) return null // 瀏覽器不認得這個值
  const out = getComputedStyle(probe).color
  if (/^rgba?\(/.test(out)) return out
  const m = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+%?))?\s*\)$/.exec(out)
  if (!m) return out
  const ch = (v) => Math.max(0, Math.min(255, Math.round(parseFloat(v) * 255)))
  let a = m[4] == null ? 1 : (m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]))
  a = Math.round(a * 1000) / 1000
  return a >= 1 ? `rgb(${ch(m[1])}, ${ch(m[2])}, ${ch(m[3])})` : `rgba(${ch(m[1])}, ${ch(m[2])}, ${ch(m[3])}, ${a})`
}

// #rrggbb（忽略透明度），給 <input type="color"> 用
export function resolveCssHex(raw) {
  const rgb = resolveCssColor(raw)
  const m = rgb && /rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(rgb)
  if (!m) return null
  return '#' + [m[1], m[2], m[3]].map((n) => Number(n).toString(16).padStart(2, '0')).join('')
}
