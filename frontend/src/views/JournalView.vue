<template>
  <div class="journal-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">📓 觀測重點</span>
      系統會從你的實戰學習：記錄每筆進出場，算出<strong>你自己的</strong>勝率、期望值與 R 分布。這才是把工具變成系統的地基。
    </div>

    <!-- 統計總覽 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>交易日誌（Trade Journal）</h2>
          <p class="muted">以 R 倍數（每筆風險＝1R）衡量績效，勝率與期望值可回灌部位試算。</p>
        </div>
      </div>
      <div class="stat-cards">
        <div class="scard"><span class="slabel">已平倉筆數</span><strong class="sval">{{ stats.count }}</strong><span class="shint">進行中 {{ openTrades.length }}</span></div>
        <div class="scard"><span class="slabel">勝率</span><strong class="sval">{{ stats.count ? (stats.winRate * 100).toFixed(0) + '%' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">期望值 / 筆</span><strong class="sval" :class="stats.expectancyR >= 0 ? 'up' : 'down'">{{ stats.count ? stats.expectancyR.toFixed(2) + ' R' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">獲利因子</span><strong class="sval" :class="stats.profitFactor >= 1 ? 'up' : 'down'">{{ stats.count ? fmt(stats.profitFactor) : '—' }}</strong></div>
        <div class="scard"><span class="slabel">累計 R</span><strong class="sval" :class="stats.totalR >= 0 ? 'up' : 'down'">{{ stats.count ? (stats.totalR >= 0 ? '+' : '') + stats.totalR.toFixed(2) + ' R' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">累計損益</span><strong class="sval" :class="stats.totalPnl >= 0 ? 'up' : 'down'">{{ stats.count ? fmtInt(stats.totalPnl) : '—' }}</strong></div>
        <div class="scard"><span class="slabel">最大連虧</span><strong class="sval">{{ stats.count ? stats.maxConsecLoss : '—' }}</strong></div>
        <div class="scard"><span class="slabel">平均獲利 / 虧損</span><strong class="sval">{{ stats.count ? stats.avgWinR.toFixed(2) + ' / ' + stats.avgLossR.toFixed(2) + ' R' : '—' }}</strong></div>
      </div>

      <div v-if="equityPoints.length > 1" class="equity">
        <span class="slabel">權益曲線（累計 R）</span>
        <svg class="equity-svg" :viewBox="`0 0 ${eqW} ${eqH}`" preserveAspectRatio="none">
          <line :x1="0" :y1="eqZeroY" :x2="eqW" :y2="eqZeroY" class="eq-zero" />
          <polyline :points="equityPolyline" class="eq-line" :class="{ down: stats.totalR < 0 }" />
        </svg>
      </div>
    </section>

    <!-- 新增交易 -->
    <section class="section-block" v-reveal>
      <h3>記錄一筆交易</h3>
      <div class="add-form">
        <input v-model="form.symbol" class="inp w110" placeholder="代碼 2330" aria-label="股票代碼" />
        <select v-model="form.side" class="inp" aria-label="交易方向"><option value="long">做多</option><option value="short">做空</option></select>
        <input v-model.number="form.entry" type="number" class="inp w110" placeholder="進場價" step="0.05" aria-label="進場價" />
        <input v-model.number="form.stop" type="number" class="inp w110" placeholder="停損價" step="0.05" aria-label="停損價" />
        <input v-model.number="form.target" type="number" class="inp w110" placeholder="目標價(選填)" step="0.05" aria-label="目標價（選填）" />
        <input v-model.number="form.lots" type="number" class="inp w90" placeholder="張數" min="1" step="1" aria-label="張數" />
        <input v-model="form.tag" class="inp w110" placeholder="型態(選填)" aria-label="交易型態（選填）" />
        <input v-model="form.catalyst" class="inp w160" placeholder="進場理由/催化劑(選填)" aria-label="進場理由/催化劑（選填）" />
        <button class="btn btn-primary" @click="addTrade">加入</button>
        <button class="btn" @click="importOpenPositions">從投組帶入</button>
      </div>
      <p v-if="formError" class="error-text">{{ formError }}</p>
      <p v-if="importMsg" class="muted small">{{ importMsg }}</p>
    </section>

    <!-- 進行中 -->
    <section class="section-block" v-reveal v-if="openTrades.length">
      <div class="head-row">
        <h3>進行中（{{ openTrades.length }}）<span class="muted small paper-tag">🧾 紙上交易 — 沒有真的下單，練習盯盤與停損紀律</span></h3>
        <button class="btn" :disabled="pricesLoading" @click="fetchLivePricesForOpenTrades">
          <span v-if="pricesLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>🔄 更新現價
        </button>
      </div>
      <div class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>目標</th><th>張</th><th>風險(1R)</th><th>現價</th><th>未實現R</th><th>未實現損益</th><th>平倉價</th><th>動作</th></tr></thead>
          <tbody>
            <tr v-for="t in openTrades" :key="t.id" :class="{ 'row-breach': stopBreached(t) }">
              <td class="sym">
                {{ t.symbol }}<small>{{ t.name && t.name !== t.symbol ? ' ' + t.name : '' }}</small>
                <span v-if="t.catalyst" class="catalyst-tag" :title="`進場理由：${t.catalyst}`">📝</span>
                <span
                  v-if="nextEvent(t)"
                  class="event-tag"
                  :title="`${nextEvent(t).date} ${nextEvent(t).label}${nextEvent(t).estimated ? '（預估）' : ''} — 留倉過夜前留意這個地雷日`"
                >📅 {{ nextEvent(t).date.slice(5) }}</span>
              </td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ t.target ? fmt(t.target) : '—' }}</td>
              <td>{{ t.lots }}</td>
              <td>{{ fmtInt(riskAmount(t)) }}</td>
              <td>
                {{ livePrice(t) != null ? fmt(livePrice(t)) : '—' }}
                <span v-if="stopBreached(t)" class="breach-tag" title="現價已觸及停損">⚠已觸停損</span>
                <span
                  v-else-if="emaBroken(t)"
                  class="ema-tag"
                  :title="emaBrokenTitle(t)"
                >📉 跌破8EMA</span>
              </td>
              <td v-if="unrealizedR(t) != null"><strong :class="unrealizedR(t) >= 0 ? 'up' : 'down'">{{ unrealizedR(t) >= 0 ? '+' : '' }}{{ unrealizedR(t).toFixed(2) }}R</strong></td>
              <td v-else>—</td>
              <td :class="unrealizedPnl(t) != null ? (unrealizedPnl(t) >= 0 ? 'up' : 'down') : ''">
                {{ unrealizedPnl(t) != null ? fmtInt(unrealizedPnl(t)) : '—' }}
                <span
                  v-if="profitGivebackPct(t) != null && profitGivebackPct(t) >= PROFIT_GIVEBACK_WARN_PCT"
                  class="giveback-tag"
                  :title="`這筆單未實現獲利曾經最高到 ${fmtInt(t.peakUnrealizedPnl)}，目前已回吐 ${profitGivebackPct(t).toFixed(0)}%，考慮分批停利或移動停損`"
                >📉 回吐{{ profitGivebackPct(t).toFixed(0) }}%</span>
              </td>
              <td><input v-model.number="t._exitInput" type="number" class="inp w90" step="0.05" placeholder="價格" /></td>
              <td class="actions">
                <button class="btn xs" :disabled="livePrice(t) == null" title="用目前市價直接平倉" @click="closeAtMarket(t)">現價平倉</button>
                <button class="btn xs" @click="closeTrade(t)">平倉</button>
                <button class="del" @click="removeTrade(t.id)" title="刪除" aria-label="刪除交易紀錄">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="disclaimer">※ 紙上交易：未實現損益以最新市價估算，僅供練習與紀律訓練，非實際成交結果。</p>
    </section>

    <!-- 已平倉 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <h3>已平倉（{{ closedTrades.length }}）</h3>
        <div class="head-actions">
          <button class="btn" @click="triggerImport">匯入 CSV</button>
          <input ref="csvFileInput" type="file" accept=".csv,text/csv" class="hidden-file" @change="importCsv" />
          <button v-if="trades.length" class="btn" @click="exportCsv">匯出 CSV</button>
          <button v-if="trades.length" class="btn" @click="clearAll">清空全部</button>
        </div>
      </div>
      <p v-if="csvMsg" class="muted small csv-msg">{{ csvMsg }}</p>
      <div v-if="closedTrades.length" class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>出場</th><th>張</th><th>R 倍數</th><th>損益</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in closedTrades" :key="t.id">
              <td class="sym">
                {{ t.symbol }}<small>{{ t.name && t.name !== t.symbol ? ' ' + t.name : '' }}</small>
                <span v-if="t.catalyst" class="catalyst-tag" :title="`進場理由：${t.catalyst}`">📝</span>
              </td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ fmt(t.exit) }}</td>
              <td>{{ t.lots }}</td>
              <td><strong :class="realizedR(t) >= 0 ? 'up' : 'down'">{{ realizedR(t) >= 0 ? '+' : '' }}{{ realizedR(t).toFixed(2) }}R</strong></td>
              <td :class="pnl(t) >= 0 ? 'up' : 'down'">{{ fmtInt(pnl(t)) }}</td>
              <td><button class="del" @click="removeTrade(t.id)" title="刪除" aria-label="刪除交易紀錄">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">還沒有已平倉紀錄。記錄幾筆交易並平倉，系統就會算出你的實戰勝率與期望值。</p>
      <p class="disclaimer">※ R＝(出場−進場)/|進場−停損|（做空反向）。本工具僅為交易紀錄與統計，非投資建議。</p>
    </section>

    <!-- 複盤分析 -->
    <section class="section-block" v-reveal v-if="closedTrades.length">
      <h3>複盤分析</h3>
      <div class="analytics-grid">
        <div class="an-block" v-if="rHist">
          <span class="slabel">R 分布（{{ closedTrades.length }} 筆）——留意有沒有「凹單放大虧損」或「賺一點就跑」</span>
          <svg class="rhist-svg" :viewBox="`0 0 ${eqW} ${eqH}`" preserveAspectRatio="none">
            <line :x1="rHist.zeroX" y1="0" :x2="rHist.zeroX" :y2="eqH" class="rh-zero" />
            <rect v-for="(b, i) in rHist.bars" :key="i" :x="b.x" :y="eqH - b.h" :width="b.w" :height="b.h" :class="b.mid >= 0 ? 'bar-up' : 'bar-down'" />
          </svg>
          <div class="rhist-axis"><span>{{ rHist.min.toFixed(1) }}R</span><span>0</span><span>+{{ rHist.max.toFixed(1) }}R</span></div>
        </div>
        <div class="an-block">
          <span class="slabel">依型態統計（哪種設定最會賺，就多做那種）</span>
          <div class="table-wrap">
            <table class="j-table">
              <thead><tr><th>型態</th><th>筆數</th><th>勝率</th><th>期望值</th><th>累計 R</th></tr></thead>
              <tbody>
                <tr v-for="g in byTag" :key="g.tag">
                  <td class="sym">{{ g.tag }}</td>
                  <td>{{ g.count }}</td>
                  <td>{{ (g.winRate * 100).toFixed(0) }}%</td>
                  <td :class="g.expectancyR >= 0 ? 'up' : 'down'">{{ g.expectancyR >= 0 ? '+' : '' }}{{ g.expectancyR.toFixed(2) }}R</td>
                  <td><strong :class="g.totalR >= 0 ? 'up' : 'down'">{{ g.totalR >= 0 ? '+' : '' }}{{ g.totalR.toFixed(2) }}R</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- E15 複盤教練：從既有統計自動生成的紀律建議 -->
    <section class="section-block" v-reveal v-if="closedTrades.length">
      <h3>🎓 複盤教練</h3>
      <ul class="coach-list">
        <li v-for="(insight, i) in coachInsights" :key="i" class="coach-item" :class="'coach-' + insight.tone">
          <span class="coach-icon">{{ insight.icon }}</span>
          <span class="coach-text">{{ insight.text }}</span>
        </li>
      </ul>
      <p class="disclaimer">※ 教練建議由你自己的交易紀錄統計規則產生，僅供覆盤參考，非投資建議。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useStockStore } from '../stores/stock.js'
import { riskPerShare, profitPerShare, realizedR, tradePnl as pnl, riskAmount, loadJournal, saveJournal, localDateStr } from '../lib/tradeMath'
import { fetchLivePrices } from '../lib/livePriceCache'
import { useSparkline } from '../composables/useSparkline'
import { resolveStockName } from '../lib/stockSearch'

const stockStore = useStockStore()

const trades = ref([])
const form = reactive({ symbol: stockStore.symbol || '', side: 'long', entry: null, stop: null, target: null, lots: 1, tag: '', catalyst: '' })

// 側欄搜尋切換全站目前個股時，新增交易表單的代號欄位跟著換
// （只在使用者還沒動過欄位、或欄位仍是上一個全站個股時才更新，避免蓋掉
// 使用者正在手動輸入的其他代號）。
watch(() => stockStore.symbol, (sym, prevGlobalSym) => {
  if (sym && (!form.symbol || form.symbol === prevGlobalSym)) form.symbol = sym
})
const formError = ref('')
const importMsg = ref('')

const openTrades = computed(() => trades.value.filter(t => t.status === 'open'))
const openSymbols = computed(() => [...new Set(openTrades.value.map(t => t.symbol))].sort().join(','))

// E16 紙上交易：進行中的部位是「紙上」的（沒有真的下單），但用即時市價算
// 未實現損益，讓使用者練習盯盤/停損紀律，而不用真的冒風險。
const livePrices = ref({}) // symbol -> { price, as_of, loading, error }
const pricesLoading = ref(false)

// 進行中交易的代號組合一變（新增/帶入/刪除），就重新查一次現價。
watch(openSymbols, () => { fetchLivePricesForOpenTrades() })

// N1：波段留倉最怕撞上財報/除息等「地雷日」——當沖不用管這個，因為當天就平倉了。
// 進行中部位的代號一變就查一次行事曆，7 天內有事件就在該筆旁標警示。
const EVENT_WARN_DAYS = 7
const upcomingEvents = ref({}) // symbol -> [{date, type, label, estimated}]
watch(openSymbols, () => { fetchUpcomingEventsForOpenTrades() })

async function fetchUpcomingEventsForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  const today = new Date()
  const cutoff = new Date(today.getTime() + EVENT_WARN_DAYS * 86400000)
  await Promise.all(symbols.map(async (sym) => {
    try {
      const res = await fetch(`/api/v1/analysis/${sym}/calendar`)
      const json = await res.json()
      const events = json?.data?.events || []
      upcomingEvents.value[sym] = events.filter((e) => {
        const d = new Date(e.date + 'T00:00:00')
        return d >= today && d <= cutoff
      })
    } catch {
      upcomingEvents.value[sym] = []
    }
  }))
}

function nextEvent(t) {
  const events = upcomingEvents.value[t.symbol]
  return events && events.length ? events[0] : null
}

// N4：波段持倉的去留不看「抱了幾分鐘」，看「股價是否仍沿著 8 日均線走」——
// 日K實體收盤跌破 8EMA（多單）或站上 8EMA（空單）就是趨勢轉弱的訊號。
const EMA_PERIOD = 8
const emaTrend = ref({}) // symbol -> { ema8, lastClose, broken }
watch(openSymbols, () => { fetchEmaTrendForOpenTrades() })

function computeEma(closes, period) {
  if (closes.length < period) return null
  const k = 2 / (period + 1)
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period
  for (let i = period; i < closes.length; i++) ema = closes[i] * k + ema * (1 - k)
  return ema
}

async function fetchEmaTrendForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  await Promise.all(symbols.map(async (sym) => {
    try {
      const res = await fetch(`/api/v1/stocks/${sym}/price`)
      const json = await res.json()
      const items = json?.data?.items || []
      const closes = items.map(i => Number(i.close)).filter(Number.isFinite)
      const ema8 = computeEma(closes, EMA_PERIOD)
      const lastClose = closes.length ? closes[closes.length - 1] : null
      emaTrend.value[sym] = (ema8 == null || lastClose == null) ? null : { ema8, lastClose }
    } catch {
      emaTrend.value[sym] = null
    }
  }))
}

function emaBroken(t) {
  const info = emaTrend.value[t.symbol]
  if (!info) return false
  return t.side === 'long' ? info.lastClose < info.ema8 : info.lastClose > info.ema8
}

function emaBrokenTitle(t) {
  const info = emaTrend.value[t.symbol]
  if (!info) return ''
  return `日K收盤 ${fmt(info.lastClose)} 已${t.side === 'long' ? '跌破' : '站上'} 8 日均線 ${fmt(info.ema8)}，波段趨勢轉弱訊號`
}

async function fetchLivePricesForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  pricesLoading.value = true
  for (const sym of symbols) livePrices.value[sym] = { ...(livePrices.value[sym] || {}), loading: true, error: '' }
  const results = await fetchLivePrices(symbols)
  for (const sym of symbols) {
    const r = results[sym]
    livePrices.value[sym] = { price: r.price, as_of: r.as_of, loading: false, error: r.error }
  }
  pricesLoading.value = false
  updatePeakUnrealized()
}

// N2：波段停利看的是「這筆單曾經賺最多到多少，現在回吐了多少」，不是當沖的
// 「當日總損益回吐 30%」——用高水位（峰值未實現損益）當基準才抓得到。
function updatePeakUnrealized() {
  let changed = false
  for (const t of openTrades.value) {
    const pnl = unrealizedPnl(t)
    if (pnl == null) continue
    if (t.peakUnrealizedPnl == null || pnl > t.peakUnrealizedPnl) {
      t.peakUnrealizedPnl = pnl
      changed = true
    }
  }
  if (changed) save()
}

const PROFIT_GIVEBACK_WARN_PCT = 30

function profitGivebackPct(t) {
  const peak = t.peakUnrealizedPnl
  const pnl = unrealizedPnl(t)
  if (peak == null || pnl == null || peak <= 0) return null
  return Math.max(0, (peak - pnl) / peak * 100)
}

function livePrice(t) { return livePrices.value[t.symbol]?.price ?? null }
function unrealizedProfitPerShare(t) {
  const price = livePrice(t)
  return price == null ? null : profitPerShare(t, price)
}
function unrealizedR(t) {
  const pps = unrealizedProfitPerShare(t)
  if (pps == null) return null
  const risk = riskPerShare(t)
  return risk > 0 ? pps / risk : null
}
function unrealizedPnl(t) {
  const pps = unrealizedProfitPerShare(t)
  return pps == null ? null : (Number(t.lots) || 0) * 1000 * pps
}
function stopBreached(t) {
  const price = livePrice(t)
  if (price == null) return false
  return t.side === 'short' ? price >= Number(t.stop) : price <= Number(t.stop)
}
function closeAtMarket(t) {
  const price = livePrice(t)
  if (price == null) return
  t._exitInput = price
  closeTrade(t)
}
const closedTrades = computed(() => trades.value.filter(t => t.status === 'closed'))

const stats = computed(() => {
  const cl = closedTrades.value
  const n = cl.length
  if (!n) return { count: 0, winRate: 0, expectancyR: 0, profitFactor: 0, totalR: 0, totalPnl: 0, maxConsecLoss: 0, avgWinR: 0, avgLossR: 0 }
  const Rs = cl.map(realizedR)
  const pnls = cl.map(pnl)
  const wins = Rs.filter(r => r > 0)
  const losses = Rs.filter(r => r <= 0)
  const grossWin = pnls.filter(p => p > 0).reduce((a, b) => a + b, 0)
  const grossLoss = Math.abs(pnls.filter(p => p < 0).reduce((a, b) => a + b, 0))
  let maxConsec = 0, cur = 0
  for (const r of Rs) { if (r <= 0) { cur += 1; maxConsec = Math.max(maxConsec, cur) } else cur = 0 }
  return {
    count: n,
    winRate: wins.length / n,
    expectancyR: Rs.reduce((a, b) => a + b, 0) / n,
    profitFactor: grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? 99.99 : 0),
    totalR: Rs.reduce((a, b) => a + b, 0),
    totalPnl: pnls.reduce((a, b) => a + b, 0),
    maxConsecLoss: maxConsec,
    avgWinR: wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0,
    avgLossR: losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0,
  }
})

// cumulative-R equity curve
const equityPoints = computed(() => {
  let cum = 0
  const pts = [0]
  for (const t of closedTrades.value) { cum += realizedR(t); pts.push(cum) }
  return pts
})
const eqW = 600, eqH = 120
// R7：共用 sparkline composable，includeValue: 0 讓零線永遠落在圖表範圍內
// （權益曲線要看得到零線，不能因為全部都是正值/負值而被擠出畫面）。
const { points: equityPolyline, toY: eqToY } = useSparkline(equityPoints, { width: eqW, height: eqH, includeValue: 0 })
const eqZeroY = computed(() => eqToY.value(0))

// R-multiple distribution histogram
const rHist = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (!Rs.length) return null
  const min = Math.min(-1, ...Rs), max = Math.max(1, ...Rs)
  const bins = 16
  const range = (max - min) || 1
  const counts = new Array(bins).fill(0)
  for (const r of Rs) { let idx = Math.floor(((r - min) / range) * bins); if (idx >= bins) idx = bins - 1; if (idx < 0) idx = 0; counts[idx] += 1 }
  const maxC = Math.max(...counts, 1)
  const bw = eqW / bins
  return {
    min, max, zeroX: ((0 - min) / range) * eqW,
    bars: counts.map((c, i) => ({ x: i * bw, w: Math.max(bw - 1, 1), h: (c / maxC) * eqH, mid: min + (i + 0.5) * (range / bins) })),
  }
})

// group closed trades by 型態 tag
const byTag = computed(() => {
  const groups = {}
  for (const t of closedTrades.value) {
    const key = (t.tag && String(t.tag).trim()) || '未分類'
    if (!groups[key]) groups[key] = []
    groups[key].push(t)
  }
  return Object.entries(groups).map(([tag, arr]) => {
    const Rs = arr.map(realizedR)
    const totalR = Rs.reduce((a, b) => a + b, 0)
    return { tag, count: arr.length, winRate: Rs.filter(r => r > 0).length / arr.length, expectancyR: totalR / arr.length, totalR }
  }).sort((a, b) => b.totalR - a.totalR)
})

// F2 部位大小一致性：抓「哪幾筆押注明顯比平常大」（風險金額 ≥ 該交易者
// 自己歷史中位數的 1.5 倍），再看這些押得比較重的交易表現是不是反而比較
// 差——常是報復性下單/情緒化加碼的訊號，而非真的更有信心的紀律決策。
const sizeConsistency = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 8) return null
  const amounts = cl.map(riskAmount).filter(a => a > 0).sort((a, b) => a - b)
  if (amounts.length < 8) return null
  const mid = Math.floor(amounts.length / 2)
  const median = amounts.length % 2 ? amounts[mid] : (amounts[mid - 1] + amounts[mid]) / 2
  if (median <= 0) return null
  const oversized = cl.filter(t => riskAmount(t) >= median * 1.5)
  const normal = cl.filter(t => riskAmount(t) < median * 1.5)
  if (oversized.length < 3 || normal.length < 3) return null
  const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length
  return { count: oversized.length, oversizedR: avg(oversized.map(realizedR)), normalR: avg(normal.map(realizedR)) }
})

// F3 期望值趨勢（邊際衰退偵測）：把已平倉交易按出場日排序，比較「最近 N
// 筆」跟「更早之前」的期望值。以前有正期望值、最近卻明顯轉差，代表策略
// 邊際可能在衰退、市場體制變了，或是執行紀律開始鬆動——不是單純的運氣
// 波動，值得先降部位、重新檢視最近的交易，而不是照常加大力度想拗回來。
const RECENT_TREND_N = 10
const expectancyTrend = computed(() => {
  const cl = closedTrades.value
  const n = cl.length
  if (n < 20) return null
  const chrono = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const recent = chrono.slice(-RECENT_TREND_N)
  const earlier = chrono.slice(0, n - RECENT_TREND_N)
  if (!earlier.length) return null
  const avg = (arr) => arr.reduce((a, t) => a + realizedR(t), 0) / arr.length
  return { recentR: avg(recent), earlierR: avg(earlier), recentN: recent.length, earlierN: earlier.length }
})

// F4 過度交易偵測：把所有交易（不分已平倉/進行中）按進場日分組，算出「有
// 交易的那些天」典型一天做幾筆，再看有沒有哪天筆數暴增。不管那天賺賠，
// 單日筆數突然暴增本身就是衝動/報復性下單的訊號，跟結果無關。
const overtradingDay = computed(() => {
  const byDay = {}
  for (const t of trades.value) {
    if (!t.openDate) continue
    byDay[t.openDate] = (byDay[t.openDate] || 0) + 1
  }
  const counts = Object.values(byDay)
  if (counts.length < 5) return null
  const sorted = [...counts].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  if (median <= 0) return null
  let maxDay = null, maxCount = 0
  for (const [day, c] of Object.entries(byDay)) {
    if (c > maxCount) { maxCount = c; maxDay = day }
  }
  if (maxCount >= Math.max(4, median * 3)) {
    return { day: maxDay, count: maxCount, median }
  }
  return null
})

// F5 停損執行紀律：虧損交易的實際出場價，有沒有真的在停損價附近出場，還是
// 凹單讓虧損超過原本設定的停損（尤其做多不設停損就跑，虧更深）。這是「執行
// 有沒有照計畫」的問題，跟賺賠不對稱、部位大小、頻率都是不同角度。
const stopAdherence = computed(() => {
  const losers = closedTrades.value.filter(t => realizedR(t) < 0)
  if (losers.length < 5) return null
  const blownThrough = losers.filter((t) => {
    const risk = riskPerShare(t)
    if (risk <= 0) return false
    const diff = t.side === 'short' ? (Number(t.exit) || 0) - (Number(t.stop) || 0) : (Number(t.stop) || 0) - (Number(t.exit) || 0)
    return diff > risk * 0.1
  })
  if (blownThrough.length < 3) return null
  const ratio = blownThrough.length / losers.length
  if (ratio < 0.4) return null
  const avgBlownR = blownThrough.reduce((a, t) => a + realizedR(t), 0) / blownThrough.length
  return { count: blownThrough.length, total: losers.length, ratio, avgBlownR }
})

// E15 複盤教練：純用既有統計（stats/byTag）產生規則式建議，不打任何 API。
// tone 排序 bad > warn > good > info；最多顯示 6 條，避免資訊過載。
const coachInsights = computed(() => {
  const s = stats.value
  const out = []
  if (!s.count) return out

  // 1. 賺賠不對稱：平均獲利遠小於平均虧損（賺一點就跑、賠了拗單）
  if (s.avgWinR > 0 && s.avgLossR < 0 && s.avgWinR < Math.abs(s.avgLossR) * 0.8) {
    out.push({
      tone: 'bad', icon: '✂️',
      text: `平均獲利 ${s.avgWinR.toFixed(2)}R 小於平均虧損 ${Math.abs(s.avgLossR).toFixed(2)}R——典型「賺一點就跑、賠了拗單」。就算勝率不低也難賺錢，建議停損照設定執行、目標價至少拉到 1.5 倍風險。`,
    })
  }

  // 2. 停損執行紀律：虧損交易常常凹單超過原本設定的停損
  const sa = stopAdherence.value
  if (sa) {
    out.push({
      tone: 'bad', icon: '⛔',
      text: `近 ${sa.total} 筆虧損交易中，有 ${sa.count} 筆（${(sa.ratio * 100).toFixed(0)}%）實際出場價比原本設定的停損還差——代表停損常常沒有照計畫執行、放任虧損擴大（凹單）。這些凹過頭的交易平均 ${sa.avgBlownR.toFixed(2)}R，通常比乾脆照停損出場更慘。停損要嘛照設定執行、要嘛出場前先改單，別盤中臨時凹單。`,
    })
  }

  // 3. 連續虧損過多：情緒最容易在此時被放大成報復性下單
  if (s.maxConsecLoss >= 4) {
    out.push({
      tone: 'warn', icon: '🔥',
      text: `最長連續虧損 ${s.maxConsecLoss} 筆。連虧到第 3 筆之後最容易報復性下單、越做越大——建議連虧 3 筆就強制停手一天，冷靜後再上場。`,
    })
  }

  // 4. 整體期望值為負且樣本夠大：目前做法長期是虧錢的
  if (s.count >= 10 && s.expectancyR < 0) {
    out.push({
      tone: 'bad', icon: '📉',
      text: `近 ${s.count} 筆交易整體期望值為 ${s.expectancyR.toFixed(2)}R（負值）——照目前的做法長期會虧錢。先停手複盤找出問題，別急著加碼攤平想扳回來。`,
    })
  }

  // 5. 最拖累績效的型態：筆數夠多、期望值為負
  const tags = byTag.value
  const worstTag = tags.find(g => g.count >= 5 && g.expectancyR < 0)
  if (worstTag) {
    out.push({
      tone: 'warn', icon: '🚫',
      text: `「${worstTag.tag}」型態做了 ${worstTag.count} 次，期望值 ${worstTag.expectancyR.toFixed(2)}R——是拖累績效的主因，建議先停用這個 setup 或重新檢視進場條件。`,
    })
  }

  // 6. 表現最好的型態：值得集中火力
  const bestTag = tags.find(g => g.count >= 3 && g.expectancyR >= 0.3)
  if (bestTag) {
    out.push({
      tone: 'good', icon: '🎯',
      text: `「${bestTag.tag}」型態勝率 ${(bestTag.winRate * 100).toFixed(0)}%、期望值 +${bestTag.expectancyR.toFixed(2)}R，是目前表現最好的設定——之後可以優先找這種形態進場。`,
    })
  }

  // 7. 部位大小一致性：押得比平常大的那些單，表現反而更差
  const sc = sizeConsistency.value
  if (sc && sc.oversizedR < sc.normalR - 0.3) {
    out.push({
      tone: 'warn', icon: '⚖️',
      text: `押注明顯偏大（風險金額 ≥ 平時 1.5 倍）的 ${sc.count} 筆，平均 ${sc.oversizedR.toFixed(2)}R，比一般大小的 ${sc.normalR.toFixed(2)}R 還差——加碼的那幾筆常是情緒化決策而非紀律決策，建議把單筆風險金額固定下來，別憑感覺放大。`,
    })
  }

  // 8. 期望值趨勢：最近表現比先前基準明顯轉差（邊際衰退）
  const et = expectancyTrend.value
  if (et && et.earlierR > 0.1 && et.recentR < et.earlierR - 0.4) {
    out.push({
      tone: 'warn', icon: '🕰️',
      text: `最近 ${et.recentN} 筆期望值 ${et.recentR.toFixed(2)}R，比先前 ${et.earlierN} 筆的 ${et.earlierR.toFixed(2)}R 明顯轉差——留意是策略邊際真的在衰退、市場體制變了，還是自己執行紀律開始鬆動（提早出場、追高進場）。建議先降低部位到有把握的水準，重新檢視最近的交易。`,
    })
  }

  // 9. 過度交易：某天筆數暴增，不管賺賠都是衝動下單的訊號
  const ot = overtradingDay.value
  if (ot) {
    out.push({
      tone: 'warn', icon: '🌀',
      text: `${ot.day} 那天做了 ${ot.count} 筆交易，是你平常一天（中位數 ${ot.median} 筆）的 ${(ot.count / ot.median).toFixed(1)} 倍——單日爆量下單常是衝動/報復性交易的訊號，不管那天賺賠，都建議設下每日交易筆數上限。`,
    })
  }

  // 10. 樣本數不足：統計還不太可靠
  if (s.count < 15) {
    out.push({
      tone: 'info', icon: 'ℹ️',
      text: `目前只有 ${s.count} 筆已平倉紀錄，統計上還不太可靠。建議累積到至少 20-30 筆，再認真檢討要不要調整策略。`,
    })
  }

  // 11. 沒有任何警訊時的正向回饋
  if (!out.some(x => x.tone === 'bad' || x.tone === 'warn') && s.count >= 10 && s.expectancyR > 0 && s.profitFactor >= 1.5) {
    out.push({
      tone: 'good', icon: '✅',
      text: `期望值 +${s.expectancyR.toFixed(2)}R、獲利因子 ${s.profitFactor.toFixed(2)}，目前紀律執行得不錯——繼續保持，別因為手癢而破壞已經有效的作法。`,
    })
  }

  const order = { bad: 0, warn: 1, good: 2, info: 3 }
  return out.sort((a, b) => order[a.tone] - order[b.tone]).slice(0, 6)
})

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }

function save() { saveJournal(trades.value) }
function load() { trades.value = loadJournal() }

function addTrade() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  const entry = Number(form.entry), stop = Number(form.stop), lots = Math.floor(Number(form.lots) || 0)
  if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop) {
    formError.value = '請填代碼、有效的進場/停損價（不可相等）與至少 1 張。'
    return
  }
  const id = Date.now() + '-' + Math.random().toString(36).slice(2, 7)
  trades.value.unshift({
    id,
    symbol, name: symbol, side: form.side, entry, stop,
    target: Number(form.target) > 0 ? Number(form.target) : null,
    lots, tag: String(form.tag || '').trim(), catalyst: String(form.catalyst || '').trim(),
    openDate: localDateStr(), status: 'open',
    exit: null, exitDate: null,
  })
  save()
  resolveName(id, symbol) // 補上股票名稱（背景，代號伴隨名稱）
  form.symbol = ''; form.entry = null; form.stop = null; form.target = null; form.lots = 1; form.tag = ''; form.catalyst = ''
}

// 手動輸入只有代號 → 用搜尋 API 補中文名（best-effort，不阻塞新增）
async function resolveName(id, symbol) {
  const name = await resolveStockName(symbol)
  if (!name) return
  const t = trades.value.find(x => x.id === id)
  if (t) { t.name = name; save() }
}

function closeTrade(t) {
  const exit = Number(t._exitInput)
  if (!(exit > 0)) { formError.value = '請在該筆輸入有效的平倉價。'; return }
  formError.value = ''
  t.exit = exit
  t.exitDate = localDateStr()
  t.status = 'closed'
  delete t._exitInput
  save()
}

function removeTrade(id) {
  if (!window.confirm('確定要刪除這筆交易紀錄嗎？')) return
  trades.value = trades.value.filter(t => t.id !== id); save()
}
function clearAll() {
  if (!window.confirm(`確定要清空全部 ${trades.value.length} 筆交易紀錄嗎？localStorage 是唯一儲存位置，清掉就救不回來了。`)) return
  trades.value = []; save()
}

// A3 CSV 匯入：localStorage 是這份日誌唯一的儲存位置，瀏覽器清資料就全沒
// 了。既有的匯出 CSV 因此也是備份手段——但少了匯入就還原不了。這裡吃匯出
// 的同一種格式（欄位名相同即可，欄位順序不限），R/pnl 欄為衍生值直接忽略。
const csvFileInput = ref(null)
const csvMsg = ref('')
const CSV_MAX_BYTES = 5 * 1024 * 1024 // F5：一筆交易頂多百來個字元，5MB 已遠超正常日誌大小，超過視為誤選檔案，避免把大檔讀進來卡住畫面。

function triggerImport() { csvFileInput.value?.click() }

function importCsv(event) {
  const file = event.target.files?.[0]
  event.target.value = '' // 允許重選同一個檔案
  if (!file) return
  if (file.size > CSV_MAX_BYTES) {
    csvMsg.value = `匯入失敗：檔案 ${(file.size / 1024 / 1024).toFixed(1)}MB 超過上限 ${CSV_MAX_BYTES / 1024 / 1024}MB，請確認選對檔案。`
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    try { applyCsvImport(String(reader.result || '')) } catch (e) { csvMsg.value = '匯入失敗：' + (e?.message || '格式錯誤') }
  }
  reader.onerror = () => { csvMsg.value = '匯入失敗：讀取檔案錯誤。' }
  reader.readAsText(file)
}

function parseCsvText(text) {
  const s = String(text).replace(/^﻿/, '')
  const rows = []
  let row = [], cell = '', inQuotes = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') { cell += '"'; i++ } else inQuotes = false
      } else cell += c
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(cell); cell = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++
      row.push(cell); cell = ''
      if (row.some(v => v !== '')) rows.push(row)
      row = []
    } else {
      cell += c
    }
  }
  row.push(cell)
  if (row.some(v => v !== '')) rows.push(row)
  return rows
}

function applyCsvImport(text) {
  const rows = parseCsvText(text)
  if (rows.length < 2) { csvMsg.value = '匯入失敗：CSV 沒有資料列。'; return }
  const header = rows[0].map(h => h.trim())
  const idx = (name) => header.indexOf(name)
  for (const col of ['symbol', 'side', 'entry', 'stop', 'lots', 'openDate', 'status']) {
    if (idx(col) === -1) { csvMsg.value = `匯入失敗：缺少欄位 ${col}。`; return }
  }
  const get = (row, name) => { const i = idx(name); return i === -1 ? '' : (row[i] ?? '') }
  const dupKey = (t) => [t.symbol, t.side, t.entry, t.stop, t.lots, t.openDate, t.status, t.exit ?? '', t.exitDate ?? ''].join('|')
  const existing = new Set(trades.value.map(dupKey))
  let added = 0, skippedDup = 0, invalid = 0
  for (const row of rows.slice(1)) {
    const symbol = String(get(row, 'symbol')).trim().toUpperCase()
    const side = String(get(row, 'side')).trim() === 'short' ? 'short' : 'long'
    const entry = Number(get(row, 'entry'))
    const stop = Number(get(row, 'stop'))
    const lots = Math.floor(Number(get(row, 'lots')) || 0)
    const status = String(get(row, 'status')).trim() === 'closed' ? 'closed' : 'open'
    const exit = Number(get(row, 'exit'))
    if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop || (status === 'closed' && !(exit > 0))) {
      invalid += 1
      continue
    }
    const openDate = String(get(row, 'openDate')).slice(0, 10) || localDateStr()
    const exitDate = String(get(row, 'exitDate')).slice(0, 10)
    const t = {
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
      symbol, name: symbol, side, entry, stop,
      target: Number(get(row, 'target')) > 0 ? Number(get(row, 'target')) : null,
      lots, tag: String(get(row, 'tag') || '').trim(), catalyst: String(get(row, 'catalyst') || '').trim(),
      openDate, status,
      exit: status === 'closed' ? exit : null,
      exitDate: status === 'closed' ? (exitDate || openDate) : null,
    }
    if (existing.has(dupKey(t))) { skippedDup += 1; continue }
    existing.add(dupKey(t))
    trades.value.push(t)
    added += 1
  }
  save()
  csvMsg.value = `已匯入 ${added} 筆`
    + (skippedDup ? `、略過重複 ${skippedDup} 筆` : '')
    + (invalid ? `、忽略無效 ${invalid} 筆` : '') + '。'
}

function csvCell(v) { const s = String(v ?? ''); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s }
function exportCsv() {
  if (!trades.value.length) return
  const cols = ['symbol', 'side', 'entry', 'stop', 'target', 'lots', 'tag', 'catalyst', 'openDate', 'status', 'exit', 'exitDate', 'R', 'pnl']
  const lines = trades.value.map((t) => {
    const R = t.status === 'closed' ? realizedR(t).toFixed(3) : ''
    const p = t.status === 'closed' ? Math.round(pnl(t)) : ''
    return [t.symbol, t.side, t.entry, t.stop, t.target ?? '', t.lots, t.tag ?? '', t.catalyst ?? '', t.openDate, t.status, t.exit ?? '', t.exitDate ?? '', R, p].map(csvCell).join(',')
  })
  const csv = '﻿' + [cols.join(','), ...lines].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `trade-journal-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}

async function importOpenPositions() {
  importMsg.value = ''
  let positions = []
  try { const raw = JSON.parse(localStorage.getItem('portfolio_heat_positions') || '[]'); if (Array.isArray(raw)) positions = raw } catch { /* ignore */ }
  if (!positions.length) { importMsg.value = '投組是空的（先到「投組風險」建立部位）。'; return }
  const existing = new Set(openTrades.value.map(t => t.symbol))
  let added = 0
  for (const p of positions) {
    const symbol = String(p.symbol || '').trim().toUpperCase()
    if (!symbol || existing.has(symbol)) continue
    trades.value.unshift({
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
      symbol, name: p.name || symbol, side: (Number(p.entry) >= Number(p.stop)) ? 'long' : 'short',
      entry: Number(p.entry), stop: Number(p.stop), target: null,
      lots: Math.max(1, Math.floor(Number(p.lots) || 1)),
      openDate: localDateStr(), status: 'open', exit: null, exitDate: null,
    })
    added += 1
  }
  save()
  importMsg.value = added ? `已從投組帶入 ${added} 筆進行中交易。` : '投組標的都已在進行中交易內。'
}

onMounted(load)
</script>

<style scoped>
.journal-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2, .head-row h3 { margin: 0; }
.head-actions { display: flex; gap: 8px; }
.hidden-file { display: none; }
.csv-msg { margin: 4px 0 0; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.w110 { width: 110px; } .w90 { width: 90px; } .w160 { width: 160px; }

.stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }
.scard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; }
.slabel { font-size: 0.74rem; color: var(--text-muted); }
.sval { font-size: 1.35rem; }
.shint { font-size: 0.72rem; color: var(--text-muted); }

.equity { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.equity-svg { width: 100%; height: 120px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.eq-line { fill: none; stroke: #ef4444; stroke-width: 2; vector-effect: non-scaling-stroke; }
.eq-line.down { stroke: #22c55e; }
.eq-zero { stroke: var(--border-color); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 4 4; }

.add-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.table-wrap { overflow-x: auto; margin-top: 8px; }
.j-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.j-table th, .j-table td { text-align: right; padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.j-table th:first-child, .j-table td:first-child { text-align: left; }
.j-table th { color: var(--text-muted); font-weight: 500; font-size: 0.74rem; }
.sym small { color: var(--text-muted); }
.actions { display: flex; gap: 6px; align-items: center; justify-content: flex-end; }
.btn.xs { padding: 4px 10px; font-size: 0.78rem; }
.del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; }
.del:hover { color: #ef4444; }
.paper-tag { display: inline-block; margin-left: 10px; font-size: 0.74rem; font-weight: 400; vertical-align: middle; }
.row-breach { background: rgba(239, 68, 68, 0.06); }
.breach-tag { display: inline-block; margin-left: 4px; font-size: 0.7rem; color: #ef4444; white-space: nowrap; }
.event-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.catalyst-tag { display: inline-block; margin-left: 4px; font-size: 0.72rem; cursor: help; }
.giveback-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.ema-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }

.analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 8px; }
@media (max-width: 900px) { .analytics-grid { grid-template-columns: 1fr; } }
.an-block { display: flex; flex-direction: column; gap: 8px; }
.rhist-svg { width: 100%; height: 120px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.bar-up { fill: rgba(239, 68, 68, 0.75); } .bar-down { fill: rgba(34, 197, 94, 0.75); }
.rh-zero { stroke: var(--text-muted); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 3 3; }
.rhist-axis { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); }

.coach-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.coach-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 10px; font-size: 0.86rem; line-height: 1.55; border: 1px solid var(--border-color); }
.coach-icon { flex-shrink: 0; font-size: 1rem; }
.coach-text { flex: 1; }
.coach-bad { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.35); }
.coach-warn { background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.35); }
.coach-good { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.35); }
.coach-info { background: var(--bg-well); color: var(--text-muted); }
</style>
