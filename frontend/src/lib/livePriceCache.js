// E2 共用即時報價快取：交易日誌（未實現損益）與風控監控（C2 未實現回撤）
// 過去各自獨立呼叫 /api/v1/risk/sizing/{symbol}，同一個瀏覽器 session 裡若
// 兩頁都開過、且部位有重疊，會對同一批代碼重複打 FinMind（免費額度約
// 600 次/小時）。這裡用模組層級的快取（同一次頁面載入內存活，重新整理會
// 清空）+ 短 TTL，讓短時間內的重複查詢直接命中快取；同時對同一代碼的並發
// 請求去重（in-flight dedupe），避免兩個元件幾乎同時查同一檔各發一次。
//
// P4：快取的是整包 /risk/sizing 回應（不只 price/as_of），這樣投組風險頁
// （需要 name/industry/suggested_stops）跟分析頁（需要 setup）也能共用同一
// 份快取/去重，不用各自繞過去直接 fetch——四個頁面只要查同一檔、時間點夠
// 接近，就只打一次 FinMind。
const CACHE_TTL_MS = 60_000

const cache = new Map() // symbol -> { data, fetchedAt, error }
const inflight = new Map() // symbol -> Promise<entry>

async function fetchOne(symbol, apiBase) {
  const cached = cache.get(symbol)
  if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) return cached
  if (inflight.has(symbol)) return inflight.get(symbol)

  const promise = (async () => {
    try {
      const resp = await fetch(`${apiBase}/api/v1/risk/sizing/${encodeURIComponent(symbol)}`)
      const payload = await resp.json().catch(() => ({}))
      if (!resp.ok || !payload?.data || !(Number(payload.data.price) > 0)) {
        throw new Error(payload?.detail || '查價失敗')
      }
      const entry = { data: payload.data, fetchedAt: Date.now(), error: '' }
      cache.set(symbol, entry)
      return entry
    } catch (e) {
      // 失敗不快取（避免短暫錯誤在 TTL 內卡住），下次呼叫會重試。
      return { data: null, fetchedAt: Date.now(), error: e?.message || '查價失敗' }
    } finally {
      inflight.delete(symbol)
    }
  })()
  inflight.set(symbol, promise)
  return promise
}

// 回傳 { [symbol]: { price, as_of, error } }。price 為 null 代表查價失敗。
export async function fetchLivePrices(symbols, apiBase = import.meta.env.VITE_API_BASE ?? '') {
  const unique = [...new Set(symbols)].filter(Boolean)
  const results = {}
  await Promise.all(unique.map(async (sym) => {
    const entry = await fetchOne(sym, apiBase)
    results[sym] = { price: entry.data ? Number(entry.data.price) : null, as_of: entry.data?.as_of || '', error: entry.error }
  }))
  return results
}

// 回傳單一代碼的完整 /risk/sizing 回應資料（name/industry/price/atr/
// suggested_stops/setup/market_cap...），查價失敗回傳 null。
export async function fetchSizingData(symbol, apiBase = import.meta.env.VITE_API_BASE ?? '') {
  const entry = await fetchOne(symbol, apiBase)
  return entry.data
}

export function clearLivePriceCache() {
  cache.clear()
  inflight.clear()
}
