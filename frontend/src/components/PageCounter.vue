<template>
  <div class="page-counter" :class="{ visible: count > 0 }">
    <span class="counter-icon">👁</span>
    <span class="counter-value">{{ formattedCount }}</span>
    <span class="counter-label">次瀏覽</span>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'

const props = defineProps({
  page: { type: String, required: true },
  symbol: { type: String, default: '' },
})

const count = ref(0)

const formattedCount = computed(() => {
  if (count.value >= 1000) return (count.value / 1000).toFixed(1) + 'k'
  return count.value.toString()
})

async function trackPage(page, symbol) {
  if (!page) return
  try {
    await fetch('/api/v1/analytics/pageview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page, symbol }),
    })
    // Get updated count
    const res = await fetch(`/api/v1/analytics/pageviews/${encodeURIComponent(page)}`)
    const data = await res.json()
    count.value = data?.count || 0
  } catch {}
}

onMounted(() => {
  trackPage(props.page, props.symbol)
})

// This component lives once in App.vue outside <router-view>, so it never
// unmounts/remounts as the user navigates the SPA -- onMounted alone only
// ever recorded the very first page of a session (every other page's
// count stayed at 0 forever). Watching the page prop re-tracks on every
// route change so each page actually gets its own counter.
watch(
  () => props.page,
  (newPage, oldPage) => {
    if (newPage && newPage !== oldPage) {
      count.value = 0
      trackPage(newPage, props.symbol)
    }
  }
)
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
