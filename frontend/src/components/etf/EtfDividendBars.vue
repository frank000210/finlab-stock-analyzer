<template>
  <div class="bars-wrap">
    <div class="bars-scroll">
      <svg :viewBox="`0 0 ${width} ${H}`" :width="width" :height="H" class="bars" role="img" :aria-label="ariaLabel">
        <g v-for="t in ticks" :key="t.value">
          <line :x1="PAD_L" :x2="width - PAD_R" :y1="t.y" :y2="t.y" class="grid" />
          <text :x="PAD_L - 6" :y="t.y" class="tick" text-anchor="end" dominant-baseline="middle">{{ t.label }}</text>
        </g>
        <g v-for="g in groups" :key="g.year">
          <g v-for="b in g.bars" :key="b.symbol">
            <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :fill="b.color" rx="2">
              <title>{{ b.title }}</title>
            </rect>
            <text v-if="b.h === 0 && b.nonPayer" :x="b.x + b.w / 2" :y="baseY - 4" class="np" text-anchor="middle">–</text>
          </g>
          <text :x="g.cx" :y="H - 8" class="year" text-anchor="middle">{{ g.label }}</text>
        </g>
      </svg>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// series: [{ symbol, name, color, by_year: [{year, amount, yield, partial}], pays }]
// mode: 'amount'（元）| 'yield'（%）
const props = defineProps({
  series: { type: Array, required: true },
  mode: { type: String, default: 'amount' },
})

const H = 260
const PAD_L = 46
const PAD_R = 10
const PAD_T = 14
const PAD_B = 30
const GROUP_GAP = 22
const BAR_W = 18
const BAR_GAP = 4

const years = computed(() => {
  const set = new Map()
  props.series.forEach(s => (s.by_year || []).forEach(y => set.set(y.year, y.partial)))
  return [...set.entries()].sort((a, b) => a[0] - b[0]).map(([year, partial]) => ({ year, partial }))
})

function valueOf(s, year) {
  const row = (s.by_year || []).find(y => y.year === year)
  if (!row) return null
  return props.mode === 'yield' ? (row.yield == null ? null : row.yield * 100) : row.amount
}

const maxVal = computed(() => {
  let m = 0
  props.series.forEach(s => years.value.forEach(y => { const v = valueOf(s, y.year); if (v != null && v > m) m = v }))
  return m || 1
})

const niceMax = computed(() => {
  const m = maxVal.value
  const pow = Math.pow(10, Math.floor(Math.log10(m)))
  const n = m / pow
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10
  return step * pow
})

const groupW = computed(() => props.series.length * (BAR_W + BAR_GAP) - BAR_GAP)
const width = computed(() => Math.max(360, PAD_L + PAD_R + years.value.length * (groupW.value + GROUP_GAP * 2)))
const baseY = H - PAD_B
const plotH = H - PAD_T - PAD_B

const ticks = computed(() => {
  const out = []
  for (let i = 0; i <= 4; i++) {
    const v = (niceMax.value * i) / 4
    out.push({
      value: v,
      y: baseY - (plotH * i) / 4,
      label: props.mode === 'yield' ? `${v.toFixed(v < 10 ? 1 : 0)}%` : v.toFixed(v < 10 ? 1 : 0),
    })
  }
  return out
})

const groups = computed(() => {
  const slot = (width.value - PAD_L - PAD_R) / Math.max(years.value.length, 1)
  return years.value.map((y, gi) => {
    const cx = PAD_L + slot * gi + slot / 2
    const x0 = cx - groupW.value / 2
    const bars = props.series.map((s, si) => {
      const v = valueOf(s, y.year)
      const h = v == null ? 0 : (plotH * v) / niceMax.value
      const x = x0 + si * (BAR_W + BAR_GAP)
      const unit = props.mode === 'yield' ? '%' : ' 元'
      return {
        symbol: s.symbol, color: s.color, x, w: BAR_W, h, y: baseY - h, nonPayer: !s.pays,
        title: `${s.symbol} ${y.year}${y.partial ? '（今年累計）' : ''}：${v == null ? '無資料' : v.toFixed(2) + unit}`,
      }
    })
    return { year: y.year, cx, bars, label: y.partial ? `${y.year}（累計）` : String(y.year) }
  })
})

const ariaLabel = computed(() => `歷年${props.mode === 'yield' ? '現金殖利率' : '配息金額'}長條圖：${props.series.map(s => s.symbol).join('、')}`)
</script>

<style scoped>
.bars-wrap { width: 100%; }
.bars-scroll { overflow-x: auto; }
.bars { display: block; margin: 0 auto; }
.grid { stroke: var(--border-color, rgba(148, 163, 184, 0.18)); stroke-width: 1; stroke-dasharray: 3 3; }
.tick { fill: var(--text-muted, #64748b); font-size: 10px; }
.year { fill: var(--text-secondary, #94a3b8); font-size: 11px; font-weight: 600; }
.np { fill: var(--text-muted, #64748b); font-size: 11px; }
</style>
