<template>
  <div class="decision-page">
    <section class="hero card">
      <div class="hero-copy">
        <p class="eyebrow">Quick Decision Dashboard</p>
        <h1>📊 今日決策面板</h1>
        <p class="hero-subtitle">{{ currentDateTimeLabel }} · {{ loading ? '同步最新信號中…' : '每 60 秒自動更新一次' }}</p>
      </div>
      <div class="hero-meta">
        <span class="meta-label">最後更新</span>
        <strong>{{ lastUpdatedLabel }}</strong>
      </div>
    </section>

    <section class="overview-grid">
      <article class="card sentiment-card">
        <div class="section-head">
          <div>
            <p class="section-kicker">Market Overview</p>
            <h2>大盤情緒溫度計</h2>
          </div>
          <span class="sentiment-tag" :class="sentimentClass">{{ sentimentLabel }}</span>
        </div>
        <div class="meter-shell">
          <div class="meter-track">
            <div class="meter-fill" :style="{ width: `${sentimentPercent}%` }"></div>
            <div class="meter-marker" :style="{ left: `${sentimentPercent}%` }"></div>
          </div>
          <div class="meter-scale">
            <span>空方</span>
            <span>中性</span>
            <span>多方</span>
          </div>
        </div>
        <div class="overview-stats">
          <div>
            <strong>{{ signalCounts.BUY }}</strong>
            <span>買進</span>
          </div>
          <div>
            <strong>{{ signalCounts.SELL }}</strong>
            <span>賣出</span>
          </div>
          <div>
            <strong>{{ signalCounts.HOLD }}</strong>
            <span>觀望</span>
          </div>
          <div>
            <strong>{{ averageConfidence }}%</strong>
            <span>平均信心</span>
          </div>
        </div>
      </article>

      <article class="card watchlist-card">
        <div class="section-head">
          <div>
            <p class="section-kicker">Watchlist</p>
            <h2>追蹤清單</h2>
          </div>
          <span class="watchlist-count">{{ trackedSymbols.length }} 檔</span>
        </div>
        <div class="watchlist-input-row">
          <div class="watchlist-search">
            <input
              v-model="watchInput"
              type="text"
              class="watchlist-input"
              placeholder="新增股票代碼或名稱，例如 2330 / 台積電"
              @keydown.enter.prevent="submitWatchInput"
            />
            <ul v-if="watchSearchResults.length" class="watchlist-dropdown">
              <li
                v-for="item in watchSearchResults"
                :key="`${item.symbol}-${item.name_zh}`"
                @click="addWatchSymbol(item.symbol)"
              >
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.name_zh || '未命名個股' }}</span>
              </li>
            </ul>
          </div>
          <button class="btn add-button" @click="submitWatchInput">加入追蹤</button>
        </div>
        <p class="watchlist-hint">自訂清單會儲存在本機瀏覽器 localStorage。</p>
        <div v-if="trackedSymbols.length" class="watchlist-chips">
          <button
            v-for="symbol in trackedSymbols"
            :key="symbol"
            type="button"
            class="watch-chip"
            :title="`移除 ${symbol}`"
            @click="removeWatchSymbol(symbol)"
          >
            {{ symbol }} <span>×</span>
          </button>
        </div>
        <div v-else class="empty-watchlist">目前沒有追蹤股票，請先加入清單。</div>
      </article>
    </section>

    <section class="toolbar card">
      <div class="filter-group">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="filter-pill"
          :class="{ active: selectedFilter === filter.value }"
          @click="selectedFilter = filter.value"
        >
          {{ filter.label }}
          <span>{{ filterCount(filter.value) }}</span>
        </button>
      </div>
      <button type="button" class="btn refresh-button" @click="loadDashboard">
        {{ loading ? '更新中…' : '立即更新' }}
      </button>
    </section>

    <section v-if="errorMessage" class="card feedback-card error-card">
      {{ errorMessage }}
    </section>
    <section v-else-if="loading && !cards.length" class="card feedback-card">
      正在整理今日追蹤個股的決策信號…
    </section>
    <section v-else-if="!cards.length" class="card feedback-card">
      尚未取得可顯示的信號，請稍後再試或新增追蹤股票。
    </section>

    <section v-else class="cards-grid">
      <article v-for="card in cards" :key="card.symbol" class="signal-card">
        <div class="card-top">
          <div>
            <div class="stock-title-row">
              <h3>{{ card.symbol }}</h3>
              <router-link :to="`/stocks/${card.symbol}`" class="analysis-link">分析 →</router-link>
            </div>
            <p class="stock-name">{{ card.name }}</p>
          </div>
          <div class="signal-badge" :class="signalClass(card.signal)">
            <strong>{{ signalText(card.signal) }}</strong>
            <span>{{ card.confidence }}%</span>
          </div>
        </div>

        <div class="price-row">
          <div>
            <p class="price-label">現價</p>
            <strong class="price-value">{{ formatCurrency(card.price) }}</strong>
          </div>
          <div class="price-change" :class="priceDeltaClass(card.changePercent)">
            {{ formatSigned(card.changePercent) }}%
          </div>
        </div>

        <div class="sparkline-shell">
          <div class="sparkline-head">
            <span>近 20 日走勢</span>
            <span>{{ card.sparkline.length ? `${card.sparkline.length} 筆` : '暫無資料' }}</span>
          </div>
          <div :ref="element => setSparklineRef(element, card.symbol)" class="sparkline"></div>
        </div>

        <div class="condition-block">
          <p class="condition-title">關鍵訊號條件</p>
          <ul class="condition-list">
            <li v-for="condition in card.topConditions" :key="condition">{{ condition }}</li>
          </ul>
        </div>

        <div class="card-foot">
          <span v-if="card.volumeRatio">量比 {{ formatNumber(card.volumeRatio, 2) }}x</span>
          <span v-else>量能資料同步中</span>
          <span>{{ card.reasoning }}</span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createChart } from 'lightweight-charts'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const WATCHLIST_STORAGE_KEY = 'decision-dashboard-watchlist'
const filters = [
  { label: '全部', value: 'ALL' },
  { label: '買進', value: 'BUY' },
  { label: '賣出', value: 'SELL' },
  { label: '觀望', value: 'HOLD' },
]
const signalPriority = { BUY: 0, SELL: 1, HOLD: 2 }
const signalColors = {
  BUY: { line: '#22c55e', top: 'rgba(34, 197, 94, 0.32)', bottom: 'rgba(34, 197, 94, 0.02)' },
  SELL: { line: '#f87171', top: 'rgba(248, 113, 113, 0.28)', bottom: 'rgba(248, 113, 113, 0.02)' },
  HOLD: { line: '#cbd5e1', top: 'rgba(148, 163, 184, 0.24)', bottom: 'rgba(148, 163, 184, 0.02)' },
}

const now = ref(new Date())
const lastUpdatedAt = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedFilter = ref('ALL')
const rawSignals = ref([])
const stockProfiles = ref({})
const priceSnapshots = ref({})
const watchInput = ref('')
const watchSearchResults = ref([])
const storedWatchlist = ref(loadStoredWatchlist())

const sparklineContainers = new Map()
const sparklineCharts = new Map()
let refreshTimer = null
let clockTimer = null
let searchTimer = null
let sparklineFrame = 0

const trackedSymbols = computed(() => Array.isArray(storedWatchlist.value) ? uniqueSymbols(storedWatchlist.value) : [])

const signalCounts = computed(() => ({
  BUY: rawSignals.value.filter(item => item.signal === 'BUY').length,
  SELL: rawSignals.value.filter(item => item.signal === 'SELL').length,
  HOLD: rawSignals.value.filter(item => item.signal === 'HOLD').length,
}))

const averageConfidence = computed(() => {
  if (!rawSignals.value.length) return 0
  const total = rawSignals.value.reduce((sum, item) => sum + item.confidence, 0)
  return Math.round(total / rawSignals.value.length)
})

const sentimentScore = computed(() => {
  if (!rawSignals.value.length) return 0
  const totalWeight = rawSignals.value.reduce((sum, item) => sum + item.confidence, 0)
  if (!totalWeight) return 0
  const weighted = rawSignals.value.reduce((sum, item) => {
    const direction = item.signal === 'BUY' ? 1 : item.signal === 'SELL' ? -1 : 0
    return sum + direction * item.confidence
  }, 0)
  return weighted / totalWeight
})

const sentimentPercent = computed(() => Math.round(((sentimentScore.value + 1) / 2) * 100))
const sentimentLabel = computed(() => {
  if (sentimentScore.value >= 0.45) return '強勢多方'
  if (sentimentScore.value >= 0.15) return '偏多'
  if (sentimentScore.value <= -0.45) return '強勢空方'
  if (sentimentScore.value <= -0.15) return '偏空'
  return '中性觀望'
})
const sentimentClass = computed(() => {
  if (sentimentScore.value >= 0.15) return 'bullish'
  if (sentimentScore.value <= -0.15) return 'bearish'
  return 'neutral'
})

const currentDateTimeLabel = computed(() => formatDateTime(now.value, true))
const lastUpdatedLabel = computed(() => lastUpdatedAt.value ? formatDateTime(lastUpdatedAt.value, false) : '尚未同步')

const cards = computed(() => {
  const base = rawSignals.value
    .filter(item => selectedFilter.value === 'ALL' || item.signal === selectedFilter.value)
    .map(item => {
      const profile = stockProfiles.value[item.symbol] || {}
      const priceSnapshot = priceSnapshots.value[item.symbol] || {}
      return {
        ...item,
        name: profile.name_zh || profile.name || item.name || '未命名個股',
        price: priceSnapshot.latestPrice ?? item.price,
        changePercent: priceSnapshot.changePercent ?? 0,
        sparkline: priceSnapshot.sparkline || [],
        topConditions: buildTopConditions(item),
      }
    })

  return base.sort((left, right) => {
    if (right.confidence !== left.confidence) return right.confidence - left.confidence
    const priorityDiff = (signalPriority[left.signal] ?? 9) - (signalPriority[right.signal] ?? 9)
    if (priorityDiff !== 0) return priorityDiff
    return left.symbol.localeCompare(right.symbol)
  })
})

watch(watchInput, value => {
  if (searchTimer) window.clearTimeout(searchTimer)
  if (!value.trim()) {
    watchSearchResults.value = []
    return
  }
  searchTimer = window.setTimeout(() => {
    searchWatchCandidates(value.trim())
  }, 250)
})

watch(cards, async () => {
  await nextTick()
  queueSparklineRender()
}, { deep: true })

onMounted(async () => {
  await loadDashboard()
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
  refreshTimer = window.setInterval(loadDashboard, 60000)
  window.addEventListener('resize', queueSparklineRender)
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (searchTimer) window.clearTimeout(searchTimer)
  if (sparklineFrame) window.cancelAnimationFrame(sparklineFrame)
  window.removeEventListener('resize', queueSparklineRender)
  destroyAllSparklines()
})

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''

  try {
    const symbols = trackedSymbols.value
    if (storedWatchlist.value && symbols.length === 0) {
      rawSignals.value = []
      priceSnapshots.value = {}
      lastUpdatedAt.value = new Date()
      return
    }

    const query = new URLSearchParams({ type: 'ALL' })
    if (symbols.length) {
      query.set('symbols', symbols.join(','))
    }

    const payload = await apiGet(`/api/v1/agent/signals?${query.toString()}`)
    const normalizedSignals = normalizeSignals(payload)
    rawSignals.value = normalizedSignals

    if (storedWatchlist.value === null && normalizedSignals.length) {
      storedWatchlist.value = normalizedSignals.map(item => item.symbol)
      persistWatchlist()
    }

    await Promise.allSettled(uniqueSymbols(normalizedSignals.map(item => item.symbol)).map(symbol => hydrateStockCard(symbol)))
    lastUpdatedAt.value = new Date()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '載入決策面板失敗'
    rawSignals.value = []
  } finally {
    loading.value = false
  }
}

async function hydrateStockCard(symbol) {
  const end = new Date()
  const start = new Date(end.getTime() - 45 * 86400000)
  const startDate = toDateInputValue(start)
  const endDate = toDateInputValue(end)

  const [profileResult, priceResult] = await Promise.allSettled([
    loadStockProfile(symbol),
    apiGet(`/api/v1/stocks/${symbol}/price?start=${startDate}&end=${endDate}`),
  ])

  if (profileResult.status === 'fulfilled' && profileResult.value) {
    stockProfiles.value = {
      ...stockProfiles.value,
      [symbol]: profileResult.value,
    }
  }

  if (priceResult.status === 'fulfilled') {
    const items = Array.isArray(priceResult.value?.items) ? priceResult.value.items : []
    const latest = items[items.length - 1]
    const previous = items.length > 1 ? items[items.length - 2] : latest
    const previousClose = Number(previous?.close ?? latest?.close ?? 0)
    const latestClose = Number(latest?.close ?? 0)
    const changePercent = previousClose > 0 ? ((latestClose - previousClose) / previousClose) * 100 : 0

    priceSnapshots.value = {
      ...priceSnapshots.value,
      [symbol]: {
        latestPrice: latestClose || null,
        changePercent: Number.isFinite(changePercent) ? roundNumber(changePercent, 2) : 0,
        sparkline: items.slice(-20).map(item => ({
          time: item.date,
          value: Number(item.close ?? 0),
        })).filter(item => item.value > 0),
      },
    }
  }
}

async function loadStockProfile(symbol) {
  if (stockProfiles.value[symbol]) return stockProfiles.value[symbol]

  try {
    return await apiGet(`/api/v1/stocks/${symbol}/info`)
  } catch {
    const payload = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(symbol)}`)
    return payload.items?.find(item => item.symbol === symbol) || payload.items?.[0] || { symbol, name_zh: symbol }
  }
}

async function searchWatchCandidates(query) {
  try {
    const payload = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(query)}`)
    watchSearchResults.value = (payload.items || []).slice(0, 8)
  } catch {
    watchSearchResults.value = []
  }
}

async function submitWatchInput() {
  const query = watchInput.value.trim()
  if (!query) return

  const exactMatch = watchSearchResults.value.find(item => item.symbol === query)
  if (exactMatch) {
    addWatchSymbol(exactMatch.symbol)
    return
  }

  try {
    const payload = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(query)}`)
    const candidate = payload.items?.find(item => item.symbol === query || item.name_zh === query) || payload.items?.[0]
    if (candidate?.symbol) {
      addWatchSymbol(candidate.symbol)
      return
    }
    errorMessage.value = `找不到「${query}」對應的股票代碼`
  } catch {
    errorMessage.value = `找不到「${query}」對應的股票代碼`
  }
}

function addWatchSymbol(symbol) {
  const next = uniqueSymbols([symbol, ...trackedSymbols.value])
  storedWatchlist.value = next
  persistWatchlist()
  watchInput.value = ''
  watchSearchResults.value = []
  errorMessage.value = ''
  loadDashboard()
}

function removeWatchSymbol(symbol) {
  storedWatchlist.value = trackedSymbols.value.filter(item => item !== symbol)
  persistWatchlist()
  loadDashboard()
}

function persistWatchlist() {
  localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(storedWatchlist.value || []))
}

function loadStoredWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY)
    if (raw === null) return null
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? uniqueSymbols(parsed) : null
  } catch {
    return null
  }
}

function normalizeSignals(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : []
  return items.map(item => ({
    symbol: String(item.symbol || '').trim(),
    signal: normalizeSignal(item.signal),
    confidence: normalizePercent(item.confidence),
    price: Number(item.price ?? 0),
    reasoning: item.reasoning || '暫無推論說明',
    conditions: Array.isArray(item.conditions) ? item.conditions : [],
    indicators: item.indicators && typeof item.indicators === 'object' ? item.indicators : {},
    volumeRatio: Number(item.volume_ratio ?? 0) || null,
  })).filter(item => item.symbol)
}

function normalizeSignal(value) {
  const signal = String(value || 'HOLD').toUpperCase()
  return ['BUY', 'SELL', 'HOLD'].includes(signal) ? signal : 'HOLD'
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function buildTopConditions(signal) {
  const metConditions = signal.conditions
    .filter(item => item?.met)
    .map(item => humanizeCondition(item, signal.indicators, signal.volumeRatio))

  const fallbacks = [
    signal.indicators?.rsi14 != null ? `RSI ${formatNumber(signal.indicators.rsi14, 2)}` : null,
    signal.indicators?.sma20 != null ? `SMA20 ${formatNumber(signal.indicators.sma20, 2)}` : null,
    signal.indicators?.macd != null && signal.indicators?.macd_signal != null
      ? `MACD ${formatNumber(signal.indicators.macd, 2)} / ${formatNumber(signal.indicators.macd_signal, 2)}`
      : null,
    signal.volumeRatio ? `量比 ${formatNumber(signal.volumeRatio, 2)}x` : null,
    ...(signal.reasoning || '').split(';').map(item => item.trim()).filter(Boolean),
  ].filter(Boolean)

  return [...new Set([...metConditions, ...fallbacks])].slice(0, 3)
}

function humanizeCondition(condition, indicators, volumeRatio) {
  switch (condition.name) {
    case 'RSI(14) oversold':
      return `RSI 超賣 ${formatNumber(indicators?.rsi14, 2)}`
    case 'RSI(14) overbought':
      return `RSI 過熱 ${formatNumber(indicators?.rsi14, 2)}`
    case 'MACD golden cross':
      return 'MACD 黃金交叉'
    case 'MACD death cross':
      return 'MACD 死亡交叉'
    case 'Price above SMA20':
      return `站上 SMA20 ${formatNumber(indicators?.sma20, 2)}`
    case 'Touch Bollinger lower':
      return '觸及布林下緣'
    case 'Touch Bollinger upper':
      return '觸及布林上緣'
    case 'Volume confirmation':
      return `量能確認 ${formatNumber(volumeRatio, 2)}x`
    default:
      return [condition.name, condition.value].filter(Boolean).join(' ')
  }
}

function signalText(signal) {
  return signal === 'BUY' ? '買進' : signal === 'SELL' ? '賣出' : '觀望'
}

function signalClass(signal) {
  return signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'hold'
}

function priceDeltaClass(changePercent) {
  if (changePercent > 0) return 'up'
  if (changePercent < 0) return 'down'
  return 'flat'
}

function filterCount(signalType) {
  return signalType === 'ALL'
    ? rawSignals.value.length
    : rawSignals.value.filter(item => item.signal === signalType).length
}

function formatCurrency(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return '--'
  return `NT$ ${numeric.toFixed(2)}`
}

function formatSigned(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return '0.00'
  const fixed = numeric.toFixed(2)
  return numeric > 0 ? `+${fixed}` : fixed
}

function formatNumber(value, digits = 2) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  return numeric.toFixed(digits)
}

function roundNumber(value, digits = 2) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function formatDateTime(value, showSeconds) {
  return new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: showSeconds ? '2-digit' : undefined,
    hour12: false,
  }).format(value)
}

function toDateInputValue(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function uniqueSymbols(items) {
  return [...new Set((items || []).map(item => String(item || '').trim()).filter(Boolean))]
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.detail || 'API 請求失敗')
  return payload?.data ?? payload
}

function setSparklineRef(element, symbol) {
  if (element) {
    sparklineContainers.set(symbol, element)
    return
  }
  sparklineContainers.delete(symbol)
  destroySparkline(symbol)
}

function queueSparklineRender() {
  if (sparklineFrame) window.cancelAnimationFrame(sparklineFrame)
  sparklineFrame = window.requestAnimationFrame(renderSparklines)
}

function renderSparklines() {
  sparklineFrame = 0
  const visibleSymbols = new Set(cards.value.map(item => item.symbol))

  for (const symbol of sparklineCharts.keys()) {
    if (!visibleSymbols.has(symbol) || !sparklineContainers.has(symbol)) {
      destroySparkline(symbol)
    }
  }

  for (const card of cards.value) {
    const container = sparklineContainers.get(card.symbol)
    const points = Array.isArray(card.sparkline) ? card.sparkline : []
    if (!container || !points.length) continue

    const palette = signalColors[card.signal] || signalColors.HOLD
    const width = Math.max(container.clientWidth, 160)
    let sparkline = sparklineCharts.get(card.symbol)

    if (!sparkline) {
      const chart = createChart(container, {
        width,
        height: 82,
        layout: {
          background: { color: 'transparent' },
          textColor: '#94a3b8',
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { visible: false },
        },
        leftPriceScale: { visible: false },
        rightPriceScale: { visible: false },
        timeScale: { visible: false, borderVisible: false },
        crosshair: {
          vertLine: { visible: false, labelVisible: false },
          horzLine: { visible: false, labelVisible: false },
        },
        handleScale: false,
        handleScroll: false,
      })
      const series = chart.addAreaSeries({
        lineColor: palette.line,
        topColor: palette.top,
        bottomColor: palette.bottom,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      sparkline = { chart, series }
      sparklineCharts.set(card.symbol, sparkline)
    } else {
      sparkline.chart.applyOptions({ width })
      sparkline.series.applyOptions({
        lineColor: palette.line,
        topColor: palette.top,
        bottomColor: palette.bottom,
      })
    }

    sparkline.series.setData(points)
    sparkline.chart.timeScale().fitContent()
  }
}

function destroySparkline(symbol) {
  const sparkline = sparklineCharts.get(symbol)
  if (!sparkline) return
  sparkline.chart.remove()
  sparklineCharts.delete(symbol)
}

function destroyAllSparklines() {
  for (const symbol of [...sparklineCharts.keys()]) {
    destroySparkline(symbol)
  }
}
</script>

<style scoped>
.decision-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero,
.toolbar,
.section-head,
.card-top,
.price-row,
.sparkline-head,
.card-foot,
.stock-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hero {
  padding: 24px 28px;
  border-color: rgba(59, 130, 246, 0.28);
  background: radial-gradient(circle at top right, rgba(37, 99, 235, 0.24), transparent 38%), #0f172a;
}

.eyebrow,
.section-kicker,
.hero-subtitle,
.meta-label,
.stock-name,
.price-label,
.sparkline-head,
.watchlist-hint,
.card-foot,
.empty-watchlist,
.feedback-card {
  color: #94a3b8;
}

.hero-copy h1,
.section-head h2,
.stock-title-row h3 {
  margin: 4px 0;
}

.hero-copy h1 {
  font-size: 2rem;
}

.hero-meta {
  text-align: right;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
  gap: 20px;
}

.sentiment-card,
.watchlist-card {
  padding: 22px;
}

.sentiment-tag,
.watchlist-count {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
}

.sentiment-tag.bullish {
  background: rgba(22, 163, 74, 0.18);
  color: #86efac;
}

.sentiment-tag.bearish {
  background: rgba(220, 38, 38, 0.18);
  color: #fca5a5;
}

.sentiment-tag.neutral,
.watchlist-count {
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
}

.meter-shell {
  margin-top: 18px;
}

.meter-track {
  position: relative;
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(90deg, #dc2626 0%, #6b7280 50%, #16a34a 100%);
  overflow: hidden;
}

.meter-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(15, 23, 42, 0.55), rgba(15, 23, 42, 0.05));
}

.meter-marker {
  position: absolute;
  top: 50%;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 3px solid #f8fafc;
  background: #0f172a;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 0 4px rgba(15, 23, 42, 0.5);
}

.meter-scale,
.overview-stats,
.watchlist-chips,
.filter-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.meter-scale {
  justify-content: space-between;
  margin-top: 10px;
  color: #94a3b8;
  font-size: 0.85rem;
}

.overview-stats {
  margin-top: 18px;
}

.overview-stats > div {
  min-width: 88px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.overview-stats strong {
  display: block;
  font-size: 1.25rem;
}

.overview-stats span {
  color: #94a3b8;
  font-size: 0.82rem;
}

.watchlist-input-row {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-top: 16px;
}

.watchlist-search {
  position: relative;
}

.watchlist-input {
  width: 100%;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #f8fafc;
  outline: none;
}

.watchlist-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
}

.watchlist-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  z-index: 20;
  list-style: none;
  padding: 8px;
  border-radius: 14px;
  border: 1px solid rgba(51, 65, 85, 0.9);
  background: #0f172a;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.35);
}

.watchlist-dropdown li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}

.watchlist-dropdown li:hover {
  background: rgba(37, 99, 235, 0.2);
}

.add-button,
.refresh-button {
  padding-inline: 18px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
}

.watchlist-hint {
  margin-top: 10px;
  font-size: 0.85rem;
}

.watchlist-chips {
  margin-top: 16px;
}

.watch-chip {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.72);
  color: #e2e8f0;
  cursor: pointer;
}

.watch-chip span {
  margin-left: 6px;
  color: #94a3b8;
}

.empty-watchlist,
.feedback-card {
  padding: 20px;
  text-align: center;
}

.toolbar {
  padding: 14px 18px;
}

.filter-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.68);
  color: #cbd5e1;
  cursor: pointer;
}

.filter-pill span {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  font-size: 0.78rem;
}

.filter-pill.active {
  border-color: rgba(37, 99, 235, 0.75);
  background: rgba(37, 99, 235, 0.18);
  color: #fff;
}

.error-card {
  color: #fecaca;
  border-color: rgba(220, 38, 38, 0.24);
  background: rgba(127, 29, 29, 0.18);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.signal-card {
  padding: 20px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.15);
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.98));
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
}

.analysis-link {
  color: #60a5fa;
  text-decoration: none;
  font-weight: 600;
}

.stock-title-row h3 {
  font-size: 1.5rem;
}

.stock-name {
  font-size: 0.92rem;
}

.signal-badge {
  min-width: 94px;
  padding: 10px 12px;
  border-radius: 16px;
  text-align: center;
  color: #fff;
}

.signal-badge strong {
  display: block;
  font-size: 1.05rem;
  letter-spacing: 0.04em;
}

.signal-badge span {
  display: block;
  margin-top: 4px;
  font-size: 0.88rem;
}

.signal-badge.buy {
  background: linear-gradient(180deg, #16a34a, #166534);
}

.signal-badge.sell {
  background: linear-gradient(180deg, #dc2626, #991b1b);
}

.signal-badge.hold {
  background: linear-gradient(180deg, #6b7280, #475569);
}

.price-row {
  margin-top: 18px;
  padding: 14px 0;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.price-value {
  font-size: 1.6rem;
}

.price-change {
  padding: 8px 12px;
  border-radius: 999px;
  font-weight: 700;
}

.price-change.up {
  color: #86efac;
  background: rgba(22, 163, 74, 0.14);
}

.price-change.down {
  color: #fca5a5;
  background: rgba(220, 38, 38, 0.14);
}

.price-change.flat {
  color: #e2e8f0;
  background: rgba(107, 114, 128, 0.2);
}

.sparkline-shell {
  margin-top: 16px;
}

.sparkline-head {
  color: #94a3b8;
  font-size: 0.82rem;
}

.sparkline {
  width: 100%;
  min-height: 82px;
  margin-top: 10px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.72);
}

.condition-block {
  margin-top: 18px;
}

.condition-title {
  margin-bottom: 10px;
  color: #e2e8f0;
  font-weight: 600;
}

.condition-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.condition-list li {
  position: relative;
  padding-left: 16px;
  color: #cbd5e1;
}

.condition-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #2563eb;
}

.card-foot {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed rgba(148, 163, 184, 0.18);
  color: #94a3b8;
  font-size: 0.8rem;
  align-items: flex-start;
}

.card-foot span:last-child {
  text-align: right;
}

@media (max-width: 1180px) {
  .overview-grid,
  .cards-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .hero,
  .toolbar,
  .section-head,
  .card-top,
  .price-row,
  .stock-title-row,
  .card-foot {
    flex-direction: column;
    align-items: flex-start;
  }

  .overview-grid,
  .cards-grid,
  .watchlist-input-row {
    grid-template-columns: 1fr;
  }

  .hero-meta,
  .card-foot span:last-child {
    text-align: left;
  }
}
</style>
