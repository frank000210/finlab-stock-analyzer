<template>
  <Teleport to="body">
    <div v-if="open" class="qs-backdrop" @click.self="close" role="dialog" aria-label="快速切換">
      <div class="qs-panel">
        <input
          ref="inputEl"
          v-model="query"
          class="qs-input"
          placeholder="輸入頁面名稱或股票代號/名稱…（↑↓ 選擇、Enter 前往、Esc 關閉）"
          @keydown.down.prevent="move(1)"
          @keydown.up.prevent="move(-1)"
          @keydown.enter.prevent="go(activeIndex)"
          @keydown.esc.prevent="close"
        />
        <div class="qs-list" v-if="results.length">
          <div
            v-for="(item, i) in results"
            :key="item.key"
            class="qs-item"
            :class="{ active: i === activeIndex }"
            @mouseenter="activeIndex = i"
            @mousedown.prevent="go(i)"
          >
            <span class="qs-icon">{{ item.icon }}</span>
            <span class="qs-main">{{ item.title }}</span>
            <span class="qs-sub">{{ item.sub }}</span>
          </div>
        </div>
        <div v-else-if="query" class="qs-empty">查無「{{ query }}」——試試頁面名稱（作戰台、日誌…）或股票代號/名稱。</div>
        <div v-else class="qs-hint">頁面：作戰台、訊號、交易日誌、投組風險…　個股：輸入代號或名稱</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const router = useRouter()

const open = ref(false)
const query = ref('')
const activeIndex = ref(0)
const inputEl = ref(null)
const stockHits = ref([])
let debounceTimer = null

// 頁面捷徑（含常用別名，全部可被查詢命中）
const PAGES = [
  { icon: '⚡', title: '作戰台', sub: '/command', to: '/command', alias: 'command 作戰 儀表板' },
  { icon: '📡', title: '訊號', sub: '/signals', to: '/signals', alias: 'signals 觀察清單訊號' },
  { icon: '📓', title: '交易日誌', sub: '/journal', to: '/journal', alias: 'journal 日誌 複盤' },
  { icon: '🔥', title: '投組風險', sub: '/portfolio-heat', to: '/portfolio-heat', alias: 'portfolio heat 熱度 組合' },
  { icon: '🛡️', title: '部位風控', sub: '/risk-sizing', to: '/risk-sizing', alias: 'risk sizing 凱利 部位' },
  { icon: '🎯', title: '決策面板', sub: '/decision', to: '/decision', alias: 'decision 決策' },
  { icon: '🕸️', title: '關聯圖', sub: '/graph', to: '/graph', alias: 'graph 關聯' },
  { icon: '🔄', title: '類股輪動', sub: '/rotation', to: '/rotation', alias: 'rotation 輪動 rrg' },
  { icon: '🎲', title: '蒙地卡羅', sub: '/monte-carlo', to: '/monte-carlo', alias: 'monte carlo 破產 模擬' },
  { icon: '📊', title: '總覽', sub: '/overview', to: '/overview', alias: 'overview 總覽' },
  { icon: '🚀', title: '新手上路', sub: '/guide', to: '/guide', alias: 'guide 導覽 教學' },
  { icon: '⚙️', title: '設定', sub: '/settings', to: '/settings', alias: 'settings 設定' },
]

const pageHits = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return PAGES.slice(0, 6)
  return PAGES.filter(p => (p.title + ' ' + p.sub + ' ' + p.alias).toLowerCase().includes(q))
})

const results = computed(() => {
  const pages = pageHits.value.map(p => ({ key: 'p:' + p.to, icon: p.icon, title: p.title, sub: p.sub, to: p.to }))
  const stocks = stockHits.value.map(s => ({
    key: 's:' + s.symbol, icon: '📈',
    title: `${s.symbol} ${s.name_zh || ''}`.trim(),
    sub: s.industry || '個股分析', to: `/stocks/${s.symbol}`,
  }))
  return [...pages, ...stocks].slice(0, 12)
})

watch(query, (q) => {
  activeIndex.value = 0
  clearTimeout(debounceTimer)
  const term = q.trim()
  if (!term || !/[0-9a-zA-Z一-鿿]/.test(term)) { stockHits.value = []; return }
  debounceTimer = setTimeout(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(term)}`)
      const payload = await resp.json().catch(() => ({}))
      stockHits.value = (payload?.data?.items || []).slice(0, 8)
    } catch { stockHits.value = [] }
  }, 250)
})

function move(step) {
  const n = results.value.length
  if (!n) return
  activeIndex.value = (activeIndex.value + step + n) % n
}

function go(i) {
  const item = results.value[i]
  if (!item) return
  close()
  router.push(item.to)
}

function openPanel() {
  open.value = true
  query.value = ''
  stockHits.value = []
  activeIndex.value = 0
  nextTick(() => inputEl.value?.focus())
}

function close() { open.value = false }

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    open.value ? close() : openPanel()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

defineExpose({ openPanel })
</script>

<style scoped>
.qs-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(2, 6, 23, 0.6);
  backdrop-filter: blur(2px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 14vh;
}
.qs-panel {
  width: min(560px, 92vw);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}
.qs-input {
  width: 100%;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  padding: 14px 16px;
  font-size: 0.95rem;
  border-bottom: 1px solid var(--border-color);
}
.qs-list { max-height: 46vh; overflow-y: auto; padding: 6px; }
.qs-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 9px;
  cursor: pointer;
  font-size: 0.88rem;
}
.qs-item.active { background: rgba(99, 102, 241, 0.16); }
.qs-icon { width: 22px; text-align: center; }
.qs-main { font-weight: 600; }
.qs-sub { margin-left: auto; color: var(--text-muted); font-size: 0.74rem; }
.qs-empty, .qs-hint { padding: 14px 16px; color: var(--text-muted); font-size: 0.82rem; }
</style>
