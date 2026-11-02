<template>
  <figure class="radar-wrap">
    <svg :viewBox="`0 0 ${SIZE} ${SIZE}`" class="radar" role="img" :aria-label="ariaLabel" :data-visible="series.map(s => s.symbol).join(',')">
      <g class="rings">
        <polygon v-for="r in RINGS" :key="r" :points="ringPoints(r)" class="ring" />
        <line v-for="(a, i) in axes" :key="a.key" :x1="C" :y1="C" :x2="pt(i, 100).x" :y2="pt(i, 100).y" class="spoke" />
      </g>
      <text v-for="r in [50, 100]" :key="`t${r}`" :x="C + 3" :y="C - (R * r) / 100 + 11" class="ring-label">{{ r }}</text>
      <g v-for="s in series" :key="s.symbol" class="poly">
        <polygon :points="polyPoints(s)" :fill="s.color" fill-opacity="0.14" :stroke="s.color" stroke-width="2" stroke-linejoin="round" />
        <circle v-for="(a, i) in axes" :key="a.key" :cx="pt(i, val(s, a.key)).x" :cy="pt(i, val(s, a.key)).y" r="3"
                :fill="s.scores[a.key] == null ? 'var(--bg-card, #111827)' : s.color" :stroke="s.color" stroke-width="1.5" />
      </g>
      <text v-for="(a, i) in axes" :key="`l${a.key}`" :x="labelPos(i).x" :y="labelPos(i).y" class="axis-label"
            :text-anchor="labelPos(i).anchor" dominant-baseline="middle">{{ a.label }}</text>
    </svg>
    <figcaption v-if="hasMissing" class="radar-note">
      空心圓點＝該項不適用（不配息或資料不足），雷達圖上以 0 顯示，但<strong>不計入總分</strong>。
    </figcaption>
  </figure>
</template>

<script setup>
import { computed } from 'vue'

// series: [{ symbol, color, scores: { return, defense, sharpe, yield, fill } }]（值 0–100 或 null）
const props = defineProps({
  series: { type: Array, required: true },
})

const SIZE = 340
const C = SIZE / 2
const R = 112
const RINGS = [20, 40, 60, 80, 100]
const axes = [
  { key: 'return', label: '報酬潛力' },
  { key: 'defense', label: '抗跌防禦' },
  { key: 'sharpe', label: '夏普性價比' },
  { key: 'yield', label: '現金殖利率' },
  { key: 'fill', label: '填息復原力' },
]

function angle(i) {
  return -Math.PI / 2 + (2 * Math.PI * i) / axes.length
}
function pt(i, value) {
  const r = (R * Math.max(0, Math.min(100, value))) / 100
  return { x: C + r * Math.cos(angle(i)), y: C + r * Math.sin(angle(i)) }
}
function val(s, key) {
  const v = s.scores[key]
  return v == null ? 0 : v
}
function ringPoints(r) {
  return axes.map((_, i) => { const p = pt(i, r); return `${p.x.toFixed(1)},${p.y.toFixed(1)}` }).join(' ')
}
function polyPoints(s) {
  return axes.map((a, i) => { const p = pt(i, val(s, a.key)); return `${p.x.toFixed(1)},${p.y.toFixed(1)}` }).join(' ')
}
function labelPos(i) {
  const a = angle(i)
  const r = R + 20
  const x = C + r * Math.cos(a)
  const y = C + r * Math.sin(a)
  const c = Math.cos(a)
  return { x, y, anchor: Math.abs(c) < 0.2 ? 'middle' : c > 0 ? 'start' : 'end' }
}

const hasMissing = computed(() => props.series.some(s => axes.some(a => s.scores[a.key] == null)))
const ariaLabel = computed(() => (props.series.length
  ? `五維評分雷達圖：${props.series.map(s => s.symbol).join('、')}`
  : '五維評分雷達圖：目前沒有顯示任何標的'))
</script>

<style scoped>
.radar-wrap { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.radar { width: 100%; max-width: 380px; height: auto; overflow: visible; }
.ring { fill: none; stroke: var(--border-color, rgba(148, 163, 184, 0.18)); stroke-width: 1; }
.spoke { stroke: var(--border-color, rgba(148, 163, 184, 0.18)); stroke-width: 1; }
.ring-label { fill: var(--text-muted, #64748b); font-size: 9px; }
.axis-label { fill: var(--text-secondary, #94a3b8); font-size: 12px; font-weight: 600; }
.radar-note { font-size: 0.74rem; color: var(--text-muted); text-align: center; max-width: 340px; line-height: 1.5; }
</style>
