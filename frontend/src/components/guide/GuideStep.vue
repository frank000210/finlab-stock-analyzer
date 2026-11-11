<template>
  <article :id="step.id" class="gstep" :class="{ done }" data-testid="guide-step">
    <header class="gstep-head">
      <span class="gstep-no">步驟 {{ index + 1 }}</span>
      <h3>{{ step.title }}</h3>
      <label class="gstep-check">
        <input
          type="checkbox"
          :checked="done"
          :data-testid="`check-${step.id}`"
          :aria-label="`標記完成：${step.title}`"
          @change="$emit('toggle', step.id)"
        />
        <span>做完了</span>
      </label>
    </header>

    <p v-if="step.who" class="gstep-who"><User :size="14" aria-hidden="true" /><span>{{ step.who }}</span></p>

    <ol class="gstep-list">
      <li v-for="(t, i) in step.items" :key="i" v-html="richText(t)"></li>
    </ol>

    <p v-if="step.see" class="gstep-note see"><Eye :size="15" aria-hidden="true" /><span><b>你會看到：</b>{{ step.see }}</span></p>
    <p v-if="step.why" class="gstep-note why"><Info :size="15" aria-hidden="true" /><span><b>為什麼：</b>{{ step.why }}</span></p>
    <p v-if="step.warn" class="gstep-note warn"><TriangleAlert :size="15" aria-hidden="true" /><span>{{ step.warn }}</span></p>
  </article>
</template>

<script setup>
import { Eye, Info, TriangleAlert, User } from 'lucide-vue-next'
import { richText } from '../../lib/guideText.js'

defineProps({
  step: { type: Object, required: true },
  index: { type: Number, default: 0 },
  done: { type: Boolean, default: false },
})
defineEmits(['toggle'])
</script>

<style scoped>
.gstep {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scroll-margin-top: 16px;
}
.gstep.done { opacity: 0.72; }
.gstep.done h3 { text-decoration: line-through; text-decoration-color: var(--text-muted); }

.gstep-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.gstep-head h3 { margin: 0; flex: 1; min-width: 0; font-size: 1.05rem; }
.gstep-no {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--accent-blue);
  background: color-mix(in srgb, var(--blue) 12%, transparent);
  border-radius: 999px;
  padding: 2px 10px;
  white-space: nowrap;
}
.gstep-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
}
.gstep-check input { width: 18px; height: 18px; accent-color: var(--accent-blue); cursor: pointer; }
.gstep-check input:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }

.gstep-who {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.gstep-who svg { flex: none; margin-top: 3px; }

.gstep-list { margin: 0; padding-left: 1.3em; display: flex; flex-direction: column; gap: 6px; }
.gstep-list li { line-height: 1.7; color: var(--text-secondary); font-size: 0.93rem; }
.gstep-list :deep(strong) { color: var(--text-primary); }
.gstep-list :deep(code) {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.85em;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  border-radius: 5px;
  padding: 1px 6px;
  word-break: break-all;
}
.gstep-list :deep(a) { color: var(--accent-blue); text-decoration: underline; text-underline-offset: 2px; }

.gstep-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 0.86rem;
  line-height: 1.6;
}
.gstep-note svg { flex: none; margin-top: 3px; }
.gstep-note b { color: var(--text-primary); }
.gstep-note.see { background: color-mix(in srgb, var(--down) 10%, transparent); color: var(--text-secondary); }
.gstep-note.see svg { color: var(--color-down); }
.gstep-note.why { background: color-mix(in srgb, var(--blue) 10%, transparent); color: var(--text-secondary); }
.gstep-note.why svg { color: var(--accent-blue); }
.gstep-note.warn { background: color-mix(in srgb, var(--warn) 12%, transparent); color: var(--text-secondary); }
.gstep-note.warn svg { color: var(--color-warning); }

@media print {
  .gstep { break-inside: avoid; opacity: 1; }
  .gstep-check { display: none; }
}
</style>
