// 交易數學共用模組（B1）：R 倍數、每股風險、損益與交易日誌讀寫。
// JournalView / CommandView / RiskSizingView / useJournalRisk 過去各自複製
// 這些公式，日後若調整定義（例如納入手續費），容易改一處漏三處，統一收斂
// 在這裡。所有函式都吃交易日誌的單筆 trade 物件（entry/stop/exit/side/lots）。

export const JOURNAL_KEY = 'finlab_trade_journal'

// F1：本地（使用者所在時區）日期字串 YYYY-MM-DD。toISOString() 回傳的是
// UTC 日期，凌晨到天亮這段時間（台灣 UTC+8）記錄的交易會被蓋成「昨天」，
// 導致單日虧損熔斷、過度交易偵測、當日交易數全部算錯天——這個 app 也看
// 美股，半夜盯盤後平倉正好踩到。日誌相關的「現在是哪一天」一律用這個，
// 不要用 new Date().toISOString().slice(0, 10)。
export function localDateStr(date = new Date()) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function riskPerShare(t) {
  return Math.abs((Number(t.entry) || 0) - (Number(t.stop) || 0))
}

// exitPrice 預設用已平倉的 exit；傳入現價即為未實現版本。
export function profitPerShare(t, exitPrice = t.exit) {
  const diff = (Number(exitPrice) || 0) - (Number(t.entry) || 0)
  return t.side === 'short' ? -diff : diff
}

export function realizedR(t) {
  const risk = riskPerShare(t)
  return risk > 0 ? profitPerShare(t) / risk : 0
}

export function tradePnl(t, exitPrice = t.exit) {
  return (Number(t.lots) || 0) * 1000 * profitPerShare(t, exitPrice)
}

export function riskAmount(t) {
  return (Number(t.lots) || 0) * 1000 * riskPerShare(t)
}

export function loadJournal() {
  try {
    const raw = JSON.parse(localStorage.getItem(JOURNAL_KEY) || '[]')
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export function saveJournal(trades) {
  localStorage.setItem(JOURNAL_KEY, JSON.stringify(trades))
}

// F2：凱利公式（作戰台、部位風控共用）。f* = W×(PF-1)/PF；winRate 為 0-1
// 小數、profitFactor 為獲利因子。沒有數學優勢（PF≤1 或勝率為 0/1）回傳 0
// ——勝率剛好 100% 幾乎必然是樣本太小的假象，不當作真的邊界情況推薦重倉。
export function kellyFraction(winRate, profitFactor) {
  const w = winRate || 0
  const pf = profitFactor || 0
  if (w <= 0 || w >= 1 || pf <= 1) return 0
  return Math.max(0, w * (pf - 1) / pf)
}

// 半凱利建議單筆風險%：全凱利波動過大，實務取半凱利；上限 10% 純粹是
// 防呆，避免極端樣本算出離譜數字。
export function halfKellyRiskPct(winRate, profitFactor) {
  return Math.min(kellyFraction(winRate, profitFactor) * 0.5 * 100, 10)
}

// 已平倉統計（勝率/獲利因子）：凱利建議（作戰台、部位風控）共用。
export function journalWinStats(closed) {
  const pnls = closed.map((t) => tradePnl(t))
  const wins = pnls.filter((p) => p > 0)
  const grossWin = wins.reduce((a, b) => a + b, 0)
  const grossLoss = Math.abs(pnls.filter((p) => p < 0).reduce((a, b) => a + b, 0))
  return {
    count: closed.length,
    winRate: closed.length ? wins.length / closed.length : 0,
    profitFactor: grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? 99.99 : 0),
  }
}
