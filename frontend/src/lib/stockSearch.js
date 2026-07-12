// F5：股票代碼補中文名（best-effort）。交易日誌手動新增與交易核准中心核准
// 寫入日誌都只有代號，這裡統一查一次 /api/v1/stocks/search，避免兩處各寫
// 一份幾乎一樣的邏輯。查不到就回傳 null，呼叫端維持原本的代號顯示即可。
export async function resolveStockName(symbol, apiBase = import.meta.env.VITE_API_BASE ?? '') {
  const sym = String(symbol || '').trim().toUpperCase()
  if (!sym) return null
  try {
    const resp = await fetch(`${apiBase}/api/v1/stocks/search?q=${encodeURIComponent(sym)}`)
    const payload = await resp.json().catch(() => ({}))
    const items = payload?.data?.items || []
    const hit = items.find((i) => String(i.symbol).toUpperCase() === sym)
    return hit?.name_zh || null
  } catch {
    return null
  }
}
