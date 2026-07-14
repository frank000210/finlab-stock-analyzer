<template>
  <div class="risk-page">
    <PageFocusBanner text="監控帳戶與部位風險指標，及早發現超出容忍範圍的風險。" />

    <div class="page-header">
      <div>
        <h1>風控監控</h1>
        <p>追蹤最大回撤、熔斷機制與權益曲線</p>
      </div>
      <button class="btn btn-primary" @click="loadRiskData" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </div>

    <section class="top-grid">
      <article class="card gauge-card">
        <div class="section-header">
          <div>
            <h2>MDD 風險儀表 <InfoTooltip v-bind="metricGlossary.mdd" /></h2>
            <p>綠色 &lt; {{ mddWarnPct }}%，黃色 {{ mddWarnPct }}-{{ mddPausePct }}%，紅色 ≥ {{ mddPausePct }}%</p>
          </div>
        </div>
        <div class="gauge-wrap">
          <div class="gauge" :style="gaugeStyle">
            <div class="gauge-inner">
              <strong>{{ formatPercent(mddValue) }}</strong>
              <span>MDD</span>
            </div>
          </div>
        </div>
        <MetricScale
          v-if="hasJournalData"
          class="mdd-scale"
          :min="0" :max="mddScaleMax" :value="mddPercent"
          :zones="mddZones" :thresholds="mddThresholds"
          left-label="0%" :decimals="1"
        />
        <p class="mdd-narrative" v-if="hasJournalData">{{ mddNarrative }}</p>
      </article>

      <article class="card state-card">
        <div class="section-header">
          <div>
            <h2>熔斷機制狀態</h2>
            <p>依交易日誌實際回撤與當日交易數判定</p>
          </div>
        </div>
        <div class="state-body">
          <span class="status-pill" :class="statusClass(circuitStatus)">{{ circuitStatus }}</span>
          <p>{{ statusDescription }}</p>
          <div class="threshold-cfg">
            <label>警戒 MDD<input v-model.number="mddWarnPct" type="number" min="0.5" step="0.5" class="cfg-inp" @change="saveThresholds" />%</label>
            <label>熔斷 MDD<input v-model.number="mddPausePct" type="number" min="1" step="0.5" class="cfg-inp" @change="saveThresholds" />%</label>
            <label>當日上限<input v-model.number="dailyTradeLimit" type="number" min="1" step="1" class="cfg-inp" @change="saveThresholds" />筆</label>
          </div>
        </div>
      </article>

      <article class="card trades-card">
        <div class="section-header">
          <div>
            <h2>當日交易次數</h2>
            <p>達 {{ warnTrades }} 筆警戒、{{ dailyTradeLimit }} 筆熔斷</p>
          </div>
        </div>
        <div class="trade-counter">
          <strong>{{ dailyTrades }}</strong>
          <span>/ {{ dailyTradeLimit }}</span>
        </div>
        <div class="progress-track counter-track">
          <div class="progress-fill counter-fill" :style="{ width: `${tradePercent}%` }"></div>
        </div>
      </article>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益曲線</h2>
          <p>依「交易日誌」已平倉紀錄按日彙總，起始為投組風險頁設定的帳戶資金</p>
        </div>
        <span v-if="unrealizedInfo" class="badge-estimated badge-unrealized">含 {{ unrealizedInfo.priced }} 筆未實現損益</span>
        <span v-if="hasJournalData" class="badge-estimated">資料來源：交易日誌</span>
      </div>
      <div v-if="equitySeries.length" class="chart-wrapper">
        <span class="y-axis-label">新台幣(元)</span>
        <div ref="chartEl" class="chart-area"></div>
      </div>
      <div v-if="!equitySeries.length" class="empty-state">尚無已平倉交易紀錄，請先在「交易日誌」記錄並平倉交易後再回來查看權益曲線。</div>
      <div class="x-axis-label" v-if="equitySeries.length">日期</div>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益日變動分布</h2>
          <p>直方圖 + 核密度估計，觀察報酬是否過度偏態或有厚尾風險</p>
        </div>
        <span v-if="hasJournalData" class="badge-estimated">資料來源：交易日誌</span>
      </div>
      <div ref="histEl" class="chart-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Histogram / Kernel density estimation；資料取自權益曲線期間日變動率（需至少 8 個平倉交易日才會繪製）。
      </p>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import MetricScale from '../components/MetricScale.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createChart } from 'lightweight-charts'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'
import { useJournalRisk } from '../composables/useJournalRisk'
import { tradePnl } from '../lib/tradeMath'
import { fetchLivePrices } from '../lib/livePriceCache'

const theme = useChartTheme()
const loading = ref(false)
const chartEl = ref(null)
const histEl = ref(null)
let chart = null

const {
  hasJournalData, equitySeries, mddPercent, dailyTrades, dailyTradeLimit,
  mddWarnPct, mddPausePct, warnTrades, circuitBreaker, reload, saveRiskConfig,
  openTrades, unrealizedPnl,
} = useJournalRisk()

// C2 未實現回撤：抓進行中部位的現價（與交易日誌同一個 sizing API），把
// 浮動損益灌回權益曲線，讓 MDD/熔斷即時反映凹單中的風險。best-effort：
// 抓不到價的部位就跳過，全都抓不到則維持只看已實現。
const unrealizedInfo = ref(null) // { priced, total } 供 UI 標示
async function refreshUnrealized() {
  const open = openTrades.value
  if (!open.length) { unrealizedInfo.value = null; return }
  const symbols = [...new Set(open.map(t => t.symbol))]
  const results = await fetchLivePrices(symbols)
  const priced = open.filter(t => results[t.symbol]?.price > 0)
  if (!priced.length) { unrealizedInfo.value = null; unrealizedPnl.value = null; return }
  const total = priced.reduce((a, t) => a + tradePnl(t, results[t.symbol].price), 0)
  unrealizedPnl.value = total
  unrealizedInfo.value = { priced: priced.length, total }
}

const returnSeries = computed(() => computeReturns(equitySeries.value))

const mddValue = computed(() => mddPercent.value / 100)
const circuitStatus = circuitBreaker

// 尺標滿刻度跟圓環刻度用同一個「熔斷門檻 × 1.2」邏輯，兩個視覺化才會對得起來。
const mddScaleMax = computed(() => Math.max(1, mddPausePct.value * 1.2))
const mddZones = computed(() => [
  { to: mddWarnPct.value, tone: 'good' },
  { to: mddPausePct.value, tone: 'warn' },
  { to: mddScaleMax.value, tone: 'bad' },
])
const mddThresholds = computed(() => [
  { value: mddWarnPct.value, label: `${mddWarnPct.value}% 警戒` },
  { value: mddPausePct.value, label: `${mddPausePct.value}% 熔斷` },
])
const mddNarrative = computed(() => {
  const v = mddPercent.value
  if (v >= mddPausePct.value) return `目前回撤 ${formatPercent(mddValue.value)}，已超過熔斷門檻 ${mddPausePct.value}%，系統會暫停新倉，建議先複盤交易日誌。`
  if (v >= mddWarnPct.value) return `目前回撤 ${formatPercent(mddValue.value)}，已達警戒線 ${mddWarnPct.value}%，建議暫緩加碼並檢視部位。`
  return `目前回撤 ${formatPercent(mddValue.value)}，低於警戒線 ${mddWarnPct.value}%，風險在可控範圍。`
})
const tradePercent = computed(() => Math.min(100, Math.round((dailyTrades.value / Math.max(1, dailyTradeLimit.value)) * 100)))

function saveThresholds() {
  saveRiskConfig()
}
const statusDescription = computed(() => {
  if (!hasJournalData.value) return '尚無已平倉交易紀錄，請先在「交易日誌」記錄並平倉交易。'
  if (circuitStatus.value === 'ACTIVE') return '回撤與當日交易次數都在安全範圍內。'
  if (circuitStatus.value === 'WARNING') return '回撤或當日交易次數接近風控上限，建議降低部位或暫緩加碼。'
  if (circuitStatus.value === 'PAUSED') return '回撤或當日交易次數已超過風控上限，建議停止新倉並先複盤交易日誌。'
  return '尚未取得狀態說明。'
})
const gaugeColor = computed(() => {
  if (mddPercent.value >= mddPausePct.value) return theme.down
  if (mddPercent.value >= mddWarnPct.value) return theme.warn
  return theme.up
})
const gaugeStyle = computed(() => {
  // 滿刻度取熔斷門檻的 1.2 倍，讓達門檻時圓環明顯接近全滿。
  const fullScale = Math.max(1, mddPausePct.value * 1.2)
  const percent = Math.min(100, Math.round((mddPercent.value / fullScale) * 100))
  return { background: `conic-gradient(${gaugeColor.value} ${percent}%, ${theme.border} ${percent}% 100%)` }
})

onMounted(async () => {
  window.addEventListener('resize', renderChart)
  window.addEventListener('resize', renderHistogram)
  await loadRiskData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  window.removeEventListener('resize', renderHistogram)
  if (chart) chart.remove()
})

async function loadRiskData() {
  loading.value = true
  reload()
  await refreshUnrealized()
  await nextTick()
  renderChart()
  renderHistogram()
  loading.value = false
}

// B2 跨分頁同步觸發 reload 後（unrealizedPnl 會被清空），重抓現價。
watch(openTrades, (now, prev) => {
  const key = (arr) => arr.map(t => t.id).join(',')
  if (key(now) !== key(prev || [])) refreshUnrealized()
})

function computeReturns(series) {
  const rets = []
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].value
    const cur = series[i].value
    if (prev > 0) rets.push(((cur - prev) / prev) * 100)
  }
  return rets
}

function renderHistogram() {
  const host = histEl.value
  if (!host) return
  host.innerHTML = ''
  const rets = returnSeries.value
  if (rets.length < 8) {
    host.innerHTML = '<p class="chart-empty">資料點不足，無法繪製分布圖。</p>'
    return
  }

  const width = host.clientWidth || 720
  const height = 300
  const margin = { top: 16, right: 16, bottom: 30, left: 40 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const innerH = height - margin.top - margin.bottom

  const x = d3.scaleLinear().domain(d3.extent(rets)).nice().range([0, innerW])
  const bins = d3.bin().domain(x.domain()).thresholds(20)(rets)
  const y = d3.scaleLinear().domain([0, d3.max(bins, (b) => b.length) || 1]).nice().range([innerH, 0])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.append('g').attr('transform', `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6).tickFormat((v) => `${v}%`)).attr('class', 'axis')
  g.append('g').call(d3.axisLeft(y).ticks(5)).attr('class', 'axis')

  g.selectAll('rect.bin')
    .data(bins)
    .join('rect')
    .attr('class', 'bin')
    .attr('x', (d) => x(d.x0) + 1)
    .attr('width', (d) => Math.max(0, x(d.x1) - x(d.x0) - 1))
    .attr('y', (d) => y(d.length))
    .attr('height', (d) => innerH - y(d.length))
    .attr('fill', 'var(--accent-blue)')
    .attr('fill-opacity', 0.55)

  // KDE overlay, scaled to the same bin-count y-axis for visual comparison.
  const bandwidth = 1.06 * d3.deviation(rets) * Math.pow(rets.length, -0.2) || 0.5
  const kernel = (u) => Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI)
  const xs = d3.range(x.domain()[0], x.domain()[1], (x.domain()[1] - x.domain()[0]) / 100)
  const binWidth = bins[0] ? bins[0].x1 - bins[0].x0 : 1
  const density = xs.map((xv) => {
    const sum = rets.reduce((acc, v) => acc + kernel((xv - v) / bandwidth), 0)
    return { x: xv, y: (sum / (rets.length * bandwidth)) * rets.length * binWidth }
  })
  const kdeLine = d3.line().x((d) => x(d.x)).y((d) => y(d.y)).curve(d3.curveBasis)
  g.append('path')
    .datum(density)
    .attr('fill', 'none')
    .attr('stroke', 'var(--accent-red)')
    .attr('stroke-width', 2)
    .attr('d', kdeLine)

  g.append('line')
    .attr('x1', x(0)).attr('x2', x(0))
    .attr('y1', 0).attr('y2', innerH)
    .attr('stroke', 'var(--border-color)')
    .attr('stroke-dasharray', '3,3')
}

watch(returnSeries, () => nextTick(renderHistogram))
// B2 跨分頁同步：storage 事件觸發 reload 後，權益曲線圖跟著重畫。
watch(equitySeries, () => nextTick(renderChart))

function renderChart() {
  if (!chartEl.value || !equitySeries.value.length) return
  if (chart) chart.remove()
  chart = createChart(chartEl.value, {
    width: chartEl.value.clientWidth || 720,
    height: 320,
    layout: { background: { color: '#0d1117' }, textColor: theme.muted },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
  })
  const lineSeries = chart.addLineSeries({ color: theme.up, lineWidth: 2 })
  lineSeries.setData(equitySeries.value)
  chart.timeScale().fitContent()
}

function formatPercent(unitValue) {
  return `${(unitValue * 100).toFixed(2)}%`
}

function statusClass(status) {
  if (status === 'ACTIVE') return 'is-active'
  if (status === 'WARNING') return 'is-warning'
  if (status === 'PAUSED') return 'is-paused'
  return 'is-neutral'
}
</script>

<style scoped>
.risk-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header p,
.section-header p,
.state-body p,
.empty-state {
  color: var(--text-secondary);
}

.top-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.gauge-wrap,
.state-body,
.trade-counter {
  margin-top: 16px;
}

.gauge-wrap {
  display: flex;
  justify-content: center;
}

.mdd-scale { margin-top: 16px; }
.mdd-narrative { font-size: 0.78rem; color: var(--text-secondary); margin: 8px 0 0; line-height: 1.5; }

.gauge {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  padding: 14px;
}

.gauge-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #0d1117;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.gauge-inner strong,
.trade-counter strong {
  font-size: 2rem;
}

.state-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}

.status-pill {
  padding: 6px 12px;
  border-radius: 999px;
  font-weight: 700;
}

.threshold-cfg {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.threshold-cfg label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.cfg-inp {
  width: 58px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 0.82rem;
}

.is-active {
  background: var(--up-soft);
  color: var(--color-up);
}

.is-warning {
  background: var(--warn-soft);
  color: var(--color-warning);
}

.is-paused {
  background: var(--down-soft);
  color: var(--color-down);
}

.is-neutral {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

.trade-counter {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.counter-track,
.chart-area {
  margin-top: 16px;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.counter-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #2563eb);
}

.chart-area {
  width: 100%;
  min-height: 320px;
  border-radius: 12px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
  margin-top: 16px;
}

.chart-wrapper .chart-area {
  flex: 1;
  margin-top: 0;
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

.x-axis-label {
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.chart-host { width: 100%; min-height: 300px; margin-top: 16px; }
.chart-host :deep(.axis text) { fill: var(--text-muted); font-size: 0.7rem; }
.chart-host :deep(.axis path),
.chart-host :deep(.axis line) { stroke: var(--border-color); }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }
.chart-empty { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }

@media (max-width: 1100px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 420px) {
  .risk-page {
    gap: var(--space-3);
  }
  .rule-card,
  .card {
    padding: var(--space-3);
  }
}
</style>
