<template>
  <div id="app-root">
    <!-- 手繪線條用的 SVG 濾鏡（風格 8）：卡片/按鈕的 ::before 邊框引用它 -->
    <svg class="sk-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <filter id="sk-rough" x="-6%" y="-14%" width="112%" height="128%">
          <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="7" />
          <feDisplacementMap in="SourceGraphic" scale="2.6" />
        </filter>
      </defs>
    </svg>
    <AppSidebar v-model:mobileOpen="mobileSidebarOpen" />
    <div class="app-body">
      <header class="app-topbar" data-testid="app-topbar">
        <div class="topbar-left">
          <button
            type="button"
            class="sidebar-mobile-toggle"
            @click="mobileSidebarOpen = !mobileSidebarOpen"
            aria-label="開啟選單"
            aria-haspopup="true"
            :aria-expanded="mobileSidebarOpen ? 'true' : 'false'"
          >
            <Menu :size="18" />
          </button>
          <span class="topbar-page-title" data-testid="topbar-page-title">{{ currentPageTitle }}</span>
          <router-link
            v-if="stockStore.symbol"
            :to="`/stocks/${stockStore.symbol}`"
            class="topbar-stock-pill"
            data-testid="topbar-stock-pill"
            :title="`前往 ${stockStore.symbol} ${stockStore.name || ''} 個股分析`"
          >
            <strong>{{ stockStore.symbol }}</strong>
            <span v-if="stockStore.name" class="topbar-stock-name">{{ stockStore.name }}</span>
          </router-link>
        </div>

        <button
          type="button"
          class="topbar-search-btn"
          data-testid="topbar-quick-switcher"
          @click="openQuickSwitcher"
          aria-label="搜尋個股或跳頁 (Ctrl+K)"
        >
          <Search :size="14" class="topbar-search-icon" />
          <span class="topbar-search-label">搜尋個股／跳頁</span>
          <kbd class="topbar-kbd">Ctrl+K</kbd>
        </button>

        <div class="topbar-right">
          <ThemePicker />
        </div>
      </header>
      <div v-if="showOnboard" class="onboard-banner">
        <span>👋 第一次來？花 3 分鐘看「新手上路」，把整套交易紀律流程走一遍。</span>
        <router-link class="ob-go" to="/guide" @click="dismissOnboard">開始導覽 →</router-link>
        <button class="ob-x" @click="dismissOnboard" aria-label="關閉導覽提示">✕</button>
      </div>
      <main class="main-content">
        <!-- T-026/T-027：移除 :key="themeTick"，切換主題原地重繪圖表，不再重掛整頁與清空表單狀態 -->
        <router-view />
      </main>
    </div>
    <!-- Global page counter - tracks via route -->
    <div class="global-counter-wrap">
      <PageCounter :page="currentRouteName" :symbol="stockStore.symbol" />
    </div>
    <!-- Ctrl/Cmd+K 全域快速切換（頁面 + 個股） -->
    <QuickSwitcher ref="quickSwitcherRef" />
    <!-- Global error toasts (fed by app.config.errorHandler via finlab:app-error) -->
    <div v-if="errorToasts.length" class="error-toasts" role="alert" aria-live="assertive">
      <div v-for="t in errorToasts" :key="t.id" class="error-toast">
        <span class="et-icon">⚠</span>
        <span class="et-text">頁面發生錯誤：{{ t.text }}（其餘功能不受影響，可重新整理此頁）</span>
        <button class="et-x" aria-label="關閉錯誤提示" @click="dismissToast(t.id)">✕</button>
      </div>
    </div>
    <!-- S8：偵測到新版本部署時提示，讓使用者自己選擇何時重新整理 -->
    <div v-if="swUpdateAvailable" class="sw-update-toast" role="status">
      <span class="et-icon">🔄</span>
      <span class="et-text">有新版本可用，重新整理即可更新。</span>
      <button class="ob-go sw-update-btn" @click="applySwUpdate">立即重新整理</button>
      <button class="et-x" aria-label="稍後再說" @click="swUpdateAvailable = false">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Menu, Search } from 'lucide-vue-next'
import { useStockStore } from './stores/stock.js'
import PageCounter from './components/PageCounter.vue'
import QuickSwitcher from './components/QuickSwitcher.vue'
import AppSidebar from './components/AppSidebar.vue'
import ThemePicker from './components/ThemePicker.vue'

const route = useRoute()
const stockStore = useStockStore()
const showOnboard = ref(false)
const mobileSidebarOpen = ref(false)
const quickSwitcherRef = ref(null)

function dismissOnboard() { showOnboard.value = false; localStorage.setItem('finlab_onboarded', '1') }
function openQuickSwitcher() {
  if (quickSwitcherRef.value?.openPanel) quickSwitcherRef.value.openPanel()
  else window.dispatchEvent(new CustomEvent('finlab:open-quick-switcher'))
}

const ROUTE_TITLES = {
  home: '首頁',
  overview: '個股總覽',
  decision: '決策面板',
  watchlist: '觀察清單',
  graph: '關聯圖',
  rotation: '類股輪動',
  compare: '多股比較',
  'etf-compare': 'ETF 比較',
  'market-lights': '大盤多空',
  'news-checker': '新聞可信度',
  screener: 'AI 選股',
  analysis: '個股分析',
  backtest: '策略回測',
  seasonal: '季節性分析',
  'lead-lag': '領先落後',
  'major-players': '主力動向',
  chip: '籌碼分析',
  'social-buzz': '市場熱度',
  'public-data': '公開資訊',
  'risk-sizing': '部位風控',
  'portfolio-heat': '投組風險',
  journal: '交易日誌',
  events: '事件研究台',
  'event-brief': '事件簡報',
  'monte-carlo': '風險模擬',
  'price-alerts': '價格警報',
  signals: '觀察訊號',
  'daily-brief': '盤後日報',
  command: '作戰台',
  guide: '新手上路',
  settings: '設定',
  TradeDashboard: '交易儀表板',
  AISignals: 'AI 交易信號',
  RiskMonitor: '風控監控',
  DataAgent: '資料爬蟲',
  TradeApproval: '交易核准中心',
  SignalRules: '信號規則',
  admin: '後台管理',
  feedback: '意見回饋',
  'kb-qa': '知識庫問答',
  learn: '學習中心',
  'learn-placement': '學習測驗',
  'learn-unit': '課程單元',
  'learn-cert': '完課證書',
  'learn-admin': '課程管理',
  'build-guide': '建站教學',
}

const currentPageTitle = computed(() => {
  const key = route.name ? String(route.name) : ''
  return ROUTE_TITLES[key] || 'FinLab'
})

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

// S8：Service Worker 更新提示（見 main.js）
const swUpdateAvailable = ref(false)
function applySwUpdate() {
  swUpdateAvailable.value = false
  window.__finlabApplySwUpdate?.()
}
onMounted(() => {
  window.addEventListener('finlab:sw-update-available', () => { swUpdateAvailable.value = true })
})

onMounted(() => {
  // Only surface the first-visit banner on the landing page.
  if (!localStorage.getItem('finlab_onboarded') && route.path === '/') showOnboard.value = true
})

// Route name for the page counter. Before the router resolves (first tick),
// route.name is undefined and route.path is '/', which used to get tracked as
// page='/' -> POST junk analytics rows and GET /pageviews/%2F -> 404 (logged
// as 'pageviews//'). Return '' in that window so PageCounter skips it, and
// slash-sanitize any unnamed-path fallback so it can never 404 the GET.
const currentRouteName = computed(() => {
  if (route.name) return String(route.name)
  return route.path.replace(/^\/+|\/+$/g, '').replace(/\//g, '-')
})

// Load Google Client ID from backend (consumed by AppSidebar's sign-in button)
onMounted(async () => {
  try {
    const r = await fetch('/api/v1/settings')
    const data = await r.json()
    const clientId = data?.data?.google_client_id || ''
    if (clientId) window.__GOOGLE_CLIENT_ID__ = clientId
  } catch {}
})
</script>

<style scoped>
.sk-defs { position: absolute; width: 0; height: 0; overflow: hidden; }
/* T-026 統一實底頂欄：收容手機漢堡鈕、當前頁名／個股膠囊、Ctrl+K 搜尋入口與主題選單 */
.app-topbar {
  position: sticky;
  top: 0;
  z-index: 120;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 50px;
  padding: 6px 12px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 8px;
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
}
.sidebar-mobile-toggle {
  display: none;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  align-items: center;
  justify-content: center;
}
.sidebar-mobile-toggle:hover { background: var(--bg-hover); }
.topbar-page-title {
  font-weight: 700;
  font-size: 0.92rem;
  color: var(--heading);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.topbar-stock-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  text-decoration: none;
  font-size: 0.78rem;
  white-space: nowrap;
  flex: 0 0 auto;
}
.topbar-stock-pill:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.topbar-stock-name { color: var(--text-muted); font-size: 0.74rem; }

.topbar-search-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  min-width: 0;
  flex: 0 1 280px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-muted);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.topbar-search-btn:hover {
  border-color: var(--accent-blue);
  color: var(--text-primary);
  background: var(--bg-card);
}
.topbar-search-icon { flex: 0 0 auto; }
.topbar-search-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
  text-align: left;
}
.topbar-kbd {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}
.topbar-right {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
}

@media (max-width: 1024px) {
  .sidebar-mobile-toggle { display: inline-flex; }
}
@media (max-width: 899px) {
  .app-topbar {
    border-radius: 0;
    margin-bottom: 0;
    padding: 6px 10px;
  }
}
@media (max-width: 640px) {
  .topbar-stock-name,
  .topbar-kbd { display: none; }
  .topbar-search-btn { flex: 0 1 auto; padding: 6px 9px; gap: 5px; }
  .topbar-search-label { font-size: 0.76rem; max-width: 78px; }
  .topbar-stock-pill { padding: 2px 7px; font-size: 0.74rem; }
  .topbar-page-title { font-size: 0.85rem; }
}
@media (max-width: 420px) {
  .app-topbar { gap: 6px; padding: 6px 8px; }
  .topbar-stock-pill { display: none; }
  .topbar-search-label { display: none; }
  .topbar-search-btn { width: 34px; height: 34px; padding: 0; justify-content: center; flex: 0 0 auto; }
}
@media print {
  .app-topbar { display: none !important; }
}
.onboard-banner {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: linear-gradient(90deg, color-mix(in srgb, var(--down) 14%, transparent), color-mix(in srgb, var(--blue) 14%, transparent));
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
  background: color-mix(in srgb, var(--status-danger) 12%, var(--card));
  border: 1.5px solid var(--status-danger);
  color: var(--ink);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.84rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}
.error-toast .et-icon { flex: 0 0 auto; }
.error-toast .et-text { flex: 1; min-width: 0; line-height: 1.5; word-break: break-word; }
.error-toast .et-x { background: none; border: none; color: var(--ink-2); cursor: pointer; flex: 0 0 auto; }
.error-toast .et-x:hover { color: var(--ink); }

/* S8：Service Worker 更新提示——用資訊藍而不是錯誤紅，這是例行更新不是問題 */
.sw-update-toast {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 18px;
  z-index: 500;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: min(480px, calc(100vw - 24px));
  background: var(--card);
  border: 1.5px solid var(--accent-blue, var(--blue));
  color: var(--ink);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.84rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}
.sw-update-toast .et-text { flex: 1; min-width: 0; line-height: 1.5; }
.sw-update-toast .sw-update-btn { flex: 0 0 auto; background: var(--accent-blue, var(--blue)); color: var(--on-accent); border: none; border-radius: 8px; padding: 6px 12px; font-weight: 600; font-size: 0.8rem; cursor: pointer; }
.sw-update-toast .et-x { background: none; border: none; color: var(--ink-2); cursor: pointer; flex: 0 0 auto; }
.sw-update-toast .et-x:hover { color: var(--ink); }

.global-counter-wrap {
  position: fixed;
  bottom: 80px;
  right: 16px;
  z-index: 100;
}
</style>
