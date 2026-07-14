<template>
  <span class="info-tip" ref="rootEl">
    <button
      type="button"
      class="info-tip-btn"
      :aria-label="`說明：${label || ''}`"
      :aria-expanded="open"
      @click.stop="toggle"
    >ⓘ</button>
    <div v-if="open" class="info-tip-pop" role="tooltip" @click.stop>
      <strong v-if="label" class="info-tip-label">{{ label }}</strong>
      <p class="info-tip-text">{{ text }}</p>
    </div>
  </span>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

// 點擊展開（不只 hover）才能在手機上也看得到說明——原生 title 屬性在觸控裝置上
// 不會觸發，這是本站唯一用 JS 控制開合的說明元件，其餘靜態徽章仍用 title。
defineProps({
  label: { type: String, default: '' },
  text: { type: String, required: true },
})

const open = ref(false)
const rootEl = ref(null)

function toggle() {
  open.value = !open.value
}

function onDocClick(e) {
  if (open.value && rootEl.value && !rootEl.value.contains(e.target)) {
    open.value = false
  }
}

document.addEventListener('click', onDocClick)
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.info-tip { position: relative; display: inline-flex; }
.info-tip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: none;
  background: var(--bg-tertiary);
  color: var(--text-muted);
  font-size: 0.68rem;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}
.info-tip-btn:hover, .info-tip-btn[aria-expanded="true"] {
  background: var(--accent-blue);
  color: #fff;
}
.info-tip-pop {
  position: absolute;
  z-index: 40;
  top: calc(100% + 6px);
  left: 0;
  width: 240px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm, 10px);
  padding: 10px 12px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}
.info-tip-label { display: block; font-size: 0.78rem; color: var(--text-primary); margin-bottom: 4px; }
.info-tip-text { margin: 0; font-size: 0.76rem; line-height: 1.5; color: var(--text-secondary); }

@media (max-width: 480px) {
  .info-tip-pop { width: 200px; }
}
</style>
