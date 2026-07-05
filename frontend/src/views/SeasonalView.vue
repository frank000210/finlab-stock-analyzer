<template>
  <div class="seasonal-page">
    <PageFocusBanner text="找出這檔股票是否存在季節性慣性，作為擇時的輔助參考。" />

    <header class="page-header">
      <div>
        <h1>📅 季節性分析</h1>
        <p class="subtitle">觀察個股在不同月份的歷史表現規律</p>
      </div>
      <div class="controls">
        <input v-model="symbol" placeholder="股票代號" class="input-symbol" @keyup.enter="fetchData" />
        <select v-model="years">
          <option :value="3">3 年</option>
          <option :value="5">5 年</option>
          <option :value="7">7 年</option>
          <option :value="10">10 年</option>
        </select>
        <button class="btn btn-primary" @click="fetchData" :disabled="loading">
          {{ loading ? '分析中...' : '開始分析' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <div v-if="data" class="results">
      <!-- Patterns -->
      <section class="card patterns-section">
        <h2>🔍 偵測到的規律</h2>
        <div class="patterns-grid">
          <div v-for="p in data.patterns" :key="p.type" class="pattern-card" :class="p.type">
            <div class="pattern-header">
              <span class="pattern-name">{{ p.name }}</span>
              <span class="pattern-strength" :class="'strength-' + p.strength">{{ p.strength }}</span>
            </div>
            <p class="pattern-desc">{{ p.description }}</p>
            <p class="pattern-suggestion">💡 {{ p.suggestion }}</p>
          </div>
        </div>
      </section>

      <!-- Monthly Heatmap -->
      <section class="card">
        <h2>📊 月報酬率熱力圖</h2>
        <div class="heatmap-container">
          <table class="heatmap-table">
            <thead>
              <tr>
                <th>年份</th>
                <th v-for="m in 12" :key="m">{{ m }}月</th>
                <th>年度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.yearly_matrix" :key="row.year">
                <td class="year-cell">{{ row.year }}</td>
                <td v-for="m in 12" :key="m" class="heat-cell" :style="heatColor(row.months[m])">
                  {{ row.months[m] != null ? row.months[m].toFixed(1) : '–' }}
                </td>
                <td class="year-total" :style="heatColor(yearTotal(row))">
                  {{ yearTotal(row).toFixed(1) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Monthly Stats -->
      <section class="card">
        <h2>📈 各月統計</h2>
        <div class="stats-grid">
          <div v-for="ms in data.month_stats" :key="ms.month" class="month-stat-card">
            <div class="month-label">{{ ms.month }}月</div>
            <div class="stat-value" :class="ms.avg_return >= 0 ? 'positive' : 'negative'">
              {{ ms.avg_return >= 0 ? '+' : '' }}{{ ms.avg_return }}%
            </div>
            <div class="win-rate-bar">
              <div class="win-fill" :style="{ width: ms.win_rate + '%' }"></div>
            </div>
            <div class="stat-meta">勝率 {{ ms.win_rate }}%</div>
          </div>
        </div>
      </section>

      <!-- Quarterly -->
      <section class="card">
        <h2>📋 季度彙整</h2>
        <div class="quarter-grid">
          <div v-for="q in data.quarterly_stats" :key="q.quarter" class="quarter-card">
            <div class="quarter-label">Q{{ q.quarter }}</div>
            <div class="quarter-value" :class="q.avg_return >= 0 ? 'positive' : 'negative'">
              {{ q.avg_return >= 0 ? '+' : '' }}{{ q.avg_return }}%
            </div>
            <div class="quarter-wr">勝率 {{ q.win_rate }}%</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'

const route = useRoute()
const stockStore = useStockStore()
const symbol = ref(route.params.symbol || stockStore.symbol)
const years = ref(5)
const loading = ref(false)
const error = ref('')
const data = ref(null)

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${symbol.value}/seasonal?years=${years.value}`)
    const json = await res.json()
    if (json.success) {
      data.value = json.data
    } else {
      error.value = json.error || '分析失敗'
    }
  } catch (e) {
    error.value = '無法連線到伺服器'
  } finally {
    loading.value = false
  }
}

function heatColor(val) {
  if (val == null) return { background: 'var(--bg-tertiary)' }
  const clamped = Math.max(-10, Math.min(10, val))
  if (clamped >= 0) {
    const intensity = Math.min(1, clamped / 8)
    return { background: `rgba(34, 197, 94, ${0.1 + intensity * 0.6})`, color: intensity > 0.4 ? '#fff' : 'inherit' }
  } else {
    const intensity = Math.min(1, Math.abs(clamped) / 8)
    return { background: `rgba(239, 68, 68, ${0.1 + intensity * 0.6})`, color: intensity > 0.4 ? '#fff' : 'inherit' }
  }
}

function yearTotal(row) {
  const vals = Object.values(row.months).filter(v => v != null)
  return vals.reduce((a, b) => a + b, 0)
}

fetchData()
</script>

<style scoped>
.seasonal-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.input-symbol { width: 90px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font-weight: 700; text-align: center; }
.controls select { padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); }
.error-card { color: var(--color-down); background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); }

.patterns-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--space-4); }
.pattern-card { padding: var(--space-4); background: var(--bg-tertiary); border-radius: var(--radius); }
.pattern-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pattern-name { font-weight: 700; font-size: 1rem; }
.pattern-strength { font-size: 0.75rem; padding: 2px 10px; border-radius: 20px; font-weight: 600; }
.strength-強 { background: rgba(34, 197, 94, 0.15); color: var(--accent-green); }
.strength-中 { background: rgba(234, 179, 8, 0.15); color: #eab308; }
.strength-弱 { background: rgba(156, 163, 175, 0.15); color: var(--text-muted); }
.pattern-desc { font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; margin: 8px 0; }
.pattern-suggestion { font-size: 0.8rem; color: var(--accent-blue); background: rgba(59, 130, 246, 0.08); padding: 8px 12px; border-radius: var(--radius-sm); }

.heatmap-container { overflow-x: auto; }
.heatmap-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; text-align: center; }
.heatmap-table th { padding: 8px 4px; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color); }
.heatmap-table td { padding: 6px 4px; }
.heat-cell { border-radius: 4px; font-weight: 600; min-width: 44px; }
.year-cell { font-weight: 700; color: var(--text-secondary); }
.year-total { font-weight: 700; border-radius: 4px; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); gap: var(--space-3); }
.month-stat-card { text-align: center; padding: var(--space-3); background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.month-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }
.stat-value { font-size: 1.1rem; font-weight: 700; margin: 4px 0; }
.stat-value.positive { color: var(--accent-green); }
.stat-value.negative { color: var(--accent-red); }
.win-rate-bar { height: 4px; background: var(--bg-primary); border-radius: 2px; margin: 6px 0 4px; }
.win-fill { height: 100%; background: var(--accent-blue); border-radius: 2px; transition: width 0.3s; }
.stat-meta { font-size: 0.65rem; color: var(--text-muted); }

.quarter-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.quarter-card { text-align: center; padding: var(--space-4); background: var(--bg-tertiary); border-radius: var(--radius); }
.quarter-label { font-size: 0.85rem; color: var(--text-muted); font-weight: 700; }
.quarter-value { font-size: 1.4rem; font-weight: 700; margin: 6px 0; }
.quarter-value.positive { color: var(--accent-green); }
.quarter-value.negative { color: var(--accent-red); }
.quarter-wr { font-size: 0.75rem; color: var(--text-secondary); }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .quarter-grid { grid-template-columns: repeat(2, 1fr); }
  .patterns-grid { grid-template-columns: 1fr; }
}
@media (max-width: 420px) {
  .stats-grid { grid-template-columns: repeat(4, 1fr); }
  .heatmap-table { font-size: 0.65rem; }
  .heat-cell { min-width: 32px; padding: 4px 2px; }
}
</style>