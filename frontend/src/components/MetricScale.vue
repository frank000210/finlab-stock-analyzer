<template>
  <div class="metric-scale">
    <div class="ms-track">
      <div
        v-for="(z, i) in zoneSegments"
        :key="i"
        class="ms-zone"
        :class="'ms-' + z.tone"
        :style="{ flex: z.span }"
      ></div>
    </div>
    <div class="ms-marker-row">
      <div class="ms-marker" :style="{ left: markerPct + '%' }"></div>
    </div>
    <div class="ms-labels">
      <span class="ms-label ms-label-start">{{ leftLabel ?? formatValue(min) }}</span>
      <span
        v-for="(t, i) in thresholds"
        :key="i"
        class="ms-label ms-label-mid"
        :style="{ left: pct(t.value) + '%' }"
      >{{ t.label }}</span>
      <span class="ms-label ms-label-end">{{ rightLabel ?? formatValue(max) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// 尺標元件：把數值範圍切成低/中/高（或安全/警戒/危險）色塊，標出目前數值位置與
// 門檻標籤。色塊寬度依門檻值本身的比例分配，不是均分——這樣尺標上的位置才跟
// 數字本身的意義一致（例如熔斷門檻在尺標上真的比較靠右）。
// tone 刻意不沿用 theme.up/theme.down：本站那兩個變數綁的是「股價漲跌」配色
// （漲=紅、跌=綠，台股慣例），套到風險安全/危險語境會恰好顏色相反、更誤導，
// 所以這裡用獨立的 good/warn/bad 三色，語意上跟股價方向脫鉤。
const props = defineProps({
  min: { type: Number, required: true },
  max: { type: Number, required: true },
  value: { type: Number, required: true },
  // 依 min→max 順序描述每一段色塊：[{ to: Number, tone: 'good'|'warn'|'bad' }]
  // 最後一段的 to 應等於 max。
  zones: { type: Array, required: true },
  // 尺標下方要標的門檻刻度：[{ value: Number, label: String }]
  thresholds: { type: Array, default: () => [] },
  leftLabel: { type: String, default: null },
  rightLabel: { type: String, default: null },
  decimals: { type: Number, default: 0 },
})

function pct(v) {
  const clamped = Math.min(props.max, Math.max(props.min, v))
  return ((clamped - props.min) / (props.max - props.min)) * 100
}

function formatValue(v) {
  return Number(v).toFixed(props.decimals)
}

const markerPct = computed(() => pct(props.value))

const zoneSegments = computed(() => {
  let prev = props.min
  return props.zones.map((z) => {
    const span = Math.max(0, z.to - prev)
    prev = z.to
    return { span: span || 0.0001, tone: z.tone }
  })
})
</script>

<style scoped>
.metric-scale { display: flex; flex-direction: column; gap: 4px; }
.ms-track { display: flex; height: 8px; border-radius: 4px; overflow: hidden; }
.ms-zone { }
.ms-zone.ms-good { background: #10b981; }
.ms-zone.ms-warn { background: var(--color-warning, #f59e0b); }
.ms-zone.ms-bad { background: #ef4444; }

.ms-marker-row { position: relative; height: 10px; }
.ms-marker {
  position: absolute;
  top: -14px;
  width: 2px;
  height: 14px;
  background: var(--text-primary);
  transform: translateX(-1px);
}
.ms-marker::after {
  content: '';
  position: absolute;
  top: 12px;
  left: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-primary);
}

.ms-labels { position: relative; height: 14px; font-size: 0.68rem; color: var(--text-muted); }
.ms-label { position: absolute; white-space: nowrap; }
.ms-label-start { left: 0; }
.ms-label-end { right: 0; }
.ms-label-mid { transform: translateX(-50%); }
</style>
