<template>
  <div class="graph-page">
    <PageFocusBanner text="檢視這檔股票與其他標的的關聯強度與網絡結構，評估風險是否集中在同一群。" />

    <section class="section-block graph-hero" v-reveal>
      <div>
        <h1>觀察股關聯圖（Graph）</h1>
        <p>用每日圖譜追蹤領先落後、資金流向與產業關聯，支援門檻調整與逐日播放。點選節點或連線可於右側檢視細節。</p>
      </div>
      <div class="hero-meta">
        <span class="badge">觀察池 {{ symbols.length }} 檔</span>
        <span class="badge">門檻 {{ threshold.toFixed(2) }}</span>
        <span class="badge">已載入節點 {{ snapshotNodes.length }} 個</span>
        <span class="badge">已載入邊（{{ layerLabel(activeLayer) }}）{{ activeEdges.length }} 條</span>
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
        <button class="btn btn-primary" :disabled="loading" @click="reloadTimeline">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
          {{ loading ? '運算中…' : '重算圖譜' }}
        </button>
      </div>

      <div class="switch-row">
        <div class="seg" role="tablist" aria-label="視覺化模式">
          <button
            v-for="mode in viewModes"
            :key="mode.value"
            class="seg-btn"
            :class="{ active: viewMode === mode.value }"
            @click="viewMode = mode.value"
          >{{ mode.label }}</button>
        </div>
        <div class="seg" role="tablist" aria-label="關聯層">
          <button
            v-for="layer in layerOptions"
            :key="layer.value"
            class="seg-btn"
            :class="{ active: activeLayer === layer.value }"
            @click="activeLayer = layer.value"
          >{{ layer.label }}</button>
        </div>
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
        <div ref="graphHost" class="graph-canvas"></div>
        <div v-if="loading" class="canvas-loading" role="status" aria-live="polite">
          <div class="loading-spinner canvas-spinner"></div>
          <span>重算圖譜中…</span>
        </div>
        <div v-if="!hasGraphData && !loading" class="canvas-empty">
          目前區間查無可視化資料，已自動嘗試以單日快照回補。請調整日期區間或降低門檻。
        </div>
        <div class="legend">
          <span class="lg-item"><i class="dot" style="background:#4f8cff"></i>正向關聯</span>
          <span class="lg-item"><i class="dot" style="background:#ef4444"></i>負向關聯</span>
          <span class="lg-hint" v-if="viewMode !== 'matrix'">節點大小＝加權連結；顏色＝產業</span>
          <span class="lg-hint" v-else>參考：D3 gallery 矩陣式關聯視覺化；灰色＝低於目前門檻或無資料，滑鼠移到格子看數值</span>
        </div>
      </div>

      <aside class="graph-side">
        <template v-if="selectedEdge">
          <h3>連線明細（{{ layerLabel(selectedEdge.layer) }}）</h3>
          <div class="detail-card">
            <p class="symbol">{{ selectedEdge.src }} → {{ selectedEdge.dst }}</p>
            <p class="muted">{{ nodeName(selectedEdge.src) }} → {{ nodeName(selectedEdge.dst) }}</p>
            <div class="kv"><span>融合權重 weight</span><strong :class="signClass(selectedEdge.weight)">{{ fixed(selectedEdge.weight, 4) }}</strong></div>
            <div class="kv"><span>絕對權重 |weight|</span><strong>{{ fixed(selectedEdge.abs_weight, 4) }}</strong></div>
            <div class="kv"><span>領先天數 lag</span><strong>{{ selectedEdge.lag ?? 0 }} 日</strong></div>
            <div class="kv"><span>方向 directed</span><strong>{{ selectedEdge.directed ? '有向 →' : '無向 ↔' }}</strong></div>
            <div class="kv" v-if="selectedEdge.confidence != null"><span>信心 confidence</span><strong>{{ percent(selectedEdge.confidence) }}</strong></div>

            <template v-if="selectedEdge.components">
              <p class="sub-title">融合成分（α·領先 + β·資金 + γ·產業）</p>
              <div class="comp-bar" v-for="comp in edgeComponents(selectedEdge)" :key="comp.key">
                <span class="comp-label">{{ comp.label }}</span>
                <span class="comp-track">
                  <span class="comp-fill" :class="signClass(comp.value)" :style="{ width: comp.pct + '%' }"></span>
                </span>
                <span class="comp-val">{{ fixed(comp.value, 3) }}</span>
              </div>
            </template>
          </div>
        </template>

        <template v-else>
          <h3>節點明細</h3>
          <div v-if="selectedNode" class="detail-card">
            <p class="symbol">{{ selectedNode.symbol }} · {{ selectedNode.name_zh }}</p>
            <p class="muted">{{ selectedNode.industry }}</p>
            <div class="kv"><span>最新收盤</span><strong>{{ selectedNode.latest_close != null ? fixed(selectedNode.latest_close, 2) : '—' }}</strong></div>
            <div class="kv"><span>中心性 centrality</span><strong>{{ percent(selectedNode.centrality) }}</strong></div>
            <div class="kv"><span>PageRank</span><strong>{{ fixed(selectedNode.pagerank, 4) }}</strong></div>
            <div class="kv"><span>加權連結 degree</span><strong>{{ fixed(selectedNode.weighted_degree) }}</strong></div>
            <div class="kv"><span>風險傳導</span><strong>{{ fixed(selectedNode.risk_transmission) }}</strong></div>
            <div class="kv"><span>20日動能</span><strong :class="signClass(selectedNode.momentum_20)">{{ percent(selectedNode.momentum_20) }}</strong></div>
            <div class="kv"><span>資金強度 flow</span><strong :class="signClass(selectedNode.flow_strength)">{{ fixed(selectedNode.flow_strength) }}</strong></div>
          </div>
          <div v-else class="detail-card muted">點選節點或連線查看明細</div>
        </template>

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
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'
import { loadWatchlist as loadSharedWatchlist } from '../lib/watchlist'

const theme = useChartTheme()
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
// Y1 修正：這裡存的是「這次要畫關聯圖的股票組合」，跟觀察清單（Watchlist
// 頁／作戰台在用的共用清單）是不同概念——原本兩者共用同一把 localStorage
// key，導致在這裡套用任意股票組合會直接覆蓋掉使用者真正的觀察清單。
// 改用本頁專屬 key 存這次的圖組合，只在「還沒存過」時才拿觀察清單當初始值。
const GRAPH_SYMBOLS_STORAGE_KEY = 'finlab_graph_symbols'

const viewModes = [
  { value: 'force', label: '力導向圖' },
  { value: 'bundle', label: '階層邊綁定' },
  { value: 'matrix', label: '相關矩陣熱力圖' },
]
const layerOptions = [
  { value: 'fusion', label: '融合' },
  { value: 'lead', label: '領先落後' },
  { value: 'chip', label: '資金流向' },
  { value: 'industry', label: '產業' },
]

const loading = ref(false)
const errorMessage = ref('')
const symbols = ref(loadWatchlist())
const symbolInput = ref(symbols.value.join(','))
// 0.35 曾是預設值，但實測 fusion/lead/chip 權重多落在 0.06~0.32 之間
// （尤其當 FinMind 產業資料缺失時，fusion 的 industry 分量恆為 0，
// 使融合權重被結構性壓低），導致預設門檻下幾乎每次都是空圖（只有節點沒有邊）。
// 改用貼近「邊建立門檻」(lead>=0.12) 的預設值，讓已算出的邊預設就看得到。
const threshold = ref(0.12)
const lookbackDays = ref(60)
const endDate = ref(todayISO())
const startDate = ref(offsetISO(30))
const timelineItems = ref([])
const currentIndex = ref(0)
const selectedSymbol = ref('')
const selectedEdgeKey = ref('')
const alerts = ref([])
const isPlaying = ref(false)
const playIntervalMs = ref(700)
const viewMode = ref('force')
const activeLayer = ref('fusion')
const graphHost = ref(null)

let playTimer = null
let reloadTimer = null
let simulation = null
let resizeObserver = null

const timelineDates = computed(() => timelineItems.value.map(item => item.date))
const activeDate = computed(() => timelineDates.value[currentIndex.value] || '')
const currentSnapshot = computed(() => timelineItems.value[currentIndex.value] || null)
const snapshotNodes = computed(() => currentSnapshot.value?.nodes || [])
const activeEdges = computed(() => {
  const layers = currentSnapshot.value?.layers || {}
  const edges = Array.isArray(layers[activeLayer.value]) ? layers[activeLayer.value] : []
  const present = new Set(snapshotNodes.value.map(n => n.symbol))
  return edges.filter(e => present.has(e.src) && present.has(e.dst))
})
const hasGraphData = computed(() => snapshotNodes.value.length > 0)

const selectedNode = computed(() =>
  snapshotNodes.value.find(node => node.symbol === selectedSymbol.value) || null
)
const selectedEdge = computed(() =>
  activeEdges.value.find(e => edgeKey(e) === selectedEdgeKey.value) || null
)

watch(currentSnapshot, (snapshot) => {
  if (!snapshot?.nodes?.length) {
    selectedSymbol.value = ''
    selectedEdgeKey.value = ''
  } else if (!snapshot.nodes.some(node => node.symbol === selectedSymbol.value)) {
    selectedSymbol.value = snapshot.nodes[0].symbol
    selectedEdgeKey.value = ''
  }
})

watch([currentSnapshot, viewMode, activeLayer], () => {
  nextTick(renderGraph)
})

watch(threshold, () => {
  clearTimeout(reloadTimer)
  reloadTimer = setTimeout(reloadTimeline, 350)
})

onMounted(async () => {
  await reloadTimeline()
  if (graphHost.value && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => renderGraph())
    resizeObserver.observe(graphHost.value)
  }
})

onBeforeUnmount(() => {
  if (playTimer) clearInterval(playTimer)
  if (reloadTimer) clearTimeout(reloadTimer)
  if (simulation) simulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
})

/* ------------------------- D3 rendering ------------------------- */

function renderGraph() {
  const host = graphHost.value
  if (!host) return
  d3.select(host).selectAll('*').remove()
  if (simulation) { simulation.stop(); simulation = null }
  if (!hasGraphData.value) return
  if (viewMode.value === 'bundle') renderBundle(host)
  else if (viewMode.value === 'matrix') renderMatrix(host)
  else renderForce(host)
}

function renderMatrix(host) {
  // 參考：D3 gallery 矩陣式關聯視覺化；同一份 activeEdges 資料的另一種檢視模式，
  // 網絡圖看結構、矩陣看每一對標的的關聯強度數值。
  const nodes = snapshotNodes.value
  const n = nodes.length
  if (!n) return
  const size = Math.min(host.clientWidth || 700, 720)
  const margin = { top: 90, right: 20, bottom: 20, left: 90 }
  const cell = Math.max(16, Math.floor((size - margin.left - margin.right) / n))
  const inner = cell * n
  const width = inner + margin.left + margin.right
  const height = inner + margin.top + margin.bottom

  const weightBySymbolPair = new Map()
  activeEdges.value.forEach((e) => {
    weightBySymbolPair.set(`${e.src}|${e.dst}`, Number(e.weight) || 0)
  })

  const maxAbs = d3.max(activeEdges.value, (e) => Math.abs(Number(e.weight) || 0)) || 1
  const color = (w) => {
    if (!w) return 'var(--bg-tertiary)'
    const t = Math.min(1, Math.abs(w) / maxAbs)
    return w >= 0
      ? d3.interpolateRgb('rgba(59,130,246,0.15)', theme.blue)(t)
      : d3.interpolateRgb(theme.negativeSoft, theme.negative)(t)
  }

  const svg = d3.select(host).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('width', '100%')
    .style('height', '100%')
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  nodes.forEach((row, i) => {
    nodes.forEach((col, j) => {
      const w = row.symbol === col.symbol ? null : weightBySymbolPair.get(`${row.symbol}|${col.symbol}`)
      g.append('rect')
        .attr('x', j * cell)
        .attr('y', i * cell)
        .attr('width', cell - 1)
        .attr('height', cell - 1)
        .attr('fill', row.symbol === col.symbol ? 'var(--border-color)' : color(w))
        .append('title')
        .text(row.symbol === col.symbol ? row.symbol : `${row.symbol} → ${col.symbol}：${w != null ? w.toFixed(3) : '無資料（低於門檻）'}`)
    })
  })

  // Row labels
  g.selectAll('text.row-label')
    .data(nodes)
    .join('text')
    .attr('class', 'row-label')
    .attr('x', -6)
    .attr('y', (d, i) => i * cell + cell / 2 + 4)
    .attr('text-anchor', 'end')
    .attr('font-size', Math.min(11, cell - 4))
    .attr('fill', 'var(--text-muted)')
    .text((d) => d.symbol)

  // Column labels (rotated)
  g.selectAll('text.col-label')
    .data(nodes)
    .join('text')
    .attr('class', 'col-label')
    .attr('transform', (d, j) => `translate(${j * cell + cell / 2},-6) rotate(-60)`)
    .attr('text-anchor', 'start')
    .attr('font-size', Math.min(11, cell - 4))
    .attr('fill', 'var(--text-muted)')
    .text((d) => d.symbol)
}

function baseSvg(host, width, height) {
  const svg = d3.select(host).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('width', '100%')
    .style('height', '100%')
  const defs = svg.append('defs')
  ;['pos', 'neg'].forEach((sign) => {
    defs.append('marker')
      .attr('id', `arrow-${sign}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', sign === 'pos' ? theme.blue : theme.negative)
  })
  return svg
}

function industryScale() {
  const industries = Array.from(new Set(snapshotNodes.value.map(n => n.industry || '未知產業')))
  return d3.scaleOrdinal(d3.schemeTableau10).domain(industries)
}

function renderForce(host) {
  const width = host.clientWidth || 900
  const height = 560
  const color = industryScale()
  const nodes = snapshotNodes.value.map(n => ({ ...n, id: n.symbol }))
  const links = activeEdges.value.map(e => ({ ...e, source: e.src, target: e.dst }))

  const maxDeg = d3.max(nodes, n => Number(n.weighted_degree) || 0) || 1
  const rScale = d3.scaleSqrt().domain([0, maxDeg]).range([9, 26])
  const maxW = d3.max(links, l => Number(l.abs_weight) || 0) || 1
  const wScale = d3.scaleLinear().domain([0, maxW]).range([1, 6])

  const svg = baseSvg(host, width, height)
  const root = svg.append('g')
  svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', (event) => {
    root.attr('transform', event.transform)
  }))
  svg.on('click', () => clearSelection())

  const linkSel = root.append('g')
    .attr('fill', 'none')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', d => Number(d.weight) >= 0 ? theme.blue : theme.negative)
    .attr('stroke-width', d => wScale(Number(d.abs_weight) || 0))
    .attr('stroke-opacity', 0.6)
    .attr('marker-end', d => d.directed ? `url(#arrow-${Number(d.weight) >= 0 ? 'pos' : 'neg'})` : null)
    .style('cursor', 'pointer')
    .on('click', (event, d) => { event.stopPropagation(); pickEdge(d) })

  const nodeSel = root.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .style('cursor', 'pointer')
    .on('click', (event, d) => { event.stopPropagation(); pickNode(d) })
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null; d.fy = null
      }))

  nodeSel.append('circle')
    .attr('r', d => rScale(Number(d.weighted_degree) || 0))
    .attr('fill', d => color(d.industry || '未知產業'))
    .attr('stroke', theme.textSoft)
    .attr('stroke-width', 1.4)

  const label = nodeSel.append('text')
    .attr('text-anchor', 'middle')
    .attr('fill', theme.text)
    .attr('font-size', 9)
    .attr('font-weight', 700)
    .style('pointer-events', 'none')
  label.append('tspan')
    .attr('x', 0)
    .attr('dy', '-0.15em')
    .text(d => d.symbol)
  label.append('tspan')
    .attr('x', 0)
    .attr('dy', '1.1em')
    .attr('font-size', 8)
    .attr('font-weight', 500)
    .attr('fill', theme.textSoft)
    .text(d => d.name_zh || d.name || '')

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(220).strength(d => Math.min(1, (Number(d.abs_weight) || 0.2) + 0.15)))
    .force('charge', d3.forceManyBody().strength(-640))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => rScale(Number(d.weighted_degree) || 0) + 12))
    .on('tick', () => {
      linkSel
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`)
    })

  if (prefersReducedMotion()) {
    simulation.stop()
    for (let i = 0; i < 250; i += 1) simulation.tick()
    linkSel.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    nodeSel.attr('transform', d => `translate(${d.x},${d.y})`)
  }

  registerHighlighters(nodeSel, linkSel, null)
  applyHighlight()
}

function renderBundle(host) {
  const width = host.clientWidth || 900
  const height = 560
  const radius = Math.min(width, height) / 2 - 90
  const color = industryScale()

  // hierarchy: root -> industry -> symbol
  const groups = d3.group(snapshotNodes.value, n => n.industry || '未知產業')
  const hierarchyData = {
    name: 'root',
    children: Array.from(groups, ([industry, items]) => ({
      name: industry,
      children: items.map(n => ({ name: n.symbol, node: n })),
    })),
  }
  const rootNode = d3.hierarchy(hierarchyData)
  d3.cluster().size([2 * Math.PI, radius])(rootNode)
  const leaves = rootNode.leaves()
  const leafById = new Map(leaves.map(l => [l.data.name, l]))

  const svg = baseSvg(host, width, height)
  const g = svg.append('g').attr('transform', `translate(${width / 2},${height / 2})`)
  svg.on('click', () => clearSelection())

  const line = d3.lineRadial().curve(d3.curveBundle.beta(0.85)).radius(d => d.y).angle(d => d.x)
  const maxW = d3.max(activeEdges.value, e => Number(e.abs_weight) || 0) || 1
  const wScale = d3.scaleLinear().domain([0, maxW]).range([1, 5])

  const bundleLinks = activeEdges.value.map((e) => {
    const s = leafById.get(e.src)
    const t = leafById.get(e.dst)
    if (!s || !t) return null
    return { edge: e, path: s.path(t) }
  }).filter(Boolean)

  const linkSel = g.append('g')
    .attr('fill', 'none')
    .selectAll('path')
    .data(bundleLinks)
    .join('path')
    .attr('d', d => line(d.path))
    .attr('stroke', d => Number(d.edge.weight) >= 0 ? theme.blue : theme.negative)
    .attr('stroke-width', d => wScale(Number(d.edge.abs_weight) || 0))
    .attr('stroke-opacity', 0.55)
    .style('cursor', 'pointer')
    .on('click', (event, d) => { event.stopPropagation(); pickEdge(d.edge) })

  const nodeSel = g.append('g')
    .selectAll('g')
    .data(leaves)
    .join('g')
    .attr('transform', d => `rotate(${d.x * 180 / Math.PI - 90}) translate(${d.y},0)`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => { event.stopPropagation(); pickNode(d.data.node) })

  nodeSel.append('circle')
    .attr('r', 5)
    .attr('fill', d => color(d.data.node.industry || '未知產業'))
    .attr('stroke', theme.textSoft)

  nodeSel.append('text')
    .attr('dy', '.31em')
    .attr('x', d => d.x < Math.PI ? 9 : -9)
    .attr('text-anchor', d => d.x < Math.PI ? 'start' : 'end')
    .attr('transform', d => d.x >= Math.PI ? 'rotate(180)' : null)
    .attr('fill', theme.text)
    .attr('font-size', 10)
    .attr('font-weight', 600)
    .text(d => `${d.data.node.symbol} ${d.data.node.name_zh || ''}`)

  registerHighlighters(nodeSel, linkSel, leafById)
  applyHighlight()
}

/* ------------------------- selection & highlight ------------------------- */

let highlighters = { node: null, link: null, leafById: null, mode: 'force' }

function registerHighlighters(nodeSel, linkSel, leafById) {
  highlighters = { node: nodeSel, link: linkSel, leafById, mode: viewMode.value }
}

function applyHighlight() {
  const { node, link, mode } = highlighters
  if (!node || !link) return
  const sym = selectedSymbol.value
  const ek = selectedEdgeKey.value

  if (mode === 'force') {
    if (ek) {
      link.attr('stroke-opacity', d => edgeKey(d) === ek ? 0.95 : 0.08)
        .attr('stroke-width', d => (edgeKey(d) === ek ? 4 : 1))
      node.attr('opacity', d => {
        const e = selectedEdge.value
        return e && (d.symbol === e.src || d.symbol === e.dst) ? 1 : 0.25
      })
    } else if (sym) {
      const connected = new Set([sym])
      link.each(d => { if (d.src === sym) connected.add(d.dst); if (d.dst === sym) connected.add(d.src) })
      link.attr('stroke-opacity', d => (d.src === sym || d.dst === sym) ? 0.9 : 0.06)
        .attr('stroke-width', d => (d.src === sym || d.dst === sym) ? Math.max(2, wForce(d)) : 1)
      node.attr('opacity', d => connected.has(d.symbol) ? 1 : 0.28)
      node.select('circle').attr('stroke', d => d.symbol === sym ? theme.text : theme.textSoft)
        .attr('stroke-width', d => d.symbol === sym ? 3 : 1.4)
    } else {
      link.attr('stroke-opacity', 0.6)
      node.attr('opacity', 1).select('circle').attr('stroke', theme.textSoft).attr('stroke-width', 1.4)
    }
  } else {
    if (ek) {
      link.attr('stroke-opacity', d => edgeKey(d.edge) === ek ? 0.95 : 0.05)
        .attr('stroke-width', d => edgeKey(d.edge) === ek ? 4 : 1)
      node.attr('opacity', d => {
        const e = selectedEdge.value
        return e && (d.data.name === e.src || d.data.name === e.dst) ? 1 : 0.3
      })
    } else if (sym) {
      link.attr('stroke-opacity', d => (d.edge.src === sym || d.edge.dst === sym) ? 0.9 : 0.04)
        .attr('stroke-width', d => (d.edge.src === sym || d.edge.dst === sym) ? 3 : 1)
      const connected = new Set([sym])
      activeEdges.value.forEach(e => { if (e.src === sym) connected.add(e.dst); if (e.dst === sym) connected.add(e.src) })
      node.attr('opacity', d => connected.has(d.data.name) ? 1 : 0.3)
    } else {
      link.attr('stroke-opacity', 0.55)
      node.attr('opacity', 1)
    }
  }
}

function wForce(d) {
  const maxW = d3.max(activeEdges.value, e => Number(e.abs_weight) || 0) || 1
  return d3.scaleLinear().domain([0, maxW]).range([1, 6])(Number(d.abs_weight) || 0)
}

function pickNode(node) {
  selectedEdgeKey.value = ''
  selectedSymbol.value = node.symbol
  applyHighlight()
}

function pickEdge(edge) {
  selectedSymbol.value = ''
  selectedEdgeKey.value = edgeKey(edge)
  applyHighlight()
}

function clearSelection() {
  selectedEdgeKey.value = ''
  selectedSymbol.value = ''
  applyHighlight()
}

/* ------------------------- data loading ------------------------- */

function loadWatchlist() {
  try {
    const raw = localStorage.getItem(GRAPH_SYMBOLS_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    const normalized = Array.isArray(parsed)
      ? parsed.map(item => String(item || '').trim()).filter(Boolean)
      : []
    if (normalized.length) return normalized
    // 這頁還沒存過自己的組合：拿共用觀察清單當初始值，方便使用者一開始就
    // 看到自己平常在追蹤的股票，但之後套用新組合不會回頭去動觀察清單本身
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
    .filter((item) => item && !seen.has(item) && seen.add(item))
}

function applySymbols() {
  const parsed = normalizeSymbols(symbolInput.value)
  if (parsed.length < 2) {
    errorMessage.value = '至少需要 2 檔股票建立關聯圖'
    return
  }
  symbols.value = parsed
  localStorage.setItem(GRAPH_SYMBOLS_STORAGE_KEY, JSON.stringify(parsed))
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
    nextTick(renderGraph)
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

/* ------------------------- helpers ------------------------- */

function edgeKey(edge) {
  return `${edge.layer || activeLayer.value}:${edge.src}->${edge.dst}`
}

function nodeName(symbol) {
  return snapshotNodes.value.find(n => n.symbol === symbol)?.name_zh || symbol
}

function layerLabel(layer) {
  return layerOptions.find(l => l.value === layer)?.label || layer || '融合'
}

function edgeComponents(edge) {
  const comps = edge.components || {}
  const entries = [
    { key: 'lead', label: '領先落後', value: Number(comps.lead || 0) },
    { key: 'chip', label: '資金流向', value: Number(comps.chip || 0) },
    { key: 'industry', label: '產業關聯', value: Number(comps.industry || 0) },
  ]
  const max = Math.max(1, ...entries.map(e => Math.abs(e.value)))
  return entries.map(e => ({ ...e, pct: Math.round((Math.abs(e.value) / max) * 100) }))
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

function percent(value) {
  const numeric = Number(value || 0)
  if (!Number.isFinite(numeric)) return '0.00%'
  return `${(numeric * 100).toFixed(2)}%`
}

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
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

.switch-row {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.seg {
  display: inline-flex;
  padding: 4px;
  gap: 4px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(11, 17, 33, 0.5);
}

.seg-btn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-weight: 600;
  transition: background 0.18s ease, color 0.18s ease;
}

.seg-btn.active {
  background: rgba(59, 130, 246, 0.24);
  color: var(--text-primary);
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
  border: 1px solid var(--chart-border);
  border-radius: 18px;
  background: var(--bg-well);
  overflow: hidden;
}

.graph-canvas {
  width: 100%;
  height: 560px;
  display: block;
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

.legend {
  position: absolute;
  left: 14px;
  top: 12px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 0.76rem;
  color: var(--text-muted);
  pointer-events: none;
}

.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.lg-item .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.lg-hint {
  opacity: 0.75;
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

.detail-card .symbol {
  font-weight: 700;
  margin: 0 0 2px;
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

.sub-title {
  margin: 12px 0 8px;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.comp-bar {
  display: grid;
  grid-template-columns: 68px 1fr 52px;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
  font-size: 0.8rem;
}

.comp-label {
  color: var(--text-muted);
}

.comp-track {
  height: 8px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.16);
  overflow: hidden;
}

.comp-fill {
  display: block;
  height: 100%;
  border-radius: 6px;
  background: #4f8cff;
}

.comp-fill.neg {
  background: var(--color-down);
}

.comp-val {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.pos {
  color: #4f8cff;
}

.neg {
  color: var(--color-down);
}

.alerts-title {
  margin-top: 16px !important;
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
