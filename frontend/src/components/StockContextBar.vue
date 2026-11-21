<template>
  <div class="stock-context-bar" data-testid="stock-context-bar" role="region" aria-label="個股快速切換列">
    <!-- 左側：目前個股 + 快速換股 -->
    <div class="ctx-left">
      <div class="ctx-current" :title="`${activeSymbol}${displayName ? ' ' + displayName : ''}`">
        <span class="ctx-symbol">{{ activeSymbol }}</span>
        <span v-if="displayName" class="ctx-name">{{ displayName }}</span>
      </div>

      <form class="ctx-switch" @submit.prevent="submitSwitch">
        <div class="ctx-switch-wrap">
          <input
            v-model="switchInput"
            type="text"
            class="ctx-switch-input"
            placeholder="快速換股…"
            aria-label="快速換股（輸入代號或名稱）"
            autocomplete="off"
            data-testid="ctx-switch-input"
            @input="onSwitchInput"
            @focus="onSwitchFocus"
            @blur="onSwitchBlur"
            @keydown.down.prevent="moveHighlight(1)"
            @keydown.up.prevent="moveHighlight(-1)"
            @keydown.escape="closeDropdown"
          />
          <button type="submit" class="ctx-switch-btn" aria-label="切換個股" data-testid="ctx-switch-btn">切換</button>

          <ul
            v-if="showSuggestions && suggestions.length"
            class="ctx-dropdown"
            role="listbox"
            aria-label="個股搜尋建議"
          >
            <li
              v-for="(item, idx) in suggestions"
              :key="item.symbol"
              role="option"
              :aria-selected="idx === highlightedIdx"
              :class="{ highlighted: idx === highlightedIdx }"
              @mousedown.prevent="applyStock(item.symbol, item.name_zh || item.name || '')"
            >
              <span class="dd-sym">{{ item.symbol }}</span>
              <span class="dd-name">{{ item.name_zh || item.name || '' }}</span>
            </li>
          </ul>
        </div>
        <span v-if="switchError" class="ctx-switch-error" role="alert">{{ switchError }}</span>
      </form>
    </div>

    <!-- 中間：9 大個股子頁橫向膠囊 -->
    <nav class="ctx-tabs" aria-label="個股分析子頁" data-testid="ctx-subpage-tabs">
      <RouterLink
        v-for="tab in subPages"
        :key="tab.key"
        :to="tab.to(activeSymbol)"
        class="ctx-tab"
        :class="{ active: isActiveTab(tab) }"
        :aria-current="isActiveTab(tab) ? 'page' : undefined"
        :data-subpage="tab.key"
        @click="syncStoreBeforeNav"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <!-- 右側：高頻捷徑 -->
    <div class="ctx-actions">
      <button
        type="button"
        class="ctx-action-btn"
        :class="{ 'is-watched': isWatched }"
        :aria-pressed="isWatched"
        data-testid="ctx-watchlist-btn"
        @click="toggleWatchlist"
      >
        {{ isWatched ? '★ 已追蹤' : '☆ 觀察清單' }}
      </button>
      <RouterLink
        :to="{ name: 'risk-sizing', query: { symbol: activeSymbol } }"
        class="ctx-action-btn"
        data-testid="ctx-risk-sizing-link"
        @click="syncStoreBeforeNav"
      >
        🛡️ 部位試算
      </RouterLink>
      <RouterLink
        :to="{ name: 'price-alerts', query: { symbol: activeSymbol } }"
        class="ctx-action-btn"
        data-testid="ctx-price-alerts-link"
        @click="syncStoreBeforeNav"
      >
        🔔 設價格警報
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { resolveStockName } from '../lib/stockSearch.js'
import {
  addToWatchlist,
  loadWatchlist,
  removeFromWatchlist,
  WATCHLIST_STORAGE_KEY,
} from '../lib/watchlist.js'

const props = defineProps({
  symbol: { type: String, default: '' },
  name: { type: String, default: '' },
})

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const route = useRoute()
const router = useRouter()
const stockStore = useStockStore()

const subPages = [
  { key: 'overview', routeName: 'overview', label: '總覽', to: () => ({ name: 'overview' }) },
  { key: 'analysis', routeName: 'analysis', label: '技術分析', to: (s) => ({ name: 'analysis', params: { symbol: s } }) },
  { key: 'seasonal', routeName: 'seasonal', label: '季節性', to: (s) => ({ name: 'seasonal', params: { symbol: s } }) },
  { key: 'lead-lag', routeName: 'lead-lag', label: '領先落後', to: (s) => ({ name: 'lead-lag', params: { symbol: s } }) },
  { key: 'major-players', routeName: 'major-players', label: '主力', to: (s) => ({ name: 'major-players', params: { symbol: s } }) },
  { key: 'chip', routeName: 'chip', label: '籌碼', to: (s) => ({ name: 'chip', params: { symbol: s } }) },
  { key: 'social-buzz', routeName: 'social-buzz', label: '熱度', to: (s) => ({ name: 'social-buzz', params: { symbol: s } }) },
  { key: 'public-data', routeName: 'public-data', label: '公開資訊', to: (s) => ({ name: 'public-data', params: { symbol: s } }) },
  { key: 'backtest', routeName: 'backtest', label: '回測', to: (s) => ({ name: 'backtest', params: { symbol: s } }) },
]

const activeSymbol = computed(() => {
  const raw = props.symbol || route.params.symbol || stockStore.symbol || '2330'
  return String(raw).trim().toUpperCase() || '2330'
})

const resolvedName = ref('')
const displayName = computed(() => {
  if (props.name) return props.name
  if (resolvedName.value) return resolvedName.value
  if (String(stockStore.symbol || '').trim().toUpperCase() === activeSymbol.value) {
    return stockStore.name || ''
  }
  return ''
})

let nameToken = 0
async function refreshName(sym) {
  const token = ++nameToken
  if (!sym) {
    resolvedName.value = ''
    return
  }
  if (props.name) {
    resolvedName.value = props.name
    return
  }
  if (String(stockStore.symbol || '').trim().toUpperCase() === sym && stockStore.name) {
    resolvedName.value = stockStore.name
    return
  }
  resolvedName.value = ''
  const fetched = await resolveStockName(sym, API_BASE)
  if (token !== nameToken) return
  if (fetched) {
    resolvedName.value = fetched
    if (String(stockStore.symbol || '').trim().toUpperCase() === sym && !stockStore.name) {
      stockStore.setStock(sym, fetched)
    }
  }
}

watch(activeSymbol, (sym) => {
  refreshName(sym)
}, { immediate: true })

function isActiveTab(tab) {
  return route.name === tab.routeName
}

function syncStoreBeforeNav() {
  if (activeSymbol.value) {
    stockStore.setStock(activeSymbol.value, displayName.value || '')
  }
}

// ── 觀察清單同步 ──
const watchlist = ref(loadWatchlist())
const isWatched = computed(() => watchlist.value.includes(activeSymbol.value))

function toggleWatchlist() {
  const sym = activeSymbol.value
  if (!sym) return
  if (isWatched.value) {
    watchlist.value = removeFromWatchlist(sym)
  } else {
    watchlist.value = addToWatchlist(sym)
  }
}

function onStorage(e) {
  if (!e || !e.key || e.key === WATCHLIST_STORAGE_KEY) {
    watchlist.value = loadWatchlist()
  }
}

// ── 快速換股（留在同一子頁） ──
const switchInput = ref('')
const suggestions = ref([])
const showSuggestions = ref(false)
const highlightedIdx = ref(-1)
const switchError = ref('')
let searchTimer = null
let blurTimer = null
let searchSeq = 0

function onSwitchInput() {
  switchError.value = ''
  highlightedIdx.value = -1
  clearTimeout(searchTimer)
  const q = switchInput.value.trim()
  if (!q) {
    suggestions.value = []
    return
  }
  searchTimer = setTimeout(() => fetchSuggestions(q), 200)
}

function onSwitchFocus() {
  clearTimeout(blurTimer)
  showSuggestions.value = true
}

function onSwitchBlur() {
  blurTimer = setTimeout(() => {
    showSuggestions.value = false
  }, 150)
}

function closeDropdown() {
  showSuggestions.value = false
  highlightedIdx.value = -1
}

function moveHighlight(delta) {
  if (!suggestions.value.length) return
  showSuggestions.value = true
  const len = suggestions.value.length
  highlightedIdx.value = (highlightedIdx.value + delta + len) % len
}

async function fetchSuggestions(q) {
  const seq = ++searchSeq
  try {
    const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
    const payload = await resp.json().catch(() => ({}))
    if (seq !== searchSeq) return
    suggestions.value = (payload?.data?.items || payload?.items || []).slice(0, 6)
    showSuggestions.value = true
  } catch {
    if (seq === searchSeq) suggestions.value = []
  }
}

function applyStock(sym, nameZh = '') {
  const normalized = String(sym || '').trim().toUpperCase()
  if (!normalized) return
  switchError.value = ''
  switchInput.value = ''
  suggestions.value = []
  showSuggestions.value = false
  highlightedIdx.value = -1
  stockStore.setStock(normalized, nameZh)

  if (route.name === 'overview') {
    // OverviewView 監聽 stockStore.symbol 自動重載
    return
  }
  const targetName = subPages.some((p) => p.routeName === route.name) ? route.name : 'analysis'
  router.push({ name: targetName, params: { ...route.params, symbol: normalized } })
}

async function submitSwitch() {
  switchError.value = ''
  if (highlightedIdx.value >= 0 && suggestions.value[highlightedIdx.value]) {
    const picked = suggestions.value[highlightedIdx.value]
    applyStock(picked.symbol, picked.name_zh || picked.name || '')
    return
  }
  const q = switchInput.value.trim()
  if (!q) return

  // 合法台股 4~6 碼（含 ETF 英文字尾如 00940B）或美股純英文字母代碼直接切換
  if (/^\d{4,6}[A-Za-z]?$/.test(q) || /^[A-Za-z^][A-Za-z0-9.-]{0,9}$/.test(q)) {
    const upper = q.toUpperCase()
    const hit = suggestions.value.find((i) => String(i.symbol).toUpperCase() === upper)
    applyStock(upper, hit?.name_zh || hit?.name || '')
    return
  }

  // 名稱搜尋：查 API 解析，查無結果不盲導壞頁
  try {
    const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
    const payload = await resp.json().catch(() => ({}))
    const items = payload?.data?.items || payload?.items || []
    const exact = items.find((i) => i.name_zh === q || i.name === q) || items[0]
    if (exact?.symbol) {
      applyStock(exact.symbol, exact.name_zh || exact.name || '')
      return
    }
    switchError.value = `查無「${q}」`
  } catch {
    switchError.value = '搜尋失敗，請輸入代號'
  }
}

onMounted(() => {
  window.addEventListener('storage', onStorage)
})

onBeforeUnmount(() => {
  window.removeEventListener('storage', onStorage)
  clearTimeout(searchTimer)
  clearTimeout(blurTimer)
})
</script>

<style scoped>
.stock-context-bar {
  position: sticky;
  top: 44px;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-radius: var(--radius-lg, 14px);
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(var(--shadow-rgb), 0.14);
}

.ctx-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ctx-current {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.ctx-symbol {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: 800;
  font-size: 0.92rem;
  color: var(--accent-blue);
}

.ctx-name {
  font-size: 0.82rem;
  color: var(--text-secondary);
  font-weight: 600;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ctx-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.ctx-switch-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.ctx-switch-input {
  width: 112px;
  height: 30px;
  padding: 0 8px;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--border-color);
  background: var(--bg-well);
  color: var(--text-primary);
  font-size: 0.8rem;
}

.ctx-switch-input::placeholder {
  color: var(--text-muted);
}

.ctx-switch-btn {
  height: 30px;
  padding: 0 10px;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid color-mix(in srgb, var(--blue) 45%, transparent);
  background: var(--blue-soft);
  color: var(--accent-blue);
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.ctx-switch-btn:hover {
  background: color-mix(in srgb, var(--blue) 22%, transparent);
}

.ctx-switch-error {
  font-size: 0.74rem;
  color: var(--color-up);
  white-space: nowrap;
}

.ctx-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 190px;
  max-width: 260px;
  list-style: none;
  margin: 0;
  padding: 4px;
  border-radius: var(--radius, 10px);
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-md);
  z-index: 200;
}

.ctx-dropdown li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-primary);
}

.ctx-dropdown li:hover,
.ctx-dropdown li.highlighted {
  background: var(--bg-hover);
}

.dd-sym {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--accent-blue);
}

.dd-name {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ctx-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1 1 320px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
  padding: 2px 0;
}

.ctx-tabs::-webkit-scrollbar {
  display: none;
}

.ctx-tab {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-decoration: none;
  border: 1px solid transparent;
  white-space: nowrap;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}

.ctx-tab:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.ctx-tab.active {
  background: linear-gradient(transparent 14%, var(--mark) 14%);
  color: var(--text-primary);
  font-weight: 700;
  border-color: color-mix(in srgb, var(--ink) 22%, transparent);
}

.ctx-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ctx-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.ctx-action-btn:hover {
  background: var(--bg-hover);
  border-color: var(--accent-blue);
}

.ctx-action-btn.is-watched {
  background: var(--warn-soft);
  border-color: color-mix(in srgb, var(--warn) 45%, transparent);
  color: var(--warn);
}

@media (max-width: 900px) {
  .stock-context-bar {
    gap: 8px;
    padding: 8px 10px;
  }
  .ctx-tabs {
    order: 3;
    flex-basis: 100%;
  }
}

@media (max-width: 480px) {
  .ctx-switch-input {
    width: 92px;
  }
  .ctx-action-btn {
    padding: 0 8px;
    font-size: 0.74rem;
  }
}
</style>
