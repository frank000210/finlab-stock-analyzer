<template>
  <div class="page-counter" :class="{ visible: count > 0 }">
    <span class="counter-icon">👁</span>
    <span class="counter-value">{{ formattedCount }}</span>
    <span class="counter-label">次瀏覽</span>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'

const props = defineProps({
  page: { type: String, required: true },
  symbol: { type: String, default: '' },
})

const count = ref(0)

const formattedCount = computed(() => {
  if (count.value >= 1000) return (count.value / 1000).toFixed(1) + 'k'
  return count.value.toString()
})

onMounted(async () => {
  // Track this page view
  try {
    await fetch('/api/v1/analytics/pageview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page: props.page, symbol: props.symbol }),
    })
    // Get updated count
    const res = await fetch(`/api/v1/analytics/pageviews/${encodeURIComponent(props.page)}`)
    const data = await res.json()
    count.value = data?.count || 0
  } catch {}
})
</script>

<style scoped>
.page-counter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-secondary, #8899aa);
  opacity: 0;
  transition: opacity 0.4s ease;
}
.page-counter.visible { opacity: 1; }
.counter-icon { font-size: 11px; }
.counter-value { font-weight: 600; color: var(--text-primary, #e2e8f0); }
</style>
