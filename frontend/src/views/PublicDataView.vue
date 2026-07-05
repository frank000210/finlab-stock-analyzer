<template>
  <div class="public-data-page">
    <PageFocusBanner text="檢視基本面數據，判斷目前股價相對獲利與成長性是便宜還是昂貴。" />

    <header class="page-header">
      <div>
        <h1>📋 公開資訊</h1>
        <p class="subtitle">{{ stockStore.symbol }} {{ stockStore.name }} — 證交所重大公告與財務資訊</p>
      </div>
      <button class="btn btn-primary" @click="fetchData" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <div v-if="data" class="results">
      <!-- Announcements -->
      <section class="card">
        <h2>📢 重大公告</h2>
        <div v-if="data.announcements && data.announcements.length" class="announcements-list">
          <div v-for="(a, i) in data.announcements" :key="i" class="announcement-item">
            <span class="ann-date">{{ a.date }}</span>
            <span class="ann-title">{{ a.title }}</span>
          </div>
        </div>
        <p v-else class="no-data">暫無重大公告</p>
      </section>

      <!-- Dividends -->
      <section class="card">
        <h2>💰 歷年配息</h2>
        <div v-if="data.dividends && data.dividends.length" class="dividend-table">
          <div class="div-header">
            <span>年度</span><span>現金股利</span><span>股票股利</span><span>合計</span>
          </div>
          <div v-for="d in data.dividends" :key="d.year" class="div-row">
            <span>{{ d.year }}</span>
            <span>{{ d.cash }}</span>
            <span>{{ d.stock }}</span>
            <span class="div-total">{{ d.total }}</span>
          </div>
        </div>
        <p v-else class="no-data">暫無配息資料</p>
      </section>

      <!-- Financial Summary -->
      <section class="card" v-if="data.financial_summary">
        <h2>📊 最新財務摘要</h2>
        <div class="fin-grid">
          <div class="fin-item" v-for="(val, key) in data.financial_summary" :key="key">
            <span class="fin-label">{{ formatLabel(key) }}</span>
            <span class="fin-value">{{ val }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'

const route = useRoute()
const stockStore = useStockStore()
const loading = ref(false)
const error = ref('')
const data = ref(null)

const labelMap = {
  revenue_latest: '最新月營收',
  eps_latest: '最新 EPS',
  pe_ratio: '本益比',
  dividend_yield: '殖利率',
  roe: 'ROE',
  roa: 'ROA',
}

function formatLabel(key) {
  return labelMap[key] || key
}

async function fetchData() {
  const sym = route.params.symbol || stockStore.symbol
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${sym}/public-data`)
    const json = await res.json()
    if (json.success) {
      data.value = json.data
    } else {
      error.value = json.error || '載入失敗'
    }
  } catch (e) {
    error.value = '無法連線到伺服器'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
watch(() => route.params.symbol, fetchData)
</script>

<style scoped>
.public-data-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.error-card { color: var(--color-down); background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); }
.no-data { color: var(--text-muted); font-style: italic; }

.announcements-list { display: flex; flex-direction: column; gap: 8px; }
.announcement-item { display: flex; gap: 12px; padding: 10px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); font-size: 0.85rem; }
.ann-date { color: var(--text-muted); min-width: 80px; font-size: 0.78rem; }
.ann-title { flex: 1; }

.dividend-table { font-size: 0.85rem; }
.div-header, .div-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; padding: 8px 12px; }
.div-header { font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color); }
.div-row { border-bottom: 1px solid var(--bg-tertiary); }
.div-total { font-weight: 700; color: var(--accent-green); }

.fin-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-3); }
.fin-item { padding: 12px 16px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.fin-label { display: block; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 4px; }
.fin-value { font-size: 1.1rem; font-weight: 700; }

@media (max-width: 420px) {
  .announcement-item { flex-direction: column; gap: 4px; }
  .ann-date { min-width: 0; }
  .fin-grid { grid-template-columns: 1fr 1fr; }
}
</style>
