<template>
  <div v-if="mobileOpen" class="sidebar-backdrop" @click="closeMobile"></div>

  <aside class="app-sidebar" :class="{ collapsed, 'mobile-open': mobileOpen }">
    <div class="sidebar-header">
      <router-link to="/" class="sidebar-logo" @click="closeMobile">
        <Diamond :size="18" class="logo-icon" />
        <span class="logo-text" v-if="showFull">FinLab</span>
      </router-link>
      <button class="collapse-btn" @click="toggleCollapsed" :title="collapsed ? '展開選單' : '收合選單'" aria-label="收合/展開選單">
        <ChevronRight v-if="collapsed" :size="14" />
        <ChevronLeft v-else :size="14" />
      </button>
    </div>

    <div class="sidebar-search">
      <button
        v-if="!showFull"
        type="button"
        class="sidebar-search-collapsed-btn"
        data-testid="sidebar-collapsed-search"
        title="搜尋個股／跳頁 (Ctrl+K)"
        aria-label="搜尋個股或跳頁"
        @click="openQuickSwitcher"
      >
        <Search :size="16" />
      </button>
      <template v-else>
        <div class="search-box">
          <Search :size="15" class="search-icon" />
          <input
            v-model="query"
            class="sidebar-search-input"
            placeholder="搜尋股票代號或名稱…"
            @input="onInput"
            @keyup.enter="onEnter"
            @focus="showResults = true"
            @blur="onBlur"
          />
        </div>
        <ul v-if="showResults && results.length" class="sidebar-search-dropdown">
          <li v-for="item in results" :key="item.symbol" @mousedown="selectStock(item)">
            <span class="r-symbol">{{ item.symbol }}</span>
            <span class="r-name">{{ item.name_zh }}</span>
          </li>
        </ul>
      </template>
    </div>

    <router-link
      v-if="showFull"
      :to="`/stocks/${stockStore.symbol}`"
      class="sidebar-current"
      :title="`目前個股：${stockStore.symbol} ${stockStore.name}`"
      @click="closeMobile"
    >
      <span class="cur-label">目前個股</span>
      <span class="cur-value">{{ stockStore.symbol }}<small v-if="stockStore.name"> {{ stockStore.name }}</small></span>
    </router-link>

    <nav class="sidebar-nav">
      <!-- T-026: ⭐ 常用釘選區塊（localStorage 持久化） -->
      <div v-if="pinnedItems.length" class="nav-group pinned-group" data-testid="sidebar-pinned">
        <div v-if="showFull" class="nav-group-head pinned-head">
          <span class="nav-group-title">⭐ 常用釘選</span>
          <button
            type="button"
            class="toggle-all-btn"
            data-testid="sidebar-toggle-all"
            @click="toggleAllGroups"
            :title="allGroupsExpanded ? '收合所有分類' : '展開所有分類'"
          >
            {{ allGroupsExpanded ? '全部收合' : '全部展開' }}
          </button>
        </div>
        <div v-for="item in pinnedItems" :key="'pin-' + item.key" class="nav-item-row">
          <router-link
            :to="item.to()"
            class="nav-item"
            :class="{ cta: item.cta }"
            :title="!showFull ? item.label : ''"
            @click="closeMobile"
          >
            <component :is="item.icon" :size="16" class="nav-icon" />
            <span class="nav-label" v-if="showFull">{{ item.label }}</span>
          </router-link>
          <button
            v-if="showFull"
            type="button"
            class="pin-action-btn pinned"
            aria-label="移除常用捷徑"
            :title="`移除常用：${item.label}`"
            @click.prevent.stop="togglePin(item.key)"
          >
            <PinOff :size="12" />
          </button>
        </div>
      </div>

      <div v-else-if="showFull" class="nav-utility-row">
        <button
          type="button"
          class="toggle-all-btn"
          data-testid="sidebar-toggle-all"
          @click="toggleAllGroups"
        >
          {{ allGroupsExpanded ? '全部收合' : '全部展開' }}
        </button>
      </div>

      <!-- 5 大分類手風琴 -->
      <div
        class="nav-group"
        v-for="group in navGroups"
        :key="group.id"
        :data-testid="`sidebar-group-${group.id}`"
      >
        <div
          v-if="showFull"
          role="heading"
          aria-level="3"
          tabindex="0"
          class="nav-group-toggle"
          :aria-expanded="isGroupExpanded(group.id) ? 'true' : 'false'"
          @click="toggleGroup(group.id)"
          @keydown.enter.space.prevent="toggleGroup(group.id)"
        >
          <span class="nav-group-title">{{ group.title }}</span>
          <span class="nav-group-meta">
            <span class="nav-group-count">{{ group.items.length }}</span>
            <ChevronDown v-if="isGroupExpanded(group.id)" :size="13" />
            <ChevronRight v-else :size="13" />
          </span>
        </div>

        <div v-if="showFull ? isGroupExpanded(group.id) : true" class="nav-group-items">
          <div
            v-for="item in visibleGroupItems(group)"
            :key="item.key"
            class="nav-item-row"
          >
            <router-link
              :to="item.to()"
              class="nav-item"
              :class="{ cta: item.cta }"
              :title="!showFull ? item.label : ''"
              @click="closeMobile"
            >
              <component :is="item.icon" :size="16" class="nav-icon" />
              <span class="nav-label" v-if="showFull">{{ item.label }}</span>
            </router-link>
            <button
              v-if="showFull"
              type="button"
              class="pin-action-btn"
              :class="{ pinned: isPinned(item.key) }"
              :data-testid="`pin-btn-${item.key}`"
              :aria-label="isPinned(item.key) ? '移除常用捷徑' : '加入常用捷徑'"
              :title="isPinned(item.key) ? `移除常用：${item.label}` : `加入常用：${item.label}`"
              @click.prevent.stop="togglePin(item.key)"
            >
              <Pin :size="12" />
            </button>
          </div>
        </div>
      </div>
    </nav>

    <div class="sidebar-footer">
      <template v-if="authStore.isLoggedIn">
        <img v-if="authStore.avatar" :src="authStore.avatar" class="sidebar-avatar" :title="authStore.email" />
        <span v-else-if="showFull" class="sidebar-user">{{ authStore.email }}</span>
      </template>
      <button v-else class="sidebar-signin-btn" @click="goAdminLogin" :title="!showFull ? '管理員登入' : ''">
        <Key v-if="!showFull" :size="16" />
        <span v-else>管理員登入</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { useAuthStore } from '../stores/auth.js'
import {
  Target, Star, Zap, Radio, Bot, CheckSquare, ClipboardList,
  BarChart2, TrendingUp, Calendar, Shuffle, Anchor, CandlestickChart,
  MessageCircle, FileText, FlaskConical, Network, RefreshCw, Scale,
  Gauge, ScanSearch, Search, Shield, Flame, AlertTriangle,
  Calculator, BookOpen, Dices, Bell, Rocket, Newspaper, Puzzle,
  Settings, Wrench, Brain, Lightbulb, Diamond,
  ChevronLeft, ChevronRight, ChevronDown, Key, GraduationCap, Layers, CalendarClock,
  Pin, PinOff,
} from 'lucide-vue-next'

const props = defineProps({
  mobileOpen: { type: Boolean, default: false },
})
const emit = defineEmits(['update:mobileOpen'])

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const router = useRouter()
const route = useRoute()
const stockStore = useStockStore()
const authStore = useAuthStore()

const collapsed = ref(localStorage.getItem('finlab_sidebar_collapsed') === '1')
const showFull = computed(() => !collapsed.value || props.mobileOpen)

function closeMobile() {
  if (props.mobileOpen) emit('update:mobileOpen', false)
}
watch(() => route.path, () => { closeMobile() })

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  localStorage.setItem('finlab_sidebar_collapsed', collapsed.value ? '1' : '0')
}

function openQuickSwitcher() {
  window.dispatchEvent(new CustomEvent('finlab:open-quick-switcher'))
}

const query = ref('')
const results = ref([])
const showResults = ref(false)
let searchTimer = null
// OO8：debounce 只避免每個按鍵都發請求，不保證回應順序——同款修法見
// WatchlistView.vue 的 searchStocks。
let searchSeq = 0

async function fetchSearchItems(q) {
  const seq = ++searchSeq
  try {
    const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
    const data = await resp.json()
    if (seq !== searchSeq) return null
    return data?.data?.items || []
  } catch {
    if (seq === searchSeq) return []
    return null
  }
}

function onInput() {
  clearTimeout(searchTimer)
  const q = query.value.trim()
  if (!q) { results.value = []; return }
  searchTimer = setTimeout(async () => {
    const items = await fetchSearchItems(q)
    if (items !== null) results.value = items
  }, 250)
}

// T-026：修復搜尋換股——任何頁面搜尋個股點選或按 Enter 皆立即導向該股分析頁；
// 若已身處個股子頁（分析/季節性/籌碼/回測…），則保留同子頁、僅切換股票代號。
function selectStock(item) {
  showResults.value = false
  query.value = ''
  results.value = []
  stockStore.setStock(item.symbol, item.name_zh || '')
  if (route.params.symbol) {
    router.push({ name: route.name, params: { ...route.params, symbol: item.symbol } })
  } else {
    router.push(`/stocks/${item.symbol}`)
  }
  closeMobile()
}

async function onEnter() {
  if (results.value.length) {
    selectStock(results.value[0])
    return
  }
  const q = query.value.trim()
  if (!q) return
  clearTimeout(searchTimer)
  const items = await fetchSearchItems(q)
  if (items && items.length) {
    selectStock(items[0])
  }
}

function onBlur() {
  setTimeout(() => { showResults.value = false }, 200)
}

const navGroups = [
  {
    id: 'decision',
    title: '決策 & 掃描',
    matchPaths: ['/decision', '/watchlist', '/command', '/signals', '/ai-signals', '/trade-approval', '/daily-brief', '/events'],
    items: [
      { key: 'decision', icon: Target, label: '決策面板', cta: true, to: () => '/decision' },
      { key: 'watchlist', icon: Star, label: '觀察清單', to: () => '/watchlist' },
      { key: 'command', icon: Zap, label: '作戰台', to: () => '/command' },
      { key: 'signals', icon: Radio, label: '訊號', to: () => '/signals' },
      { key: 'ai-signals', icon: Bot, label: 'AI 交易信號', to: () => '/ai-signals' },
      { key: 'trade-approval', icon: CheckSquare, label: '交易核准中心', to: () => '/trade-approval' },
      { key: 'daily-brief', icon: ClipboardList, label: '盤後日報', to: () => '/daily-brief' },
      { key: 'events', icon: CalendarClock, label: '事件研究台', to: () => '/events' },
    ],
  },
  {
    id: 'stock',
    title: '個股分析',
    matchPaths: ['/overview', '/stocks/', '/etf-compare'],
    items: [
      { key: 'overview', icon: BarChart2, label: '總覽', to: () => `/overview` },
      { key: 'analysis', icon: TrendingUp, label: '分析', to: () => `/stocks/${stockStore.symbol}` },
      { key: 'seasonal', icon: Calendar, label: '季節性', to: () => `/stocks/${stockStore.symbol}/seasonal` },
      { key: 'lead-lag', icon: Shuffle, label: '領先落後', to: () => `/stocks/${stockStore.symbol}/lead-lag` },
      { key: 'major-players', icon: Anchor, label: '主力', to: () => `/stocks/${stockStore.symbol}/major-players` },
      { key: 'chip', icon: CandlestickChart, label: '籌碼', to: () => `/stocks/${stockStore.symbol}/chip` },
      { key: 'social-buzz', icon: MessageCircle, label: '熱度', to: () => `/stocks/${stockStore.symbol}/social-buzz` },
      { key: 'public-data', icon: FileText, label: '公開資訊', to: () => `/stocks/${stockStore.symbol}/public-data` },
      { key: 'backtest', icon: FlaskConical, label: '回測', to: () => `/stocks/${stockStore.symbol}/backtest` },
      { key: 'etf-compare', icon: Layers, label: 'ETF 比較', to: () => '/etf-compare' },
    ],
  },
  {
    id: 'rotation',
    title: '關聯 & 輪動',
    matchPaths: ['/graph', '/rotation', '/compare', '/market-lights', '/news-checker', '/screener'],
    items: [
      { key: 'graph', icon: Network, label: '關聯圖', to: () => '/graph' },
      { key: 'rotation', icon: RefreshCw, label: '類股輪動', to: () => '/rotation' },
      { key: 'compare', icon: Scale, label: '多股比較', to: () => '/compare' },
      { key: 'market-lights', icon: Gauge, label: '大盤多空', to: () => '/market-lights' },
      { key: 'news-checker', icon: ScanSearch, label: '新聞可信度', to: () => '/news-checker' },
      { key: 'screener', icon: Search, label: 'AI 選股', to: () => '/screener' },
    ],
  },
  {
    id: 'risk',
    title: '風控 & 紀律',
    matchPaths: ['/risk-sizing', '/portfolio-heat', '/risk-monitor', '/trade-dashboard', '/journal', '/monte-carlo', '/price-alerts'],
    items: [
      { key: 'risk-sizing', icon: Shield, label: '部位風控', to: () => '/risk-sizing' },
      { key: 'portfolio-heat', icon: Flame, label: '投組風險', to: () => '/portfolio-heat' },
      { key: 'risk-monitor', icon: AlertTriangle, label: '風控監控', to: () => '/risk-monitor' },
      { key: 'trade-dashboard', icon: Calculator, label: '交易儀表板', to: () => '/trade-dashboard' },
      { key: 'journal', icon: BookOpen, label: '交易日誌', to: () => '/journal' },
      { key: 'monte-carlo', icon: Dices, label: '風險模擬', to: () => '/monte-carlo' },
      { key: 'price-alerts', icon: Bell, label: '價格警報', to: () => '/price-alerts' },
    ],
  },
  {
    id: 'other',
    title: '其他',
    matchPaths: ['/guide', '/learn', '/data-agent', '/signal-rules', '/settings', '/admin', '/kb-qa', '/feedback'],
    items: [
      { key: 'guide', icon: Rocket, label: '新手上路', to: () => '/guide' },
      { key: 'learn', icon: GraduationCap, label: '學習中心', to: () => '/learn' },
      { key: 'data-agent', icon: Newspaper, label: '資料爬蟲與新聞檢查', to: () => '/data-agent' },
      { key: 'signal-rules', icon: Puzzle, label: '信號規則編輯器', to: () => '/signal-rules' },
      { key: 'settings', icon: Settings, label: '設定', to: () => '/settings' },
      { key: 'admin', icon: Wrench, label: '後台', to: () => '/admin' },
      { key: 'kb-qa', icon: Brain, label: '知識庫問答', to: () => '/kb-qa' },
      { key: 'feedback', icon: Lightbulb, label: '意見回饋', to: () => '/feedback' },
    ],
  },
]

const itemByKey = Object.fromEntries(navGroups.flatMap(g => g.items.map(it => [it.key, it])))

// T-026：常用釘選（localStorage 持久化）
const PINS_STORAGE_KEY = 'finlab_sidebar_pins_v1'
const DEFAULT_PINS = ['decision', 'command', 'overview', 'risk-monitor', 'journal']

function loadPins() {
  try {
    const raw = localStorage.getItem(PINS_STORAGE_KEY)
    if (raw === null) return [...DEFAULT_PINS]
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.filter(k => Boolean(itemByKey[k]))
  } catch { /* ignore */ }
  return [...DEFAULT_PINS]
}
const pinnedKeys = ref(loadPins())
const pinnedSet = computed(() => new Set(pinnedKeys.value))
const pinnedItems = computed(() => pinnedKeys.value.map(k => itemByKey[k]).filter(Boolean))

function isPinned(key) { return pinnedSet.value.has(key) }
function togglePin(key) {
  if (!itemByKey[key]) return
  if (pinnedSet.value.has(key)) {
    pinnedKeys.value = pinnedKeys.value.filter(k => k !== key)
  } else {
    pinnedKeys.value = [...pinnedKeys.value, key]
  }
  try { localStorage.setItem(PINS_STORAGE_KEY, JSON.stringify(pinnedKeys.value)) } catch { /* ignore */ }
}

// T-026：5 大分類手風琴狀態（預設展開常用組 + 當前路由所屬分組）
const GROUPS_STORAGE_KEY = 'finlab_sidebar_groups_v1'
function groupIdForPath(path) {
  for (const g of navGroups) {
    if (g.matchPaths.some(p => path === p || path.startsWith(p + '/') || (p.endsWith('/') && path.startsWith(p)))) {
      return g.id
    }
  }
  return null
}
function loadExpandedGroups() {
  const active = groupIdForPath(route.path)
  try {
    const raw = localStorage.getItem(GROUPS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const s = new Set(parsed.filter(id => navGroups.some(g => g.id === id)))
        if (active) s.add(active)
        return s
      }
    }
  } catch { /* ignore */ }
  const defaults = new Set(['decision'])
  if (active) defaults.add(active)
  return defaults
}
const expandedGroups = ref(loadExpandedGroups())
function saveExpandedGroups() {
  try { localStorage.setItem(GROUPS_STORAGE_KEY, JSON.stringify([...expandedGroups.value])) } catch { /* ignore */ }
}
function isGroupExpanded(id) { return expandedGroups.value.has(id) }
function toggleGroup(id) {
  const next = new Set(expandedGroups.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedGroups.value = next
  saveExpandedGroups()
}
const allGroupsExpanded = computed(() => navGroups.every(g => expandedGroups.value.has(g.id)))
function toggleAllGroups() {
  if (allGroupsExpanded.value) {
    const active = groupIdForPath(route.path)
    expandedGroups.value = new Set(active ? [active] : [])
  } else {
    expandedGroups.value = new Set(navGroups.map(g => g.id))
  }
  saveExpandedGroups()
}

// 切頁時自動展開當前路由所屬分類，確保使用者看得到自己在哪一組
watch(() => route.path, (path) => {
  const active = groupIdForPath(path)
  if (active && !expandedGroups.value.has(active)) {
    const next = new Set(expandedGroups.value)
    next.add(active)
    expandedGroups.value = next
    saveExpandedGroups()
  }
})

// 窄欄收合態只顯示未在釘選區的其餘項目，避免 60px 窄欄重複圖示
function visibleGroupItems(group) {
  if (!showFull.value) return group.items.filter(it => !pinnedSet.value.has(it.key))
  return group.items
}

function goAdminLogin() {
  closeMobile()
  router.push('/admin')
}
</script>

<style scoped>
.sidebar-backdrop {
  display: none;
}

.app-sidebar {
  --sidebar-w: 236px;
  --sidebar-w-collapsed: 60px;
  width: var(--sidebar-w);
  flex-shrink: 0;
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.18s ease;
  z-index: 250;
}
.app-sidebar.collapsed { width: var(--sidebar-w-collapsed); }

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px;
  gap: 6px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
  font-size: 1.05rem;
  color: var(--text-primary);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
}
.logo-icon { color: var(--accent-blue); }
.collapse-btn {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.collapse-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.sidebar-search { position: relative; padding: 10px 10px 6px; flex-shrink: 0; }
.sidebar-search-collapsed-btn {
  width: 38px;
  height: 36px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  border: 1px solid var(--border-color);
  background: var(--bg-well);
  color: var(--text-secondary);
  cursor: pointer;
}
.sidebar-search-collapsed-btn:hover {
  background: var(--bg-hover);
  color: var(--accent-blue);
  border-color: var(--accent-blue);
}
.search-box { position: relative; }
.search-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: var(--text-muted); pointer-events: none; }
.sidebar-search-input {
  width: 100%;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  border-radius: 9px;
  color: var(--text-primary);
  padding: 7px 10px 7px 30px;
  font-size: 0.82rem;
}
.sidebar-search-dropdown {
  position: absolute;
  left: 10px;
  right: 10px;
  top: calc(100% - 2px);
  z-index: 260;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  max-height: 280px;
  overflow-y: auto;
  box-shadow: 0 12px 30px rgba(0,0,0,0.4);
  list-style: none;
  margin: 0;
  padding: 4px;
}
.sidebar-search-dropdown li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 7px;
  cursor: pointer;
  font-size: 0.82rem;
}
.sidebar-search-dropdown li:hover { background: var(--bg-hover); }
.r-symbol { font-weight: 700; color: var(--accent-blue); min-width: 46px; }
.r-name { color: var(--text-secondary); }

.sidebar-current {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 4px 10px 8px;
  padding: 8px 10px;
  border-radius: 9px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  text-decoration: none;
  flex-shrink: 0;
}
.cur-label { font-size: 0.68rem; color: var(--text-muted); }
.cur-value { font-size: 0.86rem; font-weight: 700; color: var(--text-primary); }
.cur-value small { font-weight: 400; color: var(--text-secondary); margin-left: 4px; }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 4px 8px 8px; }
.nav-group { margin-bottom: 6px; }
.pinned-group {
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--border-color);
}
.nav-group-head,
.nav-utility-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px 4px 6px;
}
.nav-utility-row { justify-content: flex-end; margin-bottom: 4px; }
.toggle-all-btn {
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  border-radius: 6px;
  padding: 2px 7px;
  font-size: 0.68rem;
  cursor: pointer;
  font-family: inherit;
}
.toggle-all-btn:hover { color: var(--text-primary); background: var(--bg-hover); }

.nav-group-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 6px 5px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}
.nav-group-toggle:hover { background: var(--bg-hover); }
.nav-group-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-muted);
  font-size: 0.7rem;
}
.nav-group-count {
  padding: 0 5px;
  border-radius: 999px;
  background: var(--bg-well);
  font-size: 0.66rem;
}
.nav-group-title {
  font-size: 0.68rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0;
}
.nav-group-items {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-top: 2px;
}

.nav-item-row {
  position: relative;
  display: flex;
  align-items: center;
}
.nav-item {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 8px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.84rem;
  white-space: nowrap;
}
.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.router-link-active { background: color-mix(in srgb, var(--blue) 14%, transparent); color: var(--accent-blue); font-weight: 600; }
.nav-item.cta { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); color: var(--on-accent); font-weight: 700; }
.nav-item.cta.router-link-active { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); color: var(--on-accent); }
.nav-icon { width: 16px; height: 16px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.app-sidebar.collapsed .nav-item { justify-content: center; }

.pin-action-btn {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.14s ease, color 0.14s ease, background 0.14s ease;
}
.nav-item-row:hover .pin-action-btn,
.nav-item-row:focus-within .pin-action-btn,
.pin-action-btn.pinned {
  opacity: 0.72;
}
.pin-action-btn:hover {
  opacity: 1 !important;
  background: var(--bg-hover);
  color: var(--accent-blue);
}
.pin-action-btn.pinned { color: var(--accent-blue); }

.sidebar-footer {
  padding: 10px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sidebar-avatar { width: 28px; height: 28px; border-radius: 50%; border: 2px solid color-mix(in srgb, var(--purple) 50%, transparent); }
.sidebar-user { font-size: 0.78rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; }
.sidebar-signin-btn {
  width: 100%;
  background: color-mix(in srgb, var(--purple) 15%, transparent);
  color: var(--purple);
  border: 1px solid color-mix(in srgb, var(--purple) 30%, transparent);
  border-radius: 10px;
  padding: 7px 10px;
  cursor: pointer;
  font-size: 0.82rem;
}
.sidebar-signin-btn:hover { background: color-mix(in srgb, var(--purple) 30%, transparent); }

@media (max-width: 1024px) {
  .app-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 260px;
    transform: translateX(-100%);
    box-shadow: 0 0 0 rgba(0,0,0,0);
  }
  .app-sidebar.collapsed { width: 260px; } /* collapse concept only applies on desktop */
  .app-sidebar.mobile-open {
    transform: translateX(0);
    box-shadow: 10px 0 40px rgba(0,0,0,0.5);
  }
  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(2,6,23,0.55);
    z-index: 240;
  }
}
</style>
