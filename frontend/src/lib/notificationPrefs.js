// Y2：設定頁的「價格突破通知」「技術訊號通知」勾選框原本從未被儲存或讀取
// ——使用者勾了也沒有任何效果，是純裝飾的假 UI。這裡補上真正的持久化，
// 並讓 PriceAlertView 的「新增警報」下拉選單依這裡的偏好決定顯示哪些類型，
// 讓這兩個勾選框第一次真正產生行為上的差異。
//
// 「AI 預測通知」目前還沒有對應的功能可以掛（AI 訊號警報是更大的獨立
// 功能，不在這批範圍內），先只做持久化，UI 上維持顯示但誠實不宣稱它
// 現在能做什麼。
const STORAGE_KEY = 'finlab_notification_prefs'
const DEFAULTS = { price: true, signal: true, ai: true }

export function loadNotificationPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw)
    return { ...DEFAULTS, ...(parsed && typeof parsed === 'object' ? parsed : {}) }
  } catch {
    return { ...DEFAULTS }
  }
}

export function saveNotificationPrefs(prefs) {
  const merged = { ...DEFAULTS, ...(prefs || {}) }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  return merged
}
