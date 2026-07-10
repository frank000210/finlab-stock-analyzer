<template>
  <span v-if="asOf" class="lineage" :class="{ warn: isStale }" :title="titleText">
    📅 {{ asOf }}<template v-if="sourceLabel"> · {{ sourceLabel }}</template>
    <template v-if="isStale"> ⚠ 可能未更新</template>
  </span>
</template>

<script setup>
import { computed } from 'vue'

// 資料血統徽章（A2）：資料日 + 來源 + 新鮮度。
// 過期判定：資料日落後今天超過 1 個「營業日」（跳過週末；不處理台股假日，
// 假日誤報寧可偏保守——這是提醒，不是斷言）。
const props = defineProps({
  asOf: { type: String, default: '' },
  source: { type: String, default: '' },
})

const sourceLabel = computed(() => {
  if (props.source === 'finmind') return 'FinMind'
  if (props.source === 'yfinance') return 'Yahoo備援'
  if (props.source === 'cache') return '快取'
  return ''
})

const isStale = computed(() => {
  if (!props.asOf) return false
  const d = new Date(props.asOf + 'T00:00:00')
  if (isNaN(d.getTime())) return false
  let biz = 0
  const cur = new Date()
  cur.setHours(0, 0, 0, 0)
  while (cur > d && biz <= 2) {
    cur.setDate(cur.getDate() - 1)
    const dow = cur.getDay()
    if (dow !== 0 && dow !== 6) biz += 1
  }
  return biz > 1
})

const titleText = computed(() => {
  const src = sourceLabel.value ? `來源：${sourceLabel.value}` : ''
  return isStale.value
    ? `資料日 ${props.asOf} 已落後超過 1 個營業日，數字可能過期。${src}`
    : `資料日 ${props.asOf}。${src}`
})
</script>

<style scoped>
.lineage {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 2px 9px;
  white-space: nowrap;
}
.lineage.warn {
  color: #f59e0b;
  border-color: rgba(245, 158, 11, 0.5);
  background: rgba(245, 158, 11, 0.08);
}
</style>
