<template>
  <div class="rotation-page">
    <section class="section-block rotation-hero" v-reveal>
      <div>
        <h1>類股輪動觀察（Sector Rotation）</h1>
        <p>新增獨立輪動視覺：RRG 輪動時鐘觀察類股漲跌輪動，並用有向圖看接棒順序。</p>
      </div>
      <div class="hero-meta">
        <span class="badge">頻率 {{ freq === 'daily' ? '日頻' : '週頻' }}</span>
        <span class="badge">Universe {{ universe === 'twse' ? '官方類股' : '觀察池聚合' }}</span>
        <span class="badge">日期 {{ activeDate || '—' }}</span>
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
        <button class="btn" :disabled="loading" @click="buildData">更新原始資料</button>
        <button class="btn btn-primary" :disabled="loading" @click="reloadTimeline">重算輪動</button>
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

    <section class="rotation-layout section-block" v-reveal>
      <div class="canvas-stack">
        <div class="chart-card">
          <h3>RRG 輪動時鐘</h3>
          <div ref="rrgHost" class="chart-host"></div>
        </div>
        <div class="chart-card">
          <h3>領先落後有向圖（類股接棒）</h3>
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
            <div class="kv"><span>RS-Ratio</span><strong>{{ fixed(selectedPoint.rs_ratio, 3) }}</strong></div>
            <div class="kv"><span>RS-Momentum</span><strong>{{ fixed(selectedPoint.rs_momentum, 3) }}</strong></div>
            <div class="kv"><span>角度</span><strong>{{ fixed(selectedPoint.angle, 2) }}°</strong></div>
          </div>
          <div v-else class="detail-card muted">點選 RRG 節點或下方邊即可查看明細</div>
        </template>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const WATCHLIST_STORAGE_KEY = 'finlab_watchlist'

const loading = ref(false)
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

let playTimer = null
let resizeObserver = null
let leadSimulation = null

const timelineDates = computed(() => timelineItems.value.map(item => item.date))
const activeDate = computed(() => timelineDates.value[currentIndex.value] || '')
const points = computed(() => snapshot.value?.points || [])
const trails = computed(() => snapshot.value?.trails || {})
const leadEdges = computed(() => snapshot.value?.lead_edges || [])
const rankingItems = computed(() => snapshot.value?.ranking || [])

const selectedPoint = computed(() => points.value.find(p => p.id === selectedId.value) || null)
const selectedEdge = computed(() => leadEdges.value.find(e => edgeKey(e) === selectedEdgeKey.value) || null)

watch([universe, freq], () => {
  if (freq.value === 'weekly') {
    lookbackDays.value = Math.max(lookbackDays.value, 720)
  }
})

watch(currentIndex, async () => {
  if (!timelineDates.value.length) return
  await loadSnapshot(timelineDates.value[currentIndex.value])
})

watch([snapshot], () => {
  nextTick(() => {
    renderRRG()
    renderLeadGraph()
  })
})

onMounted(async () => {
  await reloadTimeline()
  if ('ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      renderRRG()
      renderLeadGraph()
    })
    if (rrgHost.value) resizeObserver.observe(rrgHost.value)
    if (leadHost.value) resizeObserver.observe(leadHost.value)
  }
})

onBeforeUnmount(() => {
  if (playTimer) clearInterval(playTimer)
  if (leadSimulation) leadSimulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
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
    .filter(item => item && !seen.has(item) && seen.add(item))
}

function applySymbols() {
  const parsed = normalizeSymbols(symbolInput.value)
  if (parsed.length < 2) {
    errorMessage.value = '觀察池聚合至少需要 2 檔股票'
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

function renderRRG() {
  const host = rrgHost.value
  if (!host) return
  d3.select(host).selectAll('*').remove()
  const data = points.value
  if (!data.length) return

  const width = host.clientWidth || 920
  const height = 360
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
  quad.append('rect').attr('x', x(100)).attr('y', y(yMax)).attr('width', x(xMax) - x(100)).attr('height', y(100) - y(yMax)).attr('fill', 'rgba(34,197,94,.07)')
  quad.append('rect').attr('x', x(100)).attr('y', y(100)).attr('width', x(xMax) - x(100)).attr('height', y(yMin) - y(100)).attr('fill', 'rgba(245,158,11,.07)')
  quad.append('rect').attr('x', x(xMin)).attr('y', y(100)).attr('width', x(100) - x(xMin)).attr('height', y(yMin) - y(100)).attr('fill', 'rgba(239,68,68,.08)')
  quad.append('rect').attr('x', x(xMin)).attr('y', y(yMax)).attr('width', x(100) - x(xMin)).attr('height', y(100) - y(yMax)).attr('fill', 'rgba(59,130,246,.07)')
  quad.append('line').attr('x1', x(100)).attr('x2', x(100)).attr('y1', y(yMin)).attr('y2', y(yMax)).attr('stroke', 'rgba(148,163,184,.45)')
  quad.append('line').attr('x1', x(xMin)).attr('x2', x(xMax)).attr('y1', y(100)).attr('y2', y(100)).attr('stroke', 'rgba(148,163,184,.45)')

  svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x).ticks(6))
  svg.append('g').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(6))

  const label = svg.append('g').attr('class', 'quadrant-labels')
  label.append('text').attr('x', x(101)).attr('y', y(101) - 8).text('領先').attr('fill', '#22c55e').attr('font-size', 12)
  label.append('text').attr('x', x(101)).attr('y', y(99) + 14).text('轉弱').attr('fill', '#f59e0b').attr('font-size', 12)
  label.append('text').attr('x', x(99) - 36).attr('y', y(99) + 14).text('落後').attr('fill', '#ef4444').attr('font-size', 12)
  label.append('text').attr('x', x(99) - 36).attr('y', y(101) - 8).text('轉強').attr('fill', '#3b82f6').attr('font-size', 12)

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
    .attr('stroke', d => selectedId.value === d.id ? '#f8fafc' : 'rgba(255,255,255,.45)')
    .attr('stroke-width', d => selectedId.value === d.id ? 2.6 : 1.1)
    .attr('opacity', d => {
      if (selectedEdge.value) return (d.id === selectedEdge.value.src || d.id === selectedEdge.value.dst) ? 1 : 0.2
      if (selectedId.value && selectedId.value !== d.id) return 0.35
      return 1
    })

  nodes.append('text')
    .attr('dy', -11)
    .attr('text-anchor', 'middle')
    .attr('fill', '#e2e8f0')
    .attr('font-size', 10)
    .text(d => d.name.replace('類指數', ''))

  svg.append('text').attr('x', width - 90).attr('y', height - 8).attr('fill', '#94a3b8').attr('font-size', 11).text('RS-Ratio')
  svg.append('text').attr('x', 8).attr('y', 12).attr('fill', '#94a3b8').attr('font-size', 11).text('RS-Momentum')
}

function renderLeadGraph() {
  const host = leadHost.value
  if (!host) return
  d3.select(host).selectAll('*').remove()
  if (leadSimulation) {
    leadSimulation.stop()
    leadSimulation = null
  }
  if (!points.value.length) return

  const width = host.clientWidth || 920
  const height = 300
  const nodes = points.value.map(p => ({ ...p, id: p.id }))
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

  const defs = svg.append('defs')
  defs.append('marker')
    .attr('id', 'lead-arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#60a5fa')

  const root = svg.append('g')
  svg.call(d3.zoom().scaleExtent([0.4, 3]).on('zoom', event => root.attr('transform', event.transform)))

  const maxW = d3.max(validLinks, d => Number(d.abs_weight) || 0) || 1
  const wScale = d3.scaleLinear().domain([0, maxW]).range([1, 5])

  const linkSel = root.append('g')
    .attr('fill', 'none')
    .selectAll('line')
    .data(validLinks)
    .join('line')
    .attr('stroke', d => Number(d.weight) >= 0 ? '#60a5fa' : '#f87171')
    .attr('stroke-width', d => wScale(Number(d.abs_weight) || 0))
    .attr('stroke-opacity', d => selectedEdgeKey.value ? (edgeKey(d) === selectedEdgeKey.value ? 0.95 : 0.1) : 0.62)
    .attr('marker-end', 'url(#lead-arrow)')
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
    .attr('stroke', d => selectedId.value === d.id ? '#f8fafc' : 'rgba(255,255,255,.4)')
    .attr('stroke-width', d => selectedId.value === d.id ? 2.4 : 1.2)
    .attr('opacity', d => {
      if (selectedEdge.value) return (d.id === selectedEdge.value.src || d.id === selectedEdge.value.dst) ? 1 : 0.25
      if (selectedId.value && selectedId.value !== d.id) return 0.35
      return 1
    })

  nodeSel.append('text')
    .text(d => d.name.replace('類指數', ''))
    .attr('dy', -14)
    .attr('text-anchor', 'middle')
    .attr('fill', '#e2e8f0')
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
  if (quad === 'leading') return '#22c55e'
  if (quad === 'weakening') return '#f59e0b'
  if (quad === 'lagging') return '#ef4444'
  return '#3b82f6'
}

function quadrantLabel(quad) {
  if (quad === 'leading') return '領先'
  if (quad === 'weakening') return '轉弱'
  if (quad === 'lagging') return '落後'
  return '轉強'
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

.rotation-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  gap: 16px;
}

.canvas-stack {
  display: grid;
  gap: 12px;
}

.chart-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  background: rgba(11, 17, 33, 0.52);
  padding: 10px;
}

.chart-card h3 {
  margin: 4px 0 8px;
  font-size: 1rem;
}

.chart-host {
  height: 360px;
}

.lead-host {
  height: 300px;
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
}
</style>
