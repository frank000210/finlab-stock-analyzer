// F7 風控監控接真實資料：取代 backend risk_manager 的模擬亂數權益曲線，
// 改用「交易日誌」(localStorage finlab_trade_journal，與 F1-F6/複盤教練
// 同一份資料) 的已平倉紀錄，算出實際回撤(MDD)、實際當日交易筆數與熔斷狀態。
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref } from 'vue'
import { JOURNAL_KEY, loadJournal, riskPerShare, tradePnl, localDateStr } from '../lib/tradeMath'

const ACCOUNT_KEY = 'portfolio_heat_account'
const DEFAULT_ACCOUNT = 1_000_000

// A2 統一風控門檻：過去 MDD 儀表圖例(2/3%)、熔斷判定(6/10%)、當日交易
// 上限(UI 寫 15、實際 warn 12/pause 20) 三套數字互相矛盾。統一為一套可
// 自訂的設定（localStorage），衍生規則：交易數達上限的 80% 即 WARNING、
// 達上限即 PAUSED；MDD 達警戒% WARNING、達熔斷% PAUSED。
const CFG_KEYS = {
  mddWarn: 'finlab_mdd_warn_pct',
  mddPause: 'finlab_mdd_pause_pct',
  dailyLimit: 'finlab_daily_trade_limit',
}
const DEFAULTS = { mddWarn: 6, mddPause: 10, dailyLimit: 15 }

// CC7：circuitBreaker 回傳的英文列舉值(ACTIVE/WARNING/PAUSED)本身要保留
// 給 CSS class 判斷／字串比較用，不能直接改掉；顯示用的中文另外開一個
// 對照表，兩個畫面（風控監控／交易儀表板）共用同一份，不用各自維護一次。
export const CIRCUIT_LABELS = { ACTIVE: '正常', WARNING: '警戒', PAUSED: '暫停' }

function shiftDay(iso, deltaDays) {
  const d = new Date(iso)
  d.setDate(d.getDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}

export function useJournalRisk() {
  const journalTrades = ref([])
  const accountValue = ref(DEFAULT_ACCOUNT)
  const mddWarnPct = ref(DEFAULTS.mddWarn)
  const mddPausePct = ref(DEFAULTS.mddPause)
  const dailyTradeLimit = ref(DEFAULTS.dailyLimit)

  function reload() {
    journalTrades.value = loadJournal()
    unrealizedPnl.value = null // 日誌變了，舊的未實現數字不再可信，等頁面重抓
    const a = Number(localStorage.getItem(ACCOUNT_KEY))
    accountValue.value = a > 0 ? a : DEFAULT_ACCOUNT
    const warn = Number(localStorage.getItem(CFG_KEYS.mddWarn))
    const pause = Number(localStorage.getItem(CFG_KEYS.mddPause))
    const limit = Number(localStorage.getItem(CFG_KEYS.dailyLimit))
    mddWarnPct.value = warn > 0 ? warn : DEFAULTS.mddWarn
    mddPausePct.value = pause > 0 ? pause : DEFAULTS.mddPause
    dailyTradeLimit.value = limit >= 1 ? Math.floor(limit) : DEFAULTS.dailyLimit
  }

  function saveRiskConfig() {
    if (mddWarnPct.value > 0) localStorage.setItem(CFG_KEYS.mddWarn, String(mddWarnPct.value))
    if (mddPausePct.value > 0) localStorage.setItem(CFG_KEYS.mddPause, String(mddPausePct.value))
    if (dailyTradeLimit.value >= 1) localStorage.setItem(CFG_KEYS.dailyLimit, String(Math.floor(dailyTradeLimit.value)))
  }

  const closedTrades = computed(() =>
    journalTrades.value.filter((t) => t.status === 'closed' && t.exitDate && riskPerShare(t) > 0)
  )
  const openTrades = computed(() => journalTrades.value.filter((t) => t.status === 'open'))
  const hasJournalData = computed(() => closedTrades.value.length > 0)

  // C2 未實現損益：由頁面抓進行中部位的現價後設定（null = 不納入）。設定
  // 後權益曲線尾端會多出「今日現值」點，MDD 與熔斷因此能反映浮動虧損，
  // 而不是只看已平倉的結果——凹單中的部位正是最需要被熔斷看到的。
  const unrealizedPnl = ref(null)

  // 每個「有平倉紀錄的日期」一個資料點：帳戶起始資金 + 累計已實現損益。
  const equitySeries = computed(() => {
    const sorted = [...closedTrades.value].sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
    const byDay = new Map()
    for (const t of sorted) {
      const day = String(t.exitDate).slice(0, 10)
      byDay.set(day, (byDay.get(day) || 0) + tradePnl(t))
    }
    const days = [...byDay.keys()].sort()
    let points = []
    if (days.length) {
      let cum = accountValue.value
      points = [{ time: shiftDay(days[0], -1), value: Math.round(cum * 100) / 100 }]
      for (const day of days) {
        cum += byDay.get(day)
        points.push({ time: day, value: Math.round(cum * 100) / 100 })
      }
    }
    const extra = unrealizedPnl.value
    if (extra != null && openTrades.value.length) {
      const today = localDateStr()
      const base = points.length ? points[points.length - 1].value : accountValue.value
      const liveValue = Math.round((base + extra) * 100) / 100
      if (!points.length) {
        points = [{ time: shiftDay(today, -1), value: Math.round(accountValue.value * 100) / 100 }]
      }
      if (points[points.length - 1].time === today) {
        // 今天已有已實現的點：直接以「已實現+未實現」的現值取代，維持時間軸唯一遞增。
        points = [...points.slice(0, -1), { time: today, value: liveValue }]
      } else {
        points = [...points, { time: today, value: liveValue }]
      }
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
    const today = localDateStr()
    return journalTrades.value.filter((t) => t.openDate === today).length
  })

  const warnTrades = computed(() => Math.max(1, Math.ceil(dailyTradeLimit.value * 0.8)))
  const circuitBreaker = computed(() => {
    if (mddPercent.value >= mddPausePct.value || dailyTrades.value >= dailyTradeLimit.value) return 'PAUSED'
    if (mddPercent.value >= mddWarnPct.value || dailyTrades.value >= warnTrades.value) return 'WARNING'
    return 'ACTIVE'
  })
  const circuitBreakerLabel = computed(() => CIRCUIT_LABELS[circuitBreaker.value] || circuitBreaker.value)

  // B2 跨分頁同步：交易日誌在別的分頁（或視窗）新增/平倉時，storage 事件
  // 只會發到「其他」分頁——正好用來讓已開著的風控頁即時跟上，不用手動
  // 重新整理。只在元件 setup 情境下註冊，避免測試或非元件呼叫時洩漏監聽器。
  const watchedKeys = new Set([JOURNAL_KEY, ACCOUNT_KEY, ...Object.values(CFG_KEYS)])
  function onStorage(e) {
    if (!e.key || watchedKeys.has(e.key)) reload()
  }
  if (getCurrentInstance()) {
    onMounted(() => window.addEventListener('storage', onStorage))
    onBeforeUnmount(() => window.removeEventListener('storage', onStorage))
  }

  reload()

  return {
    journalTrades,
    accountValue,
    closedTrades,
    openTrades,
    hasJournalData,
    unrealizedPnl,
    equitySeries,
    portfolioValue,
    mddPercent,
    dailyTrades,
    dailyTradeLimit,
    mddWarnPct,
    mddPausePct,
    warnTrades,
    circuitBreaker,
    circuitBreakerLabel,
    reload,
    saveRiskConfig,
  }
}
