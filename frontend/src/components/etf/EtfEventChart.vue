<template>
  <div class="evc" :data-symbol="symbol" data-testid="event-chart">
    <div class="evc-head">
      <div class="evc-title">
        <strong>{{ symbol }}</strong> <span class="nm">{{ name }}</span>
        <span v-if="range" class="muted small">急跌區間 {{ range.start }} ～ {{ range.end }}（淡藍色底帶）</span>
      </div>
      <button v-if="status === 'ready'" type="button" class="btn btn-secondary xs" data-testid="event-chart-reset" @click="resetRange">重設範圍</button>
    </div>

    <p v-if="status === 'loading'" class="evc-state muted" data-testid="chart-loading">走勢圖載入中…</p>
    <div v-else-if="status === 'error'" class="evc-state evc-error" data-testid="chart-error" role="alert">
      <span>{{ errorText }}</span>
      <button type="button" class="btn btn-secondary xs" @click="load">重試</button>
    </div>

    <template v-else>
      <!-- ① 十字線所在日的開高低收量與漲跌（沒有十字線時是最新一日），仿 Yahoo 股市 -->
      <p v-if="row" class="evc-ohlc" data-testid="chart-ohlc">
        <span class="date" data-testid="ohlc-date">{{ row.dateLabel }}</span>
        <span>開 <b :class="tone(row.open - row.prevClose)" data-testid="ohlc-open">{{ px(row.open) }}</b></span>
        <span>高 <b :class="tone(row.high - row.prevClose)" data-testid="ohlc-high">{{ px(row.high) }}</b></span>
        <span>低 <b :class="tone(row.low - row.prevClose)" data-testid="ohlc-low">{{ px(row.low) }}</b></span>
        <span>收 <b :class="tone(row.change)" data-testid="ohlc-close">{{ px(row.close) }}</b></span>
        <span>量 <b data-testid="ohlc-volume">{{ row.volume.toLocaleString('en-US') }}</b></span>
        <span>漲跌 <b :class="tone(row.change)" data-testid="ohlc-change">{{ signed(row.change) }}</b></span>
      </p>

      <!-- ② 各期均線：可勾選，數值與較前一日的方向跟著十字線 -->
      <div class="evc-ma" data-testid="chart-ma" role="group" aria-label="均線">
        <label v-for="m in MAS" :key="m.n" class="ma-item" :style="{ '--c': m.color }">
          <input type="checkbox" :checked="maOn.includes(m.n)" :data-testid="`ma-toggle-${m.n}`" @change="toggleMa(m.n)" />
          <span class="ma-name">MA{{ m.n }}</span>
          <span class="ma-val" :data-testid="`ma-val-${m.n}`">{{ maValue(m.n) }}</span>
          <span v-if="maDir(m.n)" class="ma-dir" :class="maDir(m.n) === 'up' ? 'up' : 'down'">{{ maDir(m.n) === 'up' ? '▲' : '▼' }}</span>
        </label>
      </div>

      <div ref="priceEl" class="evc-price" data-testid="chart-price"></div>

      <!-- ③ 下方同步的 KD：圖例數值跟著十字線 -->
      <p class="evc-kd" data-testid="chart-kd-legend">
        <span class="k">K9 <b data-testid="kd-k">{{ kdValue('k') }}</b></span>
        <span class="d">D9 <b data-testid="kd-d">{{ kdValue('d') }}</b></span>
        <span class="j">J9 <b data-testid="kd-j9">{{ kdValue('j9') }}</b></span>
        <span>K3D2 <b data-testid="kd-k3d2">{{ kdValue('k3d2') }}</b></span>
        <span>RSV <b data-testid="kd-rsv">{{ kdValue('rsv') }}</b></span>
      </p>
      <div ref="kdEl" class="evc-kd-chart" data-testid="chart-kd"></div>

      <!-- 圖上標出的項目，數字與上方表格一致 -->
      <ul v-if="marks.length" class="evc-marks" data-testid="chart-marks" aria-label="圖上標註">
        <li v-for="m in marks" :key="m.key" :data-testid="`mark-${m.key}`">
          <i class="mk" :style="{ background: m.color }"></i>
          <span class="mk-name">{{ m.label }}</span>
          <b>{{ px(m.price) }}</b>
          <span v-if="m.date" class="dt">{{ md(m.date) }}</span>
          <span v-if="m.extra" class="muted small">{{ m.extra }}</span>
        </li>
      </ul>
      <p class="muted small evc-note">
        K 線為日線、價格已處理分割、<strong>不含息</strong>；量的單位是張，取自 FinMind 的成交股數，口徑與看盤軟體不同時數字會略有差距（開高低收、均線、KD 不受影響）。可用滑鼠滾輪縮放、拖曳平移，觸控裝置可雙指縮放。
        區間最低與其後最低是同一天時只標一次；<span class="warn-dot">息</span>＝除息日。
      </p>
    </template>
  </div>
</template>

<script setup>
// 急跌與反彈的個股走勢圖：K 線＋各期均線＋把表格裡的項目標在圖上＋下方同步的 KD。
// 後端只給看盤價日線（/api/v1/etf-compare/chart），MA 與 KD 由 lib/indicators.js 用同一份資料算。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import { useChartTheme } from '../../composables/useChartTheme'
import { kdj, sma } from '../../lib/indicators'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: '' },
  // 急跌區間 { start, end }；沒有就不畫底帶
  range: { type: Object, default: null },
  // 這檔在區間內的事件數字（/compare 的 symbols[].event）；沒有就只畫走勢、不標註
  event: { type: Object, default: null },
  lastClose: { type: Number, default: null },
  lastDate: { type: String, default: '' },
})

// 配色沿用 Yahoo 股市；中間色調在深淺兩種底色都讀得清楚
const MAS = [
  { n: 5, color: '#5aa9e6' },
  { n: 10, color: '#8b6fe0' },
  { n: 20, color: '#e8923f' },
  { n: 60, color: '#d4a72c' },
  { n: 120, color: '#b5683a' },
  { n: 240, color: '#8a94a3' },
]
const DEFAULT_MA = [5, 10, 20, 60]
const PRICE_H = 340
const KD_H = 150
const LEAD_BARS = 15 // 預設範圍從急跌起日往前多看幾根，才看得到急跌「之前」的位置

const status = ref('loading') // loading | ready | error
const errorText = ref('')
const bars = shallowRef(null)
const hoverIdx = ref(null)
const maOn = ref([...DEFAULT_MA])
const priceEl = ref(null)
const kdEl = ref(null)

let priceChart = null
let kdChart = null
let candles = null
let kSeries = null
let maSeries = new Map()
let lastWidth = 0
let seq = 0
const cache = new Map() // 同一個元件實例內切換標的再切回來，不用重抓

// ── 指標：一次算好，十字線移動時只是查表 ─────────────────────────────────────
const ma = computed(() => {
  const d = bars.value
  if (!d) return {}
  return Object.fromEntries(MAS.map(m => [m.n, sma(d.close, m.n)]))
})
const kd = computed(() => {
  const d = bars.value
  return d ? kdj(d.high, d.low, d.close) : null
})
const idx = computed(() => (hoverIdx.value ?? (bars.value ? bars.value.dates.length - 1 : -1)))

// ── 頂部資訊列 ──────────────────────────────────────────────────────────────
const row = computed(() => {
  const d = bars.value
  const i = idx.value
  if (!d || i < 0) return null
  const prevClose = i > 0 ? d.close[i - 1] : d.open[i]
  return {
    dateLabel: d.dates[i].replace(/-/g, '/'),
    open: d.open[i], high: d.high[i], low: d.low[i], close: d.close[i], volume: d.volume[i],
    prevClose,
    change: d.close[i] - prevClose,
  }
})

const px = x => (x == null || Number.isNaN(x) ? '—' : Number(x).toLocaleString('en-US', {
  minimumFractionDigits: x >= 1000 ? 0 : 2, maximumFractionDigits: x >= 1000 ? 0 : 2,
}))
const signed = x => (x == null ? '—' : `${x > 0 ? '+' : ''}${Number(x).toFixed(Math.abs(x) >= 1000 ? 0 : 2)}`)
const md = iso => (iso ? iso.slice(5).replace('-', '/') : '')
const tone = x => (x > 0 ? 'up' : x < 0 ? 'down' : '')

function maValue(n) {
  const v = ma.value[n]?.[idx.value]
  return v == null ? '—' : px(v)
}
// 與前一日的均線相比：漲＝▲（紅）、跌＝▼（綠）；沒有前一日或相等就不畫箭頭
function maDir(n) {
  const arr = ma.value[n]
  const i = idx.value
  if (!arr || i < 1 || arr[i] == null || arr[i - 1] == null || arr[i] === arr[i - 1]) return ''
  return arr[i] > arr[i - 1] ? 'up' : 'down'
}
function kdValue(key) {
  const v = kd.value?.[key]?.[idx.value]
  return v == null ? '—' : v.toFixed(2)
}

function toggleMa(n) {
  maOn.value = maOn.value.includes(n) ? maOn.value.filter(x => x !== n) : [...maOn.value, n].sort((a, b) => a - b)
}
watch(maOn, () => {
  maSeries.forEach((s, n) => s.applyOptions({ visible: maOn.value.includes(n) }))
  priceChart?.priceScale('right').applyOptions({ autoScale: true })
})

// ── 圖上標註（與上方急跌表格同一組數字）──────────────────────────────────────
const marks = computed(() => {
  const e = props.event
  const t = useChartTheme()
  const list = []
  if (e && e.high != null) list.push({ key: 'high', label: '區間最高', price: e.high, date: e.high_date, color: t.up })
  if (e && e.low != null) {
    list.push({
      key: 'low', label: '其後最低', price: e.low, date: e.low_date, color: t.down,
      extra: e.drawdown != null ? `回落 ${(e.drawdown * 100).toFixed(1)}%` : '',
    })
  }
  if (e && e.window_low != null && e.low != null && e.window_low < e.low) {
    list.push({ key: 'window-low', label: '區間最低', price: e.window_low, date: e.window_low_date, color: t.warn })
  }
  if (e && e.rebound_high != null) {
    list.push({
      key: 'rebound', label: '反彈高點', price: e.rebound_high, date: e.rebound_date, color: t.blue,
      extra: e.rebound_pct != null ? `反彈 +${(e.rebound_pct * 100).toFixed(1)}%` : '',
    })
  }
  if (props.lastClose != null) {
    list.push({ key: 'last', label: '目前價位', price: props.lastClose, date: props.lastDate, color: t.neutral })
  }
  return list
})

// ── 載入 ────────────────────────────────────────────────────────────────────
async function load() {
  const my = ++seq
  destroyCharts()
  hoverIdx.value = null
  const hit = cache.get(props.symbol)
  if (hit) {
    bars.value = hit
    status.value = 'ready'
    await nextTick()
    if (my === seq) render()
    return
  }
  status.value = 'loading'
  errorText.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/etf-compare/chart?symbol=${encodeURIComponent(props.symbol)}`)
    const payload = await resp.json().catch(() => ({}))
    if (my !== seq) return
    if (!resp.ok || !payload?.success || !payload.data?.dates?.length) {
      errorText.value = payload?.detail || `走勢圖載入失敗（HTTP ${resp.status}）`
      status.value = 'error'
      return
    }
    cache.set(props.symbol, payload.data)
    bars.value = payload.data
    status.value = 'ready'
    await nextTick()
    if (my === seq) render()
  } catch (e) {
    if (my !== seq) return
    errorText.value = e?.message || '走勢圖載入失敗'
    status.value = 'error'
  }
}
watch(() => props.symbol, load)
// 區間或事件數字改變（使用者換了急跌區間）：只重畫標註與預設範圍，不重抓資料
watch(() => [props.event, props.range, props.lastClose], () => { if (status.value === 'ready') render() })

// ── 畫圖 ────────────────────────────────────────────────────────────────────
const timeKey = t => {
  if (t == null) return null
  if (typeof t === 'string') return t
  if (typeof t === 'number') return new Date(t * 1000).toISOString().slice(0, 10)
  return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`
}
const lowerBound = (arr, x) => {
  let lo = 0
  let hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid] < x) lo = mid + 1
    else hi = mid
  }
  return lo
}
const withAlpha = (hex, a) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return hex
  const n = parseInt(m[1], 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

function destroyCharts() {
  maSeries = new Map()
  candles = null
  kSeries = null
  priceChart?.remove()
  kdChart?.remove()
  priceChart = null
  kdChart = null
}

function defaultRange(d) {
  const n = d.dates.length
  let from = Math.max(0, n - 120)
  // 窄螢幕多留一些，「區間最高」的標籤才不會被左邊界切掉
  const lead = (priceEl.value?.clientWidth || 0) < 600 ? LEAD_BARS * 2 : LEAD_BARS
  if (props.range?.start) from = Math.max(0, lowerBound(d.dates, props.range.start) - lead)
  return { from: from - 0.5, to: n - 1 + 4 }
}

function render() {
  const d = bars.value
  if (!d || !priceEl.value || !kdEl.value) return
  destroyCharts()
  const t = useChartTheme()
  const width = priceEl.value.clientWidth
  lastWidth = width
  const common = {
    width,
    layout: { background: { color: 'transparent' }, textColor: t.textSoft },
    grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
    crosshair: { mode: CrosshairMode.Normal },
    // 兩張圖的價格軸留一樣寬，繪圖區才會左右對齊（十字線與縮放才會對在同一天）
    rightPriceScale: { borderColor: t.border, minimumWidth: 64 },
  }
  priceChart = createChart(priceEl.value, {
    ...common, height: PRICE_H,
    timeScale: { borderColor: t.border, visible: false, rightOffset: 4 },
  })
  kdChart = createChart(kdEl.value, {
    ...common, height: KD_H,
    timeScale: { borderColor: t.border, rightOffset: 4, timeVisible: false },
  })

  // 急跌區間的淡色底帶：lightweight-charts 沒有矩形工具，用一條隱藏座標軸的面積圖、座標範圍固定 0～1、
  // 值恆為 1，就會鋪滿整個高度（直方圖會因為柱與柱之間的縫隙變成直條紋）。要最先建立，才會畫在 K 線與均線後面。
  if (props.range?.start && props.range?.end) {
    const band = priceChart.addAreaSeries({
      priceScaleId: 'band', topColor: withAlpha(t.blue, 0.14), bottomColor: withAlpha(t.blue, 0.14),
      lineVisible: false, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 1 } }),
    })
    priceChart.priceScale('band').applyOptions({ scaleMargins: { top: 0, bottom: 0 }, visible: false })
    band.setData(d.dates.filter(x => x >= props.range.start && x <= props.range.end).map(x => ({ time: x, value: 1 })))
  }

  candles = priceChart.addCandlestickSeries({
    upColor: t.up, downColor: t.down, borderVisible: false, wickUpColor: t.up, wickDownColor: t.down,
    priceLineVisible: false, lastValueVisible: false,
  })
  candles.setData(d.dates.map((x, i) => ({ time: x, open: d.open[i], high: d.high[i], low: d.low[i], close: d.close[i] })))

  MAS.forEach(m => {
    const s = priceChart.addLineSeries({
      color: m.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      visible: maOn.value.includes(m.n),
    })
    const arr = ma.value[m.n]
    s.setData(d.dates.flatMap((x, i) => (arr[i] == null ? [] : [{ time: x, value: arr[i] }])))
    maSeries.set(m.n, s)
  })

  applyMarks(d, t)

  // KD：暖機期用只有 time 的空點補齊，兩張圖的時間點才一模一樣，可見範圍的索引才對得上
  const line = (key, color, style = LineStyle.Solid) => {
    const s = kdChart.addLineSeries({
      color, lineWidth: 1, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    })
    s.setData(d.dates.map((x, i) => (kd.value[key][i] == null ? { time: x } : { time: x, value: kd.value[key][i] })))
    return s
  }
  kSeries = line('k', MAS[0].color)
  line('d', MAS[1].color)
  line('j9', MAS[2].color, LineStyle.Dashed)
  ;[80, 20].forEach(p => kSeries.createPriceLine({
    price: p, color: t.muted, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: '',
  }))

  wireSync(d)
  const r = defaultRange(d)
  priceChart.timeScale().setVisibleLogicalRange(r)
  kdChart.timeScale().setVisibleLogicalRange(r)
}

function applyMarks(d, t) {
  const have = new Set(d.dates)
  const e = props.event
  const list = []
  const add = (date, position, shape, color, text) => {
    if (date && have.has(date)) list.push({ time: date, position, shape, color, text })
  }
  if (e) {
    add(e.high_date, 'aboveBar', 'arrowDown', t.up, `區間最高 ${px(e.high)}`)
    add(e.low_date, 'belowBar', 'arrowUp', t.down, `其後最低 ${px(e.low)}`)
    if (e.window_low != null && e.low != null && e.window_low < e.low) {
      add(e.window_low_date, 'belowBar', 'circle', t.warn, `區間最低 ${px(e.window_low)}`)
    }
    if (e.rebound_high != null) add(e.rebound_date, 'aboveBar', 'arrowDown', t.blue, `反彈高點 ${px(e.rebound_high)}`)
  }
  ;(d.dividend_events || []).forEach(ev => add(ev.date, 'belowBar', 'square', t.warn, '息'))
  // 同一天標記要依時間排序；同一天的多個標記保留先後順序
  list.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
  candles.setMarkers(list)
  if (props.lastClose != null) {
    candles.createPriceLine({
      price: props.lastClose, color: t.neutral, lineWidth: 1, lineStyle: LineStyle.Dashed,
      axisLabelVisible: true, title: '目前價位',
    })
  }
}

// ── 兩張圖同步：可見範圍＋十字線 ──────────────────────────────────────────────
let syncing = false
let crosshairBusy = false

function wireSync(d) {
  const indexOf = new Map(d.dates.map((x, i) => [x, i]))
  const link = (from, to) => from.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (!r || syncing) return
    syncing = true
    try { to.timeScale().setVisibleLogicalRange(r) } finally { syncing = false }
  })
  link(priceChart, kdChart)
  link(kdChart, priceChart)

  const onMove = (source, param) => {
    const key = timeKey(param.time)
    const i = param.point && key != null && indexOf.has(key) ? indexOf.get(key) : -1
    hoverIdx.value = i >= 0 ? i : null
    if (crosshairBusy) return
    crosshairBusy = true
    try {
      // 把十字線畫到另一張圖的同一天（實測 4.2.3 程式設定十字線不會再觸發另一張圖的事件，這個旗標只是防萬一）
      if (source === 'price') {
        if (i < 0) kdChart?.clearCrosshairPosition()
        else kdChart?.setCrosshairPosition(kd.value.k[i] ?? 50, d.dates[i], kSeries)
      } else if (i < 0) {
        priceChart?.clearCrosshairPosition()
      } else {
        priceChart?.setCrosshairPosition(d.close[i], d.dates[i], candles)
      }
    } finally {
      crosshairBusy = false
    }
  }
  priceChart.subscribeCrosshairMove(p => onMove('price', p))
  kdChart.subscribeCrosshairMove(p => onMove('kd', p))
}

function resetRange() {
  const d = bars.value
  if (!d || !priceChart) return
  const r = defaultRange(d)
  priceChart.timeScale().setVisibleLogicalRange(r)
  kdChart?.timeScale().setVisibleLogicalRange(r)
  priceChart.priceScale('right').applyOptions({ autoScale: true })
}

// 只改寬度不夠：lightweight-charts 會沿用舊的 barSpacing，要重設可見範圍才會鋪滿
function handleResize() {
  if (!priceChart || !kdChart || !priceEl.value) return
  const w = priceEl.value.clientWidth
  if (w === lastWidth) return // 手機網址列收合只會改高度，不該把使用者縮放過的範圍洗掉
  lastWidth = w
  priceChart.applyOptions({ width: w })
  kdChart.applyOptions({ width: w })
  if (bars.value) resetRange()
}

onMounted(() => {
  load()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  seq += 1
  destroyCharts()
})
</script>

<style scoped>
.evc { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.evc-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.evc-title { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-size: 14px; }
.evc-title .nm { color: var(--text-secondary); }
.muted { color: var(--text-muted); }
.small { font-size: 12px; }
.btn.xs { padding: 5px 12px; font-size: 0.78rem; }

.evc-state { margin: 0; padding: 40px 12px; text-align: center; border: 1px dashed var(--border-color); border-radius: var(--radius, 8px); }
.evc-error { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; color: var(--color-warning); }

.evc-ohlc { margin: 0; display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.evc-ohlc .date { color: var(--text-primary, var(--ink)); font-weight: 600; }
.evc-ohlc b { font-weight: 600; color: var(--text-primary, var(--ink)); }
.evc-ohlc b.up { color: var(--color-up); }
.evc-ohlc b.down { color: var(--color-down); }

.evc-ma { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; font-variant-numeric: tabular-nums; }
.ma-item { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; color: var(--c); }
.ma-item input { accent-color: var(--c); margin: 0; cursor: pointer; }
.ma-name { font-weight: 600; }
.ma-val { color: var(--text-secondary); min-width: 48px; }
.ma-dir { font-size: 10px; }

.evc-price, .evc-kd-chart { width: 100%; min-width: 0; }
.evc-kd { margin: 4px 0 0; display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.evc-kd b { font-weight: 600; color: var(--text-primary, var(--ink)); }
.evc-kd .k { color: var(--blue); }
.evc-kd .d { color: var(--purple); }
.evc-kd .j { color: var(--warn); }

.evc-marks { list-style: none; margin: 4px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; font-variant-numeric: tabular-nums; }
.evc-marks li { display: inline-flex; align-items: baseline; gap: 6px; }
.evc-marks .mk { width: 8px; height: 8px; border-radius: 50%; display: inline-block; align-self: center; }
.evc-marks .mk-name { color: var(--text-secondary); }
.evc-marks .dt { color: var(--text-muted); font-size: 12px; }
.evc-note { margin: 0; }
.warn-dot { display: inline-block; padding: 0 4px; border-radius: 2px; background: var(--color-warning); color: var(--on-accent); font-size: 11px; line-height: 14px; }

@media (max-width: 600px) {
  .evc-ohlc { gap: 4px 10px; font-size: 12px; }
  .evc-ma { gap: 6px 10px; font-size: 12px; }
}
</style>
