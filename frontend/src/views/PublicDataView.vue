<template>
  <div class="public-data-page">
    <PageFocusBanner text="檢視基本面數據，判斷目前股價相對獲利與成長性是便宜還是昂貴。" />

    <header class="page-header">
      <div>
        <h1>📋 公開資訊</h1>
        <p class="subtitle">{{ stockStore.symbol }} {{ stockStore.name }} — 證交所重大公告與財務資訊</p>
      </div>
      <button class="btn btn-primary" @click="fetchData" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <!-- PE Band -->
    <section class="card">
      <h2>💹 本益比河流圖</h2>
      <div ref="peBandEl" class="chart-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Analysis（本益比河流圖為其延伸應用）；帶狀為歷史本益比 20/40/60/80 百分位 × 當期TTM EPS，黑線為實際股價。
      </p>
    </section>

    <!-- Revenue Growth -->
    <section class="card">
      <h2>📈 月營收年增率</h2>
      <div ref="revenueEl" class="chart-host"></div>
      <p class="chart-caption">參考：D3 gallery - Bars；柱狀＝YoY 成長率，折線＝當月營收。</p>
    </section>

    <div v-if="data" class="results">
      <!-- Announcements -->
      <section class="card">
        <h2>📢 重大公告</h2>
        <div v-if="data.announcements && data.announcements.length" class="announcements-list">
          <div v-for="(a, i) in data.announcements" :key="i" class="announcement-item">
            <span class="ann-date">{{ a.date }}</span>
            <span class="ann-title">{{ a.title }}</span>
          </div>
        </div>
        <p v-else class="no-data">暫無重大公告</p>
      </section>

      <!-- Dividends -->
      <section class="card">
        <h2>💰 歷年配息</h2>
        <div v-if="data.dividends && data.dividends.length" class="dividend-table">
          <div class="div-header">
            <span>年度</span><span>現金股利</span><span>股票股利</span><span>合計</span>
          </div>
          <div v-for="d in data.dividends" :key="d.year" class="div-row">
            <span>{{ d.year }}</span>
            <span>{{ d.cash }}</span>
            <span>{{ d.stock }}</span>
            <span class="div-total">{{ d.total }}</span>
          </div>
        </div>
        <p v-else class="no-data">暫無配息資料</p>
      </section>

      <!-- Financial Summary -->
      <section class="card" v-if="data.financial_summary">
        <h2>📊 最新財務摘要</h2>
        <div class="fin-grid">
          <div class="fin-item" v-for="(val, key) in data.financial_summary" :key="key">
            <span class="fin-label">{{ formatLabel(key) }}</span>
            <span class="fin-value">{{ val }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'

const route = useRoute()
const stockStore = useStockStore()
const theme = useChartTheme()
const loading = ref(false)
const error = ref('')
const data = ref(null)
const peBandEl = ref(null)
const revenueEl = ref(null)
const fundamental = ref(null)
const priceHistory = ref(null)

const labelMap = {
  revenue_latest: '最新月營收',
  eps_latest: '最新 EPS',
  pe_ratio: '本益比',
  dividend_yield: '殖利率',
  roe: 'ROE',
  roa: 'ROA',
}

function formatLabel(key) {
  return labelMap[key] || key
}

async function fetchData() {
  const sym = route.params.symbol || stockStore.symbol
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${sym}/public-data`)
    const json = await res.json()
    if (json.success) {
      data.value = json.data
    } else {
      error.value = json.error || '載入失敗'
    }
  } catch (e) {
    error.value = '無法連線到伺服器'
  } finally {
    loading.value = false
  }
}

async function fetchFundamental() {
  const sym = route.params.symbol || stockStore.symbol
  try {
    const res = await fetch(`/api/v1/analysis/${sym}/fundamental?metrics=revenue,eps`)
    const json = await res.json()
    if (json.success) fundamental.value = json.data
  } catch (e) {
    // 基本面圖表失敗不影響公開資訊其他區塊
  }
}

async function fetchPriceHistory() {
  const sym = route.params.symbol || stockStore.symbol
  const end = new Date()
  const start = new Date()
  start.setFullYear(start.getFullYear() - 5)
  const fmt = (d) => d.toISOString().slice(0, 10)
  try {
    const res = await fetch(
      `/api/v1/stocks/${sym}/price?start=${fmt(start)}&end=${fmt(end)}&period=1mo`
    )
    const json = await res.json()
    if (json.success) priceHistory.value = json.data.items
  } catch (e) {
    // 河流圖失敗不影響公開資訊其他區塊
  }
}

function quarterEndDate(q) {
  // q like "2024Q1" -> approximate quarter-end date
  const m = /^(\d{4})Q(\d)/.exec(q)
  if (!m) return null
  const year = Number(m[1])
  const q_num = Number(m[2])
  const month = q_num * 3
  return new Date(year, month, 0) // last day of that month
}

function renderPeBand() {
  const host = peBandEl.value
  if (!host) return
  host.innerHTML = ''
  const eps = fundamental.value?.eps_quarterly || []
  const prices = priceHistory.value || []
  if (eps.length < 4 || !prices.length) {
    host.innerHTML = '<p class="chart-empty">EPS 或股價資料不足，無法繪製本益比河流圖。</p>'
    return
  }

  // Trailing 4-quarter EPS (TTM), keyed by quarter-end date.
  const sortedEps = [...eps].sort((a, b) => (a.quarter < b.quarter ? -1 : 1))
  const ttmPoints = []
  for (let i = 3; i < sortedEps.length; i++) {
    const window = sortedEps.slice(i - 3, i + 1)
    const ttm = window.reduce((sum, w) => sum + (w.eps || 0), 0)
    const dt = quarterEndDate(sortedEps[i].quarter)
    if (dt && ttm > 0) ttmPoints.push({ date: dt, ttm })
  }
  if (!ttmPoints.length) {
    host.innerHTML = '<p class="chart-empty">EPS 資料不足，無法繪製本益比河流圖。</p>'
    return
  }

  // As-of join: for each monthly price point, find latest ttm known by that date.
  const priceParsed = prices
    .map((p) => ({ date: new Date(p.date), close: p.close }))
    .filter((p) => !Number.isNaN(p.date.getTime()))
  const joined = []
  for (const p of priceParsed) {
    let ttm = null
    for (const t of ttmPoints) {
      if (t.date <= p.date) ttm = t.ttm
      else break
    }
    if (ttm) joined.push({ date: p.date, close: p.close, ttm, pe: p.close / ttm })
  }
  if (joined.length < 6) {
    host.innerHTML = '<p class="chart-empty">股價與 EPS 對齊後資料不足，無法繪製本益比河流圖。</p>'
    return
  }

  const peSeries = joined.map((j) => j.pe).sort((a, b) => a - b)
  const bandPercentiles = [0.2, 0.4, 0.6, 0.8]
  const bandPe = bandPercentiles.map((p) => d3.quantileSorted(peSeries, p))

  const width = host.clientWidth || 760
  const height = 320
  const margin = { top: 16, right: 56, bottom: 30, left: 56 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const innerH = height - margin.top - margin.bottom

  const x = d3.scaleTime().domain(d3.extent(joined, (d) => d.date)).range([0, innerW])
  const bandTop = d3.max(bandPercentiles.map((_, i) => d3.max(joined, (d) => bandPe[i] * d.ttm)))
  const yMax = Math.max(d3.max(joined, (d) => d.close), bandTop || 0) * 1.05
  const yMin = Math.min(d3.min(joined, (d) => d.close), 0)
  const y = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.append('g').attr('transform', `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6)).attr('class', 'axis')
  g.append('g').call(d3.axisLeft(y).ticks(6)).attr('class', 'axis')

  const bandColors = [theme.blue, theme.up, theme.warn, theme.down]
  bandPercentiles.forEach((p, i) => {
    const line = d3
      .line()
      .x((d) => x(d.date))
      .y((d) => y(bandPe[i] * d.ttm))
    g.append('path')
      .datum(joined)
      .attr('fill', 'none')
      .attr('stroke', bandColors[i])
      .attr('stroke-width', 1.3)
      .attr('stroke-dasharray', '4,3')
      .attr('d', line)
    const last = joined[joined.length - 1]
    g.append('text')
      .attr('x', innerW + 4)
      .attr('y', y(bandPe[i] * last.ttm))
      .attr('fill', bandColors[i])
      .attr('font-size', 10)
      .text(`${Math.round(bandPe[i])}x`)
  })

  const priceLine = d3.line().x((d) => x(d.date)).y((d) => y(d.close))
  g.append('path')
    .datum(joined)
    .attr('fill', 'none')
    .attr('stroke', 'var(--text-primary)')
    .attr('stroke-width', 2)
    .attr('d', priceLine)
}

function renderRevenueChart() {
  const host = revenueEl.value
  if (!host) return
  host.innerHTML = ''
  const rows = (fundamental.value?.revenue_monthly || []).slice(-36)
  if (!rows.length) {
    host.innerHTML = '<p class="chart-empty">尚無月營收資料。</p>'
    return
  }

  const width = host.clientWidth || 760
  const height = 300
  const margin = { top: 16, right: 44, bottom: 40, left: 44 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const innerH = height - margin.top - margin.bottom

  const x = d3.scaleBand().domain(rows.map((r) => r.month)).range([0, innerW]).padding(0.3)
  const yoyValues = rows.map((r) => r.yoy).filter((v) => v != null)
  const yoyExtent = d3.extent(yoyValues.length ? yoyValues : [0, 1])
  const yBar = d3.scaleLinear().domain([Math.min(0, yoyExtent[0]), Math.max(0, yoyExtent[1])]).nice().range([innerH, 0])
  const yLine = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.revenue) || 1]).range([innerH, 0])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(
      d3.axisBottom(x).tickValues(x.domain().filter((_, i) => i % Math.ceil(rows.length / 8) === 0))
    )
    .attr('class', 'axis')
  g.append('g').call(d3.axisLeft(yBar).ticks(5).tickFormat((v) => `${v}%`)).attr('class', 'axis')

  g.append('line')
    .attr('x1', 0).attr('x2', innerW)
    .attr('y1', yBar(0)).attr('y2', yBar(0))
    .attr('stroke', 'var(--border-color)')

  g.selectAll('rect.yoy-bar')
    .data(rows)
    .join('rect')
    .attr('class', 'yoy-bar')
    .attr('x', (d) => x(d.month))
    .attr('width', x.bandwidth())
    .attr('y', (d) => (d.yoy == null ? yBar(0) : yBar(Math.max(0, d.yoy))))
    .attr('height', (d) => (d.yoy == null ? 0 : Math.abs(yBar(d.yoy) - yBar(0))))
    .attr('fill', (d) => (d.yoy == null ? 'var(--text-muted)' : d.yoy >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'))
    .attr('fill-opacity', 0.75)

  const revLine = d3
    .line()
    .x((d) => x(d.month) + x.bandwidth() / 2)
    .y((d) => yLine(d.revenue))
  g.append('path')
    .datum(rows)
    .attr('fill', 'none')
    .attr('stroke', 'var(--accent-blue)')
    .attr('stroke-width', 2)
    .attr('d', revLine)
}

function renderFundamentalCharts() {
  renderPeBand()
  renderRevenueChart()
}

watch([fundamental, priceHistory], () => nextTick(renderFundamentalCharts))

let fundamentalResizeHandler = null
onMounted(() => {
  fetchData()
  fetchFundamental()
  fetchPriceHistory()
  fundamentalResizeHandler = () => renderFundamentalCharts()
  window.addEventListener('resize', fundamentalResizeHandler)
})
onBeforeUnmount(() => {
  if (fundamentalResizeHandler) window.removeEventListener('resize', fundamentalResizeHandler)
})
watch(() => route.params.symbol, () => {
  fetchData()
  fetchFundamental()
  fetchPriceHistory()
})
</script>

<style scoped>
.public-data-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.error-card { color: var(--color-down); background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); }
.no-data { color: var(--text-muted); font-style: italic; }
.chart-host { width: 100%; min-height: 300px; }
.chart-host :deep(.axis text) { fill: var(--text-muted); font-size: 0.7rem; }
.chart-host :deep(.axis path),
.chart-host :deep(.axis line) { stroke: var(--border-color); }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }
.chart-empty { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }

.announcements-list { display: flex; flex-direction: column; gap: 8px; }
.announcement-item { display: flex; gap: 12px; padding: 10px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); font-size: 0.85rem; }
.ann-date { color: var(--text-muted); min-width: 80px; font-size: 0.78rem; }
.ann-title { flex: 1; }

.dividend-table { font-size: 0.85rem; }
.div-header, .div-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; padding: 8px 12px; }
.div-header { font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color); }
.div-row { border-bottom: 1px solid var(--bg-tertiary); }
.div-total { font-weight: 700; color: var(--accent-green); }

.fin-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-3); }
.fin-item { padding: 12px 16px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.fin-label { display: block; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 4px; }
.fin-value { font-size: 1.1rem; font-weight: 700; }

@media (max-width: 420px) {
  .announcement-item { flex-direction: column; gap: 4px; }
  .ann-date { min-width: 0; }
  .fin-grid { grid-template-columns: 1fr 1fr; }
}
</style>
