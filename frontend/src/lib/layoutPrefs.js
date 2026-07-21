// Y10：頁面版面自訂（顯示/隱藏＋排序），存在 localStorage、每個頁面各自一把 key。
const PREFIX = 'finlab_layout_'

export function loadLayoutPrefs(pageKey, defaultOrder) {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFIX + pageKey) || 'null')
    if (raw && Array.isArray(raw.order) && Array.isArray(raw.hidden)) {
      // 若程式更新後新增了維度/區塊，補到順序最後、預設不隱藏；
      // 若舊設定裡有已經不存在的 key（維度被移除），一併濾掉。
      const known = new Set(raw.order)
      const merged = [
        ...raw.order.filter(k => defaultOrder.includes(k)),
        ...defaultOrder.filter(k => !known.has(k)),
      ]
      return { order: merged, hidden: raw.hidden.filter(k => defaultOrder.includes(k)) }
    }
  } catch { /* malformed，當作沒有設定 */ }
  return { order: [...defaultOrder], hidden: [] }
}

export function saveLayoutPrefs(pageKey, prefs) {
  try {
    localStorage.setItem(PREFIX + pageKey, JSON.stringify({ order: prefs.order, hidden: prefs.hidden }))
  } catch { /* storage 滿了或不可用，設定不保存但不影響當前畫面 */ }
}
