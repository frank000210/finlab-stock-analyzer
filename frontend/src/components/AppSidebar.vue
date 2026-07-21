<template>
  <button class="sidebar-mobile-toggle" @click="mobileOpen = true" aria-label="開啟選單" aria-haspopup="true">☰</button>
  <div v-if="mobileOpen" class="sidebar-backdrop" @click="mobileOpen = false"></div>

  <aside class="app-sidebar" :class="{ collapsed, 'mobile-open': mobileOpen }">
    <div class="sidebar-header">
      <router-link to="/" class="sidebar-logo" @click="mobileOpen = false">
        <span class="logo-icon">◆</span>
        <span class="logo-text" v-if="!collapsed">FinLab</span>
      </router-link>
      <button class="collapse-btn" @click="toggleCollapsed" :title="collapsed ? '展開選單' : '收合選單'" aria-label="收合/展開選單">
        {{ collapsed ? '»' : '«' }}
      </button>
    </div>

    <div class="sidebar-search">
      <div class="search-box">
        <svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          v-model="query"
          class="sidebar-search-input"
          :placeholder="collapsed ? '' : '搜尋股票代號或名稱…'"
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
    </div>

    <router-link
      v-if="!collapsed"
      :to="`/stocks/${stockStore.symbol}`"
      class="sidebar-current"
      :title="`目前個股：${stockStore.symbol} ${stockStore.name}`"
    >
      <span class="cur-label">目前個股</span>
      <span class="cur-value">{{ stockStore.symbol }}<small v-if="stockStore.name"> {{ stockStore.name }}</small></span>
    </router-link>

    <nav class="sidebar-nav">
      <div class="nav-group" v-for="group in navGroups" :key="group.title">
        <div class="nav-group-title" v-if="!collapsed">{{ group.title }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.key"
          :to="item.to()"
          class="nav-item"
          :class="{ cta: item.cta }"
          :title="collapsed ? item.label : ''"
          @click="mobileOpen = false"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label" v-if="!collapsed">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <template v-if="authStore.isLoggedIn">
        <img v-if="authStore.avatar" :src="authStore.avatar" class="sidebar-avatar" :title="authStore.email" />
        <span v-else-if="!collapsed" class="sidebar-user">{{ authStore.email }}</span>
      </template>
      <button v-else class="sidebar-signin-btn" @click="triggerGoogleSignIn" :title="collapsed ? 'Google 登入' : ''">
        {{ collapsed ? '🔑' : 'Google 登入' }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { useAuthStore } from '../stores/auth.js'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const router = useRouter()
const route = useRoute()
const stockStore = useStockStore()
const authStore = useAuthStore()

const collapsed = ref(localStorage.getItem('finlab_sidebar_collapsed') === '1')
const mobileOpen = ref(false)
watch(() => route.path, () => { mobileOpen.value = false })

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  localStorage.setItem('finlab_sidebar_collapsed', collapsed.value ? '1' : '0')
}

const query = ref('')
const results = ref([])
const showResults = ref(false)
let searchTimer = null

function onInput() {
  clearTimeout(searchTimer)
  const q = query.value.trim()
  if (!q) { results.value = []; return }
  searchTimer = setTimeout(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
      const data = await resp.json()
      results.value = data?.data?.items || []
    } catch {
      results.value = []
    }
  }, 250)
}

// 一鍵搜尋切換：更新全站目前個股。若正處於某檔股票的子頁面（分析/回測/
// 籌碼…），保留該子頁面、只換代號，讓「頁面內容連動顯示股票 A」；否則
// （在作戰台/日誌等工具頁）維持原頁，該頁自己的 stockStore 監聽器會接手。
function selectStock(item) {
  showResults.value = false
  query.value = ''
  results.value = []
  stockStore.setStock(item.symbol, item.name_zh || '')
  if (route.params.symbol) {
    router.push({ name: route.name, params: { ...route.params, symbol: item.symbol } })
  }
  mobileOpen.value = false
}

function onEnter() {
  if (results.value.length) selectStock(results.value[0])
}

function onBlur() {
  setTimeout(() => { showResults.value = false }, 200)
}

const navGroups = [
  {
    title: '決策 & 掃描',
    items: [
      { key: 'decision', icon: '🎯', label: '決策面板', cta: true, to: () => '/decision' },
      { key: 'command', icon: '⚡', label: '作戰台', to: () => '/command' },
      { key: 'signals', icon: '📡', label: '訊號', to: () => '/signals' },
      { key: 'ai-signals', icon: '🤖', label: 'AI 交易信號', to: () => '/ai-signals' },
      { key: 'trade-approval', icon: '✅', label: '交易核准中心', to: () => '/trade-approval' },
      { key: 'daily-brief', icon: '📋', label: '盤後日報', to: () => '/daily-brief' },
    ],
  },
  {
    title: '個股分析',
    items: [
      { key: 'overview', icon: '📊', label: '總覽', to: () => `/overview` },
      { key: 'analysis', icon: '📈', label: '分析', to: () => `/stocks/${stockStore.symbol}` },
      { key: 'seasonal', icon: '📅', label: '季節性', to: () => `/stocks/${stockStore.symbol}/seasonal` },
      { key: 'lead-lag', icon: '🔀', label: '領先落後', to: () => `/stocks/${stockStore.symbol}/lead-lag` },
      { key: 'major-players', icon: '🐳', label: '主力', to: () => `/stocks/${stockStore.symbol}/major-players` },
      { key: 'chip', icon: '💹', label: '籌碼', to: () => `/stocks/${stockStore.symbol}/chip` },
      { key: 'social-buzz', icon: '💬', label: '熱度', to: () => `/stocks/${stockStore.symbol}/social-buzz` },
      { key: 'public-data', icon: '📄', label: '公開資訊', to: () => `/stocks/${stockStore.symbol}/public-data` },
      { key: 'backtest', icon: '🧪', label: '回測', to: () => `/stocks/${stockStore.symbol}/backtest` },
    ],
  },
  {
    title: '關聯 & 輪動',
    items: [
      { key: 'graph', icon: '🕸️', label: '關聯圖', to: () => '/graph' },
      { key: 'graph01', icon: '🕸️', label: '關聯圖01', to: () => '/graph01' },
      { key: 'rotation', icon: '🔄', label: '類股輪動', to: () => '/rotation' },
      { key: 'market-lights', icon: '🚦', label: '大盤多空', to: () => '/market-lights' },
      { key: 'news-checker', icon: '🔍', label: '新聞可信度', to: () => '/news-checker' },
      { key: 'screener', icon: '🔎', label: 'AI 選股', to: () => '/screener' },
    ],
  },
  {
    title: '風控 & 紀律',
    items: [
      { key: 'risk-sizing', icon: '🛡️', label: '部位風控', to: () => '/risk-sizing' },
      { key: 'portfolio-heat', icon: '🔥', label: '投組風險', to: () => '/portfolio-heat' },
      { key: 'risk-monitor', icon: '🚨', label: '風控監控', to: () => '/risk-monitor' },
      { key: 'trade-dashboard', icon: '🧮', label: '交易儀表板', to: () => '/trade-dashboard' },
      { key: 'journal', icon: '📓', label: '交易日誌', to: () => '/journal' },
      { key: 'monte-carlo', icon: '🎲', label: '風險模擬', to: () => '/monte-carlo' },
      { key: 'price-alerts', icon: '🔔', label: '價格警報', to: () => '/price-alerts' },
    ],
  },
  {
    title: '其他',
    items: [
      { key: 'guide', icon: '🚀', label: '新手上路', to: () => '/guide' },
      { key: 'data-agent', icon: '📰', label: '資料爬蟲與新聞檢查', to: () => '/data-agent' },
      { key: 'signal-rules', icon: '🧩', label: '信號規則編輯器', to: () => '/signal-rules' },
      { key: 'settings', icon: '⚙️', label: '設定', to: () => '/settings' },
      { key: 'admin', icon: '🔧', label: '後台', to: () => '/admin' },
    ],
  },
]

function triggerGoogleSignIn() {
  const clientId = window.__GOOGLE_CLIENT_ID__ || ''
  if (!clientId) {
    router.push('/admin')
    return
  }
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36)
  sessionStorage.setItem('gsi_nonce', nonce)
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: window.location.origin + '/admin',
    response_type: 'id_token',
    scope: 'openid email profile',
    nonce,
    prompt: 'select_account',
  })
  window.location.href = 'https://accounts.google.com/o/oauth2/v2/auth?' + params.toString()
}
</script>

<style scoped>
.sidebar-mobile-toggle {
  display: none;
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 301;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 1.1rem;
  cursor: pointer;
}

.sidebar-backdrop {
  display: none;
}

.app-sidebar {
  --sidebar-w: 232px;
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
}
.collapse-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.sidebar-search { position: relative; padding: 10px 10px 6px; flex-shrink: 0; }
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
.app-sidebar.collapsed .sidebar-search-input { padding-left: 26px; }
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
.nav-group { margin-bottom: 8px; }
.nav-group-title {
  font-size: 0.66rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 6px 6px 4px;
}
.nav-item {
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
.nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.router-link-active { background: rgba(59,130,246,0.14); color: var(--accent-blue); font-weight: 600; }
.nav-item.cta { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); color: #fff; font-weight: 700; }
.nav-item.cta.router-link-active { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); color: #fff; }
.nav-icon { width: 18px; text-align: center; flex-shrink: 0; }
.app-sidebar.collapsed .nav-item { justify-content: center; }

.sidebar-footer {
  padding: 10px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sidebar-avatar { width: 28px; height: 28px; border-radius: 50%; border: 2px solid rgba(99,102,241,0.5); }
.sidebar-user { font-size: 0.78rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; }
.sidebar-signin-btn {
  width: 100%;
  background: rgba(99,102,241,0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99,102,241,0.3);
  border-radius: 10px;
  padding: 7px 10px;
  cursor: pointer;
  font-size: 0.82rem;
}
.sidebar-signin-btn:hover { background: rgba(99,102,241,0.3); }

@media (max-width: 1024px) {
  .sidebar-mobile-toggle { display: flex; align-items: center; justify-content: center; }
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
