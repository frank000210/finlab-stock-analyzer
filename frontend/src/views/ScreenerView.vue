<template>
  <div class="screener-page">
    <PageFocusBanner text="用一句話描述想找的股票條件，AI 解析成篩選門檻，套用網站既有數據跑數字比較。" />

    <header class="page-header">
      <div>
        <h1>🔎 AI 選股 <InfoTooltip v-bind="metricGlossary.nlScreener" /></h1>
        <p class="subtitle">AI 只負責把你的話解析成篩選條件，實際篩選用網站既有數據比對，不會幫你編造股票</p>
      </div>
    </header>

    <div v-if="!aiConfigured" class="card">
      <p class="muted">AI 服務尚未設定，此功能暫時無法使用。</p>
    </div>

    <template v-else>
      <section class="card query-card">
        <label class="field">
          <span>選股條件</span>
          <textarea
            v-model="query"
            class="inp"
            rows="2"
            placeholder="例如：找散熱概念股，本益比小於20、營收年增大於10%"
            @keydown.enter.exact.prevent="runQuery()"
          ></textarea>
        </label>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="loading || !query.trim()" @click="runQuery()">
            <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
            {{ loading ? '篩選中…（約 20~60 秒）' : '開始篩選' }}
          </button>
          <span v-if="error" class="error-text">{{ error }}</span>
        </div>
      </section>

      <section v-if="result" class="card result-card">
        <div class="criteria-echo">
          <strong>解析條件：</strong>{{ result.criteria.description || '（無特定描述）' }}
          <span v-if="result.criteria.industry_keywords?.length" class="tag-list">
            <em v-for="k in result.criteria.industry_keywords" :key="k" class="kw-tag">{{ k }}</em>
          </span>
          <span v-if="result.criteria.pe_max != null" class="kw-tag">PE ≤ {{ result.criteria.pe_max }}</span>
          <span v-if="result.criteria.pe_min != null" class="kw-tag">PE ≥ {{ result.criteria.pe_min }}</span>
          <span v-if="result.criteria.revenue_yoy_min != null" class="kw-tag">營收年增 ≥ {{ result.criteria.revenue_yoy_min }}%</span>
        </div>
        <div class="pool-row">
          <p class="muted small">依產業關鍵字比對＋成交金額排序取候選池 {{ result.candidate_pool_size }} 檔（非嚴格全市場掃描），其中符合條件 {{ result.matched_count }} 檔。</p>
          <!-- X10：候選池太窄找不到符合條件的股票時，直接擴大範圍重查，不用逼使用者換句話重問 -->
          <button
            v-if="!result.expanded"
            class="btn xs"
            type="button"
            :disabled="loading"
            @click="runQuery(true)"
          >
            🔍 擴大候選池重查（{{ (result.candidate_pool_max || 0) * 2 }} 檔）
          </button>
        </div>

        <div v-if="result.matched.length" class="table-wrap">
          <table>
            <thead>
              <tr><th>代碼</th><th>名稱</th><th>股價</th><th>PE</th><th>營收YoY均</th><th>毛利率</th><th>20日漲跌</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in result.matched" :key="r.symbol" class="clickable" @click="goToStock(r.symbol)">
                <td><strong>{{ r.symbol }}</strong></td>
                <td>{{ r.name }}</td>
                <td>{{ r.price ?? '—' }}</td>
                <td>{{ r.pe ?? '—' }}</td>
                <td>{{ r.revenue_yoy_avg != null ? r.revenue_yoy_avg + '%' : '—' }}</td>
                <td>{{ r.gross_margin != null ? r.gross_margin + '%' : '—' }}</td>
                <td :class="valueTone(r.mom20_pct)">{{ r.mom20_pct != null ? (r.mom20_pct >= 0 ? '+' : '') + r.mom20_pct + '%' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty-state">候選池中沒有股票符合所有篩選條件，可以放寬門檻或換個描述再試。</p>
        <p class="disclaimer">※ 篩選結果僅為數據比對，非投資建議；候選池排序依成交金額，非全市場嚴格掃描，可能漏掉冷門但符合條件的標的。</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { useAiStatus } from '../composables/useAiStatus'

const router = useRouter()
const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const { aiConfigured, checkAiConfigured } = useAiStatus()

function valueTone(v) {
  if (v == null) return ''
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

function goToStock(symbol) {
  router.push(`/stocks/${symbol}`)
}

async function runQuery(expand = false) {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    // 呼叫 LLM，重試只會讓使用者等更久，不套用重試包裝（同 W2/W4 的慣例）
    const res = await fetch('/api/v1/screener/query', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query.value.trim(), expand }),
    })
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || '查詢失敗')
    result.value = json.data
  } catch (e) {
    error.value = e?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

onMounted(checkAiConfigured)
</script>

<style scoped>
.screener-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header h1 { margin: 0 0 4px; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin: 0; }

.query-card { display: flex; flex-direction: column; gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); resize: vertical; }
.form-actions { display: flex; align-items: center; gap: 12px; }
.error-text { color: #ef4444; font-size: 0.84rem; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.result-card { display: flex; flex-direction: column; gap: 10px; }
.criteria-echo { font-size: 0.86rem; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tag-list { display: contents; }
.kw-tag { font-style: normal; font-size: 0.74rem; padding: 2px 8px; border-radius: 999px; background: rgba(59,130,246,0.12); color: var(--accent-blue); }
.disclaimer { font-size: 0.72rem; color: var(--text-muted); margin: 0; }
.empty-state { color: var(--text-secondary); padding: 12px 0; }
.clickable { cursor: pointer; }
.clickable:hover { background: var(--bg-well, rgba(148,163,184,0.06)); }
.up { color: var(--color-up, #10b981); }
.down { color: var(--color-down, #ef4444); }
</style>
