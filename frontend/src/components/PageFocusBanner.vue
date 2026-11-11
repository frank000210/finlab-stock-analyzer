<template>
  <div class="page-focus-banner" v-if="text">
    <span class="focus-label">🎯 觀測重點</span>
    <span class="focus-text">{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: '',
  },
})
</script>

<style scoped>
.page-focus-banner {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.55rem 0.9rem;
  margin-bottom: 0.9rem;
  background: var(--accent-blue-soft, color-mix(in srgb, var(--blue) 8%, transparent));
  border-left: 3px solid var(--accent-blue, var(--blue));
  border-radius: 6px;
  font-size: 0.85rem;
  line-height: 1.5;
}

.focus-label {
  font-weight: 700;
  color: var(--accent-blue, var(--blue));
  white-space: nowrap;
}

.focus-text {
  color: var(--text-secondary, #55606e);
}
</style>
