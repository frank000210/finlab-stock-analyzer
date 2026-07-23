// Y1：觀察清單共用邏輯。原本 DecisionView/GraphView/Graph01View/RotationView
// 各自複製一份幾乎相同的 load/save/add/remove，這裡統一成單一事實來源。
//
// 順便修正一個既存的行為問題：GraphView/RotationView 原本把「這次要畫圖/
// 聚合的股票組合」跟「共用觀察清單」用同一把 localStorage key 存——使用者
// 在那兩頁輸入任意股票組合按套用，會直接覆蓋掉 DecisionView/作戰台在用
// 的真正觀察清單，且使用者完全不會發現。這裡把兩件事拆開：本模組的
// WATCHLIST_STORAGE_KEY 只給「真正的觀察清單」讀寫；頁面自己暫存的股票
// 組合改用各頁自己的 key（不歸這個模組管，呼叫端自行處理）。
//
// 同分頁內的跨元件同步：沿用 B2/F3/G1 已建立的慣例——原生 `storage` 事件
// 只在「其他分頁」修改 localStorage 時觸發，同一分頁內不會自動觸發。這裡
// 用 `new StorageEvent('storage', ...)` 手動派發，讓既有／未來在其他頁面
// 掛的 `window.addEventListener('storage', ...)` 監聽器不需要額外接線就能
// 同分頁即時收到觀察清單變化。

export const WATCHLIST_STORAGE_KEY = 'finlab_watchlist'
const META_STORAGE_KEY = 'finlab_watchlist_meta'

export function uniqueSymbols(items) {
  return [...new Set(
    (items || [])
      // DD10：CommandView/PortfolioHeatView 各自對同一把 key 多防了一手
      // 「萬一存的是 {symbol: '2330'} 這種物件形狀」，這裡原本沒有——
      // String(物件) 會變成 "[object Object]"，悄悄弄丟舊格式資料。把
      // 這兩處已經在用的防呆邏輯搬進共用模組，兩處才能真的改用同一份。
      .map(item => String(typeof item === 'string' ? item : (item?.symbol || '')).trim().toUpperCase())
      .filter(Boolean)
  )]
}

function dispatchChange(newValue) {
  try {
    window.dispatchEvent(new StorageEvent('storage', {
      key: WATCHLIST_STORAGE_KEY,
      newValue,
      storageArea: localStorage,
    }))
  } catch {
    // StorageEvent 建構子在極舊瀏覽器可能不支援 init dict，同分頁即時同步
    // 是加值體驗、不是必要功能，失敗就算了，不影響觀察清單本身已存好
  }
}

export function loadWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? uniqueSymbols(parsed) : []
  } catch {
    return []
  }
}

export function saveWatchlist(list) {
  const normalized = uniqueSymbols(list)
  const raw = JSON.stringify(normalized)
  localStorage.setItem(WATCHLIST_STORAGE_KEY, raw)
  dispatchChange(raw)
  return normalized
}

export function addToWatchlist(symbol) {
  return saveWatchlist([symbol, ...loadWatchlist()])
}

export function removeFromWatchlist(symbol) {
  const target = String(symbol || '').trim().toUpperCase()
  const next = loadWatchlist().filter(s => s !== target)
  saveWatchlist(next)
  // 從觀察清單移除時，附帶的分組/備註也一併清掉，避免孤兒資料累積
  const meta = loadWatchlistMeta()
  if (meta[target]) {
    delete meta[target]
    saveWatchlistMeta(meta)
  }
  return next
}

export function reorderWatchlist(fromIndex, toIndex) {
  const list = loadWatchlist()
  if (fromIndex < 0 || fromIndex >= list.length || toIndex < 0 || toIndex >= list.length) return list
  const [moved] = list.splice(fromIndex, 1)
  list.splice(toIndex, 0, moved)
  // 這裡不能再走 uniqueSymbols（保證去重不保證我們要的順序在 Set 語意下
  // 剛好被保留，寧可直接寫入已經手動排好序的陣列）
  const raw = JSON.stringify(list)
  localStorage.setItem(WATCHLIST_STORAGE_KEY, raw)
  dispatchChange(raw)
  return list
}

// 分組/備註（Y1 新增，選填）：{ SYMBOL: { group: string, note: string } }
export function loadWatchlistMeta() {
  try {
    const raw = localStorage.getItem(META_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function saveWatchlistMeta(meta) {
  localStorage.setItem(META_STORAGE_KEY, JSON.stringify(meta || {}))
}

export function setWatchlistMeta(symbol, patch) {
  const target = String(symbol || '').trim().toUpperCase()
  const meta = loadWatchlistMeta()
  meta[target] = { ...(meta[target] || {}), ...patch }
  saveWatchlistMeta(meta)
  return meta
}
