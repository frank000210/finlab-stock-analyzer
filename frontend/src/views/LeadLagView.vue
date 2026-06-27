<template>
  <div class="leadlag-page">
    <header class="page-header">
      <div>
        <h1>⏱️ 領先/落後分析</h1>
        <p class="subtitle">比較個股與大盤或龍頭股的漲跌時序關係</p>
      </div>
      <div class="controls">
        <input v-model="symbol" placeholder="股票代號" class="input-symbol" @keyup.enter="fetchData" />
        <select v-model="benchmark">
          <option value="TAIEX">加權指數</option>
          <option v-for="l in leaders" :key="l.symbol" :value="l.symbol">{{ l.name }} ({{ l.symbol }})</option>
        </select>
        <button class="btn btn-primary" @click="fetchData" :disabled="loading">
          {{ loading ? '計算中...' : '分析' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <div v-if="data" class="results">
      <!-- Verdict Card -->
      <section class="card verdict-card">
        <div class="verdict-header">
          <span class="verdict-badge" :class="'dir-' + data.interpretation.direction">
            {{ data.interpretation.direction }}
          </span>
          <span class="verdict-lag">
            最佳相關延遲: <strong>{{ data.optimal_lag }} 天</strong>
          </span>
        </div>
        <p class="verdict-detail">{{ data.interpretation.direction_detail }}</p>
        <p class="verdict-suggestion">💡 {{ data.interpretation.suggestion }}</p>
        <div class="verdict-meta">
          <span>相關強度: {{ data.interpretation.correlation_strength }}</span>
          <span>峰值相關: {{ data.peak_correlation }}</span>
          <span>同步相關: {{ data.concurrent_correlation }}</span>
          <span>一致性: {{ data.interpretation.consistency_pct }}%</span>
        </div>
      </section>

      <!-- Beta -->
      <section class="card beta-card">
        <h3>β 值 (Beta)</h3>
        <div class="beta-row">
          <div class="beta-value">{{ data.beta.value }}</div>
          <div class="beta-desc">{{ data.beta.interpretation }}</div>
          <div class="beta-r2">R² = {{ data.beta.r_squared }}</div>
        </div>
      </section>

      <!-- Cross-Correlation Chart -->
      <section class="card">
        <h2>📉 交叉相關性圖</h2>
        <p class="chart-hint">X 軸為延遲天數（正 = 個股領先，負 = 個股落後），Y 軸為相關係數</p>
        <div class="corr-chart">
          <div class="corr-bars">
            <div v-for="c in data.correlations" :key="c.lag" class="corr-bar-wrapper">
              <div
                class="corr-bar"
                :class="{ peak: c.lag === data.optimal_lag, positive: c.correlation > 0, negative: c.correlation < 0 }"
                :style="{ height: Math.abs(c.correlation) * 120 + 'px', marginTop: c.correlation >= 0 ? (120 - Math.abs(c.correlation) * 120) + 'px' : '120px' }"
              ></div>
              <span v-if="c.lag % 5 === 0" class="corr-label">{{ c.lag }}</span>
            </div>
          </div>
          <div class="corr-axis-labels">
            <span>← 個股落後</span>
            <span>同步</span>
            <span>個股領先 →</span>
          </div>
        </div>
      </section>

      <!-- Rolling Lead-Lag -->
      <section class="card" v-if="data.rolling_lead_lag.length">
        <h2>📊 滾動領先/落後趨勢</h2>
        <p class="chart-hint">60 日視窗的最佳延遲隨時間變化</p>
        <div class="rolling-table">
          <div v-for="r in data.rolling_lead_lag" :key="r.date" class="rolling-row">
            <span class="rolling-date">{{ r.date }}</span>
            <div class="rolling-bar-track">
              <div class="rolling-bar" :style="rollingBarStyle(r.lag)" :class="r.lag > 0 ? 'lead' : r.lag < 0 ? 'lag-bar' : 'sync'"></div>
            </div>
            <span class="rolling-val">{{ r.lag > 0 ? '+' : '' }}{{ r.lag }}天</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const symbol = ref(route.params.symbol || '2330')
const benchmark = ref('TAIEX')
const loading = ref(false)
const error = ref('')
const data = ref(null)
const leaders = ref([
  { symbol: '2330', name: '台積電', sector: '半導體' },
  { symbol: '2317', name: '鴻海', sector: '電子' },
  { symbol: '2882', name: '國泰金', sector: '金融' },
  { symbol: '2603', name: '長榮', sector: '航運' },
  { symbol: '1301', name: '台塑', sector: '傳產' },
])

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${symbol.value}/lead-lag?benchmark=${benchmark.value}&days=365&max_lag=20`)
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

function rollingBarStyle(lag) {
  const pct = (lag / 20) * 50
  if (lag >= 0) {
    return { left: '50%', width: Math.abs(pct) + '%' }
  } else {
    return { right: '50%', width: Math.abs(pct) + '%' }
  }
}

onMounted(fetchData)
</script>

<style scoped>
.leadlag-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.input-symbol { width: 90px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font-weight: 700; text-align: center; }
.controls select { padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); }
.error-card { color: var(--accent-red); border-left: 3px solid var(--accent-red); }

.verdict-card { border-left: 4px solid var(--accent-blue); }
.verdict-header { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.verdict-badge { padding: 4px 16px; border-radius: 20px; font-weight: 700; font-size: 1.1rem; }
.dir-領先 { background: rgba(34, 197, 94, 0.15); color: var(--accent-green); }
.dir-落後 { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
.dir-同步 { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }
.verdict-lag { font-size: 0.85rem; color: var(--text-secondary); }
.verdict-detail { font-size: 0.95rem; color: var(--text-primary); margin-bottom: 8px; }
.verdict-suggestion { font-size: 0.85rem; color: var(--accent-blue); background: rgba(59, 130, 246, 0.06); padding: 10px 14px; border-radius: var(--radius-sm); }
.verdict-meta { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; font-size: 0.78rem; color: var(--text-muted); }

.beta-card h3 { margin-bottom: 8px; }
.beta-row { display: flex; align-items: center; gap: 16px; }
.beta-value { font-size: 2rem; font-weight: 800; color: var(--accent-blue); }
.beta-desc { font-size: 0.85rem; color: var(--text-secondary); }
.beta-r2 { font-size: 0.8rem; color: var(--text-muted); margin-left: auto; }

.chart-hint { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px; }
.corr-chart { overflow-x: auto; }
.corr-bars { display: flex; align-items: flex-end; height: 240px; gap: 2px; padding-bottom: 20px; border-bottom: 1px solid var(--border-color); position: relative; }
.corr-bar-wrapper { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 6px; position: relative; }
.corr-bar { width: 100%; border-radius: 2px; transition: height 0.3s; }
.corr-bar.positive { background: rgba(34, 197, 94, 0.5); }
.corr-bar.negative { background: rgba(239, 68, 68, 0.5); }
.corr-bar.peak { background: var(--accent-blue) !important; box-shadow: 0 0 8px rgba(59, 130, 246, 0.5); }
.corr-label { position: absolute; bottom: -18px; font-size: 0.6rem; color: var(--text-muted); }
.corr-axis-labels { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-top: 24px; }

.rolling-table { display: flex; flex-direction: column; gap: 6px; max-height: 400px; overflow-y: auto; }
.rolling-row { display: flex; align-items: center; gap: 12px; }
.rolling-date { font-size: 0.72rem; color: var(--text-muted); min-width: 80px; }
.rolling-bar-track { flex: 1; height: 16px; background: var(--bg-tertiary); border-radius: 8px; position: relative; overflow: hidden; }
.rolling-bar { position: absolute; height: 100%; border-radius: 8px; }
.rolling-bar.lead { background: var(--accent-green); }
.rolling-bar.lag-bar { background: var(--accent-red); }
.rolling-bar.sync { background: var(--accent-blue); width: 3px !important; left: calc(50% - 1.5px) !important; }
.rolling-val { font-size: 0.72rem; font-weight: 600; min-width: 48px; text-align: right; }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .verdict-meta { flex-direction: column; gap: 4px; }
  .beta-row { flex-wrap: wrap; }
}
@media (max-width: 420px) {
  .corr-bars { height: 160px; }
  .rolling-date { min-width: 60px; font-size: 0.65rem; }
}
</style>