<template>
  <div class="risk-page">
    <PageFocusBanner text="監控帳戶與部位風險指標，及早發現超出容忍範圍的風險。" />

    <div class="page-header">
      <div>
        <h1>風控監控</h1>
        <p>追蹤最大回撤、熔斷機制與權益曲線</p>
      </div>
      <button class="btn btn-primary" @click="loadRiskData" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </div>

    <section class="top-grid">
      <article class="card gauge-card">
        <div class="section-header">
          <div>
            <h2>MDD 風險儀表</h2>
            <p>綠色 &lt; 2%，黃色 2-3%，紅色 &gt; 3%</p>
          </div>
        </div>
        <div class="gauge-wrap">
          <div class="gauge" :style="gaugeStyle">
            <div class="gauge-inner">
              <strong>{{ formatPercent(mddValue) }}</strong>
              <span>MDD</span>
            </div>
          </div>
        </div>
      </article>

      <article class="card state-card">
        <div class="section-header">
          <div>
            <h2>熔斷機制狀態</h2>
            <p>風控引擎目前的交易狀態</p>
          </div>
        </div>
        <div class="state-body">
          <span class="status-pill" :class="statusClass(circuitStatus)">{{ circuitStatus }}</span>
          <p>{{ statusDescription }}</p>
          <button class="btn btn-secondary" @click="resetCircuitBreaker" :disabled="resetting">
            {{ resetting ? '重置中...' : '重置熔斷機制' }}
          </button>
        </div>
      </article>

      <article class="card trades-card">
        <div class="section-header">
          <div>
            <h2>當日交易次數</h2>
            <p>風控限制上限 15 筆</p>
          </div>
        </div>
        <div class="trade-counter">
          <strong>{{ dailyTrades }}</strong>
          <span>/ {{ dailyTradeLimit }}</span>
        </div>
        <div class="progress-track counter-track">
          <div class="progress-fill counter-fill" :style="{ width: `${tradePercent}%` }"></div>
        </div>
      </article>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益曲線</h2>
          <p>最近 30 個資料點</p>
        </div>
      </div>
      <div v-if="equitySeries.length" class="chart-wrapper">
        <span class="y-axis-label">新台幣(元)</span>
        <div ref="chartEl" class="chart-area"></div>
      </div>
      <div class="x-axis-label" v-if="equitySeries.length">日期</div>
      <div v-if="!equitySeries.length" class="empty-state">目前沒有權益曲線資料</div>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益日變動分布</h2>
          <p>直方圖 + 核密度估計，觀察報酬是否過度偏態或有厚尾風險</p>
        </div>
      </div>
      <div ref="histEl" class="chart-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Histogram / Kernel density estimation；資料取自權益曲線期間變動率
        <span v-if="riskDataIsMock">（目前為模擬帳戶資料，串接實盤交易後會自動改用真實報酬）</span>。
      </p>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createChart } from 'lightweight-charts'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'

const theme = useChartTheme()
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const loading = ref(false)
const resetting = ref(false)
const riskStatus = ref({})
const equitySeries = ref([])
const returnSeries = ref([])
const chartEl = ref(null)
const histEl = ref(null)
// 目前風控帳戶資料為模擬（見「標註 risk/trade 模擬資料」的既有調整），此分布圖同樣沿用該資料源。
const riskDataIsMock = ref(true)
let chart = null

const mddValue = computed(() => toUnitValue(riskStatus.value?.mdd_percent ?? riskStatus.value?.mdd ?? riskStatus.value?.max_drawdown ?? riskStatus.value?.drawdown))
const circuitStatus = computed(() => String((riskStatus.value?.circuit_breaker ?? riskStatus.value?.circuit_breaker_status) || riskStatus.value?.circuitBreakerStatus || riskStatus.value?.status || 'UNKNOWN').toUpperCase())
const dailyTrades = computed(() => Number(riskStatus.value?.daily_trades ?? riskStatus.value?.dailyTrades ?? riskStatus.value?.trades_today ?? 0))
const dailyTradeLimit = computed(() => Number(riskStatus.value?.daily_trade_limit ?? riskStatus.value?.dailyTradeLimit ?? 15))
const tradePercent = computed(() => Math.min(100, Math.round((dailyTrades.value / Math.max(1, dailyTradeLimit.value)) * 100)))
const statusDescription = computed(() => {
  if (circuitStatus.value === 'ACTIVE') return '系統允許自動交易正常進行。'
  if (circuitStatus.value === 'WARNING') return '接近風控限制，建議人工關注。'
  if (circuitStatus.value === 'PAUSED') return '交易已被暫停，需重置後才可恢復。'
  return '尚未取得狀態說明。'
})
const gaugeColor = computed(() => {
  if (mddValue.value > 0.03) return theme.down
  if (mddValue.value >= 0.02) return theme.warn
  return theme.up
})
const gaugeStyle = computed(() => {
  const percent = Math.min(100, Math.round((mddValue.value / 0.05) * 100))
  return { background: `conic-gradient(${gaugeColor.value} ${percent}%, ${theme.border} ${percent}% 100%)` }
})

onMounted(async () => {
  window.addEventListener('resize', renderChart)
  window.addEventListener('resize', renderHistogram)
  await loadRiskData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  window.removeEventListener('resize', renderHistogram)
  if (chart) chart.remove()
})

async function loadRiskData() {
  loading.value = true
  const [statusResp, curveResp, longCurveResp] = await Promise.allSettled([
    apiGet('/api/v1/risk/status'),
    apiGet('/api/v1/risk/equity-curve?hours=30'),
    apiGet('/api/v1/risk/equity-curve?hours=720'),
  ])

  if (statusResp.status === 'fulfilled') riskStatus.value = statusResp.value || {}
  if (curveResp.status === 'fulfilled') equitySeries.value = normalizeEquitySeries(curveResp.value)
  if (longCurveResp.status === 'fulfilled') {
    const longSeries = normalizeEquitySeries(longCurveResp.value, 5000)
    returnSeries.value = computeReturns(longSeries)
  }

  await nextTick()
  renderChart()
  renderHistogram()
  loading.value = false
}

function computeReturns(series) {
  const rets = []
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].value
    const cur = series[i].value
    if (prev > 0) rets.push(((cur - prev) / prev) * 100)
  }
  return rets
}

function renderHistogram() {
  const host = histEl.value
  if (!host) return
  host.innerHTML = ''
  const rets = returnSeries.value
  if (rets.length < 8) {
    host.innerHTML = '<p class="chart-empty">資料點不足，無法繪製分布圖。</p>'
    return
  }

  const width = host.clientWidth || 720
  const height = 300
  const margin = { top: 16, right: 16, bottom: 30, left: 40 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const innerH = height - margin.top - margin.bottom

  const x = d3.scaleLinear().domain(d3.extent(rets)).nice().range([0, innerW])
  const bins = d3.bin().domain(x.domain()).thresholds(20)(rets)
  const y = d3.scaleLinear().domain([0, d3.max(bins, (b) => b.length) || 1]).nice().range([innerH, 0])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.append('g').attr('transform', `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6).tickFormat((v) => `${v}%`)).attr('class', 'axis')
  g.append('g').call(d3.axisLeft(y).ticks(5)).attr('class', 'axis')

  g.selectAll('rect.bin')
    .data(bins)
    .join('rect')
    .attr('class', 'bin')
    .attr('x', (d) => x(d.x0) + 1)
    .attr('width', (d) => Math.max(0, x(d.x1) - x(d.x0) - 1))
    .attr('y', (d) => y(d.length))
    .attr('height', (d) => innerH - y(d.length))
    .attr('fill', 'var(--accent-blue)')
    .attr('fill-opacity', 0.55)

  // KDE overlay, scaled to the same bin-count y-axis for visual comparison.
  const bandwidth = 1.06 * d3.deviation(rets) * Math.pow(rets.length, -0.2) || 0.5
  const kernel = (u) => Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI)
  const xs = d3.range(x.domain()[0], x.domain()[1], (x.domain()[1] - x.domain()[0]) / 100)
  const binWidth = bins[0] ? bins[0].x1 - bins[0].x0 : 1
  const density = xs.map((xv) => {
    const sum = rets.reduce((acc, v) => acc + kernel((xv - v) / bandwidth), 0)
    return { x: xv, y: (sum / (rets.length * bandwidth)) * rets.length * binWidth }
  })
  const kdeLine = d3.line().x((d) => x(d.x)).y((d) => y(d.y)).curve(d3.curveBasis)
  g.append('path')
    .datum(density)
    .attr('fill', 'none')
    .attr('stroke', 'var(--accent-red)')
    .attr('stroke-width', 2)
    .attr('d', kdeLine)

  g.append('line')
    .attr('x1', x(0)).attr('x2', x(0))
    .attr('y1', 0).attr('y2', innerH)
    .attr('stroke', 'var(--border-color)')
    .attr('stroke-dasharray', '3,3')
}

watch(returnSeries, () => nextTick(renderHistogram))

async function resetCircuitBreaker() {
  if (!window.confirm('確定要重置熔斷機制嗎？')) return
  resetting.value = true
  try {
    await apiRequest('/api/v1/risk/circuit-breaker/reset', { method: 'POST' })
    await loadRiskData()
  } catch (error) {
    window.alert(error.message || '重置失敗')
  }
  resetting.value = false
}

async function apiGet(path) {
  return apiRequest(path)
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.detail || 'API 請求失敗')
  return payload?.data ?? payload
}

function normalizeEquitySeries(payload, limit = 30) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.equity_curve)
        ? payload.equity_curve
        : []
  return list
    .slice(-limit)
    .map(item => ({
      time: normalizeDate(item.date || item.time || item.timestamp),
      value: Number(item.portfolio_value ?? item.value ?? item.equity ?? 0),
    }))
    .filter(item => item.time && Number.isFinite(item.value))
}

function renderChart() {
  if (!chartEl.value || !equitySeries.value.length) return
  if (chart) chart.remove()
  chart = createChart(chartEl.value, {
    width: chartEl.value.clientWidth || 720,
    height: 320,
    layout: { background: { color: '#0d1117' }, textColor: theme.muted },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
  })
  const lineSeries = chart.addLineSeries({ color: theme.up, lineWidth: 2 })
  lineSeries.setData(equitySeries.value)
  chart.timeScale().fitContent()
}

function normalizeDate(value) {
  if (!value) return ''
  return String(value).includes('T') ? String(value).split('T')[0] : String(value).slice(0, 10)
}

function toUnitValue(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return numeric > 1 ? numeric / 100 : numeric
}

function formatPercent(value) {
  return `${(toUnitValue(value) * 100).toFixed(2)}%`
}

function statusClass(status) {
  if (status === 'ACTIVE') return 'is-active'
  if (status === 'WARNING') return 'is-warning'
  if (status === 'PAUSED') return 'is-paused'
  return 'is-neutral'
}
</script>

<style scoped>
.risk-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header p,
.section-header p,
.state-body p,
.empty-state {
  color: var(--text-secondary);
}

.top-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.gauge-wrap,
.state-body,
.trade-counter {
  margin-top: 16px;
}

.gauge-wrap {
  display: flex;
  justify-content: center;
}

.gauge {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  padding: 14px;
}

.gauge-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #0d1117;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.gauge-inner strong,
.trade-counter strong {
  font-size: 2rem;
}

.state-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}

.status-pill {
  padding: 6px 12px;
  border-radius: 999px;
  font-weight: 700;
  color: #fff;
}

.is-active {
  background: var(--color-up);
}

.is-warning {
  background: var(--color-warning);
}

.is-paused {
  background: var(--color-down);
}

.is-neutral {
  background: #64748b;
}

.trade-counter {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.counter-track,
.chart-area {
  margin-top: 16px;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.counter-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #2563eb);
}

.chart-area {
  width: 100%;
  min-height: 320px;
  border-radius: 12px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
  margin-top: 16px;
}

.chart-wrapper .chart-area {
  flex: 1;
  margin-top: 0;
}

.y-axis-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  padding: 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.x-axis-label {
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.chart-host { width: 100%; min-height: 300px; margin-top: 16px; }
.chart-host :deep(.axis text) { fill: var(--text-muted); font-size: 0.7rem; }
.chart-host :deep(.axis path),
.chart-host :deep(.axis line) { stroke: var(--border-color); }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }
.chart-empty { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }

.btn-secondary {
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-primary);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

@media (max-width: 1100px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 420px) {
  .risk-page {
    gap: var(--space-3);
  }
  .rule-card,
  .card {
    padding: var(--space-3);
  }
}
</style>
