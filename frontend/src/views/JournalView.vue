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
        <input v-model="form.symbol" class="inp w110" placeholder="代碼 2330" />
        <select v-model="form.side" class="inp"><option value="long">做多</option><option value="short">做空</option></select>
        <input v-model.number="form.entry" type="number" class="inp w110" placeholder="進場價" step="0.05" />
        <input v-model.number="form.stop" type="number" class="inp w110" placeholder="停損價" step="0.05" />
        <input v-model.number="form.target" type="number" class="inp w110" placeholder="目標價(選填)" step="0.05" />
        <input v-model.number="form.lots" type="number" class="inp w90" placeholder="張數" min="1" step="1" />
        <input v-model="form.tag" class="inp w110" placeholder="型態(選填)" />
        <button class="btn btn-primary" @click="addTrade">加入</button>
        <button class="btn" @click="importOpenPositions">從投組帶入</button>
      </div>
      <p v-if="formError" class="error-text">{{ formError }}</p>
      <p v-if="importMsg" class="muted small">{{ importMsg }}</p>
    </section>

    <!-- 進行中 -->
    <section class="section-block" v-reveal v-if="openTrades.length">
      <h3>進行中（{{ openTrades.length }}）</h3>
      <div class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>目標</th><th>張</th><th>風險(1R)</th><th>平倉價</th><th>動作</th></tr></thead>
          <tbody>
            <tr v-for="t in openTrades" :key="t.id">
              <td class="sym">{{ t.symbol }}<small>{{ t.name && t.name !== t.symbol ? ' ' + t.name : '' }}</small></td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ t.target ? fmt(t.target) : '—' }}</td>
              <td>{{ t.lots }}</td>
              <td>{{ fmtInt(riskAmount(t)) }}</td>
              <td><input v-model.number="t._exitInput" type="number" class="inp w90" step="0.05" placeholder="價格" /></td>
              <td class="actions">
                <button class="btn xs" @click="closeTrade(t)">平倉</button>
                <button class="del" @click="removeTrade(t.id)" title="刪除">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 已平倉 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <h3>已平倉（{{ closedTrades.length }}）</h3>
        <div class="head-actions">
          <button v-if="trades.length" class="btn" @click="exportCsv">匯出 CSV</button>
          <button v-if="trades.length" class="btn" @click="clearAll">清空全部</button>
        </div>
      </div>
      <div v-if="closedTrades.length" class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>出場</th><th>張</th><th>R 倍數</th><th>損益</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in closedTrades" :key="t.id">
              <td class="sym">{{ t.symbol }}</td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ fmt(t.exit) }}</td>
              <td>{{ t.lots }}</td>
              <td><strong :class="realizedR(t) >= 0 ? 'up' : 'down'">{{ realizedR(t) >= 0 ? '+' : '' }}{{ realizedR(t).toFixed(2) }}R</strong></td>
              <td :class="pnl(t) >= 0 ? 'up' : 'down'">{{ fmtInt(pnl(t)) }}</td>
              <td><button class="del" @click="removeTrade(t.id)" title="刪除">✕</button></td>
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const LS_KEY = 'finlab_trade_journal'

const trades = ref([])
const form = reactive({ symbol: '', side: 'long', entry: null, stop: null, target: null, lots: 1, tag: '' })
const formError = ref('')
const importMsg = ref('')

const openTrades = computed(() => trades.value.filter(t => t.status === 'open'))
const closedTrades = computed(() => trades.value.filter(t => t.status === 'closed'))

function riskPerShare(t) { return Math.abs((Number(t.entry) || 0) - (Number(t.stop) || 0)) }
function riskAmount(t) { return (Number(t.lots) || 0) * 1000 * riskPerShare(t) }
function profitPerShare(t) {
  const diff = (Number(t.exit) || 0) - (Number(t.entry) || 0)
  return t.side === 'short' ? -diff : diff
}
function realizedR(t) { return riskPerShare(t) > 0 ? profitPerShare(t) / riskPerShare(t) : 0 }
function pnl(t) { return (Number(t.lots) || 0) * 1000 * profitPerShare(t) }

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
const equityBounds = computed(() => {
  const ys = equityPoints.value
  const min = Math.min(0, ...ys), max = Math.max(0, ...ys)
  return { min, max, range: (max - min) || 1 }
})
const eqZeroY = computed(() => eqH - ((0 - equityBounds.value.min) / equityBounds.value.range) * eqH)
const equityPolyline = computed(() => {
  const ys = equityPoints.value
  const n = ys.length
  return ys.map((y, i) => {
    const x = (i / (n - 1)) * eqW
    const yy = eqH - ((y - equityBounds.value.min) / equityBounds.value.range) * eqH
    return `${x.toFixed(1)},${yy.toFixed(1)}`
  }).join(' ')
})

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

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }

function save() { localStorage.setItem(LS_KEY, JSON.stringify(trades.value)) }
function load() {
  try { const raw = JSON.parse(localStorage.getItem(LS_KEY) || '[]'); if (Array.isArray(raw)) trades.value = raw } catch { /* ignore */ }
}

function addTrade() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  const entry = Number(form.entry), stop = Number(form.stop), lots = Math.floor(Number(form.lots) || 0)
  if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop) {
    formError.value = '請填代碼、有效的進場/停損價（不可相等）與至少 1 張。'
    return
  }
  trades.value.unshift({
    id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    symbol, name: symbol, side: form.side, entry, stop,
    target: Number(form.target) > 0 ? Number(form.target) : null,
    lots, tag: String(form.tag || '').trim(),
    openDate: new Date().toISOString().slice(0, 10), status: 'open',
    exit: null, exitDate: null,
  })
  save()
  form.symbol = ''; form.entry = null; form.stop = null; form.target = null; form.lots = 1; form.tag = ''
}

function closeTrade(t) {
  const exit = Number(t._exitInput)
  if (!(exit > 0)) { formError.value = '請在該筆輸入有效的平倉價。'; return }
  formError.value = ''
  t.exit = exit
  t.exitDate = new Date().toISOString().slice(0, 10)
  t.status = 'closed'
  delete t._exitInput
  save()
}

function removeTrade(id) { trades.value = trades.value.filter(t => t.id !== id); save() }
function clearAll() { trades.value = []; save() }

function csvCell(v) { const s = String(v ?? ''); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s }
function exportCsv() {
  if (!trades.value.length) return
  const cols = ['symbol', 'side', 'entry', 'stop', 'target', 'lots', 'tag', 'openDate', 'status', 'exit', 'exitDate', 'R', 'pnl']
  const lines = trades.value.map((t) => {
    const R = t.status === 'closed' ? realizedR(t).toFixed(3) : ''
    const p = t.status === 'closed' ? Math.round(pnl(t)) : ''
    return [t.symbol, t.side, t.entry, t.stop, t.target ?? '', t.lots, t.tag ?? '', t.openDate, t.status, t.exit ?? '', t.exitDate ?? '', R, p].map(csvCell).join(',')
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
      openDate: new Date().toISOString().slice(0, 10), status: 'open', exit: null, exitDate: null,
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
.muted { color: var(--text-muted); }
.small { font-size: 0.82rem; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.w110 { width: 110px; } .w90 { width: 90px; }
.error-text { color: #ef4444; margin-top: 8px; }

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
.up { color: #ef4444; } .down { color: #22c55e; }
.empty { padding: 14px 0; }
.disclaimer { font-size: 0.74rem; color: var(--text-muted); margin-top: 12px; }

.analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 8px; }
@media (max-width: 900px) { .analytics-grid { grid-template-columns: 1fr; } }
.an-block { display: flex; flex-direction: column; gap: 8px; }
.rhist-svg { width: 100%; height: 120px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.bar-up { fill: rgba(239, 68, 68, 0.75); } .bar-down { fill: rgba(34, 197, 94, 0.75); }
.rh-zero { stroke: var(--text-muted); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 3 3; }
.rhist-axis { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); }
</style>
