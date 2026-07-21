<template>
  <div class="rotation-page">
    <PageFocusBanner text="觀察資金在各類股之間的輪動方向，找出目前領漲與即將接棒的類股。" />

    <section class="section-block rotation-hero" v-reveal>
      <div>
        <h1>類股輪動觀察（Sector Rotation）</h1>
        <p>新增獨立輪動視覺：RRG 輪動時鐘觀察類股漲跌輪動，並用有向圖看接棒順序。</p>
      </div>
      <div class="hero-meta">
        <span class="badge">頻率 {{ freq === 'daily' ? '日頻' : '週頻' }}</span>
        <span class="badge">Universe {{ universe === 'twse' ? '官方類股' : '觀察池聚合' }}</span>
        <DataLineage :as-of="activeDate" source="cache" />
      </div>
    </section>

    <section class="section-block rotation-controls" v-reveal>
      <div class="control-grid">
        <label class="field">
          <span>Universe</span>
          <select v-model="universe" class="input select">
            <option value="twse">官方類股指數</option>
            <option value="watchlist">觀察池聚合</option>
          </select>
        </label>
        <label class="field">
          <span>頻率</span>
          <select v-model="freq" class="input select">
            <option value="daily">日頻</option>
            <option value="weekly">週頻</option>
          </select>
        </label>
        <label class="field" v-if="universe === 'watchlist'">
          <span>觀察池（逗號）</span>
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
          <input v-model.number="lookbackDays" class="input" type="number" min="60" max="1100" step="10" />
        </label>
        <label class="field">
          <span>尾巴長度</span>
          <input v-model.number="trailLength" class="input" type="number" min="2" max="24" step="1" />
        </label>
        <label class="field">
          <span>Lead 邊門檻</span>
          <input v-model.number="edgeThreshold" class="input" type="number" min="0" max="1" step="0.01" />
        </label>
      </div>

      <div class="control-actions">
        <button class="btn" v-if="universe === 'watchlist'" @click="applySymbols">套用觀察池</button>
        <button class="btn" :disabled="loading" @click="buildData">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>更新原始資料
        </button>
        <button class="btn btn-primary" :disabled="loading" @click="reloadTimeline">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>重算輪動
        </button>
      </div>

      <div class="sector-picker" v-if="universe === 'twse' && sectorOptions.length">
        <div class="sector-picker-head">
          <span>顯示類股（{{ visibleSectorCount }}/{{ sectorOptions.length }}）</span>
          <div class="sector-picker-actions">
            <button type="button" class="link-btn" @click="selectAllSectors">全選</button>
            <button type="button" class="link-btn" @click="clearAllSectors">全部隱藏</button>
          </div>
        </div>
        <div class="sector-chip-grid">
          <button
            v-for="opt in sectorOptions"
            :key="opt.id"
            type="button"
            class="sector-chip"
            :class="{ active: !hiddenSectors.has(opt.id) }"
            @click="toggleSector(opt.id)"
          >{{ opt.name }}</button>
        </div>
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

    <section class="card heatmap-section" v-reveal>
      <h2>🔥 每日類股漲跌熱力圖</h2>
      <div ref="heatmapEl" class="chart-host heatmap-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Treemap；方塊大小＝漲跌幅度、顏色＝漲跌方向。資料日期：{{ heatmapData?.date || '—' }}
      </p>
    </section>

    <section class="section-block ranking-strip" v-reveal>
      <h3>輪動棒次（領先 → 轉弱 → 落後 → 轉強）</h3>
      <div class="rank-list" v-if="rankingItems.length">
        <div
          v-for="item in rankingItems.slice(0, 12)"
          :key="item.id"
          class="rank-chip"
          :class="item.quadrant"
          @click="pickPoint(item.id)"
        >
          <span>{{ item.name }}</span>
          <strong>{{ quadrantLabel(item.quadrant) }}</strong>
        </div>
      </div>
      <p v-else class="muted">目前無輪動排行資料</p>
    </section>

    <div v-if="fullscreenTarget" class="fullscreen-backdrop" @click="exitFullscreen"></div>

    <section class="rotation-layout section-block" v-reveal>
      <div class="canvas-stack">
        <div v-if="loading" class="canvas-loading" role="status" aria-live="polite">
          <div class="loading-spinner canvas-spinner"></div>
          <span>{{ loadingLabel }}</span>
        </div>
        <div class="chart-card" :class="{ 'is-fullscreen': fullscreenTarget === 'rrg' }">
          <div class="chart-card-head">
            <h3>RRG 輪動時鐘</h3>
            <div class="chart-card-actions">
              <span class="muted small-hint" v-if="fullscreenTarget === 'rrg'">按 Esc 退出</span>
              <button v-if="points.length" class="icon-btn" type="button" @click="exportRotationCsv">📥 匯出 CSV</button>
              <button class="icon-btn" type="button" @click="toggleFullscreen('rrg')">
                {{ fullscreenTarget === 'rrg' ? '⤡ 退出全螢幕' : '⤢ 全螢幕' }}
              </button>
            </div>
          </div>
          <div ref="rrgHost" class="chart-host"></div>
          <div class="quadrant-legend">
            <span class="legend-item"><i class="dot leading"></i>領先</span>
            <span class="legend-item"><i class="dot weakening"></i>轉弱</span>
            <span class="legend-item"><i class="dot lagging"></i>落後</span>
            <span class="legend-item"><i class="dot improving"></i>轉強</span>
          </div>
        </div>
        <div class="chart-card" :class="{ 'is-fullscreen': fullscreenTarget === 'lead' }">
          <div class="chart-card-head">
            <h3>領先落後有向圖（類股接棒）</h3>
            <div class="chart-card-actions">
              <span class="muted small-hint" v-if="fullscreenTarget === 'lead'">按 Esc 退出</span>
              <button class="icon-btn" type="button" @click="toggleFullscreen('lead')">
                {{ fullscreenTarget === 'lead' ? '⤡ 退出全螢幕' : '⤢ 全螢幕' }}
              </button>
            </div>
          </div>
          <div ref="leadHost" class="chart-host lead-host"></div>
        </div>
      </div>

      <aside class="rotation-side">
        <template v-if="selectedEdge">
          <h3>接棒邊明細</h3>
          <div class="detail-card">
            <p class="symbol">{{ selectedEdge.src }} → {{ selectedEdge.dst }}</p>
            <p class="muted">{{ pointName(selectedEdge.src) }} → {{ pointName(selectedEdge.dst) }}</p>
            <div class="kv"><span>領先期數 lag</span><strong>{{ selectedEdge.lag }}</strong></div>
            <div class="kv"><span>相關係數</span><strong :class="signClass(selectedEdge.weight)">{{ fixed(selectedEdge.weight, 4) }}</strong></div>
            <div class="kv"><span>|weight|</span><strong>{{ fixed(selectedEdge.abs_weight, 4) }}</strong></div>
          </div>
        </template>
        <template v-else>
          <h3>類股明細</h3>
          <div v-if="selectedPoint" class="detail-card">
            <p class="symbol">{{ selectedPoint.name }}</p>
            <p class="muted">ID：{{ selectedPoint.id }}</p>
            <div class="kv"><span>象限</span><strong>{{ quadrantLabel(selectedPoint.quadrant) }}</strong></div>
            <div class="kv"><span>RS-Ratio <InfoTooltip v-bind="metricGlossary.rsRatio" /></span><strong>{{ fixed(selectedPoint.rs_ratio, 3) }}</strong></div>
            <div class="kv"><span>RS-Momentum <InfoTooltip v-bind="metricGlossary.rsMomentum" /></span><strong>{{ fixed(selectedPoint.rs_momentum, 3) }}</strong></div>
            <div class="kv"><span>角度</span><strong>{{ fixed(selectedPoint.angle, 2) }}°</strong></div>
            <p class="rs-narrative">{{ rsNarrative(selectedPoint) }}</p>
          </div>
          <div v-else class="detail-card muted">點選 RRG 節點或下方邊即可查看明細</div>
        </template>
      </aside>
    </section>

    <section class="card horizon-section" v-reveal>
      <div class="chart-card-head">
        <h3>類股 RS-Ratio 一覽（Horizon Chart）</h3>
      </div>
      <div ref="horizonHost" class="chart-host horizon-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Horizon chart；用顏色分層壓縮呈現，一次比較所有顯示中類股的相對強弱走勢（RS-Ratio，100＝與大盤同步）。
      </p>
    </section>

    <section class="card sankey-section" v-reveal>
      <div class="chart-card-head">
        <h3>類股資金流向（Sankey）</h3>
        <span class="badge-estimated">示意資料</span>
      </div>
      <div ref="sankeyHost" class="chart-host sankey-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Sankey diagram；依領先/落後方向性邊推估的示意性資金流向（雙向邊已淨額化、迴圈已斷開），粗細＝估算流量，用於觀察資金可能擴散的路徑而非精確金額。
      </p>
    </section>

    <section class="card chord-section" v-reveal>
      <div class="chart-card-head">
        <h3>類股關聯強度（Chord Diagram）</h3>
        <span class="muted small-hint">滑鼠移到弧上可聚焦該類股的連結</span>
      </div>
      <div ref="chordHost" class="chart-host chord-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Chord diagram；沿用領先/落後圖的方向性邊資料，弧段顏色＝來源類股，帶狀寬度＝領先強度（|相關係數|），可觀察資金／動能由哪些類股領先擴散到哪些類股。
      </p>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import DataLineage from '../components/DataLineage.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { sankey as d3Sankey, sankeyLinkHorizontal } from 'd3-sankey'
import { useChartTheme } from '../composables/useChartTheme'
import { loadWatchlist as loadSharedWatchlist } from '../lib/watchlist'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'

const theme = useChartTheme()
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
// Y1 修正：同 GraphView，本頁的聚合股票組合跟共用觀察清單分開存，避免
// 套用任意組合時覆蓋掉使用者真正的觀察清單
const ROTATION_SYMBOLS_STORAGE_KEY = 'finlab_rotation_symbols'

const loading = ref(false)
const loadingLabel = ref('運算中…')
const errorMessage = ref('')
const universe = ref('twse')
const freq = ref('daily')
const lookbackDays = ref(400)
const trailLength = ref(10)
const edgeThreshold = ref(0.25)
const startDate = ref(offsetISO(90))
const endDate = ref(todayISO())
const symbols = ref(loadWatchlist())
const symbolInput = ref(symbols.value.join(','))

const timelineItems = ref([])
const snapshot = ref(null)
const currentIndex = ref(0)
const selectedId = ref('')
const selectedEdgeKey = ref('')
const isPlaying = ref(false)
const playIntervalMs = ref(700)

const rrgHost = ref(null)
const leadHost = ref(null)
const horizonHost = ref(null)
const chordHost = ref(null)
const sankeyHost = ref(null)
const heatmapEl = ref(null)
const heatmapData = ref(null)

const fullscreenTarget = ref(null) // null | 'rrg' | 'lead'

// Official sector-index universe has 30+ sub-indices -- showing every one
// at once makes both the RRG clock and the lead-lag graph unreadable.
// knownSectors accumulates every {id,name} seen across loaded snapshots so
// the picker list stays stable while scrubbing the playback timeline;
// hiddenSectors holds the user's opt-outs (empty set = show everything).
const knownSectors = ref(new Map())
const hiddenSectors = ref(new Set())

let playTimer = null
let resizeObserver = null
let leadSimulation = null

const timelineDates = computed(() => timelineItems.value.map(item => item.date))
const activeDate = computed(() => timelineDates.value[currentIndex.value] || '')
const points = computed(() => snapshot.value?.points || [])

// Y5：RRG 輪動時鐘匯出，類股輪動頁原本完全沒有匯出功能
function exportRotationCsv() {
  const cols = ['名稱', '象限', 'RS-Ratio', 'RS-Momentum', '角度']
  const rows = points.value.map(p => [p.name, quadrantLabel(p.quadrant), fixed(p.rs_ratio, 3), fixed(p.rs_momentum, 3), fixed(p.angle, 2)])
  downloadCsv(timestampedFilename(`rotation-rrg-${activeDate.value || 'latest'}`), cols, rows)
}
const trails = computed(() => snapshot.value?.trails || {})
const leadEdges = computed(() => snapshot.value?.lead_edges || [])

const sectorOptions = computed(() => (
  Array.from(knownSectors.value.entries())
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'))
))
const visibleSectorCount = computed(() => (
  sectorOptions.value.filter(opt => !hiddenSectors.value.has(opt.id)).length
))

// Points/ranking actually rendered, after applying the sector picker
// (only meaningful for the 'twse' universe; watchlist has no picker).
const visiblePoints = computed(() => {
  const all = points.value
  if (universe.value !== 'twse' || hiddenSectors.value.size === 0) return all
  return all.filter(p => !hiddenSectors.value.has(p.id))
})
const rankingItems = computed(() => {
  const ranking = snapshot.value?.ranking || []
  if (universe.value !== 'twse' || hiddenSectors.value.size === 0) return ranking
  return ranking.filter(item => !hiddenSectors.value.has(item.id))
})

const selectedPoint = computed(() => points.value.find(p => p.id === selectedId.value) || null)
const selectedEdge = computed(() => leadEdges.value.find(e => edgeKey(e) === selectedEdgeKey.value) || null)

watch([universe, freq], () => {
  if (freq.value === 'weekly') {
    lookbackDays.value = Math.max(lookbackDays.value, 720)
  }
})

watch(universe, () => {
  // Switching universe invalidates the previous picker state (watchlist
  // symbols and official sector indices don't share ids).
  knownSectors.value.clear()
  hiddenSectors.value.clear()
})

watch(points, pts => {
  if (universe.value !== 'twse') return
  pts.forEach(p => {
    if (!knownSectors.value.has(p.id)) knownSectors.value.set(p.id, p.name)
  })
})

watch(hiddenSectors, () => {
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
    renderHorizon()
    renderChord()
    renderSankey()
  })
}, { deep: true })

watch(currentIndex, async () => {
  if (!timelineDates.value.length) return
  await loadSnapshot(timelineDates.value[currentIndex.value])
})

watch([snapshot], () => {
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
    renderChord()
    renderSankey()
  })
})

watch(timelineItems, () => nextTick(renderHorizon))
watch(heatmapData, () => nextTick(renderHeatmap))

let heatmapResizeHandler = null

onMounted(async () => {
  await reloadTimeline()
  loadHeatmap()
  if ('ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      renderRRG()
      renderLeadGraph()
      renderHorizon()
      renderChord()
      renderSankey()
    })
    if (rrgHost.value) resizeObserver.observe(rrgHost.value)
    if (leadHost.value) resizeObserver.observe(leadHost.value)
    if (horizonHost.value) resizeObserver.observe(horizonHost.value)
    if (chordHost.value) resizeObserver.observe(chordHost.value)
    if (sankeyHost.value) resizeObserver.observe(sankeyHost.value)
  }
  window.addEventListener('keydown', handleKeydown)
  heatmapResizeHandler = () => renderHeatmap()
  window.addEventListener('resize', heatmapResizeHandler)
})

onBeforeUnmount(() => {
  if (playTimer) clearInterval(playTimer)
  if (leadSimulation) leadSimulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
  window.removeEventListener('keydown', handleKeydown)
  if (heatmapResizeHandler) window.removeEventListener('resize', heatmapResizeHandler)
})

async function loadHeatmap() {
  try {
    const res = await fetch('/api/v1/rotation/heatmap?universe=twse')
    const json = await res.json()
    if (json.success) heatmapData.value = json.data
  } catch (e) {
    // 熱力圖失敗不影響頁面其他輪動圖表
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

function handleKeydown(event) {
  if (event.key === 'Escape' && fullscreenTarget.value) {
    exitFullscreen()
  }
}

function toggleFullscreen(target) {
  fullscreenTarget.value = fullscreenTarget.value === target ? null : target
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
  })
}

function exitFullscreen() {
  if (!fullscreenTarget.value) return
  fullscreenTarget.value = null
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
  })
}

function toggleSector(id) {
  if (hiddenSectors.value.has(id)) hiddenSectors.value.delete(id)
  else hiddenSectors.value.add(id)
}

function selectAllSectors() {
  hiddenSectors.value.clear()
}

function clearAllSectors() {
  sectorOptions.value.forEach(opt => hiddenSectors.value.add(opt.id))
}

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(ROTATION_SYMBOLS_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    const normalized = Array.isArray(parsed)
      ? parsed.map(item => String(item || '').trim()).filter(Boolean)
      : []
    if (normalized.length) return normalized
    const shared = loadSharedWatchlist()
    return shared.length ? shared : ['2330', '2317', '2454']
  } catch {
    return ['2330', '2317', '2454']
  }
}

function normalizeSymbols(raw) {
  const seen = new Set()
  return raw
    .split(',')
    .map(item => item.trim().toUpperCase())
    .filter(item => item && !seen.has(item) && seen.add(item))
}

function applySymbols() {
  const parsed = normalizeSymbols(symbolInput.value)
  if (parsed.length < 2) {
    errorMessage.value = '觀察池聚合至少需要 2 檔股票'
    return
  }
  symbols.value = parsed
  localStorage.setItem(ROTATION_SYMBOLS_STORAGE_KEY, JSON.stringify(parsed))
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

function buildCommonParams(dateValue) {
  const params = new URLSearchParams({
    universe: universe.value,
    freq: freq.value,
    lookback_days: String(lookbackDays.value),
    date: dateValue || endDate.value,
  })
  if (universe.value === 'watchlist') {
    params.set('symbols', symbols.value.join(','))
  }
  return params
}

async function buildData() {
  try {
    loading.value = true
    loadingLabel.value = '更新原始資料中…'
    errorMessage.value = ''
    await apiPost('/api/v1/rotation/build', {
      universe: universe.value,
      symbols: universe.value === 'watchlist' ? symbols.value : [],
      end: endDate.value,
      lookback_days: lookbackDays.value,
    })
    await reloadTimeline()
  } catch (error) {
    errorMessage.value = error?.message || '更新資料失敗'
  } finally {
    loading.value = false
  }
}

async function reloadTimeline() {
  try {
    loading.value = true
    loadingLabel.value = '重算輪動中…'
    errorMessage.value = ''
    const params = new URLSearchParams({
      universe: universe.value,
      freq: freq.value,
      start: startDate.value,
      end: endDate.value,
      lookback_days: String(lookbackDays.value),
    })
    if (universe.value === 'watchlist') {
      params.set('symbols', symbols.value.join(','))
    }
    let data = await apiGet(`/api/v1/rotation/timeline?${params.toString()}`)
    let items = Array.isArray(data.items) ? data.items : []
    if (!items.length) {
      await apiPost('/api/v1/rotation/build', {
        universe: universe.value,
        symbols: universe.value === 'watchlist' ? symbols.value : [],
        end: endDate.value,
        lookback_days: lookbackDays.value,
      })
      data = await apiGet(`/api/v1/rotation/timeline?${params.toString()}`)
      items = Array.isArray(data.items) ? data.items : []
    }
    timelineItems.value = items
    if (!items.length) {
      snapshot.value = null
      errorMessage.value = '查無輪動資料，請先更新資料或調整區間'
      return
    }
    currentIndex.value = Math.max(0, items.length - 1)
    await loadSnapshot(timelineDates.value[currentIndex.value])
  } catch (error) {
    timelineItems.value = []
    snapshot.value = null
    errorMessage.value = error?.message || '輪動資料載入失敗'
  } finally {
    loading.value = false
  }
}

async function loadSnapshot(dateValue) {
  try {
    const params = buildCommonParams(dateValue)
    params.set('trail_length', String(trailLength.value))
    params.set('edge_threshold', String(edgeThreshold.value))
    const data = await apiGet(`/api/v1/rotation/snapshot?${params.toString()}`)
    snapshot.value = data
    if (!selectedId.value && data?.points?.length) selectedId.value = data.points[0].id
    selectedEdgeKey.value = ''
  } catch (error) {
    snapshot.value = null
    errorMessage.value = error?.message || '快照載入失敗'
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

function renderHorizon() {
  const host = horizonHost.value
  if (!host) return
  host.innerHTML = ''
  const items = timelineItems.value
  if (!items.length) return

  // Build per-sector rs_ratio series across the loaded timeline.
  const seriesBySector = new Map()
  const namesBySector = new Map()
  items.forEach((snap) => {
    ;(snap.points || []).forEach((p) => {
      if (universe.value === 'twse' && hiddenSectors.value.has(p.id)) return
      if (!seriesBySector.has(p.id)) seriesBySector.set(p.id, [])
      seriesBySector.get(p.id).push({ date: snap.date, value: p.rs_ratio })
      namesBySector.set(p.id, p.name)
    })
  })
  const sectorIds = Array.from(seriesBySector.keys())
  if (!sectorIds.length) {
    host.innerHTML = '<p class="chart-empty">尚無資料可繪製。</p>'
    return
  }

  const rowHeight = 32
  const width = host.clientWidth || 900
  const margin = { top: 4, right: 4, bottom: 20, left: 90 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const height = rowHeight * sectorIds.length + margin.top + margin.bottom

  const dates = items.map((s) => s.date)
  const x = d3.scalePoint().domain(dates).range([0, innerW])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)

  // Sort rows by latest RS-Ratio (leading sectors on top).
  sectorIds.sort((a, b) => {
    const av = seriesBySector.get(a).at(-1)?.value ?? 100
    const bv = seriesBySector.get(b).at(-1)?.value ?? 100
    return bv - av
  })

  sectorIds.forEach((id, i) => {
    const series = seriesBySector.get(id)
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top + i * rowHeight})`)
    g.append('text')
      .attr('x', -6)
      .attr('y', rowHeight / 2 + 4)
      .attr('text-anchor', 'end')
      .attr('font-size', 10)
      .attr('fill', 'var(--text-muted)')
      .text(namesBySector.get(id) || id)

    const values = series.map((s) => s.value).filter((v) => v != null)
    const maxDev = d3.max(values, (v) => Math.abs(v - 100)) || 1
    const y = d3.scaleLinear().domain([0, maxDev]).range([0, rowHeight / 2 - 2])

    const area = d3
      .area()
      .x((d) => x(d.date))
      .y0(rowHeight / 2)
      .y1((d) => (d.value == null ? rowHeight / 2 : rowHeight / 2 - y(Math.abs(d.value - 100))))
      .defined((d) => d.value != null)

    g.append('line')
      .attr('x1', 0).attr('x2', innerW)
      .attr('y1', rowHeight / 2).attr('y2', rowHeight / 2)
      .attr('stroke', 'var(--border-color)')

    g.append('path')
      .datum(series)
      .attr('fill', (d) => 'var(--accent-green)')
      .attr('fill-opacity', 0.75)
      .attr('d', (d) => {
        const positiveOnly = d.map((pt) => ({ ...pt, value: pt.value != null && pt.value >= 100 ? pt.value : 100 }))
        return area(positiveOnly)
      })
    g.append('path')
      .datum(series)
      .attr('fill', 'var(--accent-red)')
      .attr('fill-opacity', 0.75)
      .attr('d', (d) => {
        const negativeOnly = d.map((pt) => ({ ...pt, value: pt.value != null && pt.value <= 100 ? pt.value : 100 }))
        return area(negativeOnly)
      })
  })

  svg
    .append('g')
    .attr('transform', `translate(${margin.left},${height - margin.bottom + 6})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(dates.filter((_, i) => i % Math.ceil(dates.length / 6 || 1) === 0))
    )
    .attr('class', 'axis')
}

function renderChord() {
  const host = chordHost.value
  if (!host) return
  host.innerHTML = ''

  // Reuse the same directed lead-lag edges as the force graph, honoring the
  // sector picker so the two views always describe the same visible set.
  const edges = leadEdges.value.filter((e) => {
    if (universe.value !== 'twse' || hiddenSectors.value.size === 0) return true
    return !hiddenSectors.value.has(e.src) && !hiddenSectors.value.has(e.dst)
  })
  if (!edges.length) {
    host.innerHTML = '<p class="chart-empty">尚無足夠的領先/落後關聯可繪製。</p>'
    return
  }

  const namesById = new Map(points.value.map((p) => [p.id, p.name]))
  const ids = Array.from(new Set(edges.flatMap((e) => [e.src, e.dst]))).sort((a, b) =>
    (namesById.get(a) || a).localeCompare(namesById.get(b) || b, 'zh-Hant')
  )
  const index = new Map(ids.map((id, i) => [id, i]))
  const n = ids.length
  const matrix = Array.from({ length: n }, () => new Array(n).fill(0))
  edges.forEach((e) => {
    const i = index.get(e.src)
    const j = index.get(e.dst)
    if (i == null || j == null || i === j) return
    matrix[i][j] += e.abs_weight
  })

  const width = Math.max(host.clientWidth || 700, 320)
  const height = Math.max(420, Math.min(640, width * 0.7))
  const outerRadius = Math.min(width, height) * 0.5 - 60
  const innerRadius = outerRadius - 20

  const color = d3.scaleOrdinal(d3.schemeTableau10 || d3.schemeCategory10).domain(ids)
  // padAngle widened from the original 0.04 and the arc band thickened
  // (14 -> 20px) per design density-pass: with 15-20+ sectors the ribbons
  // used to fuse into an unreadable ring at the old thinner/tighter settings.
  const chord = d3
    .chord()
    .padAngle(0.06)
    .sortSubgroups(d3.descending)(matrix)

  const arc = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius)
  const ribbon = d3.ribbon().radius(innerRadius)

  const svg = d3
    .select(host)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .append('g')
    .attr('transform', `translate(${width / 2},${height / 2})`)

  const ribbonSel = svg
    .append('g')
    .attr('fill-opacity', 0.75)
    .selectAll('path')
    .data(chord)
    .join('path')
    .attr('d', ribbon)
    .attr('fill', (d) => color(ids[d.source.index]))
    .attr('stroke', 'var(--bg-primary)')
    .style('cursor', 'pointer')
    .append('title')
    .text((d) => {
      const srcName = namesById.get(ids[d.source.index]) || ids[d.source.index]
      const dstName = namesById.get(ids[d.target.index]) || ids[d.target.index]
      return `${srcName} → ${dstName}：強度 ${matrix[d.source.index][d.target.index].toFixed(2)}`
    })
    .select(function () { return this.parentNode })

  const groupSel = svg
    .append('g')
    .selectAll('path')
    .data(chord.groups)
    .join('path')
    .attr('d', arc)
    .attr('fill', (d) => color(ids[d.index]))
    .attr('stroke', 'var(--bg-primary)')
    .style('cursor', 'pointer')
    .append('title')
    .text((d) => namesById.get(ids[d.index]) || ids[d.index])
    .select(function () { return this.parentNode })

  svg
    .append('g')
    .selectAll('text')
    .data(chord.groups)
    .join('text')
    .attr('transform', (d) => {
      const mid = (d.startAngle + d.endAngle) / 2
      const rot = (mid * 180) / Math.PI - 90
      const flip = mid > Math.PI ? 180 : 0
      return `rotate(${rot}) translate(${outerRadius + 8},0) rotate(${flip})`
    })
    .attr('text-anchor', (d) => ((d.startAngle + d.endAngle) / 2 > Math.PI ? 'end' : 'start'))
    .attr('font-size', 10)
    .attr('fill', 'var(--text-muted)')
    .text((d) => namesById.get(ids[d.index]) || ids[d.index])

  // Hover focus: dim every ribbon/group not touching the hovered sector so
  // dense charts (15-20+ sectors) stay legible instead of a solid ring.
  function focusGroup(groupIndex) {
    ribbonSel.attr('fill-opacity', (d) =>
      d.source.index === groupIndex || d.target.index === groupIndex ? 0.85 : 0.06
    )
    groupSel.attr('opacity', (d) => (d.index === groupIndex ? 1 : 0.35))
  }
  function clearFocus() {
    ribbonSel.attr('fill-opacity', 0.75)
    groupSel.attr('opacity', 1)
  }
  groupSel.on('mouseenter', (event, d) => focusGroup(d.index)).on('mouseleave', clearFocus)
  ribbonSel
    .on('mouseenter', (event, d) => focusGroup(d.source.index))
    .on('mouseleave', clearFocus)
}

function renderSankey() {
  const host = sankeyHost.value
  if (!host) return
  host.innerHTML = ''

  // Same directed lead-lag edges as the Chord diagram above -- this is a
  // second layout of the identical data, not a separate data source.
  const edges = leadEdges.value.filter((e) => {
    if (universe.value !== 'twse' || hiddenSectors.value.size === 0) return true
    return !hiddenSectors.value.has(e.src) && !hiddenSectors.value.has(e.dst)
  })
  const namesById = new Map(points.value.map((p) => [p.id, p.name]))
  const ids = Array.from(new Set(edges.flatMap((e) => [e.src, e.dst]))).sort((a, b) =>
    (namesById.get(a) || a).localeCompare(namesById.get(b) || b, 'zh-Hant')
  )
  const index = new Map(ids.map((id, i) => [id, i]))

  // d3-sankey 只吃 DAG，遇到循環邊會直接 throw「circular link」——而
  // lead-lag 資料裡 A→B 與 B→A 互指非常常見，之前整張圖因此無聲空白。
  // 先把同向重複邊加總、雙向邊淨額化（保留強的方向、值取差額），
  // 再以權重由大到小貪婪保留不成環的邊，斷開更長的迴圈。
  const agg = new Map()
  edges.forEach((e) => {
    const s = index.get(e.src)
    const t = index.get(e.dst)
    if (s == null || t == null || s === t) return
    const key = `${s}->${t}`
    agg.set(key, { source: s, target: t, value: (agg.get(key)?.value || 0) + Math.max(e.abs_weight, 0.001) })
  })
  const netted = []
  const seenPair = new Set()
  agg.forEach((l) => {
    const pairKey = l.source < l.target ? `${l.source}|${l.target}` : `${l.target}|${l.source}`
    if (seenPair.has(pairKey)) return
    seenPair.add(pairKey)
    const rev = agg.get(`${l.target}->${l.source}`)
    if (!rev) {
      netted.push(l)
    } else if (l.value !== rev.value) {
      const [win, lose] = l.value > rev.value ? [l, rev] : [rev, l]
      netted.push({ source: win.source, target: win.target, value: win.value - lose.value })
    }
    // 兩方向剛好抵銷時整組略過
  })
  const adj = new Map()
  const reaches = (from, to) => {
    const stack = [from]
    const visited = new Set()
    while (stack.length) {
      const cur = stack.pop()
      if (cur === to) return true
      if (visited.has(cur)) continue
      visited.add(cur)
      for (const next of adj.get(cur) || []) stack.push(next)
    }
    return false
  }
  const links = []
  netted.sort((a, b) => b.value - a.value).forEach((l) => {
    if (reaches(l.target, l.source)) return // 加入會成環，捨棄弱邊
    links.push(l)
    if (!adj.has(l.source)) adj.set(l.source, [])
    adj.get(l.source).push(l.target)
  })

  if (!ids.length || !links.length) {
    host.innerHTML = '<p class="chart-empty">尚無足夠的領先/落後關聯可繪製。</p>'
    return
  }

  // 淨額化/斷環後可能留下沒有任何邊的節點，d3-sankey 會給它們 NaN 高度，
  // 只保留有邊的節點並重排索引。
  const usedIdx = new Set(links.flatMap((l) => [l.source, l.target]))
  const usedIds = ids.filter((_, i) => usedIdx.has(i))
  const remap = new Map(usedIds.map((id, i) => [index.get(id), i]))
  const finalLinks = links.map((l) => ({ source: remap.get(l.source), target: remap.get(l.target), value: l.value }))

  const width = Math.max(host.clientWidth || 700, 320)
  const height = Math.max(360, Math.min(560, width * 0.55))
  const color = d3.scaleOrdinal(d3.schemeTableau10 || d3.schemeCategory10).domain(ids)

  const gen = d3Sankey()
    .nodeWidth(14)
    .nodePadding(12)
    .extent([[1, 8], [width - 1, height - 8]])
  let graph
  try {
    graph = gen({
      nodes: usedIds.map((id) => ({ id, name: namesById.get(id) || id })),
      links: finalLinks,
    })
  } catch (err) {
    host.innerHTML = '<p class="chart-empty">目前的關聯結構無法以 Sankey 呈現（含循環），請改看上方 Chord 圖。</p>'
    return
  }

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)

  const linkSel = svg
    .append('g')
    .attr('fill', 'none')
    .selectAll('path')
    .data(graph.links)
    .join('path')
    .attr('d', sankeyLinkHorizontal())
    .attr('stroke', (d) => color(d.source.id))
    .attr('stroke-opacity', 0.45)
    .attr('stroke-width', (d) => Math.max(1, d.width))
    .style('cursor', 'pointer')
    .append('title')
    .text((d) => `${d.source.name} → ${d.target.name}：強度 ${d.value.toFixed(2)}`)
    .select(function () { return this.parentNode })

  const nodeGroup = svg
    .append('g')
    .selectAll('g')
    .data(graph.nodes)
    .join('g')

  nodeGroup
    .append('rect')
    .attr('x', (d) => d.x0)
    .attr('y', (d) => d.y0)
    .attr('width', (d) => d.x1 - d.x0)
    .attr('height', (d) => Math.max(1, d.y1 - d.y0))
    .attr('fill', (d) => color(d.id))
    .style('cursor', 'pointer')
    .append('title')
    .text((d) => d.name)

  nodeGroup
    .append('text')
    .attr('x', (d) => (d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6))
    .attr('y', (d) => (d.y0 + d.y1) / 2)
    .attr('dy', '0.32em')
    .attr('text-anchor', (d) => (d.x0 < width / 2 ? 'start' : 'end'))
    .attr('font-size', 10)
    .attr('fill', theme.textSoft)
    .text((d) => d.name)

  // Hover focus, mirroring the Chord diagram's interaction so the two
  // views feel like the same instrument viewed two ways.
  function focusNode(nodeId) {
    linkSel.attr('stroke-opacity', (d) => (d.source.id === nodeId || d.target.id === nodeId ? 0.75 : 0.05))
  }
  function clearFocus() {
    linkSel.attr('stroke-opacity', 0.45)
  }
  nodeGroup.on('mouseenter', (event, d) => focusNode(d.id)).on('mouseleave', clearFocus)
  linkSel.on('mouseenter', (event, d) => focusNode(d.source.id)).on('mouseleave', clearFocus)
}

function renderRRG() {
  const host = rrgHost.value
  if (!host) return
  d3.select(host).selectAll('*').remove()
  const data = visiblePoints.value
  if (!data.length) return

  const width = host.clientWidth || 920
  const height = host.clientHeight || 360
  const margin = { top: 20, right: 24, bottom: 30, left: 34 }
  const xMin = Math.min(95, d3.min(data, d => d.rs_ratio) - 2)
  const xMax = Math.max(105, d3.max(data, d => d.rs_ratio) + 2)
  const yMin = Math.min(95, d3.min(data, d => d.rs_momentum) - 2)
  const yMax = Math.max(105, d3.max(data, d => d.rs_momentum) + 2)

  const x = d3.scaleLinear().domain([xMin, xMax]).range([margin.left, width - margin.right])
  const y = d3.scaleLinear().domain([yMin, yMax]).range([height - margin.bottom, margin.top])

  const svg = d3.select(host).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .style('width', '100%')
    .style('height', '100%')
    .on('click', () => {
      selectedId.value = ''
      selectedEdgeKey.value = ''
    })

  const quad = svg.append('g')
  quad.append('rect').attr('x', x(100)).attr('y', y(yMax)).attr('width', x(xMax) - x(100)).attr('height', y(100) - y(yMax)).attr('fill', theme.upSoft)
  quad.append('rect').attr('x', x(100)).attr('y', y(100)).attr('width', x(xMax) - x(100)).attr('height', y(yMin) - y(100)).attr('fill', 'rgba(245,158,11,.07)')
  quad.append('rect').attr('x', x(xMin)).attr('y', y(100)).attr('width', x(100) - x(xMin)).attr('height', y(yMin) - y(100)).attr('fill', theme.downSoft)
  quad.append('rect').attr('x', x(xMin)).attr('y', y(yMax)).attr('width', x(100) - x(xMin)).attr('height', y(100) - y(yMax)).attr('fill', 'rgba(59,130,246,.07)')
  quad.append('line').attr('x1', x(100)).attr('x2', x(100)).attr('y1', y(yMin)).attr('y2', y(yMax)).attr('stroke', theme.border)
  quad.append('line').attr('x1', x(xMin)).attr('x2', x(xMax)).attr('y1', y(100)).attr('y2', y(100)).attr('stroke', theme.border)

  svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x).ticks(6))
  svg.append('g').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(6))

  const label = svg.append('g').attr('class', 'quadrant-labels')
  label.append('text').attr('x', x(101)).attr('y', y(101) - 8).text('領先').attr('fill', theme.up).attr('font-size', 12)
  label.append('text').attr('x', x(101)).attr('y', y(99) + 14).text('轉弱').attr('fill', theme.warn).attr('font-size', 12)
  label.append('text').attr('x', x(99) - 36).attr('y', y(99) + 14).text('落後').attr('fill', theme.down).attr('font-size', 12)
  label.append('text').attr('x', x(99) - 36).attr('y', y(101) - 8).text('轉強').attr('fill', theme.blue).attr('font-size', 12)

  const pointMap = new Map(data.map(d => [d.id, d]))
  const trailLine = d3.line().x(d => x(d.x)).y(d => y(d.y)).curve(d3.curveMonotoneX)
  const trailGroup = svg.append('g').attr('fill', 'none')
  Object.entries(trails.value).forEach(([id, arr]) => {
    const s = pointMap.get(id)
    if (!s || !Array.isArray(arr) || !arr.length) return
    trailGroup.append('path')
      .attr('d', trailLine(arr))
      .attr('stroke', quadrantColor(s.quadrant))
      .attr('stroke-width', selectedId.value === id ? 2.5 : 1.4)
      .attr('stroke-opacity', selectedId.value && selectedId.value !== id ? 0.2 : 0.6)
  })

  const nodeGroup = svg.append('g')
  const nodes = nodeGroup.selectAll('g')
    .data(data)
    .join('g')
    .attr('transform', d => `translate(${x(d.rs_ratio)},${y(d.rs_momentum)})`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      selectedEdgeKey.value = ''
      selectedId.value = d.id
    })

  nodes.append('circle')
    .attr('r', d => selectedId.value === d.id ? 9 : 7)
    .attr('fill', d => quadrantColor(d.quadrant))
    .attr('stroke', d => selectedId.value === d.id ? theme.text : theme.textSoft)
    .attr('stroke-width', d => selectedId.value === d.id ? 2.6 : 1.1)
    .attr('opacity', d => {
      if (selectedEdge.value) return (d.id === selectedEdge.value.src || d.id === selectedEdge.value.dst) ? 1 : 0.2
      if (selectedId.value && selectedId.value !== d.id) return 0.35
      return 1
    })

  nodes.append('title').text(d => (
    `${d.name}\n象限：${quadrantLabel(d.quadrant)}\nRS-Ratio：${fixed(d.rs_ratio, 3)}\nRS-Momentum：${fixed(d.rs_momentum, 3)}`
  ))

  // Sector clusters (e.g. many "lagging" indices with near-identical
  // RS-Ratio/RS-Momentum) used to render with every label pinned exactly
  // 11px above its own point, so labels piled on top of each other and
  // became unreadable. Run a tiny force simulation to nudge overlapping
  // labels apart, with a thin leader line back to the actual point
  // whenever a label had to move more than a few pixels.
  const labelData = layoutLabels(data, x, y, margin, width, height)
  const leaderGroup = svg.append('g').attr('stroke', theme.border).attr('stroke-width', 1)
  const labelGroup = svg.append('g').attr('class', 'point-labels')

  labelData.forEach(l => {
    if (Math.hypot(l.x - l.pointX, l.y - l.pointY) > 13) {
      leaderGroup.append('line')
        .attr('x1', l.pointX).attr('y1', l.pointY)
        .attr('x2', l.x).attr('y2', l.y + 3)
    }
  })

  labelGroup.selectAll('text')
    .data(labelData)
    .join('text')
    .attr('x', d => d.x)
    .attr('y', d => d.y)
    .attr('text-anchor', 'middle')
    .attr('fill', theme.text)
    .attr('font-size', 10)
    .style('pointer-events', 'none')
    .attr('opacity', d => {
      const point = pointMap.get(d.id)
      if (!point) return 1
      if (selectedEdge.value) return (point.id === selectedEdge.value.src || point.id === selectedEdge.value.dst) ? 1 : 0.25
      if (selectedId.value && selectedId.value !== point.id) return 0.4
      return 1
    })
    .text(d => d.label)

  svg.append('text').attr('x', width - 90).attr('y', height - 8).attr('fill', theme.muted).attr('font-size', 11).text('RS-Ratio')
  svg.append('text').attr('x', 8).attr('y', 12).attr('fill', theme.muted).attr('font-size', 11).text('RS-Momentum')
}

// Rough CJK-friendly width estimate for a label at font-size 10 -- good
// enough for collision radii, doesn't need to be pixel-perfect.
function estimateLabelWidth(label) {
  return label.length * 11 + 6
}

// Declutter overlapping point labels: start each label anchored just
// above its point (same position the old fixed-offset text used), then
// let a short-lived force simulation push apart any that collide while a
// weak spring pulls them back toward their anchor so uncluttered labels
// barely move at all.
function layoutLabels(data, x, y, margin, width, height) {
  const nodes = data.map(d => {
    const pointX = x(d.rs_ratio)
    const pointY = y(d.rs_momentum)
    const label = d.name.replace('類指數', '')
    return {
      id: d.id,
      label,
      pointX,
      pointY,
      x: pointX,
      y: pointY - 11,
      width: estimateLabelWidth(label),
    }
  })

  const sim = d3.forceSimulation(nodes)
    .force('x', d3.forceX(n => n.pointX).strength(0.4))
    .force('y', d3.forceY(n => n.pointY - 11).strength(0.5))
    .force('collide', d3.forceCollide(n => n.width / 2 + 1.5).strength(1))
    .stop()
  for (let i = 0; i < 180; i += 1) sim.tick()

  const minY = margin.top + 8
  const maxY = height - margin.bottom - 4
  const minX = margin.left
  const maxX = width - margin.right
  nodes.forEach(n => {
    n.x = Math.min(maxX, Math.max(minX, n.x))
    n.y = Math.min(maxY, Math.max(minY, n.y))
  })
  return nodes
}

function renderLeadGraph() {
  const host = leadHost.value
  if (!host) return
  d3.select(host).selectAll('*').remove()
  if (leadSimulation) {
    leadSimulation.stop()
    leadSimulation = null
  }
  if (!visiblePoints.value.length) return

  const width = host.clientWidth || 920
  const height = host.clientHeight || 300
  const nodes = visiblePoints.value.map(p => ({ ...p, id: p.id }))
  const links = leadEdges.value.map(e => ({ ...e, source: e.src, target: e.dst }))
  const idSet = new Set(nodes.map(n => n.id))
  const validLinks = links.filter(l => idSet.has(l.source) && idSet.has(l.target))

  const svg = d3.select(host).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .style('width', '100%')
    .style('height', '100%')
    .on('click', () => {
      selectedEdgeKey.value = ''
      if (!selectedId.value && nodes.length) selectedId.value = nodes[0].id
    })

  // Arrowheads used to be sized in "strokeWidth" units (the SVG marker
  // default), so a thick high-|weight| edge (stroke-width up to 5) blew the
  // arrowhead up to 5x its intended size. userSpaceOnUse decouples the
  // marker from the line's stroke width, and updateArrowScale() then keeps
  // its on-screen size roughly constant as the user zooms the graph.
  const ARROW_BASE = 14
  const ARROW_REFX = 17
  const defs = svg.append('defs')
  const arrowMarkers = [
    { id: 'lead-arrow-pos', color: theme.blue },
    { id: 'lead-arrow-neg', color: theme.negative },
  ].map(spec => {
    const marker = defs.append('marker')
      .attr('id', spec.id)
      .attr('viewBox', '0 -5 10 10')
      .attr('refY', 0)
      .attr('markerUnits', 'userSpaceOnUse')
      .attr('orient', 'auto')
    marker.append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', spec.color)
    return marker
  })

  function updateArrowScale(k = 1) {
    const zoomFactor = Math.max(0.5, Math.min(1.8, 1 / k))
    const sizeFactor = Math.max(0.75, Math.min(1.25, width / 760))
    const scale = zoomFactor * sizeFactor
    arrowMarkers.forEach(marker => {
      marker
        .attr('markerWidth', ARROW_BASE * scale)
        .attr('markerHeight', ARROW_BASE * scale)
        .attr('refX', ARROW_REFX * scale)
    })
  }
  updateArrowScale(1)

  const root = svg.append('g')
  svg.call(d3.zoom().scaleExtent([0.4, 3]).on('zoom', event => {
    root.attr('transform', event.transform)
    updateArrowScale(event.transform.k)
  }))

  const maxW = d3.max(validLinks, d => Number(d.abs_weight) || 0) || 1
  const wScale = d3.scaleLinear().domain([0, maxW]).range([1, 5])

  const linkSel = root.append('g')
    .attr('fill', 'none')
    .selectAll('line')
    .data(validLinks)
    .join('line')
    .attr('stroke', d => Number(d.weight) >= 0 ? theme.blue : theme.negative)
    .attr('stroke-width', d => wScale(Number(d.abs_weight) || 0))
    .attr('stroke-opacity', d => selectedEdgeKey.value ? (edgeKey(d) === selectedEdgeKey.value ? 0.95 : 0.1) : 0.62)
    .attr('marker-end', d => Number(d.weight) >= 0 ? 'url(#lead-arrow-pos)' : 'url(#lead-arrow-neg)')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      selectedId.value = ''
      selectedEdgeKey.value = edgeKey(d)
    })

  const nodeSel = root.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      selectedEdgeKey.value = ''
      selectedId.value = d.id
    })
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) leadSimulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) leadSimulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      }))

  nodeSel.append('circle')
    .attr('r', d => selectedId.value === d.id ? 12 : 10)
    .attr('fill', d => quadrantColor(d.quadrant))
    .attr('stroke', d => selectedId.value === d.id ? theme.text : theme.textSoft)
    .attr('stroke-width', d => selectedId.value === d.id ? 2.4 : 1.2)
    .attr('opacity', d => {
      if (selectedEdge.value) return (d.id === selectedEdge.value.src || d.id === selectedEdge.value.dst) ? 1 : 0.25
      if (selectedId.value && selectedId.value !== d.id) return 0.35
      return 1
    })

  nodeSel.append('title').text(d => `${d.name}（${quadrantLabel(d.quadrant)}）`)

  nodeSel.append('text')
    .text(d => d.name.replace('類指數', ''))
    .attr('dy', -14)
    .attr('text-anchor', 'middle')
    .attr('fill', theme.text)
    .attr('font-size', 10)
    .style('pointer-events', 'none')

  leadSimulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(validLinks).id(d => d.id).distance(90).strength(0.25))
    .force('charge', d3.forceManyBody().strength(-220))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(24))
    .on('tick', () => {
      linkSel
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`)
    })
}

function pickPoint(id) {
  selectedEdgeKey.value = ''
  selectedId.value = id
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
  })
}

function edgeKey(edge) {
  return `${edge.src}->${edge.dst}`
}

function pointName(id) {
  return points.value.find(p => p.id === id)?.name || id
}

function quadrantColor(quad) {
  if (quad === 'leading') return theme.up
  if (quad === 'weakening') return theme.warn
  if (quad === 'lagging') return theme.down
  return theme.blue
}

function quadrantLabel(quad) {
  if (quad === 'leading') return '領先'
  if (quad === 'weakening') return '轉弱'
  if (quad === 'lagging') return '落後'
  return '轉強'
}

function rsNarrative(point) {
  const ratio = fixed(point.rs_ratio, 1)
  const momentum = fixed(point.rs_momentum, 1)
  const ratioDesc = point.rs_ratio >= 100 ? '相對大盤走勢較強' : '相對大盤走勢較弱'
  const momentumDesc = point.rs_momentum >= 100 ? '動能持續加速' : '動能持續減速'
  return `RS-Ratio ${ratio}（${ratioDesc}）、RS-Momentum ${momentum}（${momentumDesc}），目前處於${quadrantLabel(point.quadrant)}象限。`
}

function signClass(value) {
  const n = Number(value || 0)
  if (n > 0) return 'pos'
  if (n < 0) return 'neg'
  return ''
}

function fixed(value, digits = 2) {
  const numeric = Number(value || 0)
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : (0).toFixed(digits)
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
.rotation-page {
  display: grid;
  gap: var(--space-5);
}

.rotation-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.hero-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.control-grid {
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

.select {
  padding-right: 26px;
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

.ranking-strip h3 {
  margin: 0 0 10px;
}

.rank-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rank-chip {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  padding: 8px 10px;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
  min-width: 126px;
}

.rank-chip.leading {
  border-color: rgba(34, 197, 94, 0.5);
}
.rank-chip.weakening {
  border-color: rgba(245, 158, 11, 0.5);
}
.rank-chip.lagging {
  border-color: rgba(239, 68, 68, 0.5);
}
.rank-chip.improving {
  border-color: rgba(59, 130, 246, 0.5);
}

/* 設計稿：RRG 與領先落後圖並排各半，明細卡移到下方整列 */
.rotation-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.canvas-stack {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  position: relative;
}

.canvas-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(10, 15, 26, 0.62);
  color: var(--text-muted);
  font-size: 0.9rem;
  border-radius: 18px;
  z-index: 5;
}

.canvas-spinner {
  width: 40px;
  height: 40px;
  border-width: 3px;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border-width: 2px;
  vertical-align: -2px;
  margin-right: 6px;
}

@media (max-width: 1024px) {
  .canvas-stack {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(11, 17, 33, 0.52);
  padding: 10px;
}

.chart-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 4px 0 8px;
}

.chart-card-head h3 {
  margin: 0;
  font-size: 1rem;
}

.chart-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.small-hint {
  font-size: 0.72rem;
}

.icon-btn {
  min-height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.78rem;
  white-space: nowrap;
}

.icon-btn:hover {
  background: rgba(148, 163, 184, 0.2);
}

.fullscreen-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 15, 0.72);
  z-index: 90;
}

.chart-card.is-fullscreen {
  position: fixed;
  top: 24px;
  left: 24px;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.chart-card.is-fullscreen .chart-host {
  flex: 1;
  height: auto;
  min-height: 0;
}

.chart-host {
  height: 360px;
}

.heatmap-section {
  display: flex;
  flex-direction: column;
}

.heatmap-host {
  height: auto;
  min-height: 280px;
}

.heatmap-host :deep(svg) {
  display: block;
  width: 100%;
  height: auto;
}

.horizon-section {
  display: flex;
  flex-direction: column;
}

.horizon-host {
  height: auto;
  min-height: 120px;
  overflow-x: auto;
}

.horizon-host :deep(.axis text) {
  fill: var(--text-muted);
  font-size: 0.68rem;
}

.horizon-host :deep(.axis path),
.horizon-host :deep(.axis line) {
  stroke: var(--border-color);
}

.chord-section {
  display: flex;
  flex-direction: column;
}

.chord-host {
  height: auto;
  min-height: 320px;
  display: flex;
  justify-content: center;
}

.sankey-section {
  display: flex;
  flex-direction: column;
}

.sankey-host {
  height: auto;
  min-height: 320px;
}

.chart-caption {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 6px;
}

.chart-empty {
  color: var(--text-muted);
  font-style: italic;
  font-size: 0.85rem;
}

.lead-host {
  height: 300px;
}

.quadrant-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-item .dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  display: inline-block;
}

.dot.leading {
  background: #22c55e;
}
.dot.weakening {
  background: #f59e0b;
}
.dot.lagging {
  background: #ef4444;
}
.dot.improving {
  background: #3b82f6;
}

.sector-picker {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.sector-picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.sector-picker-actions {
  display: flex;
  gap: 10px;
}

.link-btn {
  background: none;
  border: none;
  color: #60a5fa;
  cursor: pointer;
  font-size: 0.78rem;
  padding: 0;
}

.link-btn:hover {
  text-decoration: underline;
}

.sector-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sector-chip {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-muted);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.76rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.sector-chip.active {
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(59, 130, 246, 0.18);
  color: var(--text-primary);
}

.rotation-side {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(11, 17, 33, 0.52);
  padding: 16px;
}

.rotation-side h3 {
  margin: 0 0 10px;
}

.detail-card {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.6);
}

.detail-card .symbol {
  margin: 0 0 4px;
  font-weight: 700;
}

.detail-card .muted {
  margin: 0 0 8px;
}

.rs-narrative {
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--text-secondary, #cbd5e1);
}

.kv {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  padding: 5px 0;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  font-size: 0.88rem;
}

.kv span {
  color: var(--text-muted);
}

.pos {
  color: #60a5fa;
}

.neg {
  color: #f87171;
}

.error-text {
  color: var(--color-down);
  margin-top: 10px;
}

.muted {
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .rotation-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .control-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .control-grid {
    grid-template-columns: 1fr;
  }
  .playback-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .chart-host {
    height: 320px;
  }
  .chart-card.is-fullscreen {
    top: 10px;
    left: 10px;
    right: 10px;
    bottom: 10px;
  }
}
</style>
