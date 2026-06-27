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
            @mousedown="selectStock(item.symbol)"
          >
            <span class="search-symbol">{{ item.symbol }}</span>
            <span class="search-name">{{ item.name_zh }}</span>
          </li>
        </ul>
      </div>
      <div class="nav-links primary-nav">
        <router-link to="/decision" class="nav-cta">🎯 決策面板</router-link>
        <router-link to="/stocks/2330">分析</router-link>
        <router-link to="/stocks/2330/backtest">回測</router-link>
        <router-link to="/ai-signals">AI 信號</router-link>
        <router-link to="/risk-monitor">風控</router-link>
      </div>
      <div class="nav-links secondary-nav">
        <router-link to="/trade-dashboard">儀表板</router-link>
        <router-link to="/data-agent">資料</router-link>
        <router-link to="/settings">設定</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const router = useRouter()
const searchQuery = ref('')
const searchResults = ref([])
let searchTimeout = null

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

function selectStock(symbol) {
  searchResults.value = []
  searchQuery.value = ''
  router.push(`/stocks/${symbol}`)
}

function goToStock() {
  if (searchResults.value.length > 0) {
    selectStock(searchResults.value[0].symbol)
  } else if (searchQuery.value.match(/^\d{4}$/)) {
    selectStock(searchQuery.value)
  }
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

@media (max-width: 1024px) {
  .secondary-nav { display: none; }
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
</style>
