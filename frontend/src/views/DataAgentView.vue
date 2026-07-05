<template>
  <div class="data-agent-page">
    <PageFocusBanner text="檢視資料擷取與整合流程的運作狀態，確保分析所需資料來源正常。" />

    <div class="page-header">
      <div>
        <h1>資料爬蟲與新聞檢查</h1>
        <p>新聞可信度分析與近期爬蟲資料總覽</p>
      </div>
    </div>

    <section class="grid-layout">
      <article class="card">
        <div class="section-header">
          <div>
            <h2>新聞可信度檢查</h2>
            <p>輸入網址、標題與內文後進行多層評估</p>
          </div>
        </div>
        <form class="form-grid" @submit.prevent="submitCredibilityCheck">
          <label>
            新聞網址
            <input v-model="form.url" class="form-input" placeholder="https://example.com/news" />
          </label>
          <label>
            新聞標題
            <input v-model="form.title" class="form-input" placeholder="輸入新聞標題" />
          </label>
          <label class="full-width">
            新聞內文
            <textarea v-model="form.text" class="form-input text-area" rows="8" placeholder="貼上完整新聞內文"></textarea>
          </label>
          <button class="btn btn-primary" type="submit" :disabled="checking">
            {{ checking ? '分析中...' : '檢查可信度' }}
          </button>
        </form>

        <div v-if="credibilityResult" class="result-panel">
          <div class="result-top">
            <div>
              <span class="result-label">總分</span>
              <strong :style="{ color: overallColor }">{{ credibilityResult.overallScore }}</strong>
            </div>
            <span class="badge" :style="{ background: overallColor }">{{ credibilityResult.verdict }}</span>
          </div>
          <div class="layer-list">
            <div v-for="layer in credibilityResult.layers" :key="layer.label" class="layer-item">
              <div class="layer-top">
                <span>{{ layer.label }}</span>
                <strong>{{ layer.score }}%</strong>
              </div>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: `${layer.score}%`, background: scoreColor(layer.score) }"></div>
              </div>
            </div>
          </div>
        </div>
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h2>已爬取資料</h2>
            <p>依來源查看最新 50 筆資料</p>
          </div>
        </div>
        <div class="tabs source-tabs">
          <button
            v-for="tab in sourceTabs"
            :key="tab"
            class="tab-button"
            :class="{ active: selectedSource === tab }"
            @click="selectedSource = tab"
          >
            {{ tab }}
          </button>
        </div>
        <div v-if="crawledItems.length" class="crawl-list">
          <div v-for="item in crawledItems" :key="item.id" class="crawl-item">
            <div class="crawl-head">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.source }} ・ {{ item.time }}</p>
              </div>
              <span class="sentiment" :class="sentimentClass(item.sentiment)">{{ item.sentimentText }}</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">目前沒有爬蟲資料</div>
      </article>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, onMounted, ref, watch } from 'vue'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const sourceTabs = ['ALL', 'TWSE', 'PTT', 'NEWS']
const selectedSource = ref('ALL')
const checking = ref(false)
const form = ref({ url: '', title: '', text: '' })
const credibilityResult = ref(null)
const crawledItems = ref([])

const overallColor = computed(() => scoreColor(credibilityResult.value?.overallScore || 0))

onMounted(loadCrawledData)

watch(selectedSource, async () => {
  await loadCrawledData()
})

async function submitCredibilityCheck() {
  checking.value = true
  try {
    const payload = await apiRequest('/api/v1/news/check-credibility', {
      method: 'POST',
      body: JSON.stringify(form.value),
    })
    credibilityResult.value = normalizeCredibilityResult(payload)
  } catch (error) {
    window.alert(error.message || '分析失敗')
  }
  checking.value = false
}

async function loadCrawledData() {
  try {
    const source = selectedSource.value === 'ALL' ? '' : selectedSource.value
    const payload = await apiRequest(`/api/v1/news/crawled-data?source=${encodeURIComponent(source)}&limit=50`)
    crawledItems.value = normalizeCrawledItems(payload)
  } catch {
    crawledItems.value = []
  }
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.detail || 'API 請求失敗')
  return payload?.data ?? payload
}

function normalizeCredibilityResult(payload) {
  const overallScore = normalizePercent(payload?.overall_score ?? payload?.score ?? payload?.overallScore)
  const verdict = payload?.verdict || (overallScore >= 75 ? '高可信' : overallScore >= 50 ? '待確認' : '高風險')
  const layersSource = Array.isArray(payload?.layers)
    ? payload.layers
    : Array.isArray(payload?.layer_scores)
      ? payload.layer_scores
      : payload?.layer_scores && typeof payload.layer_scores === 'object'
        ? Object.entries(payload.layer_scores).map(([label, score]) => ({ label, score }))
        : []

  const labels = ['來源可信度', '文本一致性', '事實交叉驗證', '情緒偏誤', '時間有效性']
  const layers = (layersSource.length ? layersSource : labels.map(label => ({ label, score: overallScore })))
    .slice(0, 5)
    .map((item, index) => ({
      label: item.label || item.name || labels[index] || `層級 ${index + 1}`,
      score: normalizePercent(item.score ?? item.value),
    }))

  return { overallScore, verdict, layers }
}

function normalizeCrawledItems(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.data)
        ? payload.data
        : []
  return list.map((item, index) => {
    const sentiment = Number(item.sentiment ?? item.sentiment_score ?? 0)
    return {
      id: item.id || `${item.source || 'source'}-${index}`,
      source: item.source || '未知來源',
      title: item.title || item.headline || '未命名資料',
      time: formatTime(item.timestamp || item.created_at || item.time),
      sentiment,
      sentimentText: sentiment > 0.2 ? '偏多' : sentiment < -0.2 ? '偏空' : '中性',
    }
  })
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function scoreColor(score) {
  if (score >= 75) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
}

function sentimentClass(value) {
  if (value > 0.2) return 'bullish'
  if (value < -0.2) return 'bearish'
  return 'neutral'
}

function formatTime(value) {
  if (!value) return '未提供時間'
  return String(value).replace('T', ' ').slice(0, 16)
}
</script>

<style scoped>
.data-agent-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header h1,
.section-header h2 {
  margin-bottom: 4px;
}

.page-header p,
.section-header p,
.crawl-head p,
.empty-state {
  color: var(--text-secondary);
}

.grid-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: start;
}

.section-header,
.result-top,
.layer-top,
.crawl-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.form-grid {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: #0d1117;
  color: var(--text-primary);
}

.text-area {
  resize: vertical;
}

.full-width {
  width: 100%;
}

.result-panel,
.crawl-list {
  margin-top: 20px;
}

.result-top strong {
  display: block;
  font-size: 2rem;
  margin-top: 4px;
}

.result-label {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.badge,
.sentiment {
  padding: 5px 10px;
  border-radius: 999px;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.layer-list,
.crawl-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.progress-track {
  width: 100%;
  height: 10px;
  margin-top: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.source-tabs {
  display: flex;
  gap: 10px;
  border-bottom: none;
  margin: 16px 0 0;
}

.tab-button {
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.tab-button.active {
  background: var(--accent-blue);
  color: white;
  border-color: var(--accent-blue);
}

.crawl-item {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.45);
}

.bullish {
  background: var(--color-up);
}

.bearish {
  background: var(--color-down);
}

.neutral {
  background: var(--color-warning);
}

@media (max-width: 980px) {
  .grid-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .section-header,
  .result-top,
  .layer-top,
  .crawl-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
