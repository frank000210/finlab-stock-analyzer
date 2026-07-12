// E2 共用即時報價快取：交易日誌（未實現損益）與風控監控（C2 未實現回撤）
// 過去各自獨立呼叫 /api/v1/risk/sizing/{symbol}，同一個瀏覽器 session 裡若
// 兩頁都開過、且部位有重疊，會對同一批代碼重複打 FinMind（免費額度約
// 600 次/小時）。這裡用模組層級的快取（同一次頁面載入內存活，重新整理會
// 清空）+ 短 TTL，讓短時間內的重複查詢直接命中快取；同時對同一代碼的並發
// 請求去重（in-flight dedupe），避免兩個元件幾乎同時查同一檔各發一次。
const CACHE_TTL_MS = 60_000

const cache = new Map() // symbol -> { price, as_of, fetchedAt }
const inflight = new Map() // symbol -> Promise<entry>

async function fetchOne(symbol, apiBase) {
  const cached = cache.get(symbol)
  if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) return cached
  if (inflight.has(symbol)) return inflight.get(symbol)

  const promise = (async () => {
    try {
      const resp = await fetch(`${apiBase}/api/v1/risk/sizing/${encodeURIComponent(symbol)}`)
      const payload = await resp.json().catch(() => ({}))
      if (!resp.ok || !(Number(payload?.data?.price) > 0)) {
        throw new Error(payload?.detail || '查價失敗')
      }
      const entry = { price: Number(payload.data.price), as_of: payload.data.as_of || '', fetchedAt: Date.now(), error: '' }
      cache.set(symbol, entry)
      return entry
    } catch (e) {
      // 失敗不快取（避免短暫錯誤在 TTL 內卡住），下次呼叫會重試。
      return { price: null, as_of: '', fetchedAt: Date.now(), error: e?.message || '查價失敗' }
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
    results[sym] = await fetchOne(sym, apiBase)
  }))
  return results
}

export function clearLivePriceCache() {
  cache.clear()
  inflight.clear()
}
