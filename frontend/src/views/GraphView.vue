<template>
  <div class="graph-page">
    <section class="section-block graph-hero" v-reveal>
      <div>
        <h1>觀察股關聯圖（Graph）</h1>
        <p>用每日圖譜追蹤領先落後、資金流向與產業關聯，支援門檻調整與逐日播放。</p>
      </div>
      <div class="hero-meta">
        <span class="badge">觀察池 {{ symbols.length }} 檔</span>
        <span class="badge">門檻 {{ threshold.toFixed(2) }}</span>
      </div>
    </section>

    <section class="section-block graph-controls" v-reveal>
      <div class="control-grid">
        <label class="field">
          <span>觀察池（逗號分隔）</span>
          <input v-model="symbolInput" class="input" placeholder="2330,2317,2454" />
        </label>
        <label class="field">
          <span>起始日期</span>
          <input v-model="startDate" class="input" type="date" />
        </label>
        <label class="field">
          <span>結束日期</span>
          <input v-model="endDate" class="input" type="date" />
        </label>
        <label class="field">
          <span>Lookback 天數</span>
          <input v-model.number="lookbackDays" class="input" type="number" min="30" max="365" step="5" />
        </label>
      </div>

      <div class="control-actions">
        <button class="btn" @click="applySymbols">套用觀察池</button>
        <button class="btn btn-primary" :disabled="loading" @click="reloadTimeline">重算圖譜</button>
      </div>

      <div class="slider-row">
        <label>
          Edge 門檻：<strong>{{ threshold.toFixed(2) }}</strong>
        </label>
        <input v-model.number="threshold" type="range" min="0" max="1" step="0.01" />
      </div>

      <div class="slider-row" v-if="timelineDates.length">
        <label>
          日期播放：<strong>{{ activeDate || '—' }}</strong>
        </label>
        <input v-model.number="currentIndex" type="range" :min="0" :max="timelineDates.length - 1" step="1" />
      </div>

      <div class="playback-row">
        <button class="btn btn-primary" :disabled="!timelineDates.length" @click="togglePlay">
          {{ isPlaying ? 'Pause' : 'Play' }}
        </button>
        <label class="speed-select">
          播放速度
          <select v-model.number="playIntervalMs">
            <option :value="1200">慢（1.2s）</option>
            <option :value="700">中（0.7s）</option>
            <option :value="350">快（0.35s）</option>
          </select>
        </label>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </section>

    <section class="graph-layout section-block" v-reveal>
      <div class="graph-canvas-wrap">
        <svg class="graph-canvas" viewBox="0 0 960 560" preserveAspectRatio="xMidYMid meet">
          <g>
            <line
              v-for="edge in graphEdges"
              :key="`${edge.src}-${edge.dst}`"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              :stroke="edge.weight >= 0 ? '#4f8cff' : '#ef4444'"
              :stroke-width="edge.strokeWidth"
              :opacity="0.72"
            />
          </g>
          <g>
            <g
              v-for="node in laidOutNodes"
              :key="node.symbol"
              class="node-group"
              @click="selectedSymbol = node.symbol"
            >
              <circle
                :cx="node.x"
                :cy="node.y"
                :r="node.radius"
                :fill="nodeColor(node.industry)"
                :stroke="selectedSymbol === node.symbol ? '#f8fafc' : 'rgba(255,255,255,.25)'"
                :stroke-width="selectedSymbol === node.symbol ? 3 : 1.2"
              />
              <text :x="node.x" :y="node.y + 4" text-anchor="middle" class="node-symbol">{{ node.symbol }}</text>
            </g>
          </g>
        </svg>
        <div v-if="!laidOutNodes.length && !loading" class="canvas-empty">
          目前區間查無可視化資料，已自動嘗試以單日快照回補。請調整日期區間或降低門檻。
        </div>
      </div>

      <aside class="graph-side">
        <h3>節點明細</h3>
        <div v-if="selectedNode" class="detail-card">
          <p class="symbol">{{ selectedNode.symbol }} · {{ selectedNode.name_zh }}</p>
          <p class="muted">{{ selectedNode.industry }}</p>
          <p>中心性：<strong>{{ percent(selectedNode.centrality) }}</strong></p>
          <p>加權連結：<strong>{{ fixed(selectedNode.weighted_degree) }}</strong></p>
          <p>風險傳導：<strong>{{ fixed(selectedNode.risk_transmission) }}</strong></p>
          <p>20日動能：<strong>{{ percent(selectedNode.momentum_20) }}</strong></p>
          <p>資金強度：<strong>{{ fixed(selectedNode.flow_strength) }}</strong></p>
        </div>
        <div v-else class="detail-card muted">點選左側節點查看明細</div>

        <h3 class="alerts-title">告警</h3>
        <ul class="alerts-list">
          <li v-for="item in alerts" :key="item.message">
            <span class="badge">{{ item.severity || 'info' }}</span>
            <span>{{ item.message }}</span>
          </li>
          <li v-if="!alerts.length" class="muted">目前沒有告警</li>
        </ul>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const WATCHLIST_STORAGE_KEY = 'finlab_watchlist'

const loading = ref(false)
const errorMessage = ref('')
const symbols = ref(loadWatchlist())
const symbolInput = ref(symbols.value.join(','))
const threshold = ref(0.35)
const lookbackDays = ref(60)
const endDate = ref(todayISO())
const startDate = ref(offsetISO(30))
const timelineItems = ref([])
const currentIndex = ref(0)
const selectedSymbol = ref('')
const alerts = ref([])
const isPlaying = ref(false)
const playIntervalMs = ref(700)
let playTimer = null
let reloadTimer = null

const timelineDates = computed(() => timelineItems.value.map(item => item.date))
const activeDate = computed(() => timelineDates.value[currentIndex.value] || '')
const currentSnapshot = computed(() => timelineItems.value[currentIndex.value] || null)

const laidOutNodes = computed(() => {
  const nodes = currentSnapshot.value?.nodes || []
  const cx = 480
  const cy = 280
  const radius = Math.max(120, 240 - nodes.length * 2.5)
  const maxDegree = Math.max(...nodes.map(node => Number(node.weighted_degree || 0)), 1)
  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1)
    const degree = Number(node.weighted_degree || 0)
    return {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      radius: 18 + (degree / maxDegree) * 14,
    }
  })
})

const nodeMap = computed(() => {
  const map = {}
  for (const node of laidOutNodes.value) map[node.symbol] = node
  return map
})

const graphEdges = computed(() => {
  const fusion = currentSnapshot.value?.layers?.fusion || []
  return fusion
    .map((edge) => {
      const from = nodeMap.value[edge.src]
      const to = nodeMap.value[edge.dst]
      if (!from || !to) return null
      return {
        ...edge,
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
        strokeWidth: 1 + Math.min(5, Math.abs(Number(edge.weight || 0)) * 7),
      }
    })
    .filter(Boolean)
})

const selectedNode = computed(() => {
  const symbol = selectedSymbol.value
  if (!symbol) return null
  return laidOutNodes.value.find(node => node.symbol === symbol) || null
})

watch(currentSnapshot, (snapshot) => {
  if (!snapshot?.nodes?.length) {
    selectedSymbol.value = ''
    return
  }
  if (!snapshot.nodes.some(node => node.symbol === selectedSymbol.value)) {
    selectedSymbol.value = snapshot.nodes[0].symbol
  }
})

watch(threshold, () => {
  clearTimeout(reloadTimer)
  reloadTimer = setTimeout(() => {
    reloadTimeline()
  }, 350)
})

onMounted(async () => {
  await reloadTimeline()
})

onBeforeUnmount(() => {
  if (playTimer) clearInterval(playTimer)
  if (reloadTimer) clearTimeout(reloadTimer)
})

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    const normalized = Array.isArray(parsed)
      ? parsed.map(item => String(item || '').trim()).filter(Boolean)
      : []
    return normalized.length ? normalized : ['2330', '2317', '2454']
  } catch {
    return ['2330', '2317', '2454']
  }
}

function normalizeSymbols(raw) {
  const seen = new Set()
  return raw
    .split(',')
    .map(item => item.trim().toUpperCase())
    .filter((item) => item && !seen.has(item) && seen.add(item))
}

function applySymbols() {
  const parsed = normalizeSymbols(symbolInput.value)
  if (parsed.length < 2) {
    errorMessage.value = '至少需要 2 檔股票建立關聯圖'
    return
  }
  symbols.value = parsed
  localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(parsed))
  errorMessage.value = ''
  reloadTimeline()
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.detail || payload?.message || 'API 請求失敗')
  }
  return payload?.data ?? payload
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.detail || payload?.message || 'API 請求失敗')
  }
  return payload?.data ?? payload
}

async function reloadTimeline() {
  if (symbols.value.length < 2) return
  loading.value = true
  errorMessage.value = ''
  try {
    const qs = new URLSearchParams({
      symbols: symbols.value.join(','),
      start: startDate.value,
      end: endDate.value,
      edge_threshold: String(threshold.value),
      lookback_days: String(lookbackDays.value),
    })
    const timeline = await apiGet(`/api/v1/graph/watchlist/timeline?${qs.toString()}`)
    let items = Array.isArray(timeline.items) ? timeline.items : []
    if (!items.length) {
      await apiPost('/api/v1/graph/watchlist/build', {
        symbols: symbols.value,
        target_date: endDate.value,
        lookback_days: lookbackDays.value,
      })
      const retry = await apiGet(`/api/v1/graph/watchlist/timeline?${qs.toString()}`)
      items = Array.isArray(retry.items) ? retry.items : []
    }
    // timeline 仍為空時，至少回補單日 snapshot，避免畫面全空白。
    if (!items.length) {
      const snapshotQs = new URLSearchParams({
        symbols: symbols.value.join(','),
        date: endDate.value,
        edge_threshold: String(threshold.value),
        lookback_days: String(lookbackDays.value),
      })
      const snapshot = await apiGet(`/api/v1/graph/watchlist/snapshot?${snapshotQs.toString()}`)
      if (snapshot && Array.isArray(snapshot.nodes) && snapshot.nodes.length) {
        items = [snapshot]
      }
    }
    timelineItems.value = items
    if (items.length) {
      currentIndex.value = Math.max(0, items.length - 1)
      await loadAlerts()
    } else {
      currentIndex.value = 0
      alerts.value = []
      errorMessage.value = '查無可顯示的圖資料，請調整日期區間或降低 Edge 門檻。'
    }
  } catch (error) {
    errorMessage.value = error?.message || '關聯圖載入失敗'
    timelineItems.value = []
    alerts.value = []
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  try {
    const qs = new URLSearchParams({
      symbols: symbols.value.join(','),
      edge_threshold: String(threshold.value),
    })
    const payload = await apiGet(`/api/v1/graph/watchlist/alerts?${qs.toString()}`)
    alerts.value = Array.isArray(payload.items) ? payload.items : []
  } catch {
    alerts.value = []
  }
}

function togglePlay() {
  if (!timelineDates.value.length) return
  if (isPlaying.value) {
    isPlaying.value = false
    if (playTimer) clearInterval(playTimer)
    playTimer = null
    return
  }
  isPlaying.value = true
  if (playTimer) clearInterval(playTimer)
  playTimer = setInterval(() => {
    if (currentIndex.value >= timelineDates.value.length - 1) {
      isPlaying.value = false
      clearInterval(playTimer)
      playTimer = null
      return
    }
    currentIndex.value += 1
  }, playIntervalMs.value)
}

function nodeColor(industry) {
  const text = String(industry || '')
  let hash = 0
  for (let i = 0; i < text.length; i += 1) hash = ((hash << 5) - hash) + text.charCodeAt(i)
  const palette = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#06b6d4', '#ef4444', '#a855f7']
  return palette[Math.abs(hash) % palette.length]
}

function fixed(value) {
  const numeric = Number(value || 0)
  return Number.isFinite(numeric) ? numeric.toFixed(2) : '0.00'
}

function percent(value) {
  const numeric = Number(value || 0)
  if (!Number.isFinite(numeric)) return '0.00%'
  return `${(numeric * 100).toFixed(2)}%`
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function offsetISO(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}
</script>

<style scoped>
.graph-page {
  display: grid;
  gap: var(--space-5);
}

.graph-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.graph-hero h1 {
  margin-bottom: 10px;
}

.hero-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-controls .control-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.field span {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.input {
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(11, 17, 33, 0.55);
  border-radius: 10px;
  min-height: 40px;
  padding: 0 12px;
  color: var(--text-primary);
}

.control-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

.btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-primary);
  cursor: pointer;
}

.btn-primary {
  border-color: rgba(59, 130, 246, 0.45);
  background: rgba(59, 130, 246, 0.2);
}

.slider-row {
  margin-top: 12px;
  display: grid;
  gap: 6px;
}

.playback-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.speed-select {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
}

.speed-select select {
  background: rgba(11, 17, 33, 0.55);
  color: var(--text-primary);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  min-height: 34px;
  padding: 0 10px;
}

.graph-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  gap: 16px;
}

.graph-canvas-wrap {
  position: relative;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(11, 17, 33, 0.52);
  overflow: hidden;
}

.graph-canvas {
  width: 100%;
  min-height: 560px;
  display: block;
}

.node-group {
  cursor: pointer;
}

.node-symbol {
  fill: #f8fafc;
  font-size: 12px;
  font-weight: 700;
  pointer-events: none;
}

.canvas-empty {
  position: absolute;
  inset: auto 14px 14px 14px;
  min-height: 42px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.78);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 10px 12px;
  font-size: 0.85rem;
}

.graph-side {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(11, 17, 33, 0.52);
  padding: 16px;
}

.graph-side h3 {
  margin: 0 0 10px;
}

.detail-card {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.6);
}

.detail-card p {
  margin: 6px 0;
}

.detail-card .symbol {
  font-weight: 700;
}

.alerts-title {
  margin-top: 14px !important;
}

.alerts-list {
  list-style: none;
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
}

.alerts-list li {
  display: grid;
  gap: 4px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.55);
  padding: 10px;
}

.error-text {
  color: var(--color-down);
  margin-top: 10px;
}

.muted {
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .graph-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .graph-controls .control-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .graph-controls .control-grid {
    grid-template-columns: 1fr;
  }

  .playback-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
