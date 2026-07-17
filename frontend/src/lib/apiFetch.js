// S5：後端短暫斷線時（例如今天遇到的 Docker/WSL 環境不穩定），原本任何一
// 個 fetch 打一次失敗就直接放棄、顯示錯誤，不會在後端恢復後自動重試。這裡
// 提供一個輕量的重試+退避包裝：只在網路層失敗（連不上/逾時）或 5xx（伺服
// 器端暫時性錯誤）時重試；4xx 是請求本身的問題（參數錯、404），重試沒有
// 意義，直接回傳讓呼叫端照舊處理。
const DEFAULT_RETRIES = 2
const DEFAULT_BASE_DELAY_MS = 400

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// 用法跟原生 fetch 一樣，多了第三個選填參數控制重試次數/退避間隔。
export async function fetchWithRetry(url, options = {}, { retries = DEFAULT_RETRIES, baseDelayMs = DEFAULT_BASE_DELAY_MS } = {}) {
  let lastError
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const resp = await fetch(url, options)
      if (resp.status >= 500 && attempt < retries) {
        lastError = new Error(`HTTP ${resp.status}`)
        await sleep(baseDelayMs * 2 ** attempt)
        continue
      }
      return resp
    } catch (e) {
      lastError = e
      if (attempt < retries) {
        await sleep(baseDelayMs * 2 ** attempt)
        continue
      }
    }
  }
  throw lastError
}
