<template>
  <div class="decision-dashboard">
    <header class="page-header">
      <div class="header-main">
        <div class="header-copy">
          <p class="page-kicker">Trading Decision Center</p>
          <h1>今日決策面板</h1>
          <p class="page-subtitle">
            以交易席位等級的資訊密度整合 AI 決策訊號、價格動能與觀察清單，快速鎖定今天最值得出手的機會。
          </p>
        </div>

        <div class="header-meta">
          <div class="datetime-panel">
            <span class="meta-label">Live Datetime</span>
            <strong>{{ liveDateTime }}</strong>
          </div>
          <div class="freshness-pill" :class="freshnessTone">
            <span class="pulse-dot"></span>
            <span>{{ freshnessLabel }}</span>
          </div>
        </div>
      </div>
      <div class="header-accent"></div>
    </header>

    <section class="top-grid">
      <article class="market-pulse card">
        <div class="panel-head">
          <div>
            <p class="section-kicker">Market Pulse</p>
            <h2>市場脈動總覽</h2>
          </div>
          <div class="refresh-inline">
            <span class="pulse-dot small"></span>
            <span>{{ loading ? '資料同步中…' : '60 秒自動更新' }}</span>
          </div>
        </div>

        <div class="pulse-content">
          <div class="pulse-badges">
            <div class="count-badge buy">
              <span>BUY</span>
              <strong>{{ signalCounts.BUY }}</strong>
            </div>
            <div class="count-badge sell">
              <span>SELL</span>
              <strong>{{ signalCounts.SELL }}</strong>
            </div>
            <div class="count-badge hold">
              <span>HOLD</span>
              <strong>{{ signalCounts.HOLD }}</strong>
            </div>
            <div class="count-badge neutral">
              <span>AVG CONF.</span>
              <strong>{{ averageConfidence }}%</strong>
            </div>
          </div>

          <div class="sentiment-meter-card">
            <div class="sentiment-summary">
              <span class="meta-label">Overall Sentiment</span>
              <strong :class="sentimentClass">{{ sentimentLabel }}</strong>
            </div>
            <div class="meter-track" aria-hidden="true">
              <div class="meter-gradient"></div>
              <div class="meter-marker" :style="{ left: `${sentimentPercent}%` }"></div>
            </div>
            <div class="meter-scale">
              <span>Bearish</span>
              <span>Neutral</span>
              <span>Bullish</span>
            </div>
          </div>
        </div>
      </article>

      <article class="watchlist-panel card">
        <div class="panel-head">
          <div>
            <p class="section-kicker">Watchlist</p>
            <h2>追蹤清單</h2>
          </div>
          <span class="watchlist-total">{{ watchlist.length }} 檔</span>
        </div>

        <div class="watchlist-form">
          <div class="watchlist-input-shell">
            <input
              v-model="watchInput"
              type="text"
              class="watchlist-input"
              placeholder="新增代碼或公司名稱，例如 2330 / 台積電"
              @keydown.enter.prevent="submitWatchInput"
            />

            <ul v-if="watchSearchResults.length" class="watchlist-dropdown">
              <li
                v-for="item in watchSearchResults"
                :key="`${item.symbol}-${item.name}`"
                @click="addWatchSymbol(item.symbol)"
              >
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.name }}</span>
              </li>
            </ul>
          </div>

          <button type="button" class="action-button primary" @click="submitWatchInput">
            加入
          </button>
        </div>

        <p class="watchlist-note">追蹤清單會儲存在本機 localStorage，可跨重整保留。</p>

        <div v-if="watchlist.length" class="watchlist-chips">
          <button
            v-for="symbol in watchlist"
            :key="symbol"
            type="button"
            class="watch-chip"
            @click="removeWatchSymbol(symbol)"
          >
            <span>{{ symbol }}</span>
            <span class="chip-close">×</span>
          </button>
        </div>
        <div v-else class="watchlist-empty">
          尚未建立自選清單，目前顯示系統預設覆蓋標的。
        </div>
      </article>
    </section>

    <section class="filters-bar card">
      <div class="filter-pills" role="tablist" aria-label="Signal filters">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="filter-pill"
          :class="{ active: selectedFilter === filter.value }"
          @click="selectedFilter = filter.value"
        >
          <span>{{ filter.label }}</span>
          <strong>{{ filterCount(filter.value) }}</strong>
        </button>
      </div>

      <button type="button" class="action-button ghost" @click="loadDashboard(true)">
        <span v-if="loading" class="button-spinner"></span>
        <span>{{ loading ? '同步中' : '立即更新' }}</span>
      </button>
    </section>

    <section v-if="errorMessage" class="feedback-card error-state card">
      <div>
        <p class="meta-label">Error</p>
        <h3>資料載入失敗</h3>
        <p>{{ errorMessage }}</p>
      </div>
      <button type="button" class="action-button primary" @click="loadDashboard(true)">重試</button>
    </section>

    <section v-if="loading && !filteredCards.length" class="feedback-card loading-state card">
      <div class="loading-spinner"></div>
      <div>
        <h3>正在建立交易決策面板</h3>
        <p>抓取最新信號、價格脈動與追蹤清單資訊中。</p>
      </div>
    </section>

    <section v-else-if="!filteredCards.length && !errorMessage" class="feedback-card empty-state card">
      <div>
        <p class="meta-label">No Results</p>
        <h3>目前沒有符合條件的信號</h3>
        <p>請切換篩選條件、加入追蹤股票，或稍後重新整理。</p>
      </div>
    </section>

    <section v-else class="signals-grid">
      <article
        v-for="card in filteredCards"
        :key="card.symbol"
        class="signal-card"
      >
        <div class="signal-card-glow" :class="signalTone(card.signal)"></div>

        <div class="signal-head">
          <div class="signal-title-group">
            <div class="symbol-row">
              <h3>{{ card.symbol }}</h3>
              <router-link
                class="analysis-link"
                :to="{ name: 'analysis', params: { symbol: card.symbol } }"
              >
                分析→
              </router-link>
            </div>
            <p class="company-name">{{ card.companyName }}</p>
          </div>

          <div class="signal-badge" :class="signalTone(card.signal)">
            <span>{{ signalLabel(card.signal) }}</span>
            <strong>{{ card.confidence }}%</strong>
          </div>
        </div>

        <div class="price-block">
          <div>
            <p class="meta-label">Current Price</p>
            <strong class="price-value">{{ formatPrice(card.price) }}</strong>
          </div>

          <div class="price-change" :class="deltaClass(card.change)">
            <span class="delta-arrow">{{ deltaArrow(card.change) }}</span>
            <div>
              <strong>{{ formatSigned(card.change) }}</strong>
              <span>{{ formatSigned(card.changePercent) }}%</span>
            </div>
          </div>
        </div>

        <p class="reasoning-text">{{ card.reasoning }}</p>

        <div class="sparkline-panel">
          <div class="sparkline-head">
            <span>近 20 日走勢</span>
            <span>{{ sparklineCaption(card) }}</span>
          </div>
          <div :ref="element => setSparklineRef(element, card.symbol)" class="sparkline"></div>
        </div>

        <div class="conditions-panel">
          <div class="conditions-head">
            <span>Conditions</span>
            <strong>{{ metCount(card.conditions) }}/{{ card.conditions.length }}</strong>
          </div>
          <ul class="conditions-list">
            <li v-for="condition in card.conditions" :key="`${card.symbol}-${condition.name}`">
              <span class="condition-dot" :class="{ met: condition.met }"></span>
              <div>
                <strong>{{ condition.name }}</strong>
                <span>{{ condition.value }}</span>
              </div>
            </li>
          </ul>
        </div>

        <div class="signal-footer">
          <span>量比 {{ card.volumeRatioLabel }}</span>
          <span>{{ formatGeneratedAt(card.generatedAt) }}</span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createChart } from 'lightweight-charts'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const WATCHLIST_STORAGE_KEY = 'finlab_watchlist'
const filters = [
  { label: '全部', value: 'ALL' },
  { label: '買進', value: 'BUY' },
  { label: '賣出', value: 'SELL' },
  { label: '觀望', value: 'HOLD' },
]
const signalRank = { BUY: 0, SELL: 1, HOLD: 2 }
const chartPalette = {
  BUY: { line: '#22c55e', top: 'rgba(16, 185, 129, 0.32)', bottom: 'rgba(16, 185, 129, 0.03)' },
  SELL: { line: '#f87171', top: 'rgba(239, 68, 68, 0.28)', bottom: 'rgba(239, 68, 68, 0.03)' },
  HOLD: { line: '#94a3b8', top: 'rgba(148, 163, 184, 0.22)', bottom: 'rgba(148, 163, 184, 0.03)' },
}

const now = ref(new Date())
const lastFetchedAt = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedFilter = ref('ALL')
const watchInput = ref('')
const watchSearchResults = ref([])
const watchlist = ref(loadWatchlist())
const rawSignals = ref([])
const profiles = ref({})
const histories = ref({})

const sparklineContainers = new Map()
const sparklineInstances = new Map()
let clockTimer = null
let refreshTimer = null
let searchTimer = null
let renderFrame = 0

const liveDateTime = computed(() => {
  const dateLabel = new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  }).format(now.value)
  const timeLabel = new Intl.DateTimeFormat('zh-TW', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(now.value)
  return `${dateLabel} ${timeLabel}`
})

const freshnessSeconds = computed(() => {
  if (!lastFetchedAt.value) return null
  return Math.max(0, Math.round((now.value.getTime() - lastFetchedAt.value.getTime()) / 1000))
})

const freshnessLabel = computed(() => {
  if (loading.value) return '即時同步中'
  if (freshnessSeconds.value === null) return '等待首次同步'
  if (freshnessSeconds.value < 5) return '剛剛更新'
  if (freshnessSeconds.value < 60) return `${freshnessSeconds.value} 秒前更新`
  const minutes = Math.floor(freshnessSeconds.value / 60)
  return `${minutes} 分鐘前更新`
})

const freshnessTone = computed(() => {
  if (loading.value) return 'fresh'
  if (freshnessSeconds.value === null || freshnessSeconds.value <= 75) return 'fresh'
  if (freshnessSeconds.value <= 150) return 'aging'
  return 'stale'
})

const enrichedCards = computed(() => {
  return rawSignals.value
    .map(item => {
      const profile = profiles.value[item.symbol] || {}
      const history = histories.value[item.symbol] || []
      const latestPoint = history[history.length - 1]
      const previousPoint = history.length > 1 ? history[history.length - 2] : null
      const price = latestPoint?.value ?? item.price
      const change = previousPoint ? roundNumber(price - previousPoint.value, 2) : 0
      const changePercent = previousPoint?.value
        ? roundNumber((change / previousPoint.value) * 100, 2)
        : 0

      return {
        ...item,
        companyName: profile.name || item.companyName || '未命名公司',
        price,
        history,
        change,
        changePercent,
        volumeRatioLabel: item.volumeRatio == null ? '—' : `${formatNumber(item.volumeRatio, 2)}x`,
      }
    })
    .sort((left, right) => {
      const rankDiff = (signalRank[left.signal] ?? 9) - (signalRank[right.signal] ?? 9)
      if (rankDiff !== 0) return rankDiff
      if (right.confidence !== left.confidence) return right.confidence - left.confidence
      return left.symbol.localeCompare(right.symbol)
    })
})

const filteredCards = computed(() => {
  return enrichedCards.value.filter(card => {
    return selectedFilter.value === 'ALL' || card.signal === selectedFilter.value
  })
})

const signalCounts = computed(() => ({
  BUY: enrichedCards.value.filter(item => item.signal === 'BUY').length,
  SELL: enrichedCards.value.filter(item => item.signal === 'SELL').length,
  HOLD: enrichedCards.value.filter(item => item.signal === 'HOLD').length,
}))

const averageConfidence = computed(() => {
  if (!enrichedCards.value.length) return 0
  const total = enrichedCards.value.reduce((sum, item) => sum + item.confidence, 0)
  return Math.round(total / enrichedCards.value.length)
})

const sentimentScore = computed(() => {
  if (!enrichedCards.value.length) return 0
  const totalWeight = enrichedCards.value.reduce((sum, item) => sum + item.confidence, 0)
  if (!totalWeight) return 0

  const score = enrichedCards.value.reduce((sum, item) => {
    const direction = item.signal === 'BUY' ? 1 : item.signal === 'SELL' ? -1 : 0
    return sum + direction * item.confidence
  }, 0)

  return score / totalWeight
})

const sentimentPercent = computed(() => {
  return Math.max(0, Math.min(100, Math.round(((sentimentScore.value + 1) / 2) * 100)))
})

const sentimentLabel = computed(() => {
  if (sentimentScore.value >= 0.4) return 'Bullish Bias'
  if (sentimentScore.value >= 0.12) return 'Slightly Bullish'
  if (sentimentScore.value <= -0.4) return 'Bearish Bias'
  if (sentimentScore.value <= -0.12) return 'Slightly Bearish'
  return 'Balanced / Neutral'
})

const sentimentClass = computed(() => {
  if (sentimentScore.value >= 0.12) return 'up'
  if (sentimentScore.value <= -0.12) return 'down'
  return 'flat'
})

watch(watchInput, value => {
  if (searchTimer) window.clearTimeout(searchTimer)

  if (!value.trim()) {
    watchSearchResults.value = []
    return
  }

  searchTimer = window.setTimeout(() => {
    searchSymbols(value.trim())
  }, 220)
})

watch(filteredCards, async () => {
  await nextTick()
  queueSparklineRender()
}, { deep: true })

onMounted(async () => {
  await loadDashboard()

  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)

  refreshTimer = window.setInterval(() => {
    loadDashboard()
  }, 60000)

  window.addEventListener('resize', queueSparklineRender)
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (searchTimer) window.clearTimeout(searchTimer)
  if (renderFrame) window.cancelAnimationFrame(renderFrame)
  window.removeEventListener('resize', queueSparklineRender)
  destroyAllSparklines()
})

async function loadDashboard(force = false) {
  if (loading.value && !force) return

  loading.value = true
  errorMessage.value = ''

  try {
    const query = new URLSearchParams({ type: 'ALL' })
    if (watchlist.value.length) {
      query.set('symbols', watchlist.value.join(','))
    }

    const payload = await apiGet(`/api/v1/agent/signals?${query.toString()}`)
    const items = normalizeSignals(payload)
    rawSignals.value = items

    await Promise.allSettled(uniqueSymbols(items.map(item => item.symbol)).map(symbol => hydrateSymbol(symbol)))
    lastFetchedAt.value = new Date()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '無法取得決策資料'
  } finally {
    loading.value = false
  }
}

async function hydrateSymbol(symbol) {
  const [profileResult, historyResult] = await Promise.allSettled([
    fetchProfile(symbol),
    fetchHistory(symbol),
  ])

  if (profileResult.status === 'fulfilled' && profileResult.value) {
    profiles.value = {
      ...profiles.value,
      [symbol]: profileResult.value,
    }
  }

  if (historyResult.status === 'fulfilled') {
    histories.value = {
      ...histories.value,
      [symbol]: historyResult.value,
    }
  }
}

async function fetchProfile(symbol) {
  if (profiles.value[symbol]) return profiles.value[symbol]

  try {
    const payload = await apiGet(`/api/v1/stocks/${symbol}/info`)
    return {
      name: payload.name_zh || payload.name || symbol,
    }
  } catch {
    const payload = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(symbol)}`)
    const match = extractItems(payload).find(item => String(item.symbol || '').trim() === symbol)
    return {
      name: match?.name_zh || match?.name || symbol,
    }
  }
}

async function fetchHistory(symbol) {
  const end = new Date()
  const start = new Date(end.getTime() - 45 * 86400000)
  const payload = await apiGet(
    `/api/v1/stocks/${symbol}/price?start=${toDateParam(start)}&end=${toDateParam(end)}`
  )

  return extractItems(payload)
    .map(item => ({
      time: normalizeDate(item.date || item.time || item.timestamp),
      value: toNumber(item.close),
    }))
    .filter(item => item.time && item.value > 0)
    .sort((left, right) => left.time.localeCompare(right.time))
    .slice(-20)
}

async function searchSymbols(query) {
  try {
    const payload = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(query)}`)
    watchSearchResults.value = extractItems(payload)
      .slice(0, 8)
      .map(item => ({
        symbol: String(item.symbol || '').trim(),
        name: item.name_zh || item.name || '未命名公司',
      }))
      .filter(item => item.symbol)
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
    const candidate = extractItems(payload).find(item => {
      const symbol = String(item.symbol || '').trim()
      const name = String(item.name_zh || item.name || '').trim()
      return symbol === query || name === query
    }) || extractItems(payload)[0]

    if (!candidate?.symbol) {
      throw new Error(`找不到「${query}」對應股票`)
    }

    addWatchSymbol(candidate.symbol)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : `找不到「${query}」對應股票`
  }
}

function addWatchSymbol(symbol) {
  watchlist.value = uniqueSymbols([symbol, ...watchlist.value])
  persistWatchlist()
  watchInput.value = ''
  watchSearchResults.value = []
  errorMessage.value = ''
  loadDashboard(true)
}

function removeWatchSymbol(symbol) {
  watchlist.value = watchlist.value.filter(item => item !== symbol)
  persistWatchlist()
  loadDashboard(true)
}

function persistWatchlist() {
  localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(watchlist.value))
}

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? uniqueSymbols(parsed) : []
  } catch {
    return []
  }
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))

  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.detail || payload?.message || 'API 請求失敗')
  }

  return payload?.data ?? payload
}

function normalizeSignals(payload) {
  return extractItems(payload)
    .map(item => ({
      symbol: String(item.symbol || '').trim(),
      signal: normalizeSignal(item.signal),
      confidence: normalizePercent(item.confidence),
      price: toNumber(item.price),
      reasoning: String(item.reasoning || '暫無策略推論').trim(),
      conditions: normalizeConditions(item.conditions),
      indicators: item.indicators && typeof item.indicators === 'object' ? item.indicators : {},
      volumeRatio: nullableNumber(item.volume_ratio),
      generatedAt: parseDate(item.generated_at),
      companyName: item.company_name || item.name_zh || item.name || '',
    }))
    .filter(item => item.symbol)
}

function normalizeConditions(value) {
  if (Array.isArray(value) && value.length) {
    return value.map((item, index) => {
      if (typeof item === 'string') {
        return { name: item, met: true, value: 'Condition met' }
      }

      return {
        name: item.name || item.label || `條件 ${index + 1}`,
        met: Boolean(item.met ?? item.passed ?? item.status),
        value: item.value || item.description || (Boolean(item.met) ? 'Condition met' : 'Condition unmet'),
      }
    })
  }

  return [{ name: 'Data validation', met: false, value: '尚未提供條件資料' }]
}

function extractItems(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  return []
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

function setSparklineRef(element, symbol) {
  if (element) {
    sparklineContainers.set(symbol, element)
    return
  }

  sparklineContainers.delete(symbol)
}

function queueSparklineRender() {
  if (renderFrame) window.cancelAnimationFrame(renderFrame)
  renderFrame = window.requestAnimationFrame(() => {
    renderFrame = 0
    renderSparklines()
  })
}

function renderSparklines() {
  const activeSymbols = new Set(filteredCards.value.map(card => card.symbol))

  for (const [symbol, chartState] of sparklineInstances.entries()) {
    if (!activeSymbols.has(symbol) || !sparklineContainers.has(symbol)) {
      chartState.chart.remove()
      sparklineInstances.delete(symbol)
    }
  }

  for (const card of filteredCards.value) {
    const container = sparklineContainers.get(card.symbol)
    if (!container) continue

    const palette = chartPalette[card.signal] || chartPalette.HOLD
    let chartState = sparklineInstances.get(card.symbol)

    if (!chartState) {
      const chart = createChart(container, {
        width: Math.max(container.clientWidth, 120),
        height: 72,
        layout: {
          background: { color: 'transparent' },
          textColor: '#94a3b8',
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { visible: false },
        },
        rightPriceScale: {
          visible: false,
          borderVisible: false,
        },
        leftPriceScale: {
          visible: false,
          borderVisible: false,
        },
        timeScale: {
          visible: false,
          borderVisible: false,
        },
        crosshair: {
          vertLine: { visible: false },
          horzLine: { visible: false },
        },
        handleScroll: false,
        handleScale: false,
      })

      const series = chart.addAreaSeries({
        lineColor: palette.line,
        topColor: palette.top,
        bottomColor: palette.bottom,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })

      chartState = { chart, series }
      sparklineInstances.set(card.symbol, chartState)
    }

    chartState.chart.applyOptions({
      width: Math.max(container.clientWidth, 120),
      height: 72,
    })

    chartState.series.applyOptions({
      lineColor: palette.line,
      topColor: palette.top,
      bottomColor: palette.bottom,
    })

    chartState.series.setData(card.history)
    chartState.chart.timeScale().fitContent()
  }
}

function destroyAllSparklines() {
  for (const { chart } of sparklineInstances.values()) {
    chart.remove()
  }
  sparklineInstances.clear()
}

function filterCount(filter) {
  if (filter === 'ALL') return enrichedCards.value.length
  return enrichedCards.value.filter(item => item.signal === filter).length
}

function signalTone(signal) {
  return signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'hold'
}

function signalLabel(signal) {
  return signal === 'BUY' ? '買進' : signal === 'SELL' ? '賣出' : '觀望'
}

function deltaClass(value) {
  if (value > 0) return 'up'
  if (value < 0) return 'down'
  return 'flat'
}

function deltaArrow(value) {
  if (value > 0) return '▲'
  if (value < 0) return '▼'
  return '•'
}

function sparklineCaption(card) {
  if (!card.history.length) return 'No history'
  const high = Math.max(...card.history.map(item => item.value))
  const low = Math.min(...card.history.map(item => item.value))
  return `${formatPrice(low)} - ${formatPrice(high)}`
}

function metCount(conditions) {
  return conditions.filter(item => item.met).length
}

function formatPrice(value) {
  return formatNumber(value, 2)
}

function formatSigned(value) {
  const numeric = toNumber(value)
  const prefix = numeric > 0 ? '+' : numeric < 0 ? '-' : '±'
  return `${prefix}${formatNumber(Math.abs(numeric), 2)}`
}

function formatGeneratedAt(value) {
  if (!value) return '更新時間待同步'
  return new Intl.DateTimeFormat('zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(value)
}

function formatNumber(value, digits = 0) {
  const numeric = toNumber(value)
  return numeric.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function toNumber(value) {
  const numeric = Number(value ?? 0)
  return Number.isFinite(numeric) ? numeric : 0
}

function nullableNumber(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function roundNumber(value, digits = 2) {
  return Number(toNumber(value).toFixed(digits))
}

function normalizeDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString().slice(0, 10)
}

function parseDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function uniqueSymbols(items) {
  return [...new Set(
    items
      .map(item => String(item || '').trim().toUpperCase())
      .filter(Boolean)
  )]
}

function toDateParam(value) {
  return value.toISOString().slice(0, 10)
}
</script>

<style scoped>
.decision-dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  color: var(--text-primary);
  font-family: var(--font-sans);
}

.page-header,
.card,
.signal-card {
  position: relative;
  overflow: hidden;
}

.page-header,
.market-pulse,
.watchlist-panel,
.filters-bar,
.feedback-card,
.signal-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
    rgba(26, 37, 64, 0.88);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(18px);
  box-shadow: 0 18px 45px rgba(3, 7, 18, 0.24);
}

.page-header {
  padding: var(--space-6);
}

.header-main,
.panel-head,
.signal-head,
.price-block,
.signal-footer,
.filters-bar,
.conditions-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-4);
}

.header-copy h1 {
  margin: 6px 0 10px;
  font-size: clamp(2rem, 3vw, 2.8rem);
  letter-spacing: -0.04em;
}

.page-kicker {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(191, 219, 254, 0.85);
}

.page-subtitle {
  max-width: 760px;
  color: rgba(203, 213, 225, 0.82);
}

.header-meta {
  display: grid;
  gap: var(--space-3);
  min-width: 240px;
  justify-items: end;
}

.datetime-panel,
.freshness-pill {
  min-width: 220px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(11, 17, 33, 0.52);
}

.datetime-panel strong {
  display: block;
  margin-top: 4px;
  font-size: 1rem;
  letter-spacing: -0.02em;
}

.meta-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.freshness-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

.freshness-pill.fresh {
  box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.12);
}

.freshness-pill.aging {
  box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.16);
}

.freshness-pill.stale {
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.18);
}

.pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--color-up);
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45);
  animation: pulse 1.8s infinite;
  flex: 0 0 auto;
}

.pulse-dot.small {
  width: 8px;
  height: 8px;
}

.freshness-pill.stale .pulse-dot,
.down.pulse-dot {
  background: var(--color-down);
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
}

.freshness-pill.aging .pulse-dot {
  background: var(--color-warning);
  box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
}

.header-accent {
  margin-top: 18px;
  height: 3px;
  width: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.95), rgba(6, 182, 212, 0.8), rgba(16, 185, 129, 0.75));
  box-shadow: 0 0 24px rgba(59, 130, 246, 0.22);
}

.top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.75fr) minmax(320px, 1fr);
  gap: var(--space-6);
}

.market-pulse,
.watchlist-panel,
.filters-bar,
.feedback-card {
  padding: var(--space-6);
}

.panel-head h2,
.feedback-card h3 {
  margin-top: 4px;
  letter-spacing: -0.02em;
}

.refresh-inline {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.pulse-content {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 1fr);
  gap: var(--space-5);
  margin-top: var(--space-5);
}

.pulse-badges {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.count-badge {
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(11, 17, 33, 0.5);
}

.count-badge span,
.sentiment-summary span,
.sparkline-head span,
.signal-footer span,
.watchlist-note,
.watchlist-empty,
.reasoning-text,
.company-name,
.conditions-list span {
  color: var(--text-secondary);
}

.count-badge span {
  display: block;
  margin-bottom: 8px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.count-badge strong {
  font-size: 1.85rem;
  line-height: 1;
  letter-spacing: -0.05em;
}

.count-badge.buy strong { color: #34d399; }
.count-badge.sell strong { color: #fb7185; }
.count-badge.hold strong { color: #cbd5e1; }
.count-badge.neutral strong { color: #93c5fd; }

.sentiment-meter-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(11, 17, 33, 0.5);
}

.sentiment-summary {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-4);
  margin-bottom: 18px;
}

.sentiment-summary strong {
  font-size: 1rem;
  letter-spacing: -0.02em;
}

.sentiment-summary strong.up { color: var(--color-up); }
.sentiment-summary strong.down { color: var(--color-down); }
.sentiment-summary strong.flat { color: var(--text-primary); }

.meter-track {
  position: relative;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.meter-gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.95), rgba(148, 163, 184, 0.85), rgba(16, 185, 129, 0.95));
}

.meter-marker {
  position: absolute;
  top: 50%;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  border: 3px solid rgba(255, 255, 255, 0.9);
  background: rgba(11, 17, 33, 0.95);
  transform: translate(-50%, -50%);
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.45);
}

.meter-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.watchlist-total {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #bfdbfe;
  font-size: 0.82rem;
  font-weight: 700;
}

.watchlist-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.watchlist-input-shell {
  position: relative;
}

.watchlist-input {
  width: 100%;
  height: 46px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(11, 17, 33, 0.66);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--transition-base), box-shadow var(--transition-base), transform var(--transition-base);
}

.watchlist-input::placeholder {
  color: var(--text-muted);
}

.watchlist-input:focus {
  border-color: rgba(59, 130, 246, 0.72);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.14);
}

.watchlist-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  z-index: 4;
  list-style: none;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.98);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.4);
}

.watchlist-dropdown li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--transition-base), transform var(--transition-base);
}

.watchlist-dropdown li:hover {
  background: rgba(59, 130, 246, 0.12);
  transform: translateX(2px);
}

.watchlist-note {
  margin-top: var(--space-4);
}

.watchlist-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: var(--space-4);
}

.watch-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.08);
  color: var(--text-primary);
  cursor: pointer;
  transition: transform var(--transition-base), border-color var(--transition-base), box-shadow var(--transition-base), background var(--transition-base);
}

.watch-chip:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.4);
  box-shadow: 0 10px 25px rgba(59, 130, 246, 0.15);
  background: rgba(59, 130, 246, 0.14);
}

.chip-close {
  color: #93c5fd;
  font-weight: 800;
}

.filters-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-pill,
.action-button {
  border: 1px solid rgba(148, 163, 184, 0.14);
  transition: transform var(--transition-base), box-shadow var(--transition-base), border-color var(--transition-base), background var(--transition-base), color var(--transition-base);
}

.filter-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 999px;
  background: rgba(11, 17, 33, 0.55);
  color: var(--text-secondary);
  cursor: pointer;
}

.filter-pill strong {
  min-width: 28px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-primary);
  font-size: 0.82rem;
}

.filter-pill:hover,
.action-button:hover,
.signal-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.24);
}

.filter-pill.active {
  border-color: rgba(59, 130, 246, 0.52);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(37, 99, 235, 0.06));
  color: #eff6ff;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.14), 0 0 22px rgba(59, 130, 246, 0.18);
}

.action-button {
  height: 46px;
  padding: 0 18px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 700;
  letter-spacing: 0.01em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.action-button.primary {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(6, 182, 212, 0.88));
  color: #fff;
}

.action-button.ghost {
  background: rgba(11, 17, 33, 0.58);
  color: var(--text-primary);
}

.button-spinner,
.loading-spinner {
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.16);
  border-top-color: rgba(255, 255, 255, 0.96);
  animation: spin 0.8s linear infinite;
}

.button-spinner {
  width: 14px;
  height: 14px;
}

.feedback-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-5);
}

.feedback-card p {
  margin-top: 6px;
}

.loading-state {
  justify-content: flex-start;
}

.loading-spinner {
  width: 34px;
  height: 34px;
  border-width: 3px;
  border-color: rgba(59, 130, 246, 0.14);
  border-top-color: rgba(59, 130, 246, 0.95);
}

.error-state {
  border-color: rgba(239, 68, 68, 0.28);
}

.signals-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

.signal-card {
  padding: 24px;
  min-height: 100%;
  transition: transform var(--transition-base), box-shadow var(--transition-base), border-color var(--transition-base);
}

.signal-card:hover {
  border-color: rgba(148, 163, 184, 0.22);
}

.signal-card-glow {
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 4px;
  opacity: 0.95;
}

.signal-card-glow.buy {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.9));
}

.signal-card-glow.sell {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.9));
}

.signal-card-glow.hold {
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.15), rgba(148, 163, 184, 0.9));
}

.signal-title-group {
  min-width: 0;
}

.symbol-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.symbol-row h3 {
  font-size: 1.45rem;
  letter-spacing: -0.04em;
}

.analysis-link {
  color: #93c5fd;
  font-size: 0.88rem;
  font-weight: 700;
  text-decoration: none;
  transition: color var(--transition-base), transform var(--transition-base);
}

.analysis-link:hover {
  color: #dbeafe;
  transform: translateX(2px);
}

.company-name {
  margin-top: 6px;
}

.signal-badge {
  display: grid;
  justify-items: center;
  min-width: 96px;
  padding: 12px 14px;
  border-radius: 14px;
  color: white;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.signal-badge span {
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.88);
}

.signal-badge strong {
  margin-top: 4px;
  font-size: 1.25rem;
  letter-spacing: -0.04em;
}

.signal-badge.buy {
  background: linear-gradient(135deg, #0ea76f, #10b981, #34d399);
}

.signal-badge.sell {
  background: linear-gradient(135deg, #dc2626, #ef4444, #fb7185);
}

.signal-badge.hold {
  background: linear-gradient(135deg, #475569, #64748b, #94a3b8);
}

.price-block {
  margin-top: var(--space-5);
  align-items: flex-end;
}

.price-value {
  display: block;
  margin-top: 6px;
  font-size: 2.1rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.06em;
}

.price-change {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(11, 17, 33, 0.52);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.price-change strong,
.price-change span {
  display: block;
  line-height: 1.2;
}

.price-change.up {
  color: var(--color-up);
}

.price-change.down {
  color: var(--color-down);
}

.price-change.flat {
  color: var(--text-secondary);
}

.delta-arrow {
  font-size: 1.05rem;
}

.reasoning-text {
  margin-top: var(--space-4);
  min-height: 48px;
}

.sparkline-panel,
.conditions-panel {
  margin-top: var(--space-5);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.1);
  background: rgba(11, 17, 33, 0.46);
}

.sparkline-head,
.conditions-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 0.84rem;
}

.sparkline {
  width: 100%;
  min-height: 72px;
}

.conditions-head strong {
  letter-spacing: -0.03em;
}

.conditions-list {
  list-style: none;
  display: grid;
  gap: 12px;
}

.conditions-list li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: start;
}

.conditions-list strong {
  display: block;
  margin-bottom: 2px;
  font-size: 0.92rem;
}

.conditions-list span {
  display: block;
  font-size: 0.82rem;
}

.condition-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.42);
  box-shadow: 0 0 0 6px rgba(148, 163, 184, 0.08);
}

.condition-dot.met {
  background: var(--color-up);
  box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.1);
}

.signal-footer {
  margin-top: var(--space-5);
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  align-items: center;
  font-size: 0.84rem;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.42);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(16, 185, 129, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1199px) {
  .top-grid,
  .pulse-content,
  .signals-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .top-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .signals-grid,
  .pulse-content,
  .pulse-badges {
    grid-template-columns: 1fr;
  }

  .feedback-card,
  .filters-bar,
  .header-main,
  .price-block,
  .signal-head {
    flex-direction: column;
    align-items: stretch;
  }

  .header-meta {
    justify-items: stretch;
  }

  .datetime-panel,
  .freshness-pill {
    min-width: 0;
  }
}

@media (max-width: 640px) {
  .decision-dashboard {
    gap: var(--space-5);
  }

  .page-header,
  .market-pulse,
  .watchlist-panel,
  .filters-bar,
  .feedback-card,
  .signal-card {
    padding: var(--space-5);
  }

  .watchlist-form {
    grid-template-columns: 1fr;
  }

  .filter-pills {
    width: 100%;
  }

  .filter-pill {
    flex: 1 1 calc(50% - 6px);
    justify-content: space-between;
  }

  .signals-grid {
    grid-template-columns: 1fr;
  }

  .price-value {
    font-size: 1.8rem;
  }
}

@media (max-width: 420px) {
  .decision-dashboard {
    gap: var(--space-3);
  }

  .page-header,
  .market-pulse,
  .watchlist-panel,
  .filters-bar,
  .feedback-card,
  .signal-card {
    padding: var(--space-3);
  }

  .watchlist-container {
    min-width: 0;
  }

  .market-pulse {
    min-width: 0;
  }

  .signals-list {
    min-width: 0;
  }

  .filter-pill {
    flex: 1 1 100%;
    font-size: 0.72rem;
  }

  .price-value {
    font-size: 1.4rem;
  }

  .header-title {
    font-size: 1.2rem;
  }

  .sparkline-container {
    height: 52px;
  }
}
</style>
