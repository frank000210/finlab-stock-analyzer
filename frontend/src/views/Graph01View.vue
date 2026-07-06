<template>
  <div class="graph01-page">
    <PageFocusBanner text="檢視這檔股票與其他標的的關聯強度與網絡結構，評估風險是否集中在同一群。" />

    <!-- ===== 設計稿標題列：編號徽章 + 標題 + 路徑 ===== -->
    <div class="section-head" v-reveal>
      <span class="section-index">02</span>
      <h2>觀察股關聯圖</h2>
      <span class="section-path">/graph01</span>
    </div>

    <!-- ===== 設計稿雙段控制列：視覺化模式 + 關聯層 ===== -->
    <div class="pill-row" v-reveal>
      <div class="pill-group">
        <button
          v-for="mode in viewModes"
          :key="mode.value"
          class="pill pill-mode"
          :class="{ active: viewMode === mode.value }"
          @click="viewMode = mode.value"
        >{{ mode.label }}</button>
      </div>
      <div class="pill-group">
        <button
          v-for="layer in layerOptions"
          :key="layer.value"
          class="pill pill-layer"
          :class="{ active: activeLayer === layer.value }"
          @click="activeLayer = layer.value"
        >{{ layer.label }}</button>
      </div>
    </div>

    <!-- ===== 觀察池 / 日期 / 播放控制（沿用關聯圖功能） ===== -->
    <div class="controls-card" v-reveal>
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
        <label>Edge 門檻：<strong>{{ threshold.toFixed(2) }}</strong></label>
        <input v-model.number="threshold" type="range" min="0" max="1" step="0.01" />
      </div>

      <div class="slider-row" v-if="timelineDates.length">
        <label>日期播放：<strong>{{ activeDate || '—' }}</strong></label>
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
        <span class="controls-meta">
          <template v-if="usingMockData">示意資料 · </template>已載入節點 {{ snapshotNodes.length }} 個 · 邊（{{ layerLabel(activeLayer) }}）{{ activeEdges.length }} 條
        </span>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </div>

    <!-- ===== 設計稿主版位：1fr / 300px ===== -->
    <div class="graph-grid" v-reveal>
      <div class="canvas-well">
        <div ref="graphHost" class="graph-canvas"></div>
        <span v-if="usingMockData" class="badge-estimated canvas-mock-badge">示意資料</span>
        <div v-if="!hasGraphData && !loading" class="canvas-empty">
          目前區間查無可視化資料，已自動嘗試以單日快照回補。請調整日期區間或降低門檻。
        </div>
        <div class="canvas-caption">拖曳節點可重新排列 · 邊寬＝關聯強度 · 藍＝正向 / 紅＝負向</div>
      </div>

      <aside class="side-card">
        <template v-if="selectedEdge">
          <h3>連線明細</h3>
          <div class="edge-title">{{ selectedEdge.src }} → {{ selectedEdge.dst }}</div>
          <div class="edge-sub">{{ nodeName(selectedEdge.src) }} → {{ nodeName(selectedEdge.dst) }}</div>
          <div class="detail-rows">
            <div class="detail-row">
              <span>融合權重 weight</span>
              <strong :class="signClass(selectedEdge.weight)">{{ fixed(selectedEdge.weight, 4) }}</strong>
            </div>
            <div class="detail-row">
              <span>絕對權重 |weight|</span>
              <strong>{{ fixed(selectedEdge.abs_weight, 4) }}</strong>
            </div>
            <div class="detail-row">
              <span>領先天數 lag</span>
              <strong>{{ selectedEdge.lag ?? 0 }} 日</strong>
            </div>
            <div class="detail-row">
              <span>方向 directed</span>
              <strong>{{ selectedEdge.directed ? '有向 →' : '無向 ↔' }}</strong>
            </div>
            <div class="detail-row" v-if="selectedEdge.confidence != null">
              <span>信心 confidence</span>
              <strong>{{ percent(selectedEdge.confidence) }}</strong>
            </div>
          </div>

          <template v-if="selectedEdge.components">
            <h4 class="side-subhead">融合成分</h4>
            <div class="comp-bar" v-for="comp in edgeComponents(selectedEdge)" :key="comp.key">
              <span class="comp-label">{{ comp.label }}</span>
              <span class="comp-track"><span class="comp-fill" :class="signClass(comp.value)" :style="{ width: comp.pct + '%' }"></span></span>
              <span class="comp-val">{{ fixed(comp.value, 3) }}</span>
            </div>
          </template>
        </template>

        <template v-else>
          <h3>連線明細</h3>
          <div v-if="selectedNode" class="edge-title">{{ selectedNode.symbol }}</div>
          <div v-if="selectedNode" class="edge-sub">{{ selectedNode.name_zh }} · {{ selectedNode.industry }}</div>
          <div v-if="selectedNode" class="detail-rows">
            <div class="detail-row"><span>最新收盤</span><strong>{{ selectedNode.latest_close != null ? fixed(selectedNode.latest_close, 2) : '—' }}</strong></div>
            <div class="detail-row"><span>中心性 centrality</span><strong>{{ percent(selectedNode.centrality) }}</strong></div>
            <div class="detail-row"><span>PageRank</span><strong>{{ fixed(selectedNode.pagerank, 4) }}</strong></div>
            <div class="detail-row"><span>加權連結 degree</span><strong>{{ fixed(selectedNode.weighted_degree) }}</strong></div>
            <div class="detail-row"><span>20日動能</span><strong :class="signClass(selectedNode.momentum_20)">{{ percent(selectedNode.momentum_20) }}</strong></div>
            <div class="detail-row"><span>資金強度 flow</span><strong :class="signClass(selectedNode.flow_strength)">{{ fixed(selectedNode.flow_strength) }}</strong></div>
          </div>
          <div v-else class="side-hint">點選節點或連線查看明細</div>
        </template>

        <h4 class="side-subhead alerts-head">告警</h4>
        <div v-if="alerts.length" class="alerts-list">
          <div v-for="item in alerts" :key="item.message" class="alert-row">
            <span class="alert-sev">{{ item.severity || 'warn' }}</span>
            <span class="alert-msg">{{ item.message }}</span>
          </div>
        </div>
        <div v-else class="side-hint">目前沒有告警</div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'

const theme = useChartTheme()
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const WATCHLIST_STORAGE_KEY = 'finlab_watchlist'

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
const threshold = ref(0.12)
const lookbackDays = ref(60)
const endDate = ref(todayISO())
const startDate = ref(offsetISO(30))
const timelineItems = ref([])
const currentIndex = ref(0)
const selectedSymbol = ref('')
const selectedEdgeKey = ref('')
const alerts = ref([])
const usingMockData = ref(false)
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
      .attr('id', `g01-arrow-${sign}`)
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

// 力導向圖：完全依設計稿的節點語彙 —— 圓點大小＝加權連結、填色＝產業，
// 外框環＝20日動能（綠漲/紅跌/無框），代號標籤置於圓點「下方」用等寬字。
function renderForce(host) {
  const width = host.clientWidth || 900
  const height = host.clientHeight || 440
  const color = industryScale()
  const nodes = snapshotNodes.value.map(n => ({ ...n, id: n.symbol }))
  const links = activeEdges.value.map(e => ({ ...e, source: e.src, target: e.dst }))

  const maxDeg = d3.max(nodes, n => Number(n.weighted_degree) || 0) || 1
  const rScale = d3.scaleSqrt().domain([0, maxDeg]).range([12, 26])
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
    .attr('stroke-opacity', 0.55)
    .attr('marker-end', d => d.directed ? `url(#g01-arrow-${Number(d.weight) >= 0 ? 'pos' : 'neg'})` : null)
    .style('cursor', 'pointer')
    .on('click', (event, d) => { event.stopPropagation(); pickEdge(d) })

  const nodeSel = root.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .style('cursor', 'grab')
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

  const momentumStroke = (d) => {
    const m = Number(d.momentum_20 || 0)
    if (m > 0) return theme.upStrong
    if (m < 0) return theme.downStrong
    return 'transparent'
  }

  nodeSel.append('circle')
    .attr('r', d => rScale(Number(d.weighted_degree) || 0))
    .attr('fill', d => color(d.industry || '未知產業'))
    .attr('fill-opacity', 0.9)
    .attr('stroke', momentumStroke)
    .attr('stroke-width', 2)

  // 標籤在圓點下方（設計稿）：代號用等寬字，中文名較小、淡色
  const label = nodeSel.append('text')
    .attr('text-anchor', 'middle')
    .style('pointer-events', 'none')
    .attr('font-family', 'JetBrains Mono, monospace')
  label.append('tspan')
    .attr('x', 0)
    .attr('dy', d => rScale(Number(d.weighted_degree) || 0) + 13)
    .attr('font-size', 10)
    .attr('font-weight', 700)
    .attr('fill', theme.textSoft)
    .text(d => d.symbol)
  label.append('tspan')
    .attr('x', 0)
    .attr('dy', '1.05em')
    .attr('font-size', 8.5)
    .attr('font-weight', 500)
    .attr('fill', theme.muted)
    .text(d => d.name_zh || d.name || '')

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(220).strength(d => Math.min(1, (Number(d.abs_weight) || 0.2) + 0.15)))
    .force('charge', d3.forceManyBody().strength(-640))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => rScale(Number(d.weighted_degree) || 0) + 16))
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
  const height = host.clientHeight || 440
  const radius = Math.min(width, height) / 2 - 70
  const color = industryScale()

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
    .attr('font-family', 'JetBrains Mono, monospace')
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
      node.select('circle').attr('stroke', d => d.symbol === sym ? theme.text : momentumStrokeOf(d))
        .attr('stroke-width', d => d.symbol === sym ? 3 : 2)
    } else {
      link.attr('stroke-opacity', 0.55)
      node.attr('opacity', 1).select('circle').attr('stroke', d => momentumStrokeOf(d)).attr('stroke-width', 2)
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

function momentumStrokeOf(d) {
  const m = Number(d.momentum_20 || 0)
  if (m > 0) return theme.upStrong
  if (m < 0) return theme.downStrong
  return 'transparent'
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
    if (items.length) {
      timelineItems.value = items
      usingMockData.value = false
      currentIndex.value = Math.max(0, items.length - 1)
      await loadAlerts()
    } else {
      // 後端無資料（本機常見：MongoDB 未啟用）→ 用示意假資料讓圖能運作
      useMockFallback()
    }
  } catch (error) {
    // API 失敗一律降級到示意假資料，而不是留一張空圖
    useMockFallback()
  } finally {
    loading.value = false
    nextTick(renderGraph)
  }
}

// 真實資料拿不到時的降級：改用一組固定的示意觀察池，讓力導向/矩陣/邊綁定
// 三種檢視、關聯層切換、日期播放都能正常展示。畫面會標「示意資料」。
function useMockFallback() {
  const mock = buildMockTimeline()
  timelineItems.value = mock
  usingMockData.value = true
  currentIndex.value = Math.max(0, mock.length - 1)
  alerts.value = buildMockAlerts()
  errorMessage.value = ''
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

/* ------------------------- mock fallback data ------------------------- */

// 固定的示意觀察池（取材自設計稿範例的台股）；本機無 MongoDB 時用它撐起整個頁面。
const MOCK_NODES = [
  { symbol: '2330', name_zh: '台積電', industry: '半導體業', base_close: 1015 },
  { symbol: '2317', name_zh: '鴻海', industry: '電子零組件業', base_close: 203 },
  { symbol: '2454', name_zh: '聯發科', industry: '半導體業', base_close: 1180 },
  { symbol: '3008', name_zh: '大立光', industry: '光電業', base_close: 2450 },
  { symbol: '2308', name_zh: '台達電', industry: '電子零組件業', base_close: 415 },
  { symbol: '2603', name_zh: '長榮', industry: '航運業', base_close: 205 },
  { symbol: '2609', name_zh: '陽明', industry: '航運業', base_close: 78 },
  { symbol: '1301', name_zh: '台塑', industry: '塑膠業', base_close: 48 },
]

// [src, dst, 基準強度, 正負號, 領先天數]
const MOCK_LINKS = [
  ['2330', '2317', 0.42, 1, 2],
  ['2330', '2454', 0.31, 1, 1],
  ['2330', '2603', 0.22, -1, 3],
  ['2603', '2609', 0.48, 1, 1],
  ['2330', '3008', 0.18, 1, 2],
  ['2317', '1301', 0.15, 1, 4],
  ['2330', '2308', 0.20, -1, 2],
  ['2454', '3008', 0.16, 1, 1],
]

function mulberry32(seed) {
  let a = seed >>> 0
  return function () {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildMockTimeline() {
  const dates = []
  const end = new Date(endDate.value || todayISO())
  for (let i = 7; i >= 0; i -= 1) {
    const d = new Date(end)
    d.setDate(d.getDate() - i)
    dates.push(d.toISOString().slice(0, 10))
  }
  return dates.map((dateStr, idx) => buildMockSnapshot(dateStr, mulberry32(9001 + idx)))
}

function buildMockSnapshot(dateStr, rng) {
  const jitter = (scale) => (rng() - 0.5) * 2 * scale

  // 每個節點的加權連結＝所有觸及它的邊強度加總（含當日擾動）
  const degree = {}
  const perturbed = MOCK_LINKS.map(([src, dst, val, sign, lag]) => {
    const v = Math.max(0.03, val + jitter(0.05))
    degree[src] = (degree[src] || 0) + v
    degree[dst] = (degree[dst] || 0) + v
    return { src, dst, val: v, sign, lag }
  })
  const maxDeg = Math.max(1, ...Object.values(degree))

  const industryOf = new Map(MOCK_NODES.map((n) => [n.symbol, n.industry]))
  const nodes = MOCK_NODES.map((n) => {
    const deg = degree[n.symbol] || 0
    return {
      symbol: n.symbol,
      name_zh: n.name_zh,
      industry: n.industry,
      latest_close: +(n.base_close * (1 + jitter(0.02))).toFixed(2),
      centrality: +(deg / maxDeg).toFixed(3),
      pagerank: +((deg / maxDeg) * 0.18 + 0.02).toFixed(4),
      weighted_degree: +deg.toFixed(3),
      risk_transmission: +(deg * 0.6 + rng() * 0.4).toFixed(3),
      momentum_20: +jitter(0.07).toFixed(4),
      flow_strength: +jitter(1.2).toFixed(3),
    }
  })

  const fusion = perturbed.map(({ src, dst, val, sign, lag }) => {
    const lead = +(sign * val * 0.5).toFixed(4)
    const chip = +(sign * val * 0.3).toFixed(4)
    const sameInd = industryOf.get(src) === industryOf.get(dst)
    const industry = +(sameInd ? val * 0.4 : 0).toFixed(4)
    const weight = +(lead + chip + industry).toFixed(4)
    return {
      src, dst, layer: 'fusion',
      weight, abs_weight: +Math.abs(weight).toFixed(4),
      lag: 0, directed: false,
      confidence: +Math.min(0.98, 0.45 + val).toFixed(3),
      components: { lead, chip, industry },
    }
  })

  const lead = perturbed.map(({ src, dst, val, sign, lag }) => {
    const weight = +(sign * val * 0.9).toFixed(4)
    return { src, dst, layer: 'lead', weight, abs_weight: +Math.abs(weight).toFixed(4), lag, directed: true, confidence: +Math.min(0.95, 0.4 + val).toFixed(3) }
  })

  const chip = perturbed.map(({ src, dst, val, sign }) => {
    const weight = +(sign * val * 0.7).toFixed(4)
    return { src, dst, layer: 'chip', weight, abs_weight: +Math.abs(weight).toFixed(4), lag: 0, directed: false }
  })

  // 產業層：只連同產業的標的（半導體 2330-2454、電子零組件 2317-2308、航運 2603-2609）
  const industryPairs = [['2330', '2454'], ['2317', '2308'], ['2603', '2609']]
  const industry = industryPairs.map(([src, dst]) => {
    const weight = +(0.35 + jitter(0.08)).toFixed(4)
    return { src, dst, layer: 'industry', weight, abs_weight: weight, lag: 0, directed: false }
  })

  return { date: dateStr, nodes, layers: { fusion, lead, chip, industry } }
}

function buildMockAlerts() {
  return [
    { severity: 'warn', message: '2603 與 2609 的關聯 20 日內急升至 0.81，航運股連動增強' },
    { severity: 'info', message: '2330 對觀察池中心性維持最高，仍是風險傳導樞紐' },
  ]
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
.graph01-page {
  display: grid;
  gap: 16px;
}

/* ===== 標題列（設計稿：編號徽章 + 標題 + 路徑）===== */
.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-index {
  font-size: 0.7rem;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(139, 92, 246, 0.14);
  color: #a78bfa;
  letter-spacing: 0.05em;
}
.section-head h2 {
  font-size: 1.5rem;
  font-weight: 800;
  margin: 0;
}
.section-path {
  font-size: 0.78rem;
  color: #5b6b84;
  font-family: 'JetBrains Mono', monospace;
}

/* ===== 雙段控制列（設計稿膠囊）===== */
.pill-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pill-group {
  display: flex;
  gap: 2px;
  background: #10182b;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 12px;
  padding: 4px;
}
.pill {
  padding: 8px 16px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: #8a99ad;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}
.pill-layer {
  padding: 8px 14px;
  font-size: 0.78rem;
}
.pill-mode.active {
  background: #8b5cf6;
  color: #fff;
  font-weight: 700;
}
.pill-layer.active {
  background: rgba(6, 182, 212, 0.16);
  color: #22d3ee;
  font-weight: 700;
}

/* ===== 控制卡 ===== */
.controls-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 18px;
}
.control-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.field { display: grid; gap: 6px; }
.field span { font-size: 0.78rem; color: var(--text-muted); }
.input {
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(11, 17, 33, 0.55);
  border-radius: 10px;
  min-height: 40px;
  padding: 0 12px;
  color: var(--text-primary);
}
.control-actions { margin-top: 12px; display: flex; gap: 10px; }
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
.slider-row { margin-top: 12px; display: grid; gap: 6px; }
.slider-row label { font-size: 0.82rem; color: var(--text-muted); }
.playback-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.speed-select { display: flex; align-items: center; gap: 6px; color: var(--text-muted); }
.speed-select select {
  background: rgba(11, 17, 33, 0.55);
  color: var(--text-primary);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  min-height: 34px;
  padding: 0 10px;
}
.controls-meta {
  margin-left: auto;
  font-size: 0.74rem;
  color: #5b6b84;
  font-family: 'JetBrains Mono', monospace;
}
.error-text { color: var(--color-down); margin-top: 10px; }

/* ===== 主版位（設計稿：1fr / 300px）===== */
.graph-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
}

.canvas-well {
  position: relative;
  height: 440px;
  border-radius: 18px;
  overflow: hidden;
  background: #0d1424;
  border: 1px solid rgba(148, 163, 184, 0.14);
}
.graph-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.canvas-mock-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
}
.canvas-caption {
  position: absolute;
  left: 16px;
  bottom: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem;
  color: #5b6b84;
  pointer-events: none;
}
.canvas-empty {
  position: absolute;
  inset: auto 16px 40px 16px;
  min-height: 42px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.82);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 10px 12px;
  font-size: 0.85rem;
}

/* ===== 側欄卡（設計稿：連線明細 + 告警）===== */
.side-card {
  background: #131b30;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-self: start;
}
.side-card h3 {
  font-size: 0.95rem;
  margin: 0 0 10px;
}
.edge-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 2px;
}
.edge-sub {
  font-size: 0.76rem;
  color: #5b6b84;
  margin-bottom: 10px;
}
.detail-rows { display: grid; }
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  font-size: 0.8rem;
}
.detail-row span { color: #8a99ad; }
.detail-row strong {
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}
.side-subhead {
  font-size: 0.82rem;
  color: #5b6b84;
  margin: 14px 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.alerts-head { margin-top: 6px; }
.side-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  padding: 6px 0;
}

.comp-bar {
  display: grid;
  grid-template-columns: 68px 1fr 48px;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
  font-size: 0.78rem;
}
.comp-label { color: #8a99ad; }
.comp-track {
  height: 8px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.16);
  overflow: hidden;
}
.comp-fill { display: block; height: 100%; border-radius: 6px; background: var(--accent-blue); }
.comp-fill.neg { background: var(--color-down); }
.comp-val { text-align: right; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }

.alerts-list { display: grid; gap: 8px; }
.alert-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  font-size: 0.78rem;
}
.alert-sev { font-weight: 700; color: var(--color-warning); text-transform: lowercase; }
.alert-msg { color: var(--text-secondary); }

.pos { color: var(--accent-blue); }
.neg { color: var(--color-down); }

/* ===== RWD ===== */
@media (max-width: 1100px) {
  .graph-grid { grid-template-columns: 1fr; }
  .side-card { order: -1; }
}
@media (max-width: 900px) {
  .control-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 640px) {
  .control-grid { grid-template-columns: 1fr; }
  .playback-row { flex-direction: column; align-items: flex-start; }
  .controls-meta { margin-left: 0; }
}
</style>
