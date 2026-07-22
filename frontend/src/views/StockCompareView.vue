<template>
  <div class="compare-page">
    <PageFocusBanner text="自選 2~4 檔股票疊在同一張圖看相對表現，跟同業比較（自動抓同業）是不同工具——這裡完全由你決定要比誰。" />

    <section class="card add-card">
      <div class="add-row">
        <div class="search-shell">
          <input
            v-model="searchInput"
            type="text"
            class="inp"
            placeholder="輸入代碼或名稱加入比較，例如 2330 / 台積電"
            :disabled="symbols.length >= MAX_SYMBOLS"
            @keydown.enter.prevent="submitSearchInput"
          />
          <ul v-if="searchResults.length" class="search-dropdown" role="listbox">
            <li v-for="item in searchResults" :key="item.symbol" role="option" tabindex="0"
                @click="addSymbol(item.symbol, item.name)" @keydown.enter.prevent="addSymbol(item.symbol, item.name)">
              <strong>{{ item.symbol }}</strong><span>{{ item.name }}</span>
            </li>
          </ul>
        </div>
        <label class="field">
          <span>起始日期</span>
          <input v-model="startDate" type="date" class="inp" />
        </label>
        <button class="btn btn-primary" :disabled="symbols.length < 2 || loading" @click="loadComparison">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>比較
        </button>
      </div>

      <div class="chip-row" v-if="symbols.length">
        <span v-for="s in symbols" :key="s.symbol" class="chip">
          {{ s.symbol }} {{ s.name }}
          <button type="button" class="chip-x" :aria-label="`移除 ${s.symbol}`" @click="removeSymbol(s.symbol)">✕</button>
        </span>
      </div>
      <p class="muted small">最多同時比較 {{ MAX_SYMBOLS }} 檔，至少需要 2 檔才能比較。圖表顯示的是「相對起始日的漲跌幅%」，不是原始股價（股價量級差太多沒辦法疊在同一張圖上比較）。</p>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </section>

    <section v-if="hasResult" class="card chart-card">
      <div class="section-head compact">
        <div><h2>相對表現（起始日 = 0%）</h2></div>
        <button class="btn xs" type="button" @click="exportCsv">📥 匯出 CSV</button>
      </div>
      <div class="legend-row">
        <span v-for="s in resultSeries" :key="s.symbol" class="legend-item">
          <i class="dot" :style="{ background: s.color }"></i>
          {{ s.symbol }} {{ s.name }}
          <strong :class="s.lastPct >= 0 ? 'up' : 'down'">{{ s.lastPct >= 0 ? '+' : '' }}{{ s.lastPct.toFixed(1) }}%</strong>
        </span>
      </div>
      <div ref="chartHost" class="chart-host"></div>
      <p class="disclaimer">※ 純粹是股價走勢對照，非投資建議；不同股票的成交量/籌碼/基本面條件差異很大，漲跌幅接近不代表可比性高。</p>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { createChart } from 'lightweight-charts'
import { useChartTheme } from '../composables/useChartTheme'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const MAX_SYMBOLS = 4
const theme = useChartTheme()
const COLORS = [theme.blue, theme.purple, theme.cyan, theme.warn]

const symbols = ref([]) // [{symbol, name}]
const searchInput = ref('')
const searchResults = ref([])
const startDate = ref(defaultStartDate())
const loading = ref(false)
const errorMessage = ref('')
const hasResult = ref(false)
const resultSeries = ref([]) // [{symbol, name, color, lastPct, points:[{date, pct}]}]
const chartHost = ref(null)
let chartInstance = null
let searchTimer = null

function defaultStartDate() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 1)
  return d.toISOString().slice(0, 10)
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    const q = searchInput.value.trim()
    if (!q) { searchResults.value = []; return }
    try {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
      const payload = await resp.json().catch(() => ({}))
      const items = payload?.data?.items || []
      searchResults.value = items
        .filter(it => !symbols.value.some(s => s.symbol === it.symbol))
        .slice(0, 8)
        .map(it => ({ symbol: it.symbol, name: it.name_zh || it.name || '' }))
    } catch {
      searchResults.value = []
    }
  }, 250)
}

function submitSearchInput() {
  const q = searchInput.value.trim()
  if (!q) return
  const exact = searchResults.value.find(it => it.symbol.toUpperCase() === q.toUpperCase())
  addSymbol(exact ? exact.symbol : q.toUpperCase(), exact?.name || '')
}

function addSymbol(symbol, name) {
  if (symbols.value.length >= MAX_SYMBOLS) return
  if (symbols.value.some(s => s.symbol === symbol)) return
  symbols.value = [...symbols.value, { symbol, name: name || '' }]
  searchInput.value = ''
  searchResults.value = []
}

function removeSymbol(symbol) {
  symbols.value = symbols.value.filter(s => s.symbol !== symbol)
}

async function loadComparison() {
  loading.value = true
  errorMessage.value = ''
  try {
    const results = await Promise.all(symbols.value.map(async (s) => {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/${s.symbol}/price?start=${startDate.value}&period=1d`)
      const payload = await resp.json().catch(() => ({}))
      const items = payload?.data?.items || []
      return { ...s, items }
    }))

    const withData = results.filter(r => r.items.length >= 2)
    if (withData.length < 2) {
      errorMessage.value = '至少需要 2 檔股票有足夠的價格資料才能比較，請確認代碼或縮短起始日期。'
      hasResult.value = false
      return
    }

    resultSeries.value = withData.map((r, i) => {
      const baseline = r.items[0].close
      const points = r.items.map(it => ({ date: it.date, pct: (it.close / baseline - 1) * 100 }))
      return { symbol: r.symbol, name: r.name, color: COLORS[i % COLORS.length], points, lastPct: points[points.length - 1].pct }
    })
    hasResult.value = true
    renderChart()
  } catch (e) {
    errorMessage.value = e?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

function destroyChart() {
  if (chartInstance) {
    chartInstance.remove()
    chartInstance = null
  }
}
onBeforeUnmount(destroyChart)

// Z7：原本圖表寬度只在建立當下量一次，旋轉手機/縮放視窗後圖表寬度卡住不變
// （AnalysisView 等其他圖表頁面都有掛 resize listener，這頁漏掉了）。
function handleResize() {
  if (!chartInstance || !chartHost.value) return
  chartInstance.applyOptions({ width: chartHost.value.clientWidth })
}
onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

function renderChart() {
  if (!chartHost.value) return
  destroyChart()
  const chart = createChart(chartHost.value, {
    width: chartHost.value.clientWidth,
    height: 360,
    layout: { background: { color: 'transparent' }, textColor: theme.textSoft },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
  })
  for (const s of resultSeries.value) {
    const series = chart.addLineSeries({ color: s.color, lineWidth: 2, title: s.symbol })
    series.setData(s.points.map(p => ({ time: p.date, value: Number(p.pct.toFixed(2)) })))
  }
  chart.timeScale().fitContent()
  chartInstance = chart
}

function exportCsv() {
  if (!resultSeries.value.length) return
  // 以日期聯集組表：每列一個日期，每欄一檔股票的相對漲跌幅%
  const dateSet = new Set()
  resultSeries.value.forEach(s => s.points.forEach(p => dateSet.add(p.date)))
  const dates = [...dateSet].sort()
  const cols = ['日期', ...resultSeries.value.map(s => `${s.symbol}${s.name ? '(' + s.name + ')' : ''} %`)]
  const rows = dates.map(date => [
    date,
    ...resultSeries.value.map(s => {
      const hit = s.points.find(p => p.date === date)
      return hit ? hit.pct.toFixed(2) : ''
    }),
  ])
  downloadCsv(timestampedFilename('stock-compare'), cols, rows)
}

watch(searchInput, onSearchInput)
</script>

<style scoped>
.compare-page { display: flex; flex-direction: column; gap: 16px; }
.add-card { display: flex; flex-direction: column; gap: 10px; }
.add-row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.search-shell { position: relative; flex: 1; min-width: 220px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); width: 100%; }
.search-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 20;
  background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 10px;
  list-style: none; margin: 0; padding: 4px; max-height: 260px; overflow-y: auto;
}
.search-dropdown li { display: flex; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.search-dropdown li:hover, .search-dropdown li:focus { background: var(--bg-well, rgba(148,163,184,0.1)); outline: none; }

.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: var(--bg-well, rgba(148,163,184,0.1)); border: 1px solid var(--border-color); font-size: 0.82rem; }
.chip-x { border: none; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 0.75rem; }
.chip-x:hover { color: #ef4444; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }
.error-text { color: #ef4444; font-size: 0.84rem; }

.chart-card { display: flex; flex-direction: column; gap: 10px; }
.legend-row { display: flex; flex-wrap: wrap; gap: 16px; font-size: 0.84rem; }
.legend-item { display: flex; align-items: center; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.chart-host { width: 100%; height: 360px; }
.up { color: #10b981; }
.down { color: #ef4444; }
.disclaimer { font-size: 0.72rem; color: var(--text-muted); margin: 0; }
</style>
