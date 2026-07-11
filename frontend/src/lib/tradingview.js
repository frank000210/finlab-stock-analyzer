// D1 TradingView 代碼對應與外部連結。
// 台股（純數字代碼）掛 TWSE 前綴；美股等其他代碼直接用。上櫃(TPEx)股票用
// TWSE 前綴會解析失敗，屬已知限制——外部連結走 chart 搜尋模式無此問題。
export function toTvSymbol(sym) {
  const s = String(sym || '').trim().toUpperCase()
  return /^\d{4,6}[A-Z]?$/.test(s) ? `TWSE:${s}` : s
}

export function tvChartUrl(sym) {
  return `https://tw.tradingview.com/chart/?symbol=${encodeURIComponent(toTvSymbol(sym))}`
}
