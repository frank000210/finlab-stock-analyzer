<template>
  <div class="watchlist-page">
    <PageFocusBanner text="集中管理你的觀察清單：新增/移除/排序/分組，這份清單是作戰台、訊號掃描、投組風控共用的同一份。" />

    <section class="card add-card">
      <div class="add-row">
        <div class="search-shell">
          <input
            v-model="searchInput"
            type="text"
            class="inp"
            placeholder="輸入代碼或公司名稱，例如 2330 / 台積電"
            @keydown.enter.prevent="submitSearchInput"
          />
          <ul v-if="searchResults.length" class="search-dropdown" role="listbox">
            <li
              v-for="item in searchResults"
              :key="item.symbol"
              role="option"
              tabindex="0"
              @click="addSymbol(item.symbol)"
              @keydown.enter.prevent="addSymbol(item.symbol)"
            >
              <strong>{{ item.symbol }}</strong>
              <span>{{ item.name }}</span>
            </li>
          </ul>
        </div>
        <button class="btn btn-primary" type="button" @click="submitSearchInput">加入</button>
      </div>
      <p class="muted small">清單儲存在本機瀏覽器，作戰台/訊號掃描/投組風控會直接讀取這份清單。</p>
    </section>

    <section class="card list-card">
      <div class="section-head compact">
        <div>
          <h2>觀察清單（{{ items.length }} 檔）</h2>
        </div>
        <div class="head-actions">
          <select v-model="groupFilter" class="inp xs-select" aria-label="依分組篩選">
            <option value="">全部分組</option>
            <option v-for="g in groupOptions" :key="g" :value="g">{{ g }}</option>
          </select>
          <button v-if="items.length" class="btn xs" type="button" @click="refreshPrices" :disabled="pricesLoading">
            <span v-if="pricesLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>重新整理報價
          </button>
        </div>
      </div>

      <div v-if="!items.length" class="empty-state">尚未加入任何股票，從上方搜尋新增。</div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr><th></th><th>代碼</th><th>名稱</th><th>股價</th><th>分組</th><th>備註</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="(symbol, idx) in filteredItems" :key="symbol">
              <td class="reorder-cell">
                <button class="icon-btn" type="button" :disabled="idx === 0" aria-label="上移" @click="moveUp(symbol)">▲</button>
                <button class="icon-btn" type="button" :disabled="idx === filteredItems.length - 1" aria-label="下移" @click="moveDown(symbol)">▼</button>
              </td>
              <td>
                <router-link :to="`/stocks/${symbol}`" class="symbol-link"><strong>{{ symbol }}</strong></router-link>
              </td>
              <td>{{ names[symbol] || '—' }}</td>
              <td>
                <span v-if="prices[symbol]?.price != null">{{ prices[symbol].price }}</span>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <input
                  class="inp xs-input"
                  :value="meta[symbol]?.group || ''"
                  placeholder="分組"
                  @change="e => updateMeta(symbol, { group: e.target.value.trim() })"
                />
              </td>
              <td>
                <input
                  class="inp xs-input note-input"
                  :value="meta[symbol]?.note || ''"
                  placeholder="備註（選填）"
                  @change="e => updateMeta(symbol, { note: e.target.value.trim() })"
                />
              </td>
              <td>
                <button class="icon-btn danger" type="button" :aria-label="`移除 ${symbol}`" @click="removeSymbol(symbol)">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { resolveStockName } from '../lib/stockSearch'
import { fetchLivePrices } from '../lib/livePriceCache'
import {
  loadWatchlist, addToWatchlist, removeFromWatchlist, reorderWatchlist,
  loadWatchlistMeta, setWatchlistMeta,
} from '../lib/watchlist'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const items = ref(loadWatchlist())
const meta = ref(loadWatchlistMeta())
const names = ref({})
const prices = ref({})
const pricesLoading = ref(false)
const searchInput = ref('')
const searchResults = ref([])
const groupFilter = ref('')

const groupOptions = computed(() => {
  const set = new Set()
  for (const s of items.value) {
    const g = meta.value[s]?.group
    if (g) set.add(g)
  }
  return [...set].sort()
})

const filteredItems = computed(() => {
  if (!groupFilter.value) return items.value
  return items.value.filter(s => (meta.value[s]?.group || '') === groupFilter.value)
})

async function searchStocks(query) {
  if (!query || query.trim().length < 1) {
    searchResults.value = []
    return
  }
  try {
    const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(query.trim())}`)
    const payload = await resp.json().catch(() => ({}))
    const list = payload?.data?.items || []
    searchResults.value = list
      .filter(it => !items.value.includes(String(it.symbol).toUpperCase()))
      .slice(0, 8)
      .map(it => ({ symbol: it.symbol, name: it.name_zh || it.name || '' }))
  } catch {
    searchResults.value = []
  }
}

let searchTimer = null
watch(searchInput, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => searchStocks(value), 250)
})

function submitSearchInput() {
  const query = searchInput.value.trim()
  if (!query) return
  const exact = searchResults.value.find(it => it.symbol.toUpperCase() === query.toUpperCase())
  addSymbol(exact ? exact.symbol : query)
}

async function addSymbol(symbol) {
  const sym = String(symbol || '').trim().toUpperCase()
  if (!sym) return
  items.value = addToWatchlist(sym)
  searchInput.value = ''
  searchResults.value = []
  if (!names.value[sym]) {
    const name = await resolveStockName(sym, API_BASE)
    if (name) names.value = { ...names.value, [sym]: name }
  }
  refreshPrices()
}

function removeSymbol(symbol) {
  items.value = removeFromWatchlist(symbol)
  meta.value = loadWatchlistMeta()
}

function moveUp(symbol) {
  const idx = items.value.indexOf(symbol)
  if (idx > 0) items.value = reorderWatchlist(idx, idx - 1)
}

function moveDown(symbol) {
  const idx = items.value.indexOf(symbol)
  if (idx >= 0 && idx < items.value.length - 1) items.value = reorderWatchlist(idx, idx + 1)
}

function updateMeta(symbol, patch) {
  meta.value = setWatchlistMeta(symbol, patch)
}

async function loadNames() {
  const missing = items.value.filter(s => !names.value[s])
  await Promise.all(missing.map(async (s) => {
    const name = await resolveStockName(s, API_BASE)
    if (name) names.value = { ...names.value, [s]: name }
  }))
}

async function refreshPrices() {
  if (!items.value.length) return
  pricesLoading.value = true
  try {
    const result = await fetchLivePrices(items.value, API_BASE)
    const next = {}
    for (const [sym, v] of Object.entries(result)) {
      next[sym] = { price: v.price }
    }
    prices.value = next
  } finally {
    pricesLoading.value = false
  }
}

function onStorageChange(e) {
  if (e.key && e.key !== 'finlab_watchlist') return
  items.value = loadWatchlist()
  meta.value = loadWatchlistMeta()
  loadNames()
}

onMounted(() => {
  loadNames()
  refreshPrices()
  window.addEventListener('storage', onStorageChange)
})
onBeforeUnmount(() => window.removeEventListener('storage', onStorageChange))
</script>

<style scoped>
.watchlist-page { display: flex; flex-direction: column; gap: 16px; }
.add-card { display: flex; flex-direction: column; gap: 8px; }
.add-row { display: flex; gap: 8px; align-items: flex-start; }
.search-shell { position: relative; flex: 1; }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); width: 100%; }
.search-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 20;
  background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 10px;
  list-style: none; margin: 0; padding: 4px; max-height: 260px; overflow-y: auto;
}
.search-dropdown li { display: flex; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.search-dropdown li:hover, .search-dropdown li:focus { background: var(--bg-well, rgba(148,163,184,0.1)); outline: none; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.list-card { display: flex; flex-direction: column; gap: 10px; }
.head-actions { display: flex; align-items: center; gap: 8px; }
.xs-select { padding: 6px 8px; font-size: 0.8rem; width: auto; }
.empty-state { color: var(--text-secondary); padding: 20px 0; text-align: center; }

.reorder-cell { display: flex; flex-direction: column; gap: 2px; }
.icon-btn { border: 1px solid var(--border-color); background: var(--bg-secondary); border-radius: 6px; width: 24px; height: 22px; cursor: pointer; color: var(--text-secondary); font-size: 0.7rem; line-height: 1; }
.icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.icon-btn.danger { color: #ef4444; border-color: rgba(239,68,68,0.35); }
.symbol-link { color: var(--accent-blue); text-decoration: none; }
.xs-input { padding: 5px 8px; font-size: 0.8rem; }
.note-input { min-width: 140px; }
.up { color: var(--color-up, #10b981); }
.down { color: var(--color-down, #ef4444); }
</style>
