<template>
  <div class="analysis-page">
    <aside class="sidebar">
      <div class="card stock-info">
        <h2>{{ symbol }}</h2>
        <div v-if="stockInfo">
          <p class="stock-name">{{ stockInfo.name_zh }}</p>
          <p class="stock-industry">{{ stockInfo.industry }}</p>
        </div>
        <div v-if="latestPrice" class="price-display">
          <span class="price">{{ latestPrice.close }}</span>
          <span :class="latestPrice.change >= 0 ? 'up' : 'down'">
            {{ latestPrice.change >= 0 ? '+' : '' }}{{ latestPrice.changePercent }}%
          </span>
        </div>
      </div>
      <div class="card" style="margin-top: 12px;">
        <h4>快速導航</h4>
        <ul class="quick-nav">
          <li @click="activeTab = 'technical'" :class="{ active: activeTab === 'technical' }">技術分析</li>
          <li @click="activeTab = 'fundamental'" :class="{ active: activeTab === 'fundamental' }">基本面</li>
          <li @click="activeTab = 'chip'" :class="{ active: activeTab === 'chip' }">籌碼面</li>
          <li @click="activeTab = 'ai'" :class="{ active: activeTab === 'ai' }">AI 預測</li>
        </ul>
      </div>
      <button class="btn btn-primary" style="margin-top: 12px; width: 100%;" @click="goBacktest">
        前往回測
      </button>
    </aside>

    <main class="content">
      <div class="tabs">
        <span class="tab" :class="{ active: activeTab === 'technical' }" @click="activeTab = 'technical'">技術分析</span>
        <span class="tab" :class="{ active: activeTab === 'fundamental' }" @click="activeTab = 'fundamental'">基本面</span>
        <span class="tab" :class="{ active: activeTab === 'chip' }" @click="activeTab = 'chip'">籌碼面</span>
        <span class="tab" :class="{ active: activeTab === 'ai' }" @click="activeTab = 'ai'">AI 預測</span>
      </div>

      <!-- Technical Analysis Tab -->
      <div v-if="activeTab === 'technical'">
        <div class="time-range">
          <button v-for="r in ranges" :key="r.label" :class="{ active: selectedRange === r.label }"
            @click="setRange(r)" class="range-btn">{{ r.label }}</button>
        </div>
        <div ref="chartContainer" class="chart-container"></div>
        <div v-if="technicalSignals" class="card" style="margin-top: 16px;">
          <h4>技術訊號摘要</h4>
          <p v-for="(val, key) in technicalIndicators" :key="key">
            <strong>{{ key }}:</strong> {{ JSON.stringify(val) }}
          </p>
        </div>
      </div>

      <!-- Fundamental Tab -->
      <div v-if="activeTab === 'fundamental'">
        <div class="card">
          <h4>月營收趨勢</h4>
          <div v-if="fundamentalData.revenue_monthly" class="data-table">
            <table>
              <thead><tr><th>月份</th><th>營收</th><th>YoY%</th></tr></thead>
              <tbody>
                <tr v-for="r in fundamentalData.revenue_monthly" :key="r.month">
                  <td>{{ r.month }}</td>
                  <td>{{ (r.revenue / 1e8).toFixed(1) }}億</td>
                  <td :class="r.yoy >= 0 ? 'up' : 'down'">{{ r.yoy }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty">載入中...</p>
        </div>
      </div>

      <!-- Chip Tab -->
      <div v-if="activeTab === 'chip'">
        <div class="card">
          <h4>三大法人買賣超</h4>
          <div v-if="chipData.items" class="data-table">
            <table>
              <thead><tr><th>日期</th><th>外資</th><th>投信</th><th>自營</th></tr></thead>
              <tbody>
                <tr v-for="r in chipData.items.slice(-20)" :key="r.date">
                  <td>{{ r.date }}</td>
                  <td :class="r.foreign_net_buy >= 0 ? 'up' : 'down'">{{ r.foreign_net_buy }}</td>
                  <td :class="r.investment_trust_net_buy >= 0 ? 'up' : 'down'">{{ r.investment_trust_net_buy }}</td>
                  <td :class="r.dealer_net_buy >= 0 ? 'up' : 'down'">{{ r.dealer_net_buy }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="chipData.summary" style="margin-top:12px;">
            外資連買 {{ chipData.summary.foreign_buy_streak }} 日 |
            投信趨勢: {{ chipData.summary.investment_trust_trend }}
          </p>
        </div>
      </div>

      <!-- AI Prediction Tab -->
      <div v-if="activeTab === 'ai'">
        <div class="card">
          <h4>AI 預測</h4>
          <button class="btn btn-primary" @click="runPrediction" :disabled="predicting">
            {{ predicting ? '預測中...' : '執行預測 (5日)' }}
          </button>
          <div v-if="prediction" style="margin-top: 16px;">
            <div class="grid-3">
              <div class="metric-card card">
                <div class="value" :class="prediction.direction === 'up' ? 'up' : 'down'">
                  {{ prediction.direction === 'up' ? '📈 上漲' : '📉 下跌' }}
                </div>
                <div class="label">預測方向</div>
              </div>
              <div class="metric-card card">
                <div class="value">{{ (prediction.confidence * 100).toFixed(1) }}%</div>
                <div class="label">信心度</div>
              </div>
              <div class="metric-card card">
                <div class="value">{{ prediction.horizon_days }}日</div>
                <div class="label">預測期間</div>
              </div>
            </div>
            <div class="card" style="margin-top: 12px;" v-if="prediction.feature_importance">
              <h4>特徵重要性 (Top 5)</h4>
              <ul>
                <li v-for="f in prediction.feature_importance.slice(0, 5)" :key="f.feature">
                  {{ f.feature }}: {{ (f.importance * 100).toFixed(1) }}%
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { createChart } from 'lightweight-charts'

const route = useRoute()
const router = useRouter()
const symbol = ref(route.params.symbol)
const activeTab = ref('technical')
const chartContainer = ref(null)
const stockInfo = ref(null)
const latestPrice = ref(null)
const technicalIndicators = ref(null)
const technicalSignals = ref(false)
const fundamentalData = ref({})
const chipData = ref({})
const prediction = ref(null)
const predicting = ref(false)
const selectedRange = ref('1Y')
let chart = null

const ranges = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: '3Y', days: 1095 },
  { label: '5Y', days: 1825 },
]

watch(() => route.params.symbol, (newSymbol) => {
  symbol.value = newSymbol
  loadData()
})

onMounted(() => {
  loadData()
  saveRecent()
})

function saveRecent() {
  const recent = JSON.parse(localStorage.getItem('recentStocks') || '[]')
  const updated = [symbol.value, ...recent.filter(s => s !== symbol.value)].slice(0, 10)
  localStorage.setItem('recentStocks', JSON.stringify(updated))
}

async function loadData() {
  await Promise.all([
    loadStockInfo(),
    loadPrice(365),
  ])
}

async function loadStockInfo() {
  try {
    const resp = await axios.get(`/api/v1/stocks/${symbol.value}/info`)
    stockInfo.value = resp.data.data
  } catch { /* ignore */ }
}

async function loadPrice(days) {
  const end = new Date().toISOString().split('T')[0]
  const start = new Date(Date.now() - days * 86400000).toISOString().split('T')[0]

  try {
    const resp = await axios.get(`/api/v1/stocks/${symbol.value}/price?start=${start}&end=${end}`)
    const items = resp.data.data.items
    if (items.length > 0) {
      const last = items[items.length - 1]
      const prev = items.length > 1 ? items[items.length - 2] : last
      const change = last.close - prev.close
      latestPrice.value = {
        close: last.close,
        change,
        changePercent: ((change / prev.close) * 100).toFixed(2),
      }
    }
    await nextTick()
    renderChart(items)
  } catch { /* ignore */ }
}

function renderChart(items) {
  if (!chartContainer.value) return
  if (chart) chart.remove()

  chart = createChart(chartContainer.value, {
    width: chartContainer.value.clientWidth,
    height: 400,
    layout: { background: { color: '#1e293b' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
  })

  const candleSeries = chart.addCandlestickSeries({
    upColor: '#16a34a',
    downColor: '#dc2626',
    borderUpColor: '#16a34a',
    borderDownColor: '#dc2626',
    wickUpColor: '#16a34a',
    wickDownColor: '#dc2626',
  })

  const data = items.map(i => ({
    time: i.date,
    open: i.open,
    high: i.high,
    low: i.low,
    close: i.close,
  }))
  candleSeries.setData(data)

  const volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  })
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
  volumeSeries.setData(items.map(i => ({
    time: i.date,
    value: i.volume,
    color: i.close >= i.open ? '#16a34a80' : '#dc262680',
  })))

  chart.timeScale().fitContent()
}

function setRange(r) {
  selectedRange.value = r.label
  loadPrice(r.days)
}

async function runPrediction() {
  predicting.value = true
  try {
    const resp = await axios.post('/api/v1/ml/predict', {
      symbol: symbol.value,
      horizon_days: 5,
    })
    prediction.value = resp.data.data
  } catch { /* ignore */ }
  predicting.value = false
}

function goBacktest() {
  router.push(`/stocks/${symbol.value}/backtest`)
}

// Load tab-specific data
watch(activeTab, async (tab) => {
  if (tab === 'fundamental' && !fundamentalData.value.revenue_monthly) {
    try {
      const resp = await axios.get(`/api/v1/analysis/${symbol.value}/fundamental`)
      fundamentalData.value = resp.data.data
    } catch { /* ignore */ }
  }
  if (tab === 'chip' && !chipData.value.items) {
    try {
      const resp = await axios.get(`/api/v1/analysis/${symbol.value}/chip`)
      chipData.value = resp.data.data
    } catch { /* ignore */ }
  }
})
</script>

<style scoped>
.analysis-page {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
}
.sidebar { position: sticky; top: 80px; align-self: start; }
.stock-info h2 { font-size: 1.5rem; }
.stock-name { color: var(--text-secondary); margin-top: 4px; }
.stock-industry { color: var(--text-secondary); font-size: 0.8rem; }
.price-display { margin-top: 12px; font-size: 1.3rem; font-weight: 700; }
.price-display .price { margin-right: 8px; }
.quick-nav { list-style: none; margin-top: 8px; }
.quick-nav li { padding: 6px 0; cursor: pointer; color: var(--text-secondary); }
.quick-nav li.active, .quick-nav li:hover { color: var(--accent-blue); }
.time-range { display: flex; gap: 8px; margin-bottom: 12px; }
.range-btn { background: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-secondary); padding: 4px 12px; border-radius: 4px; cursor: pointer; }
.range-btn.active { background: var(--accent-blue); color: white; border-color: var(--accent-blue); }
.chart-container { width: 100%; border-radius: var(--radius); overflow: hidden; }
.data-table { overflow-x: auto; margin-top: 12px; }
.data-table table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.data-table th, .data-table td { padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border-color); }
.data-table th { color: var(--text-secondary); }
.empty { color: var(--text-secondary); padding: 12px 0; }
</style>
