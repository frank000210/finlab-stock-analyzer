<template>
  <div class="checker-page">
    <PageFocusBanner text="貼上新聞網址/標題/內文，用五層規則式評分＋AI 語意層檢查可信度。" />

    <header class="page-header">
      <div>
        <h1>🔍 新聞可信度檢查</h1>
        <p class="subtitle">五層規則式評分（媒體來源／Cofacts 查核／內容特徵／交叉驗證／時效）＋選填 AI 語意層</p>
      </div>
    </header>

    <section class="card form-card">
      <div class="form-grid">
        <label class="field">
          <span>網址</span>
          <input v-model="form.url" class="inp" placeholder="https://..." />
        </label>
        <label class="field">
          <span>標題</span>
          <input v-model="form.title" class="inp" placeholder="新聞標題" />
        </label>
      </div>
      <label class="field">
        <span>內文（選填，貼越多內容層越準確）</span>
        <textarea v-model="form.text" class="inp" rows="5" placeholder="貼上新聞內文..."></textarea>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" :disabled="loading || !form.url" @click="checkCredibility">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
          {{ loading ? '檢查中…' : '檢查可信度' }}
        </button>
        <span v-if="error" class="error-text">{{ error }}</span>
      </div>
    </section>

    <section v-if="result" class="card result-card">
      <div class="result-head">
        <div class="score-circle" :class="verdictClass">{{ result.overall_score }}</div>
        <div>
          <strong class="verdict-label">{{ verdictLabel }}</strong>
          <p class="muted">{{ result.summary }}</p>
        </div>
      </div>

      <div class="layers">
        <div v-for="l in result.layers" :key="l.layer" class="layer-row">
          <span class="layer-name">{{ layerLabel(l.layer) }}</span>
          <div class="layer-bar"><div class="layer-bar-fill" :style="{ width: l.score + '%' }"></div></div>
          <span class="layer-score">{{ l.score }}</span>
          <span class="layer-weight muted">×{{ l.weight }}</span>
        </div>
      </div>
      <p class="disclaimer">※ 五層規則式分數為固定權重加權平均，非 AI 生成，可重現、可稽核。</p>

      <div v-if="result.llm_assessment?.available" class="llm-layer">
        <strong>🤖 AI 語意層（僅供參考，不計入上方分數）</strong>
        <p>{{ result.llm_assessment.note }}</p>
      </div>
      <p v-else-if="aiConfigured" class="muted small">本次未取得 AI 語意層結果（可能逾時或內文過短），不影響上方五層分數。</p>
    </section>

    <section v-if="history.length" class="card history-card">
      <h2>最近檢查紀錄</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>來源</th><th>標題</th><th>分數</th><th>判定</th><th>時間</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.url + h.checked_at">
              <td>{{ h.source }}</td>
              <td class="title-cell">{{ h.title }}</td>
              <td>{{ h.overall_score }}</td>
              <td>{{ h.verdict }}</td>
              <td class="muted">{{ formatDate(h.checked_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'

const form = reactive({ url: '', title: '', text: '' })
const loading = ref(false)
const error = ref('')
const result = ref(null)
const history = ref([])
const aiConfigured = ref(false)

const LAYER_LABELS = {
  media_source: '媒體來源',
  cofacts: 'Cofacts 查核',
  content: '內容特徵',
  cross_validation: '交叉驗證',
  timeliness: '時效性',
}
function layerLabel(key) {
  return LAYER_LABELS[key] || key
}

const verdictClass = computed(() => {
  const v = result.value?.verdict || ''
  if (v === 'CREDIBLE') return 'v-good'
  if (v === 'SUSPICIOUS') return 'v-bad'
  return 'v-warn'
})
const verdictLabel = computed(() => {
  const v = result.value?.verdict || ''
  return { CREDIBLE: '可信', SUSPICIOUS: '可疑', UNCERTAIN: '不確定' }[v] || v
})

function formatDate(iso) {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 16)
}

async function checkCredibility() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await fetch('/api/v1/news/check-credibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: form.url, title: form.title, text: form.text }),
    })
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || json.error || '檢查失敗')
    result.value = json.data
    loadHistory()
  } catch (e) {
    error.value = e?.message || '檢查失敗'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    const res = await fetch('/api/v1/news/crawled-data?limit=10')
    const json = await res.json()
    if (json.success) history.value = json.data.items || []
  } catch {
    // 歷史紀錄是附加資訊，抓不到不影響主要檢查功能
  }
}

async function checkAiConfigured() {
  try {
    const res = await fetch('/api/v1/stocks/ai/status')
    const json = await res.json()
    aiConfigured.value = Boolean(json?.data?.configured)
  } catch {
    aiConfigured.value = false
  }
}

onMounted(() => {
  checkAiConfigured()
  loadHistory()
})
</script>

<style scoped>
.checker-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header h1 { margin: 0 0 4px; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin: 0; }

.form-card { display: flex; flex-direction: column; gap: 12px; }
.form-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); }
.form-actions { display: flex; align-items: center; gap: 12px; }
.error-text { color: #ef4444; font-size: 0.84rem; }

.result-card { display: flex; flex-direction: column; gap: 14px; }
.result-head { display: flex; align-items: center; gap: 16px; }
.score-circle { width: 64px; height: 64px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; font-weight: 800; flex-shrink: 0; }
.score-circle.v-good { background: rgba(16,185,129,0.15); color: #10b981; }
.score-circle.v-bad { background: rgba(239,68,68,0.15); color: #ef4444; }
.score-circle.v-warn { background: rgba(245,158,11,0.15); color: #f59e0b; }
.verdict-label { font-size: 1.05rem; }
.muted { color: var(--text-muted); }

.layers { display: flex; flex-direction: column; gap: 8px; }
.layer-row { display: grid; grid-template-columns: 90px 1fr 40px 44px; align-items: center; gap: 8px; font-size: 0.8rem; }
.layer-bar { height: 8px; border-radius: 4px; background: rgba(148,163,184,0.15); overflow: hidden; }
.layer-bar-fill { height: 100%; background: var(--accent-blue); }
.layer-score { text-align: right; font-weight: 700; }
.layer-weight { text-align: right; font-size: 0.72rem; }
.disclaimer { font-size: 0.72rem; color: var(--text-muted); margin: 0; }

.llm-layer { border: 1px dashed var(--border-color); border-radius: 10px; padding: 10px 12px; font-size: 0.82rem; }
.llm-layer p { margin: 4px 0 0; color: var(--text-secondary); }
.small { font-size: 0.76rem; }

.history-card h2 { margin: 0 0 10px; font-size: 1rem; }
.title-cell { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
