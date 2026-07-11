<template>
  <div ref="host" class="tv-host">
    <p v-if="failed" class="tv-fallback">TradingView 圖表載入失敗（可能離線或外部資源被封鎖），請切回內建圖表。</p>
  </div>
</template>

<script setup>
// D1 TradingView Advanced Chart 官方嵌入：widget 自帶資料源與全套指標/畫線
// 工具，圖表瀏覽不消耗 FinMind 額度。注意它是黑盒子——資料拿不出來，所有
// 下游計算（風控/評分/回測）仍走自家資料管線；離線 PWA 模式下載不進來，
// 因此只作為選用模式，內建 lightweight-charts 仍是預設。
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { toTvSymbol } from '../lib/tradingview'

const props = defineProps({ symbol: { type: String, required: true } })
const host = ref(null)
const failed = ref(false)

function render() {
  const el = host.value
  if (!el) return
  el.querySelectorAll('.tv-widget').forEach(n => n.remove())
  failed.value = false
  const container = document.createElement('div')
  container.className = 'tv-widget tradingview-widget-container'
  const inner = document.createElement('div')
  inner.className = 'tradingview-widget-container__widget'
  container.appendChild(inner)
  // 版權連結為 TradingView 嵌入授權條款要求，不可移除。
  const copyright = document.createElement('div')
  copyright.className = 'tradingview-widget-copyright'
  copyright.innerHTML = '<a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">TradingView</a>'
  container.appendChild(copyright)
  const script = document.createElement('script')
  script.type = 'text/javascript'
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
  script.async = true
  script.onerror = () => { failed.value = true }
  script.innerHTML = JSON.stringify({
    symbol: toTvSymbol(props.symbol),
    interval: 'D',
    theme: 'dark',
    locale: 'zh_TW',
    autosize: true,
    allow_symbol_change: false,
    withdateranges: true,
  })
  container.appendChild(script)
  el.appendChild(container)
}

onMounted(render)
watch(() => props.symbol, render)
onBeforeUnmount(() => { host.value?.querySelectorAll('.tv-widget').forEach(n => n.remove()) })
</script>

<style scoped>
.tv-host {
  width: 100%;
  height: 560px;
  border-radius: 12px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.tv-host :deep(.tradingview-widget-container),
.tv-host :deep(iframe) { width: 100%; height: 100%; }
.tv-fallback { color: var(--text-muted); padding: 16px; font-size: 0.85rem; }

@media (max-width: 640px) {
  .tv-host { height: 420px; }
}
@media (max-width: 420px) {
  .tv-host { height: 340px; }
}
</style>
