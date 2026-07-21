<template>
  <div class="overview-page">
    <PageFocusBanner text="一眼掌握個股在技術、籌碼、基本面、情緒等維度的綜合健康度，作為深入分析前的第一站。" />

    <header class="page-header">
      <div>
        <h1>📊 個股總覽儀表板</h1>
        <p class="subtitle">{{ stockStore.symbol }} {{ stockStore.name }} — 各維度綜合評估</p>
      </div>
      <div class="header-actions">
        <button class="btn" type="button" @click="showLayoutPanel = !showLayoutPanel" :aria-expanded="showLayoutPanel">🧩 版面設定</button>
        <button class="btn btn-primary" @click="loadAll" :disabled="loading">
          {{ loading ? '載入中...' : '🔄 重新整理' }}
        </button>
      </div>
    </header>

    <!-- Y10：版面自訂——顯示/隱藏＋排序各維度卡片，設定存在這台裝置 -->
    <div v-if="showLayoutPanel" class="card layout-panel">
      <div class="layout-panel-head">
        <h3>自訂維度顯示與順序</h3>
        <button class="btn xs" type="button" @click="resetLayout">重置為預設</button>
      </div>
      <ul class="layout-list">
        <li v-for="(key, i) in layoutPrefs.order" :key="key" class="layout-item">
          <label>
            <input type="checkbox" :checked="!isHidden(key)" @change="toggleHidden(key)" />
            {{ cardLabel(key) }}
          </label>
          <span class="layout-move">
            <button type="button" class="icon-btn" :disabled="i === 0" @click="moveCard(key, -1)" aria-label="上移">↑</button>
            <button type="button" class="icon-btn" :disabled="i === layoutPrefs.order.length - 1" @click="moveCard(key, 1)" aria-label="下移">↓</button>
          </span>
        </li>
      </ul>
      <p class="muted small">隱藏的維度不會出現在下方卡片，也不會列入雷達圖計分（至少保留 1 個）；設定只存在這台裝置的瀏覽器。</p>
    </div>

    <!-- Radar Chart -->
    <div class="overview-hero-grid">
      <section class="card radar-section">
        <h2>🎯 綜合評分雷達圖 <InfoTooltip label="綜合評分雷達圖" text="六個維度各自 0-100 分，分數是把該維度頁面（季節性/領先落後/主力動向/社群熱度/公開資訊/技術面）的原始指標換算而來，每個維度的換算公式不同，越靠外圍代表該維度越偏多／越健康，但不同維度之間的分數不宜直接相減比較，建議點進該維度卡片看詳細數據。" /></h2>
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
    </div>

    <!-- Summary Cards Grid -->
    <div class="summary-grid">
      <!-- Seasonal -->
      <div class="card summary-card" v-show="!isHidden('seasonal')" :style="cardStyle('seasonal')" role="link" tabindex="0" aria-label="季節性分析" @click="goTo('seasonal')" @keydown.enter="goTo('seasonal')" @keydown.space.prevent="goTo('seasonal')">
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
      <div class="card summary-card" v-show="!isHidden('leadLag')" :style="cardStyle('leadLag')" role="link" tabindex="0" aria-label="領先/落後" @click="goTo('lead-lag')" @keydown.enter="goTo('lead-lag')" @keydown.space.prevent="goTo('lead-lag')">
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
      <div class="card summary-card" v-show="!isHidden('majorPlayers')" :style="cardStyle('majorPlayers')" role="link" tabindex="0" aria-label="主力動向" @click="goTo('major-players')" @keydown.enter="goTo('major-players')" @keydown.space.prevent="goTo('major-players')">
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
      <div class="card summary-card" v-show="!isHidden('socialBuzz')" :style="cardStyle('socialBuzz')" role="link" tabindex="0" aria-label="社群熱度" @click="goTo('social-buzz')" @keydown.enter="goTo('social-buzz')" @keydown.space.prevent="goTo('social-buzz')">
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
      <div class="card summary-card" v-show="!isHidden('publicData')" :style="cardStyle('publicData')" role="link" tabindex="0" aria-label="公開資訊" @click="goTo('public-data')" @keydown.enter="goTo('public-data')" @keydown.space.prevent="goTo('public-data')">
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
      <div class="card summary-card" v-show="!isHidden('technical')" :style="cardStyle('technical')" role="link" tabindex="0" aria-label="技術分析" @click="goTo('analysis')" @keydown.enter="goTo('analysis')" @keydown.space.prevent="goTo('analysis')">
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
import InfoTooltip from '../components/InfoTooltip.vue'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { loadLayoutPrefs, saveLayoutPrefs } from '../lib/layoutPrefs'

const router = useRouter()
const stockStore = useStockStore()
const loading = ref(false)

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

// Y10：版面自訂——6 個維度卡片可顯示/隱藏＋排序，隱藏的維度也不列入雷達圖。
const CARD_LABELS = {
  seasonal: '季節性分析', leadLag: '領先/落後', majorPlayers: '主力動向',
  socialBuzz: '社群熱度', publicData: '公開資訊', technical: '技術分析',
}
const DEFAULT_ORDER = Object.keys(CARD_LABELS)
const LAYOUT_PAGE_KEY = 'overview'

const layoutPrefs = ref(loadLayoutPrefs(LAYOUT_PAGE_KEY, DEFAULT_ORDER))
const showLayoutPanel = ref(false)

function cardLabel(key) { return CARD_LABELS[key] || key }
function isHidden(key) { return layoutPrefs.value.hidden.includes(key) }
function cardStyle(key) {
  const idx = layoutPrefs.value.order.indexOf(key)
  return { order: idx === -1 ? 999 : idx }
}
function persistLayout() { saveLayoutPrefs(LAYOUT_PAGE_KEY, layoutPrefs.value) }

function toggleHidden(key) {
  const currentlyHidden = isHidden(key)
  if (!currentlyHidden) {
    const visibleCount = layoutPrefs.value.order.length - layoutPrefs.value.hidden.length
    if (visibleCount <= 1) return // 至少保留 1 個維度，避免雷達圖無資料可畫
  }
  const hidden = currentlyHidden
    ? layoutPrefs.value.hidden.filter(k => k !== key)
    : [...layoutPrefs.value.hidden, key]
  layoutPrefs.value = { ...layoutPrefs.value, hidden }
  persistLayout()
}

function moveCard(key, dir) {
  const order = [...layoutPrefs.value.order]
  const i = order.indexOf(key)
  const j = i + dir
  if (i < 0 || j < 0 || j >= order.length) return
  ;[order[i], order[j]] = [order[j], order[i]]
  layoutPrefs.value = { ...layoutPrefs.value, order }
  persistLayout()
}

function resetLayout() {
  layoutPrefs.value = { order: [...DEFAULT_ORDER], hidden: [] }
  persistLayout()
}

const dimensions = computed(() => {
  const all = {
    seasonal: { label: '季節性', score: scores.value.seasonal },
    leadLag: { label: '領先落後', score: scores.value.leadLag },
    majorPlayers: { label: '主力動向', score: scores.value.majorPlayers },
    socialBuzz: { label: '社群熱度', score: scores.value.socialBuzz },
    publicData: { label: '公開資訊', score: scores.value.publicData },
    technical: { label: '技術面', score: scores.value.technical },
  }
  const hidden = new Set(layoutPrefs.value.hidden)
  return layoutPrefs.value.order.filter(k => !hidden.has(k)).map(k => all[k]).filter(Boolean)
})

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

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.overview-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-3); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.header-actions { display: flex; gap: 8px; align-items: center; }

.layout-panel { display: flex; flex-direction: column; gap: 10px; }
.layout-panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.layout-panel-head h3 { margin: 0; font-size: 0.95rem; }
.btn.xs { padding: 4px 10px; font-size: 0.78rem; }
.layout-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.layout-item {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 8px;
}
.layout-item label { display: flex; align-items: center; gap: 8px; font-size: 0.86rem; cursor: pointer; }
.layout-move { display: flex; gap: 4px; }
.icon-btn { border: 1px solid var(--border-color); background: var(--bg-secondary); border-radius: 6px; width: 26px; height: 24px; cursor: pointer; color: var(--text-secondary); font-size: 0.75rem; line-height: 1; }
.icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.overview-hero-grid {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-4);
}

.radar-section { display: flex; flex-direction: column; align-items: center; margin-bottom: 0; width: 100%; max-width: 480px; }
.radar-container { width: 100%; max-width: 420px; }
.radar-svg { width: 100%; height: auto; }

.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-4); }
.summary-card { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.summary-card:hover, .summary-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.card-icon { font-size: 1.3rem; }
.card-head h3 { font-size: 0.9rem; margin: 0; }
.summary-score { font-size: 2rem; font-weight: 800; color: var(--accent-blue); line-height: 1; }
.score-unit { font-size: 0.8rem; font-weight: 400; color: var(--text-muted); }
.summary-text { font-size: 0.85rem; margin: 8px 0 4px; font-weight: 600; }
.summary-detail { font-size: 0.75rem; color: var(--text-muted); }
.loading-placeholder { color: var(--text-muted); font-size: 0.85rem; }

.verdict-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; }
.v-拉抬 { background: var(--up-soft); color: var(--accent-green); }
.v-偏多 { background: var(--up-soft); color: var(--accent-green); }
.v-出貨 { background: var(--down-soft); color: var(--accent-red); }
.v-偏空 { background: var(--down-soft); color: var(--accent-red); }
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
