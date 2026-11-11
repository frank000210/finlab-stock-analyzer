<template>
  <figure class="gfig" data-testid="guide-figure" :data-fig="fig.id">
    <button type="button" class="gfig-frame" :aria-label="`放大圖片：${fig.caption}`" @click="openZoom">
      <img
        :src="fig.src"
        :alt="fig.alt"
        :width="fig.width"
        :height="fig.height"
        loading="lazy"
        decoding="async"
      />
      <span class="gfig-zoom" aria-hidden="true"><ZoomIn :size="14" />點圖放大</span>
    </button>
    <figcaption><span class="gfig-tag">示意圖</span>{{ fig.caption }}</figcaption>

    <dialog ref="dlg" class="gfig-dialog" :aria-label="fig.caption" data-testid="guide-figure-dialog" @click="onBackdrop" @close="zoomed = false">
      <button type="button" class="gfig-close" aria-label="關閉放大圖片" @click="closeZoom"><X :size="18" aria-hidden="true" /></button>
      <p class="gfig-hint">上下左右拖曳可看完整圖</p>
      <div v-if="zoomed" class="gfig-scroll">
        <img :src="fig.src" :alt="fig.alt" :width="fig.width" :height="fig.height" />
      </div>
    </dialog>
  </figure>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { X, ZoomIn } from 'lucide-vue-next'

// fig: { id, src, alt, caption, width, height }（內容見 lib/buildGuideContent.js 的 FIGURES）
defineProps({ fig: { type: Object, required: true } })

const dlg = ref(null)
const zoomed = ref(false)

async function openZoom() {
  zoomed.value = true
  await nextTick()
  // 不支援 <dialog> 的老瀏覽器：退而求其次，直接在新分頁開圖
  if (typeof dlg.value?.showModal !== 'function') { window.open(dlg.value?.querySelector('img')?.src, '_blank', 'noopener'); zoomed.value = false; return }
  dlg.value.showModal()
}
function closeZoom() { dlg.value?.close() }
// 點到對話框本體（暗色背景處）才關；點圖不關，方便在手機上拖曳捲動
function onBackdrop(e) { if (e.target === dlg.value) closeZoom() }
</script>

<style scoped>
.gfig { margin: 0; display: flex; flex-direction: column; gap: 8px; }

/* 圖一律放在淺色底框內：圖是白底設計，深色主題也一樣看得清楚 */
.gfig-frame {
  position: relative;
  display: block;
  width: 100%;
  padding: 10px;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  cursor: zoom-in;
  overflow: hidden;
}
.gfig-frame:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.gfig-frame img { display: block; width: 100%; height: auto; border-radius: 8px; }
.gfig-zoom {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.74rem;
  font-weight: 600;
  color: #1e293b;
  background: color-mix(in srgb, var(--ink) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--well) 14%, transparent);
  border-radius: 999px;
  padding: 3px 10px;
  pointer-events: none;
}

.gfig figcaption { font-size: 0.86rem; line-height: 1.6; color: var(--text-secondary); }
.gfig-tag {
  display: inline-block;
  margin-right: 8px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 1px 8px;
}

.gfig-dialog {
  width: min(96vw, 1400px);
  max-width: none;
  max-height: 94vh;
  /* 全站的 reset 會把 margin 歸零，<dialog> 靠 margin:auto 置中，要自己補回來 */
  margin: auto;
  padding: 0;
  border: 0;
  border-radius: 14px;
  background: #ffffff;
  overflow: hidden;
}
.gfig-dialog::backdrop { background: rgba(2, 6, 23, 0.78); }
.gfig-close {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #1e293b;
  background: color-mix(in srgb, var(--ink) 95%, transparent);
  border: 1px solid color-mix(in srgb, var(--well) 18%, transparent);
  border-radius: 999px;
  cursor: pointer;
}
.gfig-close:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.gfig-scroll { max-height: 94vh; overflow: auto; -webkit-overflow-scrolling: touch; }
.gfig-scroll img { display: block; width: 100%; height: auto; }
.gfig-hint { display: none; }

/* 手機：圖保持可讀的寬度，在對話框內左右上下拖曳 */
@media (max-width: 640px) {
  .gfig-dialog { width: 100vw; height: 100dvh; max-height: 100dvh; border-radius: 0; }
  .gfig-scroll { height: 100dvh; max-height: 100dvh; }
  .gfig-scroll img { width: 960px; max-width: none; }
  .gfig-hint {
    display: block;
    position: absolute;
    left: 10px;
    bottom: 12px;
    z-index: 1;
    margin: 0;
    padding: 4px 12px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #1e293b;
    background: color-mix(in srgb, var(--ink) 94%, transparent);
    border: 1px solid color-mix(in srgb, var(--well) 16%, transparent);
    border-radius: 999px;
    pointer-events: none;
  }
}

@media print {
  .gfig { break-inside: avoid; }
  .gfig-zoom { display: none; }
  .gfig-frame { cursor: default; }
}
</style>
