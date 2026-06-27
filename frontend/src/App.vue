<template>
  <div id="app-root">
    <nav class="top-nav">
      <router-link to="/" class="logo">📈 FinLab</router-link>
      <div class="search-bar">
        <input
          v-model="searchQuery"
          @input="onSearch"
          @keyup.enter="goToStock"
          placeholder="搜尋股票 (例: 2330 台積電)"
          class="search-input"
        />
        <ul v-if="searchResults.length" class="search-dropdown">
          <li
            v-for="item in searchResults"
            :key="item.symbol"
            @click="selectStock(item.symbol)"
          >
            {{ item.symbol }} - {{ item.name_zh }}
          </li>
        </ul>
      </div>
      <div class="nav-links">
        <router-link to="/">🏠 首頁</router-link>
        <router-link to="/decision" class="nav-highlight">🎯 決策面板</router-link>
        <router-link to="/stocks/2330">📊 分析</router-link>
        <router-link to="/stocks/2330/backtest">🧪 回測</router-link>
        <router-link to="/settings">⚙️ 設定</router-link>
      </div>
      <div class="nav-divider"></div>
      <div class="ai-nav">
        <span class="nav-section-title">AI 交易系統</span>
        <div class="nav-links">
          <router-link to="/trade-dashboard">交易儀表板</router-link>
          <router-link to="/ai-signals">AI 信號</router-link>
          <router-link to="/risk-monitor">風控監控</router-link>
          <router-link to="/data-agent">資料爬蟲</router-link>
          <router-link to="/trade-approval">交易核准</router-link>
          <router-link to="/signal-rules">信號規則</router-link>
        </div>
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
import axios from 'axios'

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
      const resp = await axios.get(`/api/v1/stocks/search?q=${searchQuery.value}`)
      searchResults.value = resp.data.data.items || []
    } catch {
      searchResults.value = []
    }
  }, 300)
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
.nav-links {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.nav-links a.router-link-active {
  color: var(--text-primary);
}

.nav-highlight {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  padding: 4px 10px;
  border-radius: 6px;
  color: #fff !important;
  font-weight: 600;
}

.nav-divider {
  width: 1px;
  min-height: 28px;
  background: var(--border-color);
}

.ai-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.nav-section-title {
  font-size: 0.78rem;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@media (max-width: 1200px) {
  .top-nav {
    height: auto;
    min-height: 64px;
    flex-wrap: wrap;
  }

  .nav-divider {
    display: none;
  }
}

@media (max-width: 768px) {
  .ai-nav {
    width: 100%;
    align-items: flex-start;
    flex-direction: column;
  }

  .search-bar {
    order: 3;
    width: 100%;
    max-width: none;
  }
}
</style>
