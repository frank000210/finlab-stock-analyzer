<template>
  <div class="overview-page">
    <PageFocusBanner text="一眼掌握個股在技術、籌碼、基本面、情緒等維度的綜合健康度，作為深入分析前的第一站。" />

    <header class="page-header">
      <div>
        <h1>📊 個股總覽儀表板</h1>
        <p class="subtitle">{{ stockStore.symbol }} {{ stockStore.name }} — 各維度綜合評估</p>
      </div>
      <button class="btn btn-primary" @click="loadAll" :disabled="loading">
        {{ loading ? '載入中...' : '🔄 重新整理' }}
      </button>
    </header>

    <!-- Daily Sector Heatmap Treemap -->
    <section class="card heatmap-section">
      <h2>🔥 每日類股漲跌熱力圖</h2>
      <div ref="heatmapEl" class="chart-host heatmap-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Treemap；方塊大小＝漲跌幅度、顏色＝漲跌方向。資料日期：{{ heatmapData?.date || '—' }}
      </p>
    </section>

    <!-- Radar Chart -->
    <section class="card radar-section">
      <h2>🎯 綜合評分雷達圖</h2>
      <div class="radar-container">
        <svg viewBox="0 0 400 400" class="radar-svg">
          <!-- Background rings -->
          <polygon v-for="ring in [0.2, 0.4, 0.6, 0.8, 1.0]" :key="ring"
            :points="ringPoints(ring)" fill="none" stroke="var(--border-color)" stroke-width="0.5"/>
          <!-- Axis lines -->
          <line v-for="(_, i) in dimensions" :key="'axis'+i"
            x1="200" y1="200" :x2="axisEnd(i).x" :y2="axisEnd(i).y"
            stroke="var(--border-color)" stroke-width="0.5"/>
          <!-- Data polygon -->
          <polygon :points="dataPoints" fill="rgba(59, 130, 246, 0.2)" stroke="var(--accent-blue)" stroke-width="2"/>
          <!-- Data dots -->
          <circle v-for="(d, i) in dimensions" :key="'dot'+i"
            :cx="dataPoint(i).x" :cy="dataPoint(i).y" r="5"
            fill="var(--accent-blue)" stroke="#fff" stroke-width="2"/>
          <!-- Labels -->
          <text v-for="(d, i) in dimensions" :key="'label'+i"
            :x="labelPos(i).x" :y="labelPos(i).y"
            text-anchor="middle" font-size="12" fill="var(--text-secondary)">
            {{ d.label }}
          </text>
          <!-- Score labels -->
          <text v-for="(d, i) in dimensions" :key="'score'+i"
            :x="scorePos(i).x" :y="scorePos(i).y"
            text-anchor="middle" font-size="11" font-weight="700" fill="var(--accent-blue)">
            {{ d.score }}
          </text>
        </svg>
      </div>
    </section>

    <!-- Summary Cards Grid -->
    <div class="summary-grid">
      <!-- Seasonal -->
      <div class="card summary-card" @click="goTo('seasonal')">
        <div class="card-head">
          <span class="card-icon">📅</span>
          <h3>季節性分析</h3>
        </div>
        <div v-if="seasonal">
          <div class="summary-score">{{ scores.seasonal }}<span class="score-unit">/100</span></div>
          <p class="summary-text">{{ seasonal.patterns?.[0]?.name || '分析中...' }}</p>
          <div class="summary-detail">{{ seasonal.patterns?.[0]?.description?.slice(0, 60) }}...</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>

      <!-- Lead-Lag -->
      <div class="card summary-card" @click="goTo('lead-lag')">
        <div class="card-head">
          <span class="card-icon">⏱️</span>
          <h3>領先/落後</h3>
        </div>
        <div v-if="leadLag">
          <div class="summary-score">{{ scores.leadLag }}<span class="score-unit">/100</span></div>
          <p class="summary-text">{{ leadLag.interpretation?.direction }} {{ Math.abs(leadLag.optimal_lag) }} 天</p>
          <div class="summary-detail">β={{ leadLag.beta?.value }} | 相關 {{ leadLag.peak_correlation }}</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>

      <!-- Major Players -->
      <div class="card summary-card" @click="goTo('major-players')">
        <div class="card-head">
          <span class="card-icon">🐋</span>
          <h3>主力動向</h3>
        </div>
        <div v-if="majorPlayers">
          <div class="summary-score">{{ scores.majorPlayers }}<span class="score-unit">/100</span></div>
          <p class="summary-text verdict-badge" :class="'v-' + majorPlayers.verdict">{{ majorPlayers.verdict }}</p>
          <div class="summary-detail">信心 {{ majorPlayers.confidence }}% | {{ majorPlayers.signals?.length || 0 }} 個信號</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>

      <!-- Social Buzz -->
      <div class="card summary-card" @click="goTo('social-buzz')">
        <div class="card-head">
          <span class="card-icon">🔥</span>
          <h3>社群熱度</h3>
        </div>
        <div v-if="socialBuzz">
          <div class="summary-score">{{ scores.socialBuzz }}<span class="score-unit">/100</span></div>
          <p class="summary-text">{{ socialBuzz.buzz_level }} — {{ socialBuzz.trend_label }}</p>
          <div class="summary-detail">PTT {{ socialBuzz.ptt?.post_count }}篇 | 新聞 {{ socialBuzz.news?.article_count }}篇</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>

      <!-- Public Data -->
      <div class="card summary-card" @click="goTo('public-data')">
        <div class="card-head">
          <span class="card-icon">📋</span>
          <h3>公開資訊</h3>
        </div>
        <div v-if="publicData">
          <div class="summary-score">{{ scores.publicData }}<span class="score-unit">/100</span></div>
          <p class="summary-text">公告 {{ publicData.announcements?.length || 0 }} 則</p>
          <div class="summary-detail">配息 {{ publicData.dividends?.[0]?.total || '–' }} 元/股</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>

      <!-- Technical Analysis -->
      <div class="card summary-card" @click="goTo('analysis')">
        <div class="card-head">
          <span class="card-icon">📈</span>
          <h3>技術分析</h3>
        </div>
        <div v-if="technical">
          <div class="summary-score">{{ scores.technical }}<span class="score-unit">/100</span></div>
          <p class="summary-text">RSI {{ technical.rsi?.toFixed(0) || '–' }}</p>
          <div class="summary-detail">{{ technical.trend || '計算中...' }}</div>
        </div>
        <div v-else class="loading-placeholder">載入中...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'

const router = useRouter()
const stockStore = useStockStore()
const theme = useChartTheme()
const loading = ref(false)
const heatmapEl = ref(null)
const heatmapData = ref(null)

const seasonal = ref(null)
const leadLag = ref(null)
const majorPlayers = ref(null)
const socialBuzz = ref(null)
const publicData = ref(null)
const technical = ref(null)

const scores = computed(() => ({
  seasonal: seasonal.value ? computeSeasonalScore(seasonal.value) : 0,
  leadLag: leadLag.value ? computeLeadLagScore(leadLag.value) : 0,
  majorPlayers: majorPlayers.value ? Math.min(100, Math.max(0, 50 + majorPlayers.value.score)) : 0,
  socialBuzz: socialBuzz.value ? socialBuzz.value.buzz_score : 0,
  publicData: publicData.value ? computePublicScore(publicData.value) : 0,
  technical: technical.value ? technical.value.score || 50 : 0,
}))

const dimensions = computed(() => [
  { label: '季節性', score: scores.value.seasonal },
  { label: '領先落後', score: scores.value.leadLag },
  { label: '主力動向', score: scores.value.majorPlayers },
  { label: '社群熱度', score: scores.value.socialBuzz },
  { label: '公開資訊', score: scores.value.publicData },
  { label: '技術面', score: scores.value.technical },
])

const dataPoints = computed(() => {
  return dimensions.value.map((d, i) => {
    const p = dataPoint(i)
    return `${p.x},${p.y}`
  }).join(' ')
})

function ringPoints(scale) {
  const n = dimensions.value.length
  return Array.from({ length: n }, (_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2
    const x = 200 + 150 * scale * Math.cos(angle)
    const y = 200 + 150 * scale * Math.sin(angle)
    return `${x},${y}`
  }).join(' ')
}

function axisEnd(i) {
  const n = dimensions.value.length
  const angle = (Math.PI * 2 * i) / n - Math.PI / 2
  return { x: 200 + 150 * Math.cos(angle), y: 200 + 150 * Math.sin(angle) }
}

function dataPoint(i) {
  const n = dimensions.value.length
  const angle = (Math.PI * 2 * i) / n - Math.PI / 2
  const val = (dimensions.value[i]?.score || 0) / 100
  return { x: 200 + 150 * val * Math.cos(angle), y: 200 + 150 * val * Math.sin(angle) }
}

function labelPos(i) {
  const n = dimensions.value.length
  const angle = (Math.PI * 2 * i) / n - Math.PI / 2
  return { x: 200 + 180 * Math.cos(angle), y: 200 + 180 * Math.sin(angle) + 4 }
}

function scorePos(i) {
  const n = dimensions.value.length
  const angle = (Math.PI * 2 * i) / n - Math.PI / 2
  const val = (dimensions.value[i]?.score || 0) / 100
  return { x: 200 + (150 * val + 15) * Math.cos(angle), y: 200 + (150 * val + 15) * Math.sin(angle) + 4 }
}

function computeSeasonalScore(d) {
  if (!d.patterns || d.patterns.length === 0) return 30
  if (d.patterns[0].type === 'no_pattern') return 30
  const strong = d.patterns.filter(p => p.strength === '強').length
  return Math.min(100, 40 + strong * 20 + d.patterns.length * 10)
}

function computeLeadLagScore(d) {
  const corr = Math.abs(d.peak_correlation || 0)
  return Math.min(100, Math.round(corr * 100))
}

function computePublicScore(d) {
  let score = 50
  if (d.announcements?.length > 3) score += 20
  if (d.dividends?.length > 0 && d.dividends[0].total > 0) score += 20
  return Math.min(100, score)
}

function goTo(page) {
  const sym = stockStore.symbol
  if (page === 'analysis') {
    router.push(`/stocks/${sym}`)
  } else {
    router.push(`/stocks/${sym}/${page}`)
  }
}

async function loadAll() {
  loading.value = true
  const sym = stockStore.symbol
  const fetches = [
    fetch(`/api/v1/stocks/${sym}/seasonal?years=5`).then(r => r.json()).then(d => { seasonal.value = d.data }).catch(() => {}),
    fetch(`/api/v1/stocks/${sym}/lead-lag?benchmark=TAIEX&days=365`).then(r => r.json()).then(d => { leadLag.value = d.data }).catch(() => {}),
    fetch(`/api/v1/stocks/${sym}/major-players?days=60`).then(r => r.json()).then(d => { majorPlayers.value = d.data }).catch(() => {}),
    fetch(`/api/v1/stocks/${sym}/social-buzz`).then(r => r.json()).then(d => { socialBuzz.value = d.data }).catch(() => {}),
    fetch(`/api/v1/stocks/${sym}/public-data`).then(r => r.json()).then(d => { publicData.value = d.data }).catch(() => {}),
    fetch(`/api/v1/stocks/${sym}/price?period=1d`).then(r => r.json()).then(d => {
      if (d.data?.items?.length > 14) {
        const items = d.data.items
        const closes = items.map(i => i.close)
        const last14 = closes.slice(-14)
        const gains = last14.filter((v, i) => i > 0 && v > last14[i-1]).length
        const rsi = (gains / 13) * 100
        const trend = closes[closes.length-1] > closes[closes.length-20] ? '短期上升趨勢' : '短期下降趨勢'
        technical.value = { rsi, trend, score: Math.round(rsi > 70 ? 80 : rsi > 30 ? 60 : 30) }
      }
    }).catch(() => {}),
  ]
  await Promise.allSettled(fetches)
  loading.value = false
}

async function loadHeatmap() {
  try {
    const res = await fetch('/api/v1/rotation/heatmap?universe=twse')
    const json = await res.json()
    if (json.success) heatmapData.value = json.data
  } catch (e) {
    // 熱力圖失敗不影響其他總覽卡片
  }
}

function renderHeatmap() {
  const host = heatmapEl.value
  if (!host) return
  host.innerHTML = ''
  const items = heatmapData.value?.items || []
  if (!items.length) return

  const width = host.clientWidth || 760
  const height = 280

  const root = d3
    .hierarchy({ children: items })
    .sum((d) => Math.max(0.05, Math.abs(d.pct_change || 0)))
    .sort((a, b) => (b.value || 0) - (a.value || 0))

  d3.treemap().size([width, height]).paddingInner(2)(root)

  const maxAbs = d3.max(items, (d) => Math.abs(d.pct_change || 0)) || 1
  const color = (pct) => {
    const t = Math.min(1, Math.abs(pct) / maxAbs)
    return pct >= 0
      ? d3.interpolateRgb(d3.color(theme.up).copy({ opacity: 0.25 }).toString(), d3.color(theme.up).copy({ opacity: 0.95 }).toString())(t)
      : d3.interpolateRgb(d3.color(theme.down).copy({ opacity: 0.25 }).toString(), d3.color(theme.down).copy({ opacity: 0.95 }).toString())(t)
  }

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const cell = svg
    .selectAll('g')
    .data(root.leaves())
    .join('g')
    .attr('transform', (d) => `translate(${d.x0},${d.y0})`)

  cell
    .append('rect')
    .attr('width', (d) => Math.max(0, d.x1 - d.x0))
    .attr('height', (d) => Math.max(0, d.y1 - d.y0))
    .attr('fill', (d) => color(d.data.pct_change || 0))
    .attr('stroke', 'var(--bg-primary)')
    .attr('rx', 3)

  cell
    .filter((d) => d.x1 - d.x0 > 46 && d.y1 - d.y0 > 26)
    .append('text')
    .attr('x', 6)
    .attr('y', 16)
    .attr('fill', theme.text)
    .attr('font-size', 11)
    .attr('font-weight', 700)
    .text((d) => d.data.name)

  cell
    .filter((d) => d.x1 - d.x0 > 46 && d.y1 - d.y0 > 40)
    .append('text')
    .attr('x', 6)
    .attr('y', 32)
    .attr('fill', theme.text)
    .attr('font-size', 12)
    .attr('font-weight', 800)
    .text((d) => `${d.data.pct_change >= 0 ? '+' : ''}${d.data.pct_change}%`)

  cell.append('title').text((d) => `${d.data.name}：${d.data.pct_change >= 0 ? '+' : ''}${d.data.pct_change}%`)
}

watch(heatmapData, () => nextTick(renderHeatmap))

let heatmapResizeHandler = null
onMounted(() => {
  loadAll()
  loadHeatmap()
  heatmapResizeHandler = () => renderHeatmap()
  window.addEventListener('resize', heatmapResizeHandler)
})
onBeforeUnmount(() => {
  if (heatmapResizeHandler) window.removeEventListener('resize', heatmapResizeHandler)
})
</script>

<style scoped>
.overview-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-3); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }

.heatmap-section { display: flex; flex-direction: column; }
.chart-host { width: 100%; min-height: 280px; }
.heatmap-host :deep(svg) { display: block; width: 100%; height: auto; }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }

.radar-section { display: flex; flex-direction: column; align-items: center; }
.radar-container { width: 100%; max-width: 420px; }
.radar-svg { width: 100%; height: auto; }

.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-4); }
.summary-card { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.summary-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.15); }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.card-icon { font-size: 1.3rem; }
.card-head h3 { font-size: 0.9rem; margin: 0; }
.summary-score { font-size: 2rem; font-weight: 800; color: var(--accent-blue); line-height: 1; }
.score-unit { font-size: 0.8rem; font-weight: 400; color: var(--text-muted); }
.summary-text { font-size: 0.85rem; margin: 8px 0 4px; font-weight: 600; }
.summary-detail { font-size: 0.75rem; color: var(--text-muted); }
.loading-placeholder { color: var(--text-muted); font-size: 0.85rem; }

.verdict-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; }
.v-拉抬 { background: rgba(34, 197, 94, 0.15); color: var(--accent-green); }
.v-偏多 { background: rgba(34, 197, 94, 0.1); color: var(--accent-green); }
.v-出貨 { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
.v-偏空 { background: rgba(239, 68, 68, 0.1); color: var(--accent-red); }
.v-中性 { background: rgba(59, 130, 246, 0.1); color: var(--accent-blue); }

@media (max-width: 768px) {
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .radar-container { max-width: 320px; }
}
@media (max-width: 420px) {
  .summary-grid { grid-template-columns: 1fr; }
  .radar-container { max-width: 280px; }
  .summary-score { font-size: 1.5rem; }
}
</style>
