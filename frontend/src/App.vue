<template>
  <div id="app-root">
    <AppSidebar />
    <div class="app-body">
      <div v-if="showOnboard" class="onboard-banner">
        <span>👋 第一次來？花 3 分鐘看「新手上路」，把整套交易紀律流程走一遍。</span>
        <router-link class="ob-go" to="/guide" @click="dismissOnboard">開始導覽 →</router-link>
        <button class="ob-x" @click="dismissOnboard" aria-label="關閉導覽提示">✕</button>
      </div>
      <main class="main-content">
        <router-view />
      </main>
    </div>
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
import { useStockStore } from './stores/stock.js'
import PageCounter from './components/PageCounter.vue'
import QuickSwitcher from './components/QuickSwitcher.vue'
import AppSidebar from './components/AppSidebar.vue'

const route = useRoute()
const stockStore = useStockStore()
const showOnboard = ref(false)
function dismissOnboard() { showOnboard.value = false; localStorage.setItem('finlab_onboarded', '1') }

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
  background: rgba(12, 24, 40, 0.96);
  border: 1px solid var(--accent-blue, #3b82f6);
  color: #bfdbfe;
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.84rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}
.sw-update-toast .et-text { flex: 1; min-width: 0; line-height: 1.5; }
.sw-update-toast .sw-update-btn { flex: 0 0 auto; background: var(--accent-blue, #3b82f6); color: #fff; border: none; border-radius: 8px; padding: 6px 12px; font-weight: 600; font-size: 0.8rem; cursor: pointer; }
.sw-update-toast .et-x { background: none; border: none; color: #bfdbfe; cursor: pointer; flex: 0 0 auto; }
.sw-update-toast .et-x:hover { color: #fff; }

.global-counter-wrap {
  position: fixed;
  bottom: 80px;
  right: 16px;
  z-index: 100;
}
</style>
