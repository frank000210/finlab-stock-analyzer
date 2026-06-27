<template>
  <div class="risk-page">
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
      <div v-if="equitySeries.length" ref="chartEl" class="chart-area"></div>
      <div v-else class="empty-state">目前沒有權益曲線資料</div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { createChart } from 'lightweight-charts'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const loading = ref(false)
const resetting = ref(false)
const riskStatus = ref({})
const equitySeries = ref([])
const chartEl = ref(null)
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
  if (mddValue.value > 0.03) return '#ef4444'
  if (mddValue.value >= 0.02) return '#f59e0b'
  return '#10b981'
})
const gaugeStyle = computed(() => {
  const percent = Math.min(100, Math.round((mddValue.value / 0.05) * 100))
  return { background: `conic-gradient(${gaugeColor.value} ${percent}%, rgba(148, 163, 184, 0.16) ${percent}% 100%)` }
})

onMounted(async () => {
  window.addEventListener('resize', renderChart)
  await loadRiskData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  if (chart) chart.remove()
})

async function loadRiskData() {
  loading.value = true
  const [statusResp, curveResp] = await Promise.allSettled([
    apiGet('/api/v1/risk/status'),
    apiGet('/api/v1/risk/equity-curve?hours=30'),
  ])

  if (statusResp.status === 'fulfilled') riskStatus.value = statusResp.value || {}
  if (curveResp.status === 'fulfilled') equitySeries.value = normalizeEquitySeries(curveResp.value)

  await nextTick()
  renderChart()
  loading.value = false
}

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

function normalizeEquitySeries(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.equity_curve)
        ? payload.equity_curve
        : []
  return list
    .slice(-30)
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
    layout: { background: { color: '#0d1117' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
    rightPriceScale: { borderColor: '#334155' },
    timeScale: { borderColor: '#334155' },
  })
  const lineSeries = chart.addLineSeries({ color: '#22c55e', lineWidth: 2 })
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
  background: #10b981;
}

.is-warning {
  background: #f59e0b;
}

.is-paused {
  background: #ef4444;
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
</style>
