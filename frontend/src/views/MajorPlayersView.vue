<template>
  <div class="major-page">
    <header class="page-header">
      <div>
        <h1>🐋 主力動向分析</h1>
        <p class="subtitle">偵測法人拉抬或出貨行為</p>
      </div>
      <div class="controls">
        <input v-model="symbol" placeholder="股票代號" class="input-symbol" @keyup.enter="fetchData" />
        <select v-model="days">
          <option :value="30">30 天</option>
          <option :value="60">60 天</option>
          <option :value="90">90 天</option>
        </select>
        <button class="btn btn-primary" @click="fetchData" :disabled="loading">
          {{ loading ? '分析中...' : '分析' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <div v-if="data" class="results">
      <!-- Verdict -->
      <section class="verdict-section">
        <div class="card verdict-card" :class="'verdict-' + data.verdict">
          <div class="verdict-top">
            <span class="verdict-label">判定結果</span>
            <span class="verdict-value">{{ data.verdict }}</span>
          </div>
          <p class="verdict-desc">{{ data.verdict_description }}</p>
          <div class="confidence-bar">
            <div class="conf-fill" :style="{ width: data.confidence + '%' }"></div>
          </div>
          <span class="conf-text">信心度 {{ data.confidence }}%</span>
        </div>

        <!-- Score gauge -->
        <div class="card score-card">
          <div class="score-label">綜合分數</div>
          <div class="score-value" :class="data.score > 0 ? 'positive' : data.score < 0 ? 'negative' : ''">
            {{ data.score > 0 ? '+' : '' }}{{ data.score }}
          </div>
          <div class="score-scale">
            <span>-100 出貨</span>
            <span>0 中性</span>
            <span>+100 拉抬</span>
          </div>
        </div>
      </section>

      <!-- Signals -->
      <section class="card">
        <h2>📡 偵測信號</h2>
        <div class="signals-list" v-if="data.signals.length">
          <div v-for="(s, i) in data.signals" :key="i" class="signal-item" :class="'signal-' + s.direction">
            <span class="signal-icon">{{ dirIcon(s.direction) }}</span>
            <span class="signal-label">{{ s.label }}</span>
            <span class="signal-weight">{{ s.weight }}</span>
          </div>
        </div>
        <p v-else class="no-signal">無明顯信號偵測</p>
      </section>

      <!-- Institutional Flow Chart -->
      <section class="card" v-if="data.institutional_flow.foreign.length">
        <h2>📊 法人買賣超趨勢</h2>
        <div class="flow-summary">
          <div class="flow-chip">
            <span>外資 5日</span>
            <strong :class="data.institutional_flow.summary.foreign_5d > 0 ? 'positive' : 'negative'">
              {{ formatNet(data.institutional_flow.summary.foreign_5d) }}
            </strong>
          </div>
          <div class="flow-chip">
            <span>外資 10日</span>
            <strong :class="data.institutional_flow.summary.foreign_10d > 0 ? 'positive' : 'negative'">
              {{ formatNet(data.institutional_flow.summary.foreign_10d) }}
            </strong>
          </div>
          <div class="flow-chip">
            <span>投信 5日</span>
            <strong :class="data.institutional_flow.summary.trust_5d > 0 ? 'positive' : 'negative'">
              {{ formatNet(data.institutional_flow.summary.trust_5d) }}
            </strong>
          </div>
          <div class="flow-chip">
            <span>外資連買</span>
            <strong>{{ data.institutional_flow.summary.foreign_streak }} 日</strong>
          </div>
        </div>
        <div class="flow-bars">
          <div v-for="d in data.institutional_flow.foreign.slice(-20)" :key="d.date" class="flow-bar-col">
            <div class="flow-bar" :class="d.net > 0 ? 'buy' : 'sell'" :style="{ height: barHeight(d.net) + 'px' }"></div>
            <span class="flow-date" v-if="data.institutional_flow.foreign.slice(-20).indexOf(d) % 5 === 0">{{ d.date.slice(5) }}</span>
          </div>
        </div>
        <div class="flow-legend">
          <span class="legend-buy">▇ 外資買超</span>
          <span class="legend-sell">▇ 外資賣超</span>
        </div>
      </section>

      <!-- Volume-Price -->
      <section class="card" v-if="data.volume_price.indicators.length">
        <h2>📈 量價分析</h2>
        <div class="vp-table">
          <div class="vp-header">
            <span>日期</span><span>收盤</span><span>成交量</span><span>量比</span><span>OBV</span>
          </div>
          <div v-for="ind in data.volume_price.indicators.slice(-10)" :key="ind.date" class="vp-row">
            <span>{{ ind.date.slice(5) }}</span>
            <span>{{ ind.close }}</span>
            <span>{{ (ind.volume / 1000).toFixed(0) }}K</span>
            <span :class="ind.vol_ratio > 1.5 ? 'highlight' : ''">{{ ind.vol_ratio }}x</span>
            <span>{{ (ind.obv / 1000000).toFixed(1) }}M</span>
          </div>
        </div>
      </section>

      <!-- Margin -->
      <section class="card" v-if="data.margin_analysis.data.length">
        <h2>💳 融資融券</h2>
        <div class="margin-summary">
          <div class="margin-chip">
            <span>融資餘額</span>
            <strong>{{ (data.margin_analysis.summary.margin_balance_latest / 1000).toFixed(0) }}K 張</strong>
          </div>
          <div class="margin-chip">
            <span>融券餘額</span>
            <strong>{{ (data.margin_analysis.summary.short_balance_latest / 1000).toFixed(0) }}K 張</strong>
          </div>
          <div class="margin-chip">
            <span>融資 5日變化</span>
            <strong :class="data.margin_analysis.summary.margin_change_5d > 0 ? 'negative' : 'positive'">
              {{ data.margin_analysis.summary.margin_change_5d > 0 ? '+' : '' }}{{ data.margin_analysis.summary.margin_change_5d }}
            </strong>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'

const route = useRoute()
const stockStore = useStockStore()
const symbol = ref(route.params.symbol || stockStore.symbol)
const days = ref(90)
const loading = ref(false)
const error = ref('')
const data = ref(null)

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${symbol.value}/major-players?days=${days.value}`)
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

function dirIcon(dir) {
  return dir === 'bullish' ? '🟢' : dir === 'bearish' ? '🔴' : '🟡'
}

function formatNet(val) {
  if (!val) return '0'
  if (Math.abs(val) >= 1000000) return (val / 1000000).toFixed(1) + 'M'
  if (Math.abs(val) >= 1000) return (val / 1000).toFixed(0) + 'K'
  return val.toString()
}

function barHeight(net) {
  const max = Math.max(...(data.value?.institutional_flow?.foreign?.map(d => Math.abs(d.net)) || [1]))
  return Math.max(2, Math.abs(net) / max * 80)
}

onMounted(fetchData)
</script>

<style scoped>
.major-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.input-symbol { width: 90px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font-weight: 700; text-align: center; }
.controls select { padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); }
.error-card { color: var(--color-down); background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); }

.verdict-section { display: grid; grid-template-columns: 2fr 1fr; gap: var(--space-4); }
.verdict-card { background: var(--bg-elevated); box-shadow: var(--shadow-md); }
.verdict-拉抬 { background: linear-gradient(135deg, rgba(34, 197, 94, 0.14), var(--bg-elevated) 55%); }
.verdict-偏多 { background: linear-gradient(135deg, rgba(34, 197, 94, 0.07), var(--bg-elevated) 55%); }
.verdict-出貨 { background: linear-gradient(135deg, rgba(239, 68, 68, 0.14), var(--bg-elevated) 55%); }
.verdict-偏空 { background: linear-gradient(135deg, rgba(239, 68, 68, 0.07), var(--bg-elevated) 55%); }
.verdict-中性 { background: linear-gradient(135deg, rgba(59, 130, 246, 0.10), var(--bg-elevated) 55%); }
.verdict-top { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.verdict-label { font-size: 0.8rem; color: var(--text-muted); }
.verdict-value { font-size: 1.5rem; font-weight: 800; }
.verdict-desc { font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 12px; }
.confidence-bar { height: 6px; background: var(--bg-tertiary); border-radius: 3px; }
.conf-fill { height: 100%; background: var(--accent-blue); border-radius: 3px; transition: width 0.4s; }
.conf-text { font-size: 0.72rem; color: var(--text-muted); }

.score-card { text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; }
.score-label { font-size: 0.8rem; color: var(--text-muted); }
.score-value { font-size: 2.5rem; font-weight: 800; }
.score-value.positive { color: var(--accent-green); }
.score-value.negative { color: var(--accent-red); }
.score-scale { display: flex; justify-content: space-between; width: 100%; font-size: 0.65rem; color: var(--text-muted); margin-top: 8px; }

.signals-list { display: flex; flex-direction: column; gap: 8px; }
.signal-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.signal-bullish { background: rgba(34, 197, 94, 0.12); }
.signal-bearish { background: rgba(239, 68, 68, 0.12); }
.signal-caution { background: rgba(234, 179, 8, 0.12); }
.signal-icon { font-size: 1rem; }
.signal-label { flex: 1; font-size: 0.85rem; }
.signal-weight { font-size: 0.7rem; color: var(--text-muted); padding: 2px 8px; background: var(--bg-primary); border-radius: 10px; }
.no-signal { color: var(--text-muted); font-style: italic; }

.flow-summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.flow-chip { display: flex; flex-direction: column; gap: 2px; padding: 8px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); font-size: 0.78rem; }
.flow-chip span { color: var(--text-muted); }
.flow-chip strong { font-size: 0.9rem; }
.positive { color: var(--accent-green); }
.negative { color: var(--accent-red); }

.flow-bars { display: flex; align-items: flex-end; gap: 3px; height: 100px; border-bottom: 1px solid var(--border-color); padding-bottom: 4px; }
.flow-bar-col { display: flex; flex-direction: column; align-items: center; flex: 1; }
.flow-bar { width: 100%; border-radius: 2px; min-height: 2px; }
.flow-bar.buy { background: var(--accent-green); }
.flow-bar.sell { background: var(--accent-red); }
.flow-date { font-size: 0.55rem; color: var(--text-muted); margin-top: 4px; }
.flow-legend { display: flex; gap: 16px; margin-top: 8px; font-size: 0.72rem; color: var(--text-muted); }
.legend-buy { color: var(--accent-green); }
.legend-sell { color: var(--accent-red); }

.vp-table { font-size: 0.78rem; }
.vp-header, .vp-row { display: grid; grid-template-columns: 1fr 1fr 1fr 0.8fr 1fr; gap: 8px; padding: 6px 0; }
.vp-header { font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color); }
.vp-row { border-bottom: 1px solid var(--bg-tertiary); }
.highlight { color: var(--accent-blue); font-weight: 700; }

.margin-summary { display: flex; gap: 12px; flex-wrap: wrap; }
.margin-chip { display: flex; flex-direction: column; gap: 2px; padding: 8px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); font-size: 0.78rem; }
.margin-chip span { color: var(--text-muted); }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .verdict-section { grid-template-columns: 1fr; }
}
@media (max-width: 420px) {
  .flow-summary { gap: 6px; }
  .flow-chip { padding: 6px 10px; font-size: 0.7rem; }
}
</style>