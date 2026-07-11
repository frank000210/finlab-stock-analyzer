// F7 風控監控接真實資料：取代 backend risk_manager 的模擬亂數權益曲線，
// 改用「交易日誌」(localStorage finlab_trade_journal，與 F1-F6/複盤教練
// 同一份資料) 的已平倉紀錄，算出實際回撤(MDD)、實際當日交易筆數與熔斷狀態。
import { computed, ref } from 'vue'

const JOURNAL_KEY = 'finlab_trade_journal'
const ACCOUNT_KEY = 'portfolio_heat_account'
const DEFAULT_ACCOUNT = 1_000_000
export const DAILY_TRADE_LIMIT = 15

const WARN_MDD_PCT = 6
const PAUSE_MDD_PCT = 10
const WARN_TRADES = 12
const PAUSE_TRADES = 20

function riskPerShare(t) {
  return Math.abs((Number(t.entry) || 0) - (Number(t.stop) || 0))
}
function profitPerShare(t) {
  const diff = (Number(t.exit) || 0) - (Number(t.entry) || 0)
  return t.side === 'short' ? -diff : diff
}
function tradePnl(t) {
  return (Number(t.lots) || 0) * 1000 * profitPerShare(t)
}
function todayStr() {
  return new Date().toISOString().slice(0, 10)
}
function shiftDay(iso, deltaDays) {
  const d = new Date(iso)
  d.setDate(d.getDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}

export function useJournalRisk() {
  const journalTrades = ref([])
  const accountValue = ref(DEFAULT_ACCOUNT)

  function reload() {
    try {
      const raw = JSON.parse(localStorage.getItem(JOURNAL_KEY) || '[]')
      journalTrades.value = Array.isArray(raw) ? raw : []
    } catch {
      journalTrades.value = []
    }
    const a = Number(localStorage.getItem(ACCOUNT_KEY))
    accountValue.value = a > 0 ? a : DEFAULT_ACCOUNT
  }

  const closedTrades = computed(() =>
    journalTrades.value.filter((t) => t.status === 'closed' && t.exitDate && riskPerShare(t) > 0)
  )
  const hasJournalData = computed(() => closedTrades.value.length > 0)

  // 每個「有平倉紀錄的日期」一個資料點：帳戶起始資金 + 累計已實現損益。
  const equitySeries = computed(() => {
    const sorted = [...closedTrades.value].sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
    const byDay = new Map()
    for (const t of sorted) {
      const day = String(t.exitDate).slice(0, 10)
      byDay.set(day, (byDay.get(day) || 0) + tradePnl(t))
    }
    const days = [...byDay.keys()].sort()
    if (!days.length) return []
    let cum = accountValue.value
    const points = [{ time: shiftDay(days[0], -1), value: Math.round(cum * 100) / 100 }]
    for (const day of days) {
      cum += byDay.get(day)
      points.push({ time: day, value: Math.round(cum * 100) / 100 })
    }
    return points
  })

  const portfolioValue = computed(() => {
    const series = equitySeries.value
    return series.length ? series[series.length - 1].value : accountValue.value
  })

  const mddPercent = computed(() => {
    let peak = 0
    let maxDd = 0
    for (const p of equitySeries.value) {
      if (p.value > peak) peak = p.value
      if (peak > 0) maxDd = Math.max(maxDd, ((peak - p.value) / peak) * 100)
    }
    return Math.round(maxDd * 100) / 100
  })

  const dailyTrades = computed(() => {
    const today = todayStr()
    return journalTrades.value.filter((t) => t.openDate === today).length
  })

  const circuitBreaker = computed(() => {
    if (mddPercent.value >= PAUSE_MDD_PCT || dailyTrades.value >= PAUSE_TRADES) return 'PAUSED'
    if (mddPercent.value >= WARN_MDD_PCT || dailyTrades.value >= WARN_TRADES) return 'WARNING'
    return 'ACTIVE'
  })

  reload()

  return {
    journalTrades,
    accountValue,
    closedTrades,
    hasJournalData,
    equitySeries,
    portfolioValue,
    mddPercent,
    dailyTrades,
    dailyTradeLimit: DAILY_TRADE_LIMIT,
    circuitBreaker,
    reload,
  }
}
