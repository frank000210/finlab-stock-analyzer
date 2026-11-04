// ETF 配息「來源」的純函式與瀏覽器端儲存。
//
// 來源＝每次配息裡，多少來自：收益（成分股股利、利息）、已實現資本利得、收益平準金、本金。
// 只在各投信的收益分配公告裡，免費資料源沒有；後端只收「有出處、驗證過」的人工整理資料
// （backend/app/analysis/etf_distribution.py），另外讓使用者把自己看到的公告數字填在這裡
// （只存在自己的瀏覽器，不上傳）。單位一律是「每受益權單位、元」。

export const PARTS = [
  { key: 'income', label: '收益（股利／利息）', short: '收益', color: 'var(--accent-blue)' },
  { key: 'gain', label: '已實現資本利得', short: '資本利得', color: 'var(--accent-purple)' },
  { key: 'equalization', label: '收益平準金', short: '平準金', color: 'var(--accent-cyan)' },
  { key: 'principal', label: '本金（其他）', short: '本金', color: 'var(--color-warning)' },
]

// 非收益來源（資本利得＋平準金＋本金）占比的門檻：> 25% 留意、> 50% 偏弱；有任何本金至少留意
export const NON_INCOME_LEVELS = [0.25, 0.5]
const STORAGE_KEY = 'finlab.etfDistSources.v1'

const num = v => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : 0)

export function total(pu) {
  return PARTS.reduce((a, p) => a + num(pu?.[p.key]), 0)
}

/** 每個組成占該次配息的比例（0～1）；合計不是正數就回 null。 */
export function shares(pu) {
  const t = total(pu)
  if (!(t > 0)) return null
  return Object.fromEntries(PARTS.map(p => [p.key, num(pu[p.key]) / t]))
}

/** 多次配息合併看：把各次的金額相加再算比例（金額大的那次影響較大）。 */
export function summarize(list) {
  const rows = (list || []).filter(pu => total(pu) > 0)
  if (!rows.length) return null
  const sum = Object.fromEntries(PARTS.map(p => [p.key, rows.reduce((a, pu) => a + num(pu[p.key]), 0)]))
  const t = Object.values(sum).reduce((a, b) => a + b, 0)
  const sh = Object.fromEntries(PARTS.map(p => [p.key, sum[p.key] / t]))
  const nonIncome = sh.gain + sh.equalization + sh.principal
  let level = nonIncome > NON_INCOME_LEVELS[1] ? 'bad' : nonIncome > NON_INCOME_LEVELS[0] ? 'warn' : 'good'
  if (level === 'good' && sh.principal > 0) level = 'warn'
  return { n: rows.length, shares: sh, nonIncome, level }
}

export const LEVEL_TEXT = {
  good: '配息主要來自成分股的股利與利息，來源相對可持續。',
  warn: '有一定比例來自資本利得、收益平準金或本金；市場轉弱時，這幾種來源會比股利先縮水。',
  bad: '超過一半不是來自股利與利息，這個配息水準比較難維持。',
}

/** 填的合計跟除息紀錄的配息金額差太多，多半是填錯期別或單位。 */
export function mismatch(pu, amount) {
  const t = total(pu)
  const a = Number(amount)
  if (!(t > 0) || !(a > 0)) return false
  return Math.abs(t - a) > Math.max(0.02, a * 0.05)
}

export function pctText(x, d = 0) {
  return (x * 100).toFixed(d) + '%'
}

// ── 瀏覽器端儲存：{ [symbol]: { [ex_date]: { income, gain, equalization, principal } } } ──
export function loadPersonal() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
  } catch {
    return {}
  }
}

export function savePersonal(all) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  } catch { /* 無痕模式或額度滿：這次存不起來，不影響頁面其他功能 */ }
}

/** 表單輸入 → 乾淨的 per_unit；任何欄位不是 ≥0 的數字，或合計 ≤ 0，回 { error }。空白當 0。 */
export function parseForm(form) {
  const out = {}
  for (const p of PARTS) {
    const raw = String(form?.[p.key] ?? '').trim()
    const v = raw === '' ? 0 : Number(raw)
    if (!Number.isFinite(v) || v < 0) return { error: `「${p.short}」需要是 0 或正數。` }
    out[p.key] = v
  }
  if (!(total(out) > 0)) return { error: '四項合計需要大於 0。' }
  return { value: out }
}
