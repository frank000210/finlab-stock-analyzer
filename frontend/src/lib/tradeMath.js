// 交易數學共用模組（B1）：R 倍數、每股風險、損益與交易日誌讀寫。
// JournalView / CommandView / RiskSizingView / useJournalRisk 過去各自複製
// 這些公式，日後若調整定義（例如納入手續費），容易改一處漏三處，統一收斂
// 在這裡。所有函式都吃交易日誌的單筆 trade 物件（entry/stop/exit/side/lots）。

export const JOURNAL_KEY = 'finlab_trade_journal'

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
