<template>
  <div class="theme-picker" ref="root" data-testid="theme-picker">
    <button
      type="button"
      class="tp-btn"
      data-testid="theme-picker-btn"
      aria-haspopup="listbox"
      :aria-expanded="open ? 'true' : 'false'"
      aria-label="選擇色彩主題"
      @click="toggle"
    >
      <span class="tp-dots" aria-hidden="true">
        <i v-for="(c, i) in current.swatch" :key="i" :style="{ background: c }"></i>
      </span>
      <span class="tp-name">{{ current.name }}</span>
      <span class="tp-caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="tp-menu" role="listbox" aria-label="色彩主題" data-testid="theme-picker-menu">
      <p class="tp-title">色彩主題</p>
      <button
        v-for="t in themes"
        :key="t.id"
        type="button"
        class="tp-item"
        role="option"
        :aria-selected="t.id === state.id ? 'true' : 'false'"
        :class="{ on: t.id === state.id }"
        :data-theme-id="t.id"
        @click="pick(t.id)"
      >
        <span class="tp-swatch" aria-hidden="true">
          <i v-for="(c, i) in t.swatch" :key="i" :style="{ background: c }"></i>
        </span>
        <span class="tp-label">
          <strong>{{ t.name }}</strong>
          <small>{{ t.hint }}</small>
        </span>
        <span class="tp-check" aria-hidden="true">{{ t.id === state.id ? '✓' : '' }}</span>
      </button>
      <label class="tp-rough">
        <input type="checkbox" :checked="state.rough" data-testid="theme-rough" @change="setRough($event.target.checked)" />
        手繪線條（卡片邊框微微抖動）
      </label>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useColorTheme } from '../lib/colorThemes.js'

const { state, themes, setTheme, setRough } = useColorTheme()
const current = computed(() => themes.find((t) => t.id === state.id) || themes[0])

const open = ref(false)
const root = ref(null)

function toggle() { open.value = !open.value }
function close() { open.value = false }
function pick(id) {
  setTheme(id)
  close()
}

function onDocClick(e) {
  if (open.value && root.value && !root.value.contains(e.target)) close()
}
function onKey(e) {
  if (e.key === 'Escape' && open.value) close()
}
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.theme-picker { position: relative; display: inline-block; pointer-events: auto; }

/* 便利貼：黃色紙片、微微傾斜，貼在頁面右上角（風格 7） */
.tp-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 12px 6px 10px;
  background: var(--sticky); color: var(--sticky-ink);
  border: none; border-radius: 3px;
  font: inherit; font-size: 0.84rem; font-weight: 700; cursor: pointer;
  transform: rotate(1.6deg);
  box-shadow: 0 2px 3px rgba(var(--shadow-rgb), 0.18), 0 8px 14px rgba(var(--shadow-rgb), 0.16);
  transition: transform 0.15s;
}
.tp-btn:hover { transform: rotate(0deg) translateY(-1px); }
.tp-dots { display: inline-flex; }
.tp-dots i { width: 12px; height: 12px; border-radius: 50%; border: 1.5px solid var(--sticky-ink); margin-left: -4px; }
.tp-dots i:first-child { margin-left: 0; }
.tp-caret { font-size: 0.7rem; }

.tp-menu {
  position: absolute; right: 0; top: calc(100% + 8px); z-index: 600;
  width: 262px; padding: 10px;
  background: var(--card); color: var(--ink);
  border: 2px solid var(--ink-2); border-radius: 12px 16px 10px 14px / 14px 10px 16px 12px;
  box-shadow: 0 12px 30px rgba(var(--shadow-rgb), 0.3);
}
.tp-title { margin: 0 4px 6px; font-family: var(--font-kai); font-weight: 700; color: var(--heading); font-size: 0.95rem; }
.tp-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 7px 8px; margin-bottom: 2px;
  background: transparent; color: var(--ink); border: 1.5px solid transparent; border-radius: 9px;
  font: inherit; text-align: left; cursor: pointer;
}
.tp-item:hover { background: var(--bg-hover); }
.tp-item.on { border-color: var(--ink-2); background: linear-gradient(transparent 15%, var(--mark) 15%); }
.tp-swatch { display: inline-flex; flex: none; border: 1.5px solid var(--ink-2); border-radius: 6px; overflow: hidden; }
.tp-swatch i { width: 16px; height: 22px; display: block; }
.tp-label { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
.tp-label strong { font-size: 0.88rem; }
.tp-label small { font-size: 0.72rem; color: var(--muted); }
.tp-check { width: 1em; text-align: center; font-weight: 800; color: var(--heading); }
.tp-rough {
  display: flex; align-items: center; gap: 8px; margin: 8px 4px 2px; padding-top: 8px;
  border-top: 1.5px dashed var(--border-color); font-size: 0.78rem; color: var(--ink-2); cursor: pointer;
}
.tp-rough input { accent-color: var(--accent-blue); width: 15px; height: 15px; }

@media (max-width: 480px) {
  .tp-name { display: none; }
  .tp-btn { padding: 7px 10px; }
}
</style>
