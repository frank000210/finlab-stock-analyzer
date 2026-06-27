<template>
  <div class="trade-dashboard">
    <div class="page-header">
      <div>
        <h1>交易儀表板</h1>
        <p>整合投資組合、AI 信號與風控狀態的即時總覽</p>
      </div>
      <button class="btn btn-primary" @click="loadDashboard" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </div>

    <p v-if="errorMessage" class="status-message error">{{ errorMessage }}</p>

    <section class="grid-4 kpi-grid">
      <article class="card metric-card">
        <div class="label">投資組合價值</div>
        <div class="value">{{ formatCurrency(portfolioValue) }}</div>
        <div class="meta">模擬帳戶總資產</div>
      </article>
      <article class="card metric-card">
        <div class="label">2330 最新股價</div>
        <div class="value">{{ latestPriceDisplay }}</div>
        <div class="meta">最近一筆收盤價</div>
      </article>
      <article class="card metric-card">
        <div class="label">熔斷機制</div>
        <div class="value" :class="statusClass(circuitStatus)">{{ circuitStatus }}</div>
        <div class="meta">{{ circuitStatusDescription }}</div>
      </article>
      <article class="card metric-card">
        <div class="label">AI 信號摘要</div>
        <div class="value">{{ summaryText }}</div>
        <div class="meta">平均信心 {{ averageConfidence }}%</div>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="card chart-card">
        <div class="section-header">
          <div>
            <h2>2330 價格走勢</h2>
            <p>近端 API 回傳的收盤價折線圖</p>
          </div>
        </div>
        <div v-if="priceSeries.length" class="chart-wrapper">
          <span class="y-axis-label">新台幣(元)</span>
          <div ref="chartEl" class="chart-area"></div>
        </div>
        <div class="x-axis-label" v-if="priceSeries.length">日期</div>
        <div v-if="!priceSeries.length" class="empty-state">目前沒有價格資料</div>
      </article>

      <article class="card side-card">
        <div class="section-header">
          <div>
            <h2>最新 AI 信號</h2>
            <p>前 4 筆高優先度訊號</p>
          </div>
        </div>
        <div v-if="topSignals.length" class="signal-list">
          <div v-for="signal in topSignals" :key="signal.id" class="signal-item">
            <div class="signal-top">
              <div>
                <strong>{{ signal.symbol }}</strong>
                <p class="signal-reason">{{ signal.reasoning }}</p>
              </div>
              <span class="badge" :class="badgeClass(signal.type)">{{ signal.type }}</span>
            </div>
            <div class="confidence-row">
              <span>信心度 {{ signal.confidence }}%</span>
              <div class="progress-track">
                <div class="progress-fill" :class="badgeClass(signal.type)" :style="{ width: `${signal.confidence}%` }"></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">目前沒有 AI 信號</div>
      </article>
    </section>

    <section class="card risk-card">
      <div class="section-header">
        <div>
          <h2>風險總覽</h2>
          <p>監控最大回撤、當日交易數與熔斷狀態</p>
        </div>
      </div>
      <div class="risk-grid">
        <div>
          <span class="risk-label">最大回撤 MDD</span>
          <strong :class="mddClass">{{ formatPercent(mddValue) }}</strong>
        </div>
        <div>
          <span class="risk-label">當日交易數</span>
          <strong>{{ dailyTrades }} / {{ dailyTradeLimit }}</strong>
        </div>
        <div>
          <span class="risk-label">熔斷狀態</span>
          <strong :class="statusClass(circuitStatus)">{{ circuitStatus }}</strong>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { createChart } from 'lightweight-charts'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const portfolioValue = 5000000
const loading = ref(false)
const errorMessage = ref('')
const signals = ref([])
const riskStatus = ref({})
const priceSeries = ref([])
const chartEl = ref(null)
let chart = null

const topSignals = computed(() => signals.value.slice(0, 4))
const latestPriceDisplay = computed(() => {
  const last = priceSeries.value[priceSeries.value.length - 1]
  return last ? formatNumber(last.value) : '--'
})
const circuitStatus = computed(() => normalizeCircuitStatus(riskStatus.value))
const circuitStatusDescription = computed(() => {
  if (circuitStatus.value === 'ACTIVE') return '風控允許正常交易'
  if (circuitStatus.value === 'WARNING') return '接近限制，請留意風險'
  if (circuitStatus.value === 'PAUSED') return '交易已暫停，待人工處理'
  return '尚未取得狀態'
})
const mddValue = computed(() => toUnitValue(riskStatus.value?.mdd ?? riskStatus.value?.max_drawdown ?? riskStatus.value?.drawdown))
const dailyTrades = computed(() => Number(riskStatus.value?.daily_trades ?? riskStatus.value?.dailyTrades ?? riskStatus.value?.trades_today ?? 0))
const dailyTradeLimit = computed(() => Number(riskStatus.value?.daily_trade_limit ?? riskStatus.value?.dailyTradeLimit ?? 15))
const averageConfidence = computed(() => {
  if (!signals.value.length) return 0
  const total = signals.value.reduce((sum, item) => sum + item.confidence, 0)
  return Math.round(total / signals.value.length)
})
const summaryText = computed(() => {
  const buyCount = signals.value.filter(item => item.type === 'BUY').length
  const sellCount = signals.value.filter(item => item.type === 'SELL').length
  return `買入 ${buyCount} / 賣出 ${sellCount}`
})
const mddClass = computed(() => {
  if (mddValue.value > 0.03) return 'down'
  if (mddValue.value >= 0.02) return 'warning-text'
  return 'up'
})

onMounted(async () => {
  window.addEventListener('resize', renderChart)
  await loadDashboard()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  destroyChart()
})

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''

  const [signalsResp, riskResp, priceResp] = await Promise.allSettled([
    apiGet('/api/v1/agent/signals'),
    apiGet('/api/v1/risk/status'),
    apiGet('/api/v1/stocks/2330/price'),
  ])

  if (signalsResp.status === 'fulfilled') {
    signals.value = normalizeSignals(signalsResp.value)
  }
  if (riskResp.status === 'fulfilled') {
    riskStatus.value = riskResp.value || {}
  }
  if (priceResp.status === 'fulfilled') {
    priceSeries.value = normalizePriceSeries(priceResp.value)
  }

  if ([signalsResp, riskResp, priceResp].every(item => item.status === 'rejected')) {
    errorMessage.value = '資料載入失敗，請稍後再試。'
  }

  await nextTick()
  renderChart()
  loading.value = false
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.detail || 'API 請求失敗')
  }
  return payload?.data ?? payload
}

function normalizeSignals(payload) {
  return extractList(payload, ['items', 'signals']).map((item, index) => ({
    id: item.id || item.task_id || `${item.symbol || item.stock_symbol || 'signal'}-${index}`,
    symbol: item.symbol || item.stock_symbol || item.ticker || 'N/A',
    type: String(item.type || item.signal || item.action || 'HOLD').toUpperCase(),
    confidence: normalizePercent(item.confidence),
    reasoning: item.reasoning || item.reason || '暫無推論說明',
  }))
}

function normalizePriceSeries(payload) {
  return extractList(payload, ['items', 'prices', 'data'])
    .map(item => ({
      time: normalizeDate(item.date || item.time || item.timestamp),
      value: Number(item.close ?? item.price ?? item.value ?? 0),
    }))
    .filter(item => item.time && Number.isFinite(item.value))
}

function extractList(payload, keys = []) {
  if (Array.isArray(payload)) return payload
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

function renderChart() {
  if (!chartEl.value || !priceSeries.value.length) return
  destroyChart()
  chart = createChart(chartEl.value, {
    width: chartEl.value.clientWidth || 720,
    height: 320,
    layout: { background: { color: '#0d1117' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
    rightPriceScale: { borderColor: '#334155' },
    timeScale: { borderColor: '#334155' },
    crosshair: { vertLine: { color: '#475569' }, horzLine: { color: '#475569' } },
  })
  const lineSeries = chart.addLineSeries({ color: '#38bdf8', lineWidth: 2 })
  lineSeries.setData(priceSeries.value)
  chart.timeScale().fitContent()
}

function destroyChart() {
  if (chart) {
    chart.remove()
    chart = null
  }
}

function normalizeDate(value) {
  if (!value) return ''
  return String(value).includes('T') ? String(value).split('T')[0] : String(value).slice(0, 10)
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function toUnitValue(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return numeric > 1 ? numeric / 100 : numeric
}

function normalizeCircuitStatus(payload) {
  return String(payload?.circuit_breaker_status || payload?.circuitBreakerStatus || payload?.status || 'UNKNOWN').toUpperCase()
}

function formatCurrency(value) {
  return `₺${formatNumber(value)}`
}

function formatNumber(value) {
  return new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format(Number(value || 0))
}

function formatPercent(value) {
  return `${(toUnitValue(value) * 100).toFixed(2)}%`
}

function badgeClass(type) {
  return type === 'BUY' ? 'badge-buy' : type === 'SELL' ? 'badge-sell' : 'badge-hold'
}

function statusClass(status) {
  if (status === 'ACTIVE') return 'up'
  if (status === 'WARNING') return 'warning-text'
  if (status === 'PAUSED') return 'down'
  return ''
}
</script>

<style scoped>
.trade-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header,
.signal-top,
.confidence-row,
.risk-grid {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header h1,
.section-header h2 {
  font-size: 1.6rem;
  margin-bottom: 4px;
}

.page-header p,
.section-header p,
.meta,
.signal-reason,
.risk-label,
.empty-state,
.status-message {
  color: var(--text-secondary);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 20px;
}

.chart-area {
  width: 100%;
  min-height: 320px;
  margin-top: 16px;
  border-radius: 12px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
}

.chart-wrapper .chart-area {
  flex: 1;
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

.signal-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.signal-item {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.45);
}

.signal-reason {
  margin-top: 6px;
  line-height: 1.5;
  font-size: 0.9rem;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  color: #fff;
}

.badge-buy,
.progress-fill.badge-buy {
  background: #10b981;
}

.badge-sell,
.progress-fill.badge-sell {
  background: #ef4444;
}

.badge-hold,
.progress-fill.badge-hold {
  background: #f59e0b;
}

.confidence-row {
  margin-top: 12px;
  align-items: center;
  font-size: 0.85rem;
}

.progress-track {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
  margin-left: 12px;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.risk-grid {
  justify-content: flex-start;
  gap: 48px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.risk-grid div {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warning-text {
  color: #f59e0b;
}

.error {
  color: #fca5a5;
}

@media (max-width: 1100px) {
  .dashboard-grid,
  .kpi-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .dashboard-grid,
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .section-header,
  .signal-top,
  .confidence-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .progress-track {
    width: 100%;
    margin-left: 0;
  }
}

@media (max-width: 420px) {
  .trade-dashboard {
    gap: var(--space-3);
  }
  .kpi-card,
  .signal-card,
  .card {
    padding: var(--space-3);
  }
}
</style>
