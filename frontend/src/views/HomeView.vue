<template>
  <div class="home">
    <section class="hero">
      <h1>台股個股深度分析平台</h1>
      <p>輸入股票代碼或名稱，開始技術面、基本面、籌碼面完整分析</p>
      <div class="hero-search">
        <input
          v-model="query"
          @keyup.enter="search"
          placeholder="搜尋股票代碼或名稱 (例: 2330)"
          class="hero-input"
        />
        <button @click="search" class="btn btn-primary">開始分析</button>
      </div>
    </section>

    <section class="grid-2" style="margin-top: 32px;">
      <div class="card">
        <h3>🕐 最近瀏覽</h3>
        <ul class="recent-list">
          <li v-for="s in recentStocks" :key="s" @click="$router.push(`/stocks/${s}`)">
            {{ s }}
          </li>
          <li v-if="!recentStocks.length" class="empty">尚無瀏覽紀錄</li>
        </ul>
      </div>
      <div class="card">
        <h3>⚡ 快速操作</h3>
        <div style="display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap;">
          <button class="btn btn-primary" @click="$router.push('/stocks/2330')">分析台積電</button>
          <button class="btn btn-primary" @click="$router.push('/stocks/2330/backtest')">回測範例</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const query = ref('')
const recentStocks = ref(JSON.parse(localStorage.getItem('recentStocks') || '[]'))

function search() {
  const q = query.value.trim()
  if (q) {
    router.push(`/stocks/${q}`)
  }
}
</script>

<style scoped>
.hero {
  text-align: center;
  padding: 48px 0;
}
.hero h1 {
  font-size: 2rem;
  margin-bottom: 8px;
}
.hero p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.hero-search {
  display: flex;
  gap: 12px;
  max-width: 500px;
  margin: 0 auto;
}
.hero-input {
  flex: 1;
  padding: 12px 16px;
  border-radius: var(--radius);
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 1rem;
}
.recent-list {
  list-style: none;
  margin-top: 12px;
}
.recent-list li {
  padding: 8px 0;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
}
.recent-list li:hover {
  color: var(--accent-blue);
}
.empty {
  color: var(--text-secondary);
}
</style>
