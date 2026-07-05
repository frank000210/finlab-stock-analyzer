<template>
  <div class="analysis-view">
    <PageFocusBanner text="檢視價格趨勢、動能與波動，判斷技術面是否支持進出場時機。" />

    <section class="hero-card card">
      <div class="hero-main">
        <div class="hero-copy">
          <div class="symbol-row">
            <h1>{{ symbol }}</h1>
            <span v-if="stockName" class="company-name">{{ stockName }}</span>
            <span v-if="stockIndustry" class="industry-chip">{{ stockIndustry }}</span>
          </div>
          <div class="price-row">
            <span class="current-price">{{ formatPrice(latestClose) }}</span>
            <span class="price-change" :class="priceChangeClass">
              {{ formatSigned(priceChange) }} ({{ formatSignedPercent(priceChangePercent) }})
            </span>
          </div>
          <p class="hero-summary">
            {{ actionSummary }}
          </p>
        </div>

        <div class="hero-signal">
          <div class="signal-badge-wrap">
            <span class="signal-badge" :class="signalClass">{{ finalAction }}</span>
            <span class="confidence-tag">信心度 {{ confidenceDisplay }} / 100</span>
          </div>
          <div class="signal-score">{{ overallScore }}</div>
          <div class="signal-score-label">AI 決策評分</div>
          <div class="signal-meta">最後更新：{{ lastUpdatedText }}</div>
        </div>
      </div>
    </section>

    <p v-if="errorMessage" class="status-message">{{ errorMessage }}</p>

    <section class="top-grid">
      <article class="card chart-card">
        <div class="section-head">
          <div>
            <h2>多因子技術圖表</h2>
          </div>
          <div class="range-selector">
            <button
              v-for="range in ranges"
              :key="range.label"
              class="range-button"
              :class="{ active: selectedRange === range.label }"
              @click="selectedRange = range.label"
            >
              {{ range.label }}
            </button>
          </div>
        </div>

        <div class="chart-stack">
          <div class="chart-block">
            <div class="chart-label-row">
              <span>Price + MA5 / MA20 / MA60</span>
              <span class="legend-group">
                <i class="legend-dot ma5"></i>MA5
                <i class="legend-dot ma20"></i>MA20
                <i class="legend-dot ma60"></i>MA60
                <template v-if="majorCost && majorCost.cost != null">
                  <i class="legend-dot cost-line"></i>主力成本 {{ majorCost.cost }}
                  <span class="legend-dev" :class="majorCost.deviation > 0 ? 'up' : majorCost.deviation < 0 ? 'down' : ''">
                    乖離 {{ majorCost.deviation > 0 ? '+' : '' }}{{ majorCost.deviation }}%
                  </span>
                </template>
              </span>
            </div>
            <div class="chart-wrapper">
              <span class="y-axis-label">新台幣(元)</span>
              <div ref="priceChartEl" class="chart-area price-chart"></div>
            </div>
            <div class="x-axis-label">日期</div>
          </div>

          <div class="chart-block">
            <div class="chart-label-row">
              <span>RSI (14)</span>
              <span class="muted-text">30 / 70 區間</span>
            </div>
            <div class="chart-wrapper">
              <span class="y-axis-label">RSI 值</span>
              <div ref="rsiChartEl" class="chart-area indicator-chart"></div>
            </div>
          </div>

          <div class="chart-block">
            <div class="chart-label-row">
              <span>MACD</span>
              <span class="muted-text">DIF / Signal / Histogram</span>
            </div>
            <div class="chart-wrapper">
              <span class="y-axis-label">MACD 值</span>
              <div ref="macdChartEl" class="chart-area indicator-chart"></div>
            </div>
            <div class="x-axis-label">日期</div>
          </div>
        </div>
      </article>

      <article class="card decision-card">
        <div class="section-head compact">
          <div>
            <h2>AI 決策評分</h2>
          </div>
        </div>

        <div class="score-ring" :style="scoreRingStyle">
          <div class="score-ring-inner">
            <strong>{{ overallScore }}</strong>
            <span>Overall</span>
          </div>
        </div>

        <div class="score-list">
          <div v-for="item in scoreBreakdown" :key="item.key" class="score-item">
            <div class="score-item-head">
              <span>{{ item.label }}</span>
              <strong>{{ item.score }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: `${item.score}%`, background: item.color }"></div>
            </div>
            <p>{{ item.description }}</p>
          </div>
        </div>
      </article>
    </section>

    <section class="card calendar-section">
      <div class="section-head compact">
        <div>
          <h2>每日漲跌日曆熱力圖</h2>
        </div>
      </div>
      <div ref="calendarEl" class="chart-host calendar-host"></div>
      <p class="chart-caption">參考：D3 gallery - Calendar；每格為一個交易日，顏色深淺＝當日漲跌幅。</p>
    </section>

    <section class="card volume-profile-section">
      <div class="section-head compact">
        <div>
          <h2>成交量分佈圖 Volume Profile</h2>
        </div>
      </div>
      <div ref="volumeProfileEl" class="chart-host volume-profile-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Contour/Hexbin（價位 × 量的概念延伸）；本站僅有日 OHLCV，非逐筆成交，故以「當日成交量平均分攤到當日高低價區間」近似估算，非真實逐筆分價量表，僅供參考主力可能的成本聚集區。
      </p>
    </section>

    <section class="metrics-grid">
      <article v-for="metric in keyMetrics" :key="metric.label" class="card metric-tile">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value" :class="metric.tone">{{ metric.value }}</div>
        <div class="metric-note">{{ metric.note }}</div>
      </article>
    </section>

    <section class="bottom-grid">
      <article class="card summary-card">
        <div class="section-head compact">
          <div>
            <h2>買賣建議</h2>
          </div>
        </div>

        <div class="summary-badge-row">
          <span class="signal-badge large" :class="signalClass">{{ finalAction }}</span>
          <div>
            <div class="summary-confidence">信心等級：{{ confidenceLabel }}</div>
            <div class="summary-subtitle">{{ summarySubtitle }}</div>
          </div>
        </div>

        <ol class="reason-list">
          <li v-for="reason in topReasons" :key="reason">{{ reason }}</li>
        </ol>

        <div class="summary-footer">
          <div class="summary-mini">
            <span>AI 原始信號</span>
            <strong>{{ aiSignalText }}</strong>
          </div>
          <div class="summary-mini">
            <span>AI 推論</span>
            <strong>{{ signalReasoning }}</strong>
          </div>
        </div>
      </article>

      <article class="card detail-card">
        <div class="section-head compact">
          <div>
            <h2>基本面重點</h2>
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-stat">
            <span>最新月營收 YoY</span>
            <strong :class="valueTone(revenueGrowth)">{{ formatSignedPercent(revenueGrowth) }}</strong>
          </div>
          <div class="detail-stat">
            <span>EPS 成長</span>
            <strong :class="valueTone(epsGrowth)">{{ formatSignedPercent(epsGrowth) }}</strong>
          </div>
          <div class="detail-stat">
            <span>毛利率</span>
            <strong>{{ formatPercent(grossMargin) }}</strong>
          </div>
          <div class="detail-stat">
            <span>負債比率</span>
            <strong :class="debtRatioTone">{{ formatPercent(debtRatio) }}</strong>
          </div>
        </div>

        <div class="mini-table">
          <div class="mini-table-head">
            <span>月份</span>
            <span>營收</span>
            <span>YoY</span>
          </div>
          <div v-for="row in recentRevenueRows" :key="row.month" class="mini-table-row">
            <span>{{ row.month }}</span>
            <span>{{ formatLargeNumber(row.revenue) }}</span>
            <span :class="valueTone(row.yoy)">{{ formatSignedPercent(row.yoy) }}</span>
          </div>
          <div v-if="!recentRevenueRows.length" class="empty-state">尚未取得基本面資料</div>
        </div>
      </article>

      <article class="card detail-card">
        <div class="section-head compact">
          <div>
            <h2>籌碼面重點</h2>
          </div>
          <router-link
            v-if="chipHealth"
            :to="`/stocks/${symbol}/chip`"
            class="chip-health-badge"
            :class="'tone-' + chipHealth.tone"
            :title="chipHealth.verdict"
          >
            <span class="chb-label">籌碼健診</span>
            <span class="chb-score">{{ chipHealth.score }}</span>
            <span class="chb-arrow">→</span>
          </router-link>
        </div>

        <div class="detail-grid">
          <div class="detail-stat">
            <span>外資近 5 日</span>
            <strong :class="valueTone(foreignNetBuy5)">{{ formatSignedCompact(foreignNetBuy5) }}</strong>
          </div>
          <div class="detail-stat">
            <span>外資連買</span>
            <strong>{{ foreignBuyStreak }} 日</strong>
          </div>
          <div class="detail-stat">
            <span>投信趨勢</span>
            <strong :class="trustTrendTone">{{ investmentTrustTrendText }}</strong>
          </div>
          <div class="detail-stat">
            <span>融券 / 融資</span>
            <strong>{{ marginShortRatio }}</strong>
          </div>
        </div>

        <div class="mini-table">
          <div class="mini-table-head">
            <span>日期</span>
            <span>外資</span>
            <span>投信</span>
          </div>
          <div v-for="row in recentChipRows" :key="row.date" class="mini-table-row">
            <span>{{ row.date }}</span>
            <span :class="valueTone(row.foreign_net_buy)">{{ formatSignedCompact(row.foreign_net_buy) }}</span>
            <span :class="valueTone(row.investment_trust_net_buy)">{{ formatSignedCompact(row.investment_trust_net_buy) }}</span>
          </div>
          <div v-if="!recentChipRows.length" class="empty-state">尚未取得籌碼資料</div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createChart } from 'lightweight-charts'
import * as d3 from 'd3'

const calendarEl = ref(null)
const volumeProfileEl = ref(null)

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''

const route = useRoute()
const router = useRouter()

const ranges = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: '2Y', days: 730 },
  { label: '5Y', days: 1825 },
]

const selectedRange = ref('1Y')
const loading = ref(false)
const errorMessage = ref('')
const stockInfo = ref({})
const priceItems = ref([])
const technicalPayload = ref({})
const fundamentalData = ref({})
const chipData = ref({})
const aiSignal = ref(null)

const priceChartEl = ref(null)
const rsiChartEl = ref(null)
const macdChartEl = ref(null)

let priceChart = null
let rsiChart = null
let macdChart = null
let syncGuard = false
let requestToken = 0
let candleSeries = null
let majorCostLine = null
const majorCost = ref(null)
const chipHealth = ref(null)

const symbol = computed(() => String(route.params.symbol || '').toUpperCase())
const stockName = computed(() => stockInfo.value?.name_zh || '')
const stockIndustry = computed(() => stockInfo.value?.industry || '')
const mergedSeries = computed(() => mergePriceWithTechnical(priceItems.value, technicalPayload.value))
const currentPoint = computed(() => mergedSeries.value[mergedSeries.value.length - 1] || {})
const previousPoint = computed(() => mergedSeries.value[mergedSeries.value.length - 2] || {})
const latestClose = computed(() => Number(currentPoint.value.close ?? 0))
const priceChange = computed(() => latestClose.value - Number(previousPoint.value.close ?? latestClose.value ?? 0))
const priceChangePercent = computed(() => {
  const previousClose = Number(previousPoint.value.close ?? 0)
  if (!previousClose) return 0
  return (priceChange.value / previousClose) * 100
})
const lastUpdatedText = computed(() => currentPoint.value.date || '--')
const latestRsi = computed(() => toNumber(currentPoint.value.rsi14))
const latestMacd = computed(() => toNumber(currentPoint.value.macd_dif))
const latestMacdSignal = computed(() => toNumber(currentPoint.value.macd_dea))
const latestMa5 = computed(() => toNumber(currentPoint.value.ma5))
const latestMa20 = computed(() => toNumber(currentPoint.value.ma20))
const latestMa60 = computed(() => toNumber(currentPoint.value.ma60))
const volumeRatio = computed(() => {
  const avg = toNumber(currentPoint.value.vol_ma20)
  const volume = toNumber(currentPoint.value.volume)
  if (!avg) return 0
  return volume / avg
})

const revenueRows = computed(() => normalizeRevenueRows(fundamentalData.value?.revenue_monthly))
const epsRows = computed(() => normalizeQuarterRows(fundamentalData.value?.eps_quarterly, 'eps'))
const marginRows = computed(() => normalizeQuarterRows(fundamentalData.value?.margins, 'gross_margin'))
const debtRows = computed(() => normalizeQuarterRows(fundamentalData.value?.debt_ratios, 'debt_ratio'))
const chipRows = computed(() => normalizeChipRows(chipData.value?.items))
const marginRowsNormalized = computed(() => normalizeChipRows(chipData.value?.margin, true))

const recentRevenueRows = computed(() => revenueRows.value.slice(-4).reverse())
const recentChipRows = computed(() => chipRows.value.slice(-5).reverse())
const revenueGrowth = computed(() => toNumber(revenueRows.value[revenueRows.value.length - 1]?.yoy))
const epsGrowth = computed(() => computeEpsGrowth(epsRows.value))
const grossMargin = computed(() => toNumber(marginRows.value[marginRows.value.length - 1]?.gross_margin))
const debtRatio = computed(() => toNumber(debtRows.value[debtRows.value.length - 1]?.debt_ratio))
const foreignNetBuy5 = computed(() => chipRows.value.slice(-5).reduce((sum, item) => sum + toNumber(item.foreign_net_buy), 0))
const foreignBuyStreak = computed(() => Number(chipData.value?.summary?.foreign_buy_streak || 0))
const investmentTrustTrendText = computed(() => normalizeTrustTrend(chipData.value?.summary?.investment_trust_trend))
const marginShortRatio = computed(() => {
  const latest = marginRowsNormalized.value[marginRowsNormalized.value.length - 1]
  if (!latest) return '--'
  const shortBalance = toNumber(latest.short_balance)
  const marginBalance = toNumber(latest.margin_balance)
  if (!marginBalance) return '--'
  return `${formatNumber(shortBalance / marginBalance, 2)}x`
})

const technicalScore = computed(() => {
  let score = 50
  if (latestClose.value && latestMa20.value) score += latestClose.value > latestMa20.value ? 12 : -12
  if (latestMa5.value && latestMa20.value) score += latestMa5.value > latestMa20.value ? 8 : -8
  if (latestMa20.value && latestMa60.value) score += latestMa20.value > latestMa60.value ? 10 : -10
  if (latestMacd.value && latestMacdSignal.value) score += latestMacd.value > latestMacdSignal.value ? 12 : -12
  if (latestRsi.value >= 45 && latestRsi.value <= 65) score += 8
  else if (latestRsi.value < 30) score += 14
  else if (latestRsi.value > 72) score -= 16
  if (volumeRatio.value > 1.2) score += 8
  return clampScore(score)
})

const fundamentalScore = computed(() => {
  let score = 50
  score += clampBetween(revenueGrowth.value / 2, -15, 15)
  score += clampBetween(epsGrowth.value / 2, -18, 18)
  if (grossMargin.value >= 35) score += 10
  else if (grossMargin.value >= 25) score += 5
  else if (grossMargin.value > 0) score -= 8
  if (debtRatio.value > 60) score -= 10
  else if (debtRatio.value > 0 && debtRatio.value < 35) score += 8
  return clampScore(score)
})

const chipScore = computed(() => {
  let score = 50
  score += clampBetween(foreignNetBuy5.value / 50000, -18, 18)
  score += clampBetween(foreignBuyStreak.value * 4, 0, 16)
  if (investmentTrustTrendText.value === '偏多') score += 10
  if (investmentTrustTrendText.value === '偏空') score -= 10
  return clampScore(score)
})

const sentimentScore = computed(() => {
  const signal = aiSignal.value
  if (!signal) return 50
  const confidence = normalizePercent(signal.confidence)
  if (signal.action === 'BUY') return clampScore(55 + confidence * 0.4)
  if (signal.action === 'SELL') return clampScore(50 - confidence * 0.45)
  return clampScore(40 + confidence * 0.2)
})

const overallScore = computed(() => {
  const weighted = (
    technicalScore.value * 0.35 +
    fundamentalScore.value * 0.25 +
    chipScore.value * 0.2 +
    sentimentScore.value * 0.2
  )
  return Math.round(weighted)
})

const finalAction = computed(() => {
  if (overallScore.value >= 68) return 'BUY'
  if (overallScore.value <= 42) return 'SELL'
  return 'HOLD'
})

const signalClass = computed(() => finalAction.value.toLowerCase())
const priceChangeClass = computed(() => (priceChange.value >= 0 ? 'up' : 'down'))
const confidenceDisplay = computed(() => {
  const base = normalizePercent(aiSignal.value?.confidence)
  const overallImpact = Math.abs(overallScore.value - 50) * 1.2
  return Math.round(clampBetween(base * 0.5 + overallImpact, 0, 100))
})
const confidenceLabel = computed(() => {
  if (confidenceDisplay.value >= 75) return '高'
  if (confidenceDisplay.value >= 55) return '中'
  return '低'
})
const summarySubtitle = computed(() => {
  if (finalAction.value === 'BUY') return '多方條件佔優勢，適合觀察切入點'
  if (finalAction.value === 'SELL') return '風險偏高，建議嚴控部位與停損'
  return '訊號分歧，建議等待更明確突破'
})
const aiSignalText = computed(() => {
  if (!aiSignal.value) return '無資料'
  return `${aiSignal.value.action} / ${normalizePercent(aiSignal.value.confidence)}`
})
const signalReasoning = computed(() => aiSignal.value?.reasoning || '尚未取得 AI 推論')
const actionSummary = computed(() => {
  if (finalAction.value === 'BUY') return '趨勢、量能與 AI 信號偏多，若回測支撐不破可分批布局。'
  if (finalAction.value === 'SELL') return '技術或籌碼轉弱，應優先防守並留意跌破關鍵均線。'
  return '多空因子拉鋸，建議等待量價或籌碼出現一致方向。'
})

const scoreBreakdown = computed(() => [
  {
    key: 'technical',
    label: '技術面',
    score: technicalScore.value,
    color: '#2563eb',
    description: technicalDescription(),
  },
  {
    key: 'fundamental',
    label: '基本面',
    score: fundamentalScore.value,
    color: '#14b8a6',
    description: fundamentalDescription(),
  },
  {
    key: 'chip',
    label: '籌碼面',
    score: chipScore.value,
    color: '#8b5cf6',
    description: chipDescription(),
  },
  {
    key: 'sentiment',
    label: '市場情緒',
    score: sentimentScore.value,
    color: '#f59e0b',
    description: sentimentDescription(),
  },
])

const keyMetrics = computed(() => [
  {
    label: 'Current Price',
    value: formatPrice(latestClose.value),
    note: lastUpdatedText.value,
    tone: priceChangeClass.value,
  },
  {
    label: 'Change %',
    value: formatSignedPercent(priceChangePercent.value),
    note: `價差 ${formatSigned(priceChange.value)}`,
    tone: priceChangeClass.value,
  },
  {
    label: 'Volume vs Avg',
    value: volumeRatio.value ? `${formatNumber(volumeRatio.value, 2)}x` : '--',
    note: `量能 ${formatLargeNumber(currentPoint.value.volume)}`,
    tone: volumeRatio.value >= 1 ? 'up' : '',
  },
  {
    label: 'RSI (14)',
    value: formatNumber(latestRsi.value, 2),
    note: latestRsi.value > 70 ? '偏熱' : latestRsi.value < 30 ? '偏冷' : '中性',
    tone: latestRsi.value > 70 ? 'down' : latestRsi.value < 35 ? 'up' : '',
  },
  {
    label: 'MACD Signal',
    value: formatNumber(latestMacdSignal.value, 2),
    note: latestMacd.value > latestMacdSignal.value ? 'DIF 在上' : 'DIF 在下',
    tone: latestMacd.value > latestMacdSignal.value ? 'up' : 'down',
  },
  {
    label: 'Foreign Net Buy (5D)',
    value: formatSignedCompact(foreignNetBuy5.value),
    note: `連買 ${foreignBuyStreak.value} 日`,
    tone: valueTone(foreignNetBuy5.value),
  },
  {
    label: 'EPS Growth',
    value: formatSignedPercent(epsGrowth.value),
    note: `毛利率 ${formatPercent(grossMargin.value)}`,
    tone: valueTone(epsGrowth.value),
  },
])

const scoreRingStyle = computed(() => ({
  background: `conic-gradient(#2563eb 0deg ${overallScore.value * 3.6}deg, rgba(148, 163, 184, 0.15) ${overallScore.value * 3.6}deg 360deg)`,
}))

const topReasons = computed(() => selectTopReasons())
const debtRatioTone = computed(() => (debtRatio.value > 60 ? 'down' : debtRatio.value > 0 && debtRatio.value < 35 ? 'up' : ''))
const trustTrendTone = computed(() => {
  if (investmentTrustTrendText.value === '偏多') return 'up'
  if (investmentTrustTrendText.value === '偏空') return 'down'
  return ''
})

watch(() => route.params.symbol, async () => {
  saveRecent()
  await loadAnalysis()
})

watch(selectedRange, async () => {
  await loadAnalysis()
})

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  saveRecent()
  await loadAnalysis()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  destroyCharts()
})

async function loadAnalysis() {
  loading.value = true
  errorMessage.value = ''
  majorCost.value = null
  chipHealth.value = null
  const token = ++requestToken

  // If symbol is non-numeric (Chinese name), resolve to code first
  let sym = symbol.value
  if (sym && !/^\d{4,6}$/.test(sym)) {
    try {
      const searchRes = await apiGet(`/api/v1/stocks/search?q=${encodeURIComponent(sym)}`)
      const items = searchRes?.items || searchRes?.data?.items || []
      const match = items[0]
      if (match && match.symbol) {
        sym = match.symbol
        // Redirect to correct URL
        router.replace(`/stocks/${sym}`)
        return
      }
    } catch {}
  }

  const { start, end } = buildDateRange(selectedRange.value)

  const [infoRes, priceRes, technicalRes, fundamentalRes, chipRes, signalRes] = await Promise.allSettled([
    apiGet(`/api/v1/stocks/${sym}/info`),
    apiGet(`/api/v1/stocks/${sym}/price?start=${start}&end=${end}`),
    apiGet(`/api/v1/analysis/${sym}/technical?indicators=ma,macd,rsi,volume&start=${start}&end=${end}`),
    apiGet(`/api/v1/analysis/${sym}/fundamental`),
    apiGet(`/api/v1/analysis/${sym}/chip`),
    apiGet(`/api/v1/agent/signals?symbols=${sym}&type=ALL`),
  ])

  if (token !== requestToken) return

  if (infoRes.status === 'fulfilled') stockInfo.value = infoRes.value || {}
  if (priceRes.status === 'fulfilled') priceItems.value = normalizePriceRows(priceRes.value?.items || priceRes.value?.prices || [])
  if (technicalRes.status === 'fulfilled') technicalPayload.value = technicalRes.value || {}
  if (fundamentalRes.status === 'fulfilled') fundamentalData.value = fundamentalRes.value || {}
  if (chipRes.status === 'fulfilled') chipData.value = chipRes.value || {}
  if (signalRes.status === 'fulfilled') aiSignal.value = normalizeSignal(signalRes.value)

  if (!priceItems.value.length) {
    errorMessage.value = '無法取得價格資料，請稍後再試。'
  }

  await nextTick()
  renderCharts()
  renderCalendar()
  renderVolumeProfile()
  loading.value = false
  loadMajorCost(sym, token)
  loadChipScore(sym, token)
}

async function loadChipScore(sym, token) {
  try {
    const payload = await apiGet(`/api/v1/stocks/${sym}/chip-score`)
    if (token !== requestToken) return
    chipHealth.value = (payload && typeof payload === 'object' && 'score' in payload) ? payload : null
  } catch {
    /* 籌碼健診為加值資訊，失敗時靜默忽略 */
  }
}

async function loadMajorCost(sym, token) {
  try {
    const payload = await apiGet(`/api/v1/stocks/${sym}/major-cost`)
    if (token !== requestToken) return
    majorCost.value = (payload && typeof payload === 'object' && 'cost' in payload) ? payload : null
    applyMajorCostLine()
  } catch {
    /* 主力成本為加值資訊，失敗時靜默忽略 */
  }
}

function applyMajorCostLine() {
  if (!candleSeries) return
  if (majorCostLine) {
    try { candleSeries.removePriceLine(majorCostLine) } catch {}
    majorCostLine = null
  }
  const c = majorCost.value
  if (!c || c.cost == null) return
  majorCostLine = candleSeries.createPriceLine({
    price: c.cost,
    color: '#f59e0b',
    lineWidth: 1,
    lineStyle: 2,
    axisLabelVisible: true,
    title: '主力成本',
  })
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.detail || 'API request failed')
  }
  return payload?.data ?? payload
}

function normalizePriceRows(items) {
  return [...items]
    .map(item => ({
      date: normalizeDate(item.date || item.time || item.timestamp),
      open: toNumber(item.open),
      high: toNumber(item.high),
      low: toNumber(item.low),
      close: toNumber(item.close),
      volume: toNumber(item.volume),
    }))
    .filter(item => item.date && item.close)
    .sort((a, b) => a.date.localeCompare(b.date))
}

function normalizeSignal(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : Array.isArray(payload) ? payload : []
  const target = items.find(item => String(item.symbol || '').toUpperCase() === symbol.value) || items[0]
  if (!target) return null
  return {
    action: String(target.signal || target.type || target.action || 'HOLD').toUpperCase(),
    confidence: target.confidence,
    reasoning: target.reasoning || target.reason || '',
    conditions: Array.isArray(target.conditions) ? target.conditions : [],
    indicators: target.indicators || {},
  }
}

function normalizeRevenueRows(items) {
  return Array.isArray(items)
    ? [...items]
      .map(item => ({
        month: item.month,
        revenue: toNumber(item.revenue),
        yoy: toNumber(item.yoy),
      }))
      .filter(item => item.month)
      .sort((a, b) => a.month.localeCompare(b.month))
    : []
}

function normalizeQuarterRows(items) {
  return Array.isArray(items)
    ? [...items]
      .map(item => ({ ...item }))
      .filter(item => item.quarter)
      .sort((a, b) => a.quarter.localeCompare(b.quarter))
    : []
}

function normalizeChipRows(items, margin = false) {
  if (!Array.isArray(items)) return []
  return [...items]
    .map(item => (margin
      ? {
        date: normalizeDate(item.date),
        margin_balance: toNumber(item.margin_balance),
        short_balance: toNumber(item.short_balance),
      }
      : {
        date: normalizeDate(item.date),
        foreign_net_buy: toNumber(item.foreign_net_buy),
        investment_trust_net_buy: toNumber(item.investment_trust_net_buy),
        dealer_net_buy: toNumber(item.dealer_net_buy),
      }))
    .filter(item => item.date)
    .sort((a, b) => a.date.localeCompare(b.date))
}

function mergePriceWithTechnical(prices, technical) {
  if (!prices.length) return []
  const fallback = computeTechnicalSeries(prices)
  const serverSeries = normalizeTechnicalSeries(technical?.series)
  const selectedSeries = serverSeries.length ? serverSeries : fallback
  const technicalMap = new Map(selectedSeries.map(item => [item.date, item]))

  return prices.map(item => ({
    ...item,
    ...(technicalMap.get(item.date) || {}),
  }))
}

function normalizeTechnicalSeries(series) {
  if (!Array.isArray(series)) return []
  return series
    .map(item => ({
      date: normalizeDate(item.date),
      ma5: nullableNumber(item.ma5),
      ma20: nullableNumber(item.ma20),
      ma60: nullableNumber(item.ma60),
      rsi14: nullableNumber(item.rsi14),
      macd_dif: nullableNumber(item.macd_dif),
      macd_dea: nullableNumber(item.macd_dea),
      macd_hist: nullableNumber(item.macd_hist),
      vol_ma20: nullableNumber(item.vol_ma20),
    }))
    .filter(item => item.date)
}

function computeTechnicalSeries(prices) {
  const closes = prices.map(item => item.close)
  const volumes = prices.map(item => item.volume)
  const ma5 = movingAverage(closes, 5)
  const ma20 = movingAverage(closes, 20)
  const ma60 = movingAverage(closes, 60)
  const volMa20 = movingAverage(volumes, 20)
  const rsi14 = computeRsi(closes, 14)
  const ema12 = exponentialMovingAverage(closes, 12)
  const ema26 = exponentialMovingAverage(closes, 26)
  const macdDif = closes.map((_, index) => {
    if (ema12[index] == null || ema26[index] == null) return null
    return roundTo(ema12[index] - ema26[index], 4)
  })
  const macdDea = exponentialMovingAverage(macdDif, 9)
  const macdHist = macdDif.map((value, index) => {
    if (value == null || macdDea[index] == null) return null
    return roundTo((value - macdDea[index]) * 2, 4)
  })

  return prices.map((item, index) => ({
    date: item.date,
    ma5: ma5[index],
    ma20: ma20[index],
    ma60: ma60[index],
    rsi14: rsi14[index],
    macd_dif: macdDif[index],
    macd_dea: macdDea[index],
    macd_hist: macdHist[index],
    vol_ma20: volMa20[index],
  }))
}

function movingAverage(values, period) {
  return values.map((_, index) => {
    if (index + 1 < period) return null
    const window = values.slice(index - period + 1, index + 1)
    return roundTo(window.reduce((sum, value) => sum + toNumber(value), 0) / period, 4)
  })
}

function exponentialMovingAverage(values, period) {
  const multiplier = 2 / (period + 1)
  let previous = null
  return values.map(value => {
    if (value == null || !Number.isFinite(Number(value))) return null
    const numeric = Number(value)
    previous = previous == null ? numeric : numeric * multiplier + previous * (1 - multiplier)
    return roundTo(previous, 4)
  })
}

function computeRsi(values, period) {
  const result = Array(values.length).fill(null)
  if (values.length <= period) return result

  let gains = 0
  let losses = 0
  for (let index = 1; index <= period; index += 1) {
    const delta = values[index] - values[index - 1]
    if (delta >= 0) gains += delta
    else losses -= delta
  }

  let averageGain = gains / period
  let averageLoss = losses / period
  result[period] = averageLoss === 0 ? 100 : roundTo(100 - 100 / (1 + averageGain / averageLoss), 4)

  for (let index = period + 1; index < values.length; index += 1) {
    const delta = values[index] - values[index - 1]
    const gain = delta > 0 ? delta : 0
    const loss = delta < 0 ? -delta : 0
    averageGain = ((averageGain * (period - 1)) + gain) / period
    averageLoss = ((averageLoss * (period - 1)) + loss) / period
    if (averageLoss === 0) result[index] = 100
    else result[index] = roundTo(100 - 100 / (1 + averageGain / averageLoss), 4)
  }

  return result
}

function renderCharts() {
  destroyCharts()
  if (!mergedSeries.value.length || !priceChartEl.value || !rsiChartEl.value || !macdChartEl.value) return

  const width = priceChartEl.value.clientWidth || 900
  const common = {
    width,
    layout: {
      background: { color: '#0f172a' },
      textColor: '#94a3b8',
    },
    grid: {
      vertLines: { color: 'rgba(51, 65, 85, 0.35)' },
      horzLines: { color: 'rgba(51, 65, 85, 0.35)' },
    },
    rightPriceScale: { borderColor: '#334155' },
    timeScale: { borderColor: '#334155' },
    crosshair: {
      vertLine: { color: '#475569' },
      horzLine: { color: '#475569' },
    },
  }

  priceChart = createChart(priceChartEl.value, {
    ...common,
    height: 420,
    timeScale: { ...common.timeScale, timeVisible: true },
  })
  rsiChart = createChart(rsiChartEl.value, {
    ...common,
    height: 150,
    timeScale: { ...common.timeScale, visible: false },
  })
  macdChart = createChart(macdChartEl.value, {
    ...common,
    height: 170,
    timeScale: { ...common.timeScale, timeVisible: true },
  })

  const candles = mergedSeries.value.map(item => ({
    time: item.date,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
  }))

  const candleSeriesLocal = priceChart.addCandlestickSeries({
    upColor: '#16a34a',
    downColor: '#dc2626',
    borderVisible: false,
    wickUpColor: '#16a34a',
    wickDownColor: '#dc2626',
  })
  candleSeriesLocal.setData(candles)
  candleSeries = candleSeriesLocal
  majorCostLine = null
  applyMajorCostLine()

  const volumeSeries = priceChart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    lastValueVisible: false,
    priceLineVisible: false,
  })
  priceChart.priceScale('volume').applyOptions({
    scaleMargins: { top: 0.78, bottom: 0 },
  })
  volumeSeries.setData(mergedSeries.value.map(item => ({
    time: item.date,
    value: item.volume,
    color: item.close >= item.open ? 'rgba(22, 163, 74, 0.45)' : 'rgba(220, 38, 38, 0.45)',
  })))

  addLineSeries(priceChart, mergedSeries.value, 'ma5', '#38bdf8')
  addLineSeries(priceChart, mergedSeries.value, 'ma20', '#f59e0b')
  addLineSeries(priceChart, mergedSeries.value, 'ma60', '#a855f7')

  const rsiSeries = rsiChart.addLineSeries({
    color: '#8b5cf6',
    lineWidth: 2,
  })
  rsiSeries.setData(toLineData(mergedSeries.value, 'rsi14'))
  addConstantLine(rsiChart, mergedSeries.value, 70, 'rgba(220, 38, 38, 0.55)')
  addConstantLine(rsiChart, mergedSeries.value, 30, 'rgba(22, 163, 74, 0.55)')

  const macdHistogram = macdChart.addHistogramSeries({
    priceLineVisible: false,
    lastValueVisible: false,
  })
  macdHistogram.setData(mergedSeries.value
    .filter(item => item.macd_hist != null)
    .map(item => ({
      time: item.date,
      value: item.macd_hist,
      color: item.macd_hist >= 0 ? 'rgba(22, 163, 74, 0.55)' : 'rgba(220, 38, 38, 0.55)',
    })))
  addLineSeries(macdChart, mergedSeries.value, 'macd_dif', '#60a5fa')
  addLineSeries(macdChart, mergedSeries.value, 'macd_dea', '#f59e0b')
  addConstantLine(macdChart, mergedSeries.value, 0, 'rgba(148, 163, 184, 0.45)')

  syncCharts([priceChart, rsiChart, macdChart])
  priceChart.timeScale().fitContent()
  rsiChart.timeScale().fitContent()
  macdChart.timeScale().fitContent()
}

function addLineSeries(chart, rows, key, color) {
  const series = chart.addLineSeries({
    color,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  })
  series.setData(toLineData(rows, key))
}

function addConstantLine(chart, rows, value, color) {
  const series = chart.addLineSeries({
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
  })
  series.setData(rows.map(item => ({ time: item.date, value })))
}

function toLineData(rows, key) {
  return rows
    .filter(item => item[key] != null)
    .map(item => ({ time: item.date, value: Number(item[key]) }))
}

function syncCharts(charts) {
  charts.forEach(sourceChart => {
    sourceChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (!range || syncGuard) return
      syncGuard = true
      charts.forEach(targetChart => {
        if (targetChart !== sourceChart) {
          targetChart.timeScale().setVisibleLogicalRange(range)
        }
      })
      syncGuard = false
    })
  })
}

function destroyCharts() {
  if (priceChart) {
    priceChart.remove()
    priceChart = null
    candleSeries = null
    majorCostLine = null
  }
  if (rsiChart) {
    rsiChart.remove()
    rsiChart = null
  }
  if (macdChart) {
    macdChart.remove()
    macdChart = null
  }
}

function handleResize() {
  if (!mergedSeries.value.length) return
  renderCharts()
  renderCalendar()
  renderVolumeProfile()
}

function renderCalendar() {
  const host = calendarEl.value
  if (!host) return
  host.innerHTML = ''
  const rows = priceItems.value
  if (rows.length < 2) return

  // Daily % change per trading day.
  const daily = []
  for (let i = 1; i < rows.length; i++) {
    const prev = rows[i - 1].close
    const cur = rows[i].close
    if (prev > 0) daily.push({ date: new Date(rows[i].date), pct: ((cur - prev) / prev) * 100 })
  }
  if (!daily.length) return

  const byYear = d3.group(daily, (d) => d.date.getFullYear())
  const years = Array.from(byYear.keys()).sort()

  const cellSize = 13
  const cellGap = 2
  const weekWidth = 53 * (cellSize + cellGap)
  const yearHeight = 7 * (cellSize + cellGap) + 20
  const width = Math.max(host.clientWidth || 900, weekWidth + 40)
  const height = yearHeight * years.length + 10

  const maxAbs = d3.max(daily, (d) => Math.abs(d.pct)) || 1
  const color = (pct) => {
    const t = Math.min(1, Math.abs(pct) / maxAbs)
    return pct >= 0
      ? d3.interpolateRgb('rgba(34,197,94,0.15)', 'rgba(34,197,94,0.95)')(t)
      : d3.interpolateRgb('rgba(239,68,68,0.15)', 'rgba(239,68,68,0.95)')(t)
  }

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)

  years.forEach((year, yi) => {
    const yearData = byYear.get(year)
    const byDate = new Map(yearData.map((d) => [d3.timeFormat('%Y-%m-%d')(d.date), d.pct]))
    const yOffset = yi * yearHeight

    const g = svg.append('g').attr('transform', `translate(20,${yOffset + 16})`)
    g.append('text')
      .attr('x', -10)
      .attr('y', -4)
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', 11)
      .attr('font-weight', 700)
      .text(year)

    const yearStart = new Date(year, 0, 1)
    const yearEnd = new Date(year, 11, 31)
    const allDays = d3.timeDays(yearStart, d3.timeDay.offset(yearEnd, 1))

    g.selectAll('rect')
      .data(allDays)
      .join('rect')
      .attr('width', cellSize)
      .attr('height', cellSize)
      .attr('rx', 2)
      .attr('x', (d) => d3.timeWeek.count(d3.timeYear(d), d) * (cellSize + cellGap))
      .attr('y', (d) => d.getDay() * (cellSize + cellGap))
      .attr('fill', (d) => {
        const pct = byDate.get(d3.timeFormat('%Y-%m-%d')(d))
        return pct == null ? 'var(--bg-tertiary)' : color(pct)
      })
      .append('title')
      .text((d) => {
        const pct = byDate.get(d3.timeFormat('%Y-%m-%d')(d))
        const label = d3.timeFormat('%Y-%m-%d')(d)
        return pct == null ? `${label}：無交易` : `${label}：${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
      })
  })
}

function renderVolumeProfile() {
  const host = volumeProfileEl.value
  if (!host) return
  host.innerHTML = ''
  const rows = priceItems.value.filter((r) => r.high > 0 && r.low > 0 && r.high >= r.low && r.volume >= 0)
  if (rows.length < 2) return

  const lo = d3.min(rows, (d) => d.low)
  const hi = d3.max(rows, (d) => d.high)
  if (!(hi > lo)) return

  const binCount = 24
  const binSize = (hi - lo) / binCount
  const bins = Array.from({ length: binCount }, (_, i) => ({
    lo: lo + i * binSize,
    hi: lo + (i + 1) * binSize,
    volume: 0,
  }))

  // Approximation: no intraday tick data is available, so each day's volume is
  // spread uniformly across that day's own [low, high] range and accumulated
  // into the overall price-level bins it overlaps.
  rows.forEach((row) => {
    const span = row.high - row.low
    if (span <= 0) {
      const idx = Math.min(binCount - 1, Math.max(0, Math.floor((row.close - lo) / binSize)))
      bins[idx].volume += row.volume
      return
    }
    const startIdx = Math.max(0, Math.floor((row.low - lo) / binSize))
    const endIdx = Math.min(binCount - 1, Math.floor((row.high - lo) / binSize))
    for (let i = startIdx; i <= endIdx; i++) {
      const overlapLo = Math.max(row.low, bins[i].lo)
      const overlapHi = Math.min(row.high, bins[i].hi)
      const overlap = Math.max(0, overlapHi - overlapLo)
      bins[i].volume += row.volume * (overlap / span)
    }
  })

  const width = Math.max(host.clientWidth || 700, 320)
  const height = Math.max(320, binCount * 16)
  const margin = { top: 8, right: 16, bottom: 24, left: 64 }
  const innerW = width - margin.left - margin.right
  const innerH = height - margin.top - margin.bottom

  const maxVolume = d3.max(bins, (d) => d.volume) || 1
  const yScale = d3.scaleBand()
    .domain(bins.map((_, i) => i))
    .range([innerH, 0])
    .padding(0.15)
  const xScale = d3.scaleLinear().domain([0, maxVolume]).range([0, innerW])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.selectAll('rect')
    .data(bins)
    .join('rect')
    .attr('x', 0)
    .attr('y', (_, i) => yScale(i))
    .attr('width', (d) => xScale(d.volume))
    .attr('height', yScale.bandwidth())
    .attr('fill', 'rgba(56,189,248,0.65)')
    .append('title')
    .text((d) => `${d.lo.toFixed(2)} ~ ${d.hi.toFixed(2)}：約 ${Math.round(d.volume).toLocaleString()} 股`)

  const priceTickEvery = Math.max(1, Math.round(binCount / 8))
  g.selectAll('text.price-tick')
    .data(bins.filter((_, i) => i % priceTickEvery === 0))
    .join('text')
    .attr('class', 'price-tick')
    .attr('x', -8)
    .attr('y', (d) => yScale(bins.indexOf(d)) + yScale.bandwidth() / 2)
    .attr('dy', '0.32em')
    .attr('text-anchor', 'end')
    .attr('font-size', 10)
    .attr('fill', 'var(--text-muted)')
    .text((d) => d.lo.toFixed(1))
}

function buildDateRange(rangeLabel) {
  const selected = ranges.find(item => item.label === rangeLabel) || ranges[3]
  const endDate = new Date()
  const startDate = new Date(endDate.getTime() - selected.days * 24 * 60 * 60 * 1000)
  return {
    start: normalizeDate(startDate.toISOString()),
    end: normalizeDate(endDate.toISOString()),
  }
}

function computeEpsGrowth(rows) {
  if (!rows.length) return 0
  const latest = toNumber(rows[rows.length - 1]?.eps)
  const previousYear = rows.length >= 5 ? toNumber(rows[rows.length - 5]?.eps) : 0
  const previousQuarter = rows.length >= 2 ? toNumber(rows[rows.length - 2]?.eps) : 0
  const base = previousYear || previousQuarter
  if (!base) return 0
  return ((latest - base) / Math.abs(base)) * 100
}

function selectTopReasons() {
  const reasons = buildReasonPool()
  if (!reasons.length) return ['目前資料不足，建議先觀察價格與量能變化。']

  if (finalAction.value === 'HOLD') {
    const sorted = [...reasons].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
    return sorted.slice(0, 3).map(item => item.text)
  }

  const targetPolarity = finalAction.value === 'BUY' ? 'bullish' : 'bearish'
  const filtered = reasons
    .filter(item => item.polarity === targetPolarity)
    .sort((a, b) => b.weight - a.weight)

  return (filtered.length ? filtered : reasons.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)))
    .slice(0, 3)
    .map(item => item.text)
}

function buildReasonPool() {
  const reasons = []
  if (latestClose.value && latestMa20.value) {
    reasons.push({
      polarity: latestClose.value > latestMa20.value ? 'bullish' : 'bearish',
      weight: 18,
      text: latestClose.value > latestMa20.value
        ? `股價站上 MA20，短中期趨勢仍維持多方。`
        : `股價跌破 MA20，短線趨勢轉弱。`,
    })
  }
  if (latestMa20.value && latestMa60.value) {
    reasons.push({
      polarity: latestMa20.value > latestMa60.value ? 'bullish' : 'bearish',
      weight: 15,
      text: latestMa20.value > latestMa60.value
        ? 'MA20 高於 MA60，中期結構偏多。'
        : 'MA20 低於 MA60，中期結構偏空。',
    })
  }
  if (latestMacd.value || latestMacdSignal.value) {
    reasons.push({
      polarity: latestMacd.value > latestMacdSignal.value ? 'bullish' : 'bearish',
      weight: 16,
      text: latestMacd.value > latestMacdSignal.value
        ? 'MACD DIF 位於 Signal 之上，動能延續。'
        : 'MACD DIF 跌破 Signal，動能有轉弱跡象。',
    })
  }
  if (latestRsi.value) {
    if (latestRsi.value < 35) {
      reasons.push({ polarity: 'bullish', weight: 11, text: `RSI(${formatNumber(latestRsi.value, 1)}) 進入偏低區，反彈機率提高。` })
    } else if (latestRsi.value > 70) {
      reasons.push({ polarity: 'bearish', weight: 12, text: `RSI(${formatNumber(latestRsi.value, 1)}) 偏熱，須留意獲利了結。` })
    }
  }
  if (volumeRatio.value) {
    reasons.push({
      polarity: volumeRatio.value >= 1 ? 'bullish' : 'bearish',
      weight: 9,
      text: volumeRatio.value >= 1
        ? `量能為近 20 日均量的 ${formatNumber(volumeRatio.value, 2)} 倍，資金參與度提升。`
        : '量能低於均值，訊號延續性需要再確認。',
    })
  }
  if (revenueGrowth.value) {
    reasons.push({
      polarity: revenueGrowth.value >= 0 ? 'bullish' : 'bearish',
      weight: 13,
      text: revenueGrowth.value >= 0
        ? `最新月營收年增 ${formatSignedPercent(revenueGrowth.value)}，基本面有支撐。`
        : `最新月營收年減 ${formatPercent(Math.abs(revenueGrowth.value))}，基本面承壓。`,
    })
  }
  if (epsGrowth.value) {
    reasons.push({
      polarity: epsGrowth.value >= 0 ? 'bullish' : 'bearish',
      weight: 15,
      text: epsGrowth.value >= 0
        ? `EPS 成長 ${formatSignedPercent(epsGrowth.value)}，獲利延續性不差。`
        : `EPS 下滑 ${formatPercent(Math.abs(epsGrowth.value))}，需留意估值修正。`,
    })
  }
  if (foreignNetBuy5.value) {
    reasons.push({
      polarity: foreignNetBuy5.value >= 0 ? 'bullish' : 'bearish',
      weight: 14,
      text: foreignNetBuy5.value >= 0
        ? `外資近 5 日累計買超 ${formatSignedCompact(foreignNetBuy5.value)}。`
        : `外資近 5 日累計賣超 ${formatSignedCompact(foreignNetBuy5.value)}。`,
    })
  }
  if (aiSignal.value?.reasoning) {
    reasons.push({
      polarity: aiSignal.value.action === 'SELL' ? 'bearish' : aiSignal.value.action === 'BUY' ? 'bullish' : 'neutral',
      weight: normalizePercent(aiSignal.value.confidence) / 5,
      text: `AI 判讀：${aiSignal.value.reasoning}`,
    })
  }
  return reasons
}

function technicalDescription() {
  if (!latestClose.value) return '等待技術資料'
  if (latestClose.value > latestMa20.value && latestMacd.value > latestMacdSignal.value) return '均線與 MACD 同步偏多'
  if (latestClose.value < latestMa20.value && latestMacd.value < latestMacdSignal.value) return '價格與動能同步轉弱'
  return '趨勢與動能仍在拉鋸'
}

function fundamentalDescription() {
  if (!revenueRows.value.length && !epsRows.value.length) return '等待財報資料'
  if (revenueGrowth.value > 10 && epsGrowth.value > 0) return '營收與 EPS 維持成長'
  if (revenueGrowth.value < 0 || epsGrowth.value < 0) return '成長動能略有放緩'
  return '基本面大致穩定'
}

function chipDescription() {
  if (!chipRows.value.length) return '等待籌碼資料'
  if (foreignNetBuy5.value > 0 && investmentTrustTrendText.value === '偏多') return '法人買盤延續，籌碼偏正向'
  if (foreignNetBuy5.value < 0) return '外資近期站在賣方'
  return '籌碼尚未形成明確趨勢'
}

function sentimentDescription() {
  if (!aiSignal.value) return '尚未取得 AI 信號'
  if (aiSignal.value.action === 'BUY') return 'AI 風險偏好轉向多方'
  if (aiSignal.value.action === 'SELL') return 'AI 風險偏好偏保守'
  return 'AI 判斷暫時觀望'
}

function saveRecent() {
  const current = symbol.value
  // Only save numeric stock codes to prevent saving Chinese names in recent list
  if (!current || !/^\d{4,6}$/.test(current)) return
  const name = stockInfo.value?.name_zh || ''
  const history = JSON.parse(localStorage.getItem('recentStocks') || '[]')
  // Normalize to objects
  const normalized = history.map(item =>
    typeof item === 'string' ? { symbol: item, name: '' } : item
  )
  // Remove duplicates and prepend current
  const next = [
    { symbol: current, name },
    ...normalized.filter(item => item.symbol !== current)
  ].slice(0, 10)
  localStorage.setItem('recentStocks', JSON.stringify(next))
}

function normalizeTrustTrend(value) {
  const text = String(value || '').toLowerCase()
  if (text === 'buy') return '偏多'
  if (text === 'sell') return '偏空'
  return '中性'
}

function normalizeDate(value) {
  if (!value) return ''
  const text = String(value)
  return text.includes('T') ? text.slice(0, 10) : text
}

function toNumber(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function nullableNumber(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function roundTo(value, digits = 2) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return Number(numeric.toFixed(digits))
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.round(numeric <= 1 ? numeric * 100 : numeric)
}

function clampScore(value) {
  return Math.round(clampBetween(value, 0, 100))
}

function clampBetween(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0))
}

function formatPrice(value) {
  return value ? formatNumber(value, 2) : '--'
}

function formatNumber(value, digits = 2) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric === 0 && value !== 0) return '--'
  return numeric.toLocaleString('zh-TW', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function formatPercent(value, digits = 1) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  return `${numeric.toFixed(digits)}%`
}

function formatSignedPercent(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(1)}%`
}

function formatSigned(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  return `${numeric >= 0 ? '+' : ''}${formatNumber(numeric, 2)}`
}

function formatLargeNumber(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  return new Intl.NumberFormat('zh-TW', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(numeric)
}

function formatSignedCompact(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '--'
  const prefix = numeric >= 0 ? '+' : ''
  return `${prefix}${formatLargeNumber(numeric)}`
}

function valueTone(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric === 0) return ''
  return numeric > 0 ? 'up' : 'down'
}
</script>

<style scoped>
.analysis-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero-card {
  padding: 24px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.22), transparent 35%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.98));
}

.hero-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: center;
}

.symbol-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}

.symbol-row h1 {
  font-size: 2.2rem;
  line-height: 1;
}

.company-name {
  color: var(--text-secondary);
  font-size: 1rem;
}

.industry-chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.15);
  color: #bfdbfe;
  font-size: 0.8rem;
}

.price-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.current-price {
  font-size: 2.8rem;
  font-weight: 700;
}

.price-change {
  font-size: 1.1rem;
  font-weight: 600;
}

.hero-summary {
  margin-top: 14px;
  max-width: 720px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-signal {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  padding: 18px;
  background: rgba(15, 23, 42, 0.72);
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}

.signal-badge-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.signal-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 84px;
  padding: 8px 16px;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.signal-badge.large {
  min-width: 96px;
  font-size: 1rem;
}

.signal-badge.buy {
  background: rgba(22, 163, 74, 0.18);
  color: #86efac;
}

.signal-badge.sell {
  background: rgba(220, 38, 38, 0.16);
  color: #fca5a5;
}

.signal-badge.hold {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}

.confidence-tag {
  color: var(--text-secondary);
  font-size: 0.86rem;
}

.signal-score {
  font-size: 3rem;
  font-weight: 800;
  line-height: 1;
}

.signal-score-label,
.signal-meta,
.metric-note,
.muted-text,
.summary-subtitle,
.score-item p,
.detail-stat span {
  color: var(--text-secondary);
}

.status-message {
  padding: 12px 16px;
  border: 1px solid rgba(220, 38, 38, 0.32);
  border-radius: 12px;
  background: rgba(127, 29, 29, 0.2);
  color: #fecaca;
}

.top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
  gap: 20px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.section-head h2 {
  font-size: 1.25rem;
  margin-top: 4px;
}

.section-head.compact {
  margin-bottom: 14px;
}

.chip-health-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: 999px;
  text-decoration: none;
  font-weight: 700;
  border: 1px solid transparent;
  transition: transform 0.18s cubic-bezier(0.22,1,0.36,1), background 0.18s ease;
}
.chip-health-badge:hover { transform: translateY(-1px); }
.chip-health-badge .chb-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.02em; }
.chip-health-badge .chb-score { font-size: 1.05rem; font-variant-numeric: tabular-nums; }
.chip-health-badge .chb-arrow { font-size: 0.85rem; opacity: 0.7; }
.chip-health-badge.tone-up { background: rgba(22,163,74,0.12); border-color: rgba(22,163,74,0.3); color: #16a34a; }
.chip-health-badge.tone-down { background: rgba(220,38,38,0.12); border-color: rgba(220,38,38,0.3); color: #dc2626; }
.chip-health-badge.tone-flat { background: rgba(234,179,8,0.12); border-color: rgba(234,179,8,0.3); color: #b45309; }

.chart-card,
.decision-card,
.summary-card,
.detail-card {
  padding: 18px;
}

.range-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.range-button {
  border: 1px solid var(--border-color);
  background: rgba(30, 41, 59, 0.85);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 7px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.range-button:hover,
.range-button.active {
  border-color: #2563eb;
  color: #eff6ff;
  background: rgba(37, 99, 235, 0.22);
}

.calendar-section { overflow-x: auto; }
.calendar-host { min-height: 120px; }
.volume-profile-section { overflow-x: auto; }
.volume-profile-host { min-height: 320px; }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }

.chart-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chart-block {
  border: 1px solid rgba(51, 65, 85, 0.55);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  padding: 12px;
}

.chart-label-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
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

.chart-wrapper .chart-area {
  flex: 1;
}

.x-axis-label {
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.legend-group {
  display: inline-flex;
  gap: 10px;
  align-items: center;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
  margin-right: 4px;
}

.legend-dot.ma5 { background: #38bdf8; }
.legend-dot.ma20 { background: var(--color-warning); }
.legend-dot.ma60 { background: #a855f7; }
.legend-dot.cost-line { width: 16px; height: 0; border-radius: 0; border-top: 2px dashed var(--color-warning); }
.legend-dev { font-variant-numeric: tabular-nums; font-weight: 700; }
.legend-dev.up { color: #16a34a; }
.legend-dev.down { color: #dc2626; }

.chart-area {
  width: 100%;
}

.decision-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.score-ring {
  width: 168px;
  height: 168px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin: 4px auto 8px;
}

.score-ring-inner {
  width: 128px;
  height: 128px;
  border-radius: 50%;
  background: #0f172a;
  border: 1px solid rgba(51, 65, 85, 0.75);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-ring-inner strong {
  font-size: 2rem;
}

.score-ring-inner span {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.score-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.score-item-head,
.summary-badge-row,
.summary-footer,
.metric-value,
.detail-grid,
.detail-stat,
.mini-table-head,
.mini-table-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.score-item-head strong,
.metric-value,
.detail-stat strong {
  font-weight: 700;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(51, 65, 85, 0.5);
  margin: 8px 0 6px;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 14px;
}

.metric-tile {
  min-height: 126px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98));
}

.metric-label {
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.metric-value {
  font-size: 1.35rem;
  align-items: center;
}

.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-confidence {
  font-weight: 700;
}

.reason-list {
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  line-height: 1.65;
}

.summary-footer {
  padding-top: 14px;
  border-top: 1px solid rgba(51, 65, 85, 0.65);
  flex-wrap: wrap;
}

.summary-mini {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 180px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.detail-stat {
  flex-direction: column;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(51, 65, 85, 0.55);
  background: rgba(15, 23, 42, 0.6);
}

.detail-stat strong {
  font-size: 1.1rem;
}

.mini-table {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mini-table-head,
.mini-table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 0.9fr;
  align-items: center;
  font-size: 0.9rem;
}

.mini-table-head {
  color: var(--text-secondary);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.mini-table-row {
  padding: 10px 0;
  border-top: 1px solid rgba(51, 65, 85, 0.45);
}

.empty-state {
  color: var(--text-secondary);
  padding: 6px 0 0;
}

.up {
  color: var(--color-up);
}

.down {
  color: var(--color-down);
}

@media (max-width: 1440px) {
  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .bottom-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1120px) {
  .hero-main,
  .top-grid {
    grid-template-columns: 1fr;
  }

  .hero-signal {
    max-width: 320px;
  }
}

@media (max-width: 768px) {
  .hero-card {
    padding: 18px;
  }

  .symbol-row h1 {
    font-size: 1.8rem;
  }

  .current-price {
    font-size: 2.2rem;
  }

  .metrics-grid,
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-head,
  .chart-label-row,
  .summary-badge-row {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 520px) {
  .metrics-grid,
  .detail-grid,
  .mini-table-head,
  .mini-table-row {
    grid-template-columns: 1fr;
  }

  .range-selector {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .hero-card {
    padding: 12px;
  }

  .symbol-row h1 {
    font-size: 1.4rem;
  }

  .current-price {
    font-size: 1.6rem;
  }

  .factor-item {
    min-width: 0;
  }

  .range-button {
    min-width: 0;
    padding: 4px 8px;
    font-size: 0.7rem;
  }

  .legend-group {
    flex-wrap: wrap;
    gap: 6px;
  }

  .legend-dot {
    min-width: 0;
  }

  .chart-area.price-chart {
    min-height: 240px;
  }

  .chart-area.indicator-chart {
    min-height: 100px;
  }

  .y-axis-label {
    font-size: 0.58rem;
    padding: 0 2px;
  }

  .decision-card {
    max-width: 100%;
  }

  .top-grid {
    gap: var(--space-3);
  }
}
</style>
