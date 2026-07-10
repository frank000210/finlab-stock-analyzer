<template>
  <div id="app-root">
    <nav class="top-nav">
      <router-link to="/" class="logo">
        <span class="logo-icon">◆</span> FinLab
      </router-link>
      <div class="search-bar">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          v-model="searchQuery"
          @input="onSearch"
          @keyup.enter="goToStock"
          @blur="() => setTimeout(() => searchResults = [], 200)"
          placeholder="搜尋股票代號或名稱..."
          class="search-input"
        />
        <ul v-if="searchResults.length" class="search-dropdown">
          <li
            v-for="item in searchResults"
            :key="item.symbol"
            @mousedown="selectStock(item.symbol, item.name_zh)"
          >
            <span class="search-symbol">{{ item.symbol }}</span>
            <span class="search-name">{{ item.name_zh }}</span>
          </li>
        </ul>
      </div>
      <div class="nav-links primary-nav">
        <router-link to="/decision" class="nav-cta">🎯 決策面板</router-link>
        <router-link to="/graph">🕸️ 關聯圖</router-link>
        <router-link to="/graph01">🕸️ 關聯圖01</router-link>
        <router-link to="/rotation">🔄 類股輪動</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}`">分析</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/seasonal`">季節性</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/lead-lag`">領先落後</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/major-players`">主力</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/chip`">籌碼</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/social-buzz`">熱度</router-link>
      </div>
      <button class="more-toggle" @click="mobileMoreOpen = !mobileMoreOpen" aria-label="更多功能" aria-haspopup="true">☰ 更多</button>
      <div class="nav-links secondary-nav" :class="{ open: mobileMoreOpen }" @click="mobileMoreOpen = false">
        <router-link to="/guide" class="nav-guide">🚀 新手上路</router-link>
        <router-link to="/overview">總覽</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/public-data`">公開資訊</router-link>
        <router-link :to="`/stocks/${stockStore.symbol}/backtest`">回測</router-link>
        <router-link to="/risk-sizing">🛡️ 部位風控</router-link>
        <router-link to="/portfolio-heat">🔥 投組風險</router-link>
        <router-link to="/journal">📓 交易日誌</router-link>
        <router-link to="/monte-carlo">🎲 風險模擬</router-link>
        <router-link to="/signals">📡 訊號</router-link>
        <router-link to="/command">⚡ 作戰台</router-link>
        <router-link to="/settings">設定</router-link>
        <router-link to="/admin" class="nav-admin">⚙️ 後台</router-link>
      </div>
      <!-- User Auth -->
      <div class="nav-auth">
        <template v-if="authStore.isLoggedIn">
          <img v-if="authStore.avatar" :src="authStore.avatar" class="nav-avatar" :title="authStore.email" />
        </template>
        <button v-else class="nav-signin-btn" @click="triggerGoogleSignIn">Google 登入</button>
      </div>
    </nav>
    <div v-if="showOnboard" class="onboard-banner">
      <span>👋 第一次來？花 3 分鐘看「新手上路」，把整套交易紀律流程走一遍。</span>
      <router-link class="ob-go" to="/guide" @click="dismissOnboard">開始導覽 →</router-link>
      <button class="ob-x" @click="dismissOnboard" aria-label="關閉導覽提示">✕</button>
    </div>
    <main class="main-content">
      <router-view />
    </main>
    <!-- Global page counter - tracks via route -->
    <div class="global-counter-wrap">
      <PageCounter :page="currentRouteName" :symbol="stockStore.symbol" />
    </div>
    <!-- Ctrl/Cmd+K 全域快速切換（頁面 + 個股） -->
    <QuickSwitcher />
    <!-- Global error toasts (fed by app.config.errorHandler via finlab:app-error) -->
    <div v-if="errorToasts.length" class="error-toasts" role="alert" aria-live="assertive">
      <div v-for="t in errorToasts" :key="t.id" class="error-toast">
        <span class="et-icon">⚠</span>
        <span class="et-text">頁面發生錯誤：{{ t.text }}（其餘功能不受影響，可重新整理此頁）</span>
        <button class="et-x" aria-label="關閉錯誤提示" @click="dismissToast(t.id)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useStockStore } from './stores/stock.js'
import { useAuthStore } from './stores/auth.js'
import PageCounter from './components/PageCounter.vue'
import QuickSwitcher from './components/QuickSwitcher.vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const router = useRouter()
const route = useRoute()
const stockStore = useStockStore()
const authStore = useAuthStore()
const searchQuery = ref('')
const searchResults = ref([])
const showOnboard = ref(false)
function dismissOnboard() { showOnboard.value = false; localStorage.setItem('finlab_onboarded', '1') }
const mobileMoreOpen = ref(false)
watch(() => route.path, () => { mobileMoreOpen.value = false })

// Global error toasts (see main.js errorHandler)
const errorToasts = ref([])
let toastSeq = 0
function pushErrorToast(text) {
  const id = ++toastSeq
  errorToasts.value.push({ id, text: String(text || '未知錯誤').slice(0, 160) })
  if (errorToasts.value.length > 3) errorToasts.value.shift() // cap the stack
  setTimeout(() => dismissToast(id), 8000)
}
function dismissToast(id) {
  errorToasts.value = errorToasts.value.filter(t => t.id !== id)
}
onMounted(() => {
  window.addEventListener('finlab:app-error', (e) => pushErrorToast(e.detail))
})
onMounted(() => {
  // Only surface the first-visit banner on the landing page.
  if (!localStorage.getItem('finlab_onboarded') && route.path === '/') showOnboard.value = true
})
let searchTimeout = null

// Route name for the page counter. Before the router resolves (first tick),
// route.name is undefined and route.path is '/', which used to get tracked as
// page='/' -> POST junk analytics rows and GET /pageviews/%2F -> 404 (logged
// as 'pageviews//'). Return '' in that window so PageCounter skips it, and
// slash-sanitize any unnamed-path fallback so it can never 404 the GET.
const currentRouteName = computed(() => {
  if (route.name) return String(route.name)
  return route.path.replace(/^\/+|\/+$/g, '').replace(/\//g, '-')
})

// Load Google Client ID from backend
onMounted(async () => {
  try {
    const r = await fetch('/api/v1/settings')
    const data = await r.json()
    const clientId = data?.data?.google_client_id || ''
    if (clientId) window.__GOOGLE_CLIENT_ID__ = clientId
  } catch {}
})

function onSearch() {
  clearTimeout(searchTimeout)
  if (searchQuery.value.length < 1) {
    searchResults.value = []
    return
  }
  searchTimeout = setTimeout(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${searchQuery.value}`)
      const data = await resp.json()
      searchResults.value = data?.data?.items || []
    } catch {
      searchResults.value = []
    }
  }, 250)
}

function selectStock(symbol, name_zh) {
  searchResults.value = []
  searchQuery.value = ''
  stockStore.setStock(symbol, name_zh || '')
  router.push(`/stocks/${symbol}`)
}

function goToStock() {
  if (searchResults.value.length > 0) {
    const item = searchResults.value[0]
    selectStock(item.symbol, item.name_zh)
  } else if (searchQuery.value.match(/^\d{4}$/)) {
    selectStock(searchQuery.value, '')
  }
}

function triggerGoogleSignIn() {
  // Redirect-based OAuth flow (works in all browsers incl. embedded; no popup)
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
.logo {
  display: flex;
  align-items: center;
  gap: 6px;
}

.logo-icon {
  color: var(--accent-blue);
  font-size: 1.1rem;
}

.search-bar {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  padding-left: 36px !important;
}

.search-dropdown li {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-symbol {
  font-weight: 700;
  color: var(--accent-blue);
  font-size: 0.85rem;
  min-width: 48px;
}

.search-name {
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.nav-cta {
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
  padding: 5px 12px !important;
  border-radius: var(--radius-sm) !important;
  color: #fff !important;
  font-weight: 700 !important;
  font-size: 0.8rem !important;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  transition: box-shadow var(--transition-fast) !important;
}

.nav-cta:hover {
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.5) !important;
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
}

.secondary-nav {
  margin-left: auto;
}

.secondary-nav a {
  font-size: 0.78rem !important;
  opacity: 0.7;
}

.secondary-nav a:hover {
  opacity: 1;
}

.nav-admin {
  font-size: 0.78rem !important;
  opacity: 0.7;
}
.nav-admin:hover { opacity: 1; }
.nav-guide { color: #22c55e !important; font-weight: 600; }

.onboard-banner {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: linear-gradient(90deg, rgba(34,197,94,0.14), rgba(79,140,255,0.14));
  border-bottom: 1px solid var(--border-color);
  padding: 10px 20px; font-size: 0.88rem;
}
.onboard-banner .ob-go { color: var(--accent-blue); font-weight: 700; text-decoration: none; }
.onboard-banner .ob-go:hover { text-decoration: underline; }
.onboard-banner .ob-x { margin-left: auto; background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; }
.onboard-banner .ob-x:hover { color: var(--text-primary); }

.error-toasts {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 18px;
  z-index: 500;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: min(560px, calc(100vw - 24px));
}
.error-toast {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: rgba(40, 12, 16, 0.96);
  border: 1px solid rgba(239, 68, 68, 0.55);
  color: #fca5a5;
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.84rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}
.error-toast .et-icon { flex: 0 0 auto; }
.error-toast .et-text { flex: 1; min-width: 0; line-height: 1.5; word-break: break-word; }
.error-toast .et-x { background: none; border: none; color: #fca5a5; cursor: pointer; flex: 0 0 auto; }
.error-toast .et-x:hover { color: #fff; }

.nav-auth {
  display: flex;
  align-items: center;
  margin-left: 8px;
}

.nav-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid rgba(99,102,241,0.5);
}

.nav-signin-btn {
  background: rgba(99,102,241,0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99,102,241,0.3);
  border-radius: 20px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
  transition: background 0.2s;
}
.nav-signin-btn:hover { background: rgba(99,102,241,0.3); }

.global-counter-wrap {
  position: fixed;
  bottom: 80px;
  right: 16px;
  z-index: 100;
}

@media (max-width: 768px) {
  .nav-auth { display: none; }
}

.more-toggle {
  display: none;
  position: relative;
  z-index: 250;
  background: rgba(99,102,241,0.12);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 0.8rem;
  white-space: nowrap;
  flex-shrink: 0;
}
.more-toggle:hover { background: rgba(99,102,241,0.22); }

@media (max-width: 1024px) {
  .more-toggle { display: inline-flex; align-items: center; }
  .secondary-nav { display: none; }
  .secondary-nav.open {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    position: absolute;
    top: calc(100% + 6px);
    right: 8px;
    z-index: 300;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 8px;
    gap: 2px;
    min-width: 190px;
    max-height: 72vh;
    overflow-y: auto;
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  }
  .secondary-nav.open a { padding: 8px 12px; border-radius: 8px; }
  .secondary-nav.open a:hover { background: var(--bg-hover); }
}

@media (max-width: 768px) {
  .primary-nav {
    order: 10;
    flex-basis: 100%;
    justify-content: center;
    padding-top: 8px;
  }
  .search-bar {
    order: 5;
    flex-basis: 100%;
    max-width: 100% !important;
  }
}

@media (max-width: 420px) {
  .primary-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 200;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
    padding: 6px 8px env(safe-area-inset-bottom, 6px);
    justify-content: space-around;
    flex-basis: auto;
    order: unset;
    gap: 0;
    flex-wrap: nowrap;
  }
  .primary-nav a,
  .primary-nav .nav-cta {
    font-size: 0.68rem !important;
    padding: 6px 4px !important;
    border-radius: 6px !important;
    text-align: center;
    flex: 1;
    min-width: 0;
    box-shadow: none !important;
    background: transparent !important;
    color: var(--text-muted) !important;
  }
  .primary-nav a.router-link-active,
  .primary-nav .nav-cta.router-link-active {
    color: var(--accent-blue) !important;
    background: rgba(59, 130, 246, 0.1) !important;
  }
  /* Make room for bottom nav */
  #app-root .main-content {
    padding-bottom: 64px;
  }
}
</style>
