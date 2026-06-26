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
        <router-link to="/settings">⚙️ 設定</router-link>
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
