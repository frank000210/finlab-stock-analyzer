<template>
  <div class="signals-page">
    <PageFocusBanner text="檢視 AI 模型產出的進出場訊號與信心度，作為決策的量化參考。" />

    <div class="page-header">
      <div>
        <h1>AI 交易信號</h1>
        <p>每 30 秒自動更新，掌握最新買賣建議與因子分數</p>
      </div>
      <div class="refresh-note">{{ loading ? '同步中...' : '自動更新：30 秒' }}</div>
    </div>

    <div class="tabs signal-tabs">
      <button
        v-for="tab in tabs"
        :key="tab"
        class="tab-button"
        :class="{ active: selectedFilter === tab }"
        @click="selectedFilter = tab"
      >
        {{ tab }}
      </button>
    </div>

    <section class="card active-rule-card">
      <div class="section-header">
        <div>
          <h2>目前生效規則</h2>
          <p>策略邏輯與訊號解讀說明</p>
        </div>
      </div>
      <div class="rule-content">
        <strong>{{ activeRule.name || '尚未設定' }}</strong>
        <p>{{ activeRule.description || '目前沒有規則說明。' }}</p>
      </div>
    </section>

    <section class="signals-layout">
      <article class="card">
        <div class="section-header">
          <div>
            <h2>信號列表</h2>
            <p>依目前篩選顯示個股信號卡片</p>
          </div>
        </div>
        <div v-if="filteredSignals.length" class="signal-grid">
          <div v-for="signal in filteredSignals" :key="signal.id" class="signal-card">
            <div class="signal-head">
              <div>
                <h3>{{ signal.symbol }} <span v-if="signal.name_zh" class="stock-name">{{ signal.name_zh }}</span></h3>
                <p>{{ signal.reasoning }}</p>
              </div>
              <span class="badge" :class="badgeClass(signal.type)">{{ signal.type }}</span>
            </div>
            <div class="confidence-row">
              <span>信心度</span>
              <strong>{{ signal.confidence }}%</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :class="badgeClass(signal.type)" :style="{ width: `${signal.confidence}%` }"></div>
            </div>
            <ul class="conditions-list">
              <li v-for="condition in signal.conditions" :key="condition.label" :class="condition.passed ? 'passed' : 'failed'">
                <span>{{ condition.passed ? '✓' : '✕' }}</span>
                {{ condition.label }}
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="empty-state">目前篩選條件下沒有信號資料</div>
      </article>

      <article class="card alpha-card">
        <div class="section-header">
          <div>
            <h2>Alpha 分數</h2>
            <p>技術面 / 法人籌碼 / 情緒面 / 基本面 / 量能</p>
          </div>
        </div>
        <div v-if="alphaScores.length" class="alpha-list">
          <div v-for="score in alphaScores" :key="score.label" class="alpha-item">
            <div class="alpha-top">
              <span>{{ score.label }}</span>
              <strong>{{ score.value }}%</strong>
            </div>
            <div class="progress-track large">
              <div class="progress-fill alpha" :style="{ width: `${score.value}%` }"></div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">尚未取得 Alpha 分數</div>
      </article>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const tabs = ['ALL', 'BUY', 'SELL', 'HOLD']
const selectedFilter = ref('ALL')
const signals = ref([])
const activeRule = ref({})
const alphaScores = ref([])
const loading = ref(false)
let refreshTimer = null

const filteredSignals = computed(() => signals.value)

onMounted(async () => {
  await loadAll()
  refreshTimer = window.setInterval(loadAll, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})

watch(selectedFilter, async () => {
  await loadSignals()
})

async function loadAll() {
  loading.value = true
  await Promise.all([loadSignals(), loadAlphaScores(), loadActiveRule()])
  loading.value = false
}

async function loadSignals() {
  try {
    const payload = await apiGet(`/api/v1/agent/signals?type=${selectedFilter.value}`)
    signals.value = normalizeSignals(payload)
  } catch {
    signals.value = []
  }
}

async function loadAlphaScores() {
  try {
    const payload = await apiGet('/api/v1/agent/alpha-scores')
    alphaScores.value = normalizeAlphaScores(payload)
  } catch {
    alphaScores.value = []
  }
}

async function loadActiveRule() {
  try {
    const payload = await apiGet('/api/v1/agent/active-rule')
    activeRule.value = (payload && typeof payload === 'object') ? payload : {}
  } catch {
    activeRule.value = {}
  }
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.detail || 'API 請求失敗')
  return payload?.data ?? payload
}

function normalizeSignals(payload) {
  return extractList(payload, ['items', 'signals']).map((item, index) => ({
    id: item.id || item.task_id || `${item.symbol || item.stock_symbol || 'signal'}-${index}`,
    symbol: item.symbol || item.stock_symbol || item.ticker || 'N/A',
    name_zh: item.name_zh || item.stock_name || '',
    type: String(item.type || item.signal || item.action || 'HOLD').toUpperCase(),
    confidence: normalizePercent(item.confidence),
    reasoning: item.reasoning || item.reason || '無推論內容',
    conditions: normalizeConditions(item.conditions),
  }))
}

function normalizeConditions(value) {
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      if (typeof item === 'string') return { label: item, passed: true }
      return {
        label: item.label || item.name || item.condition || `條件 ${index + 1}`,
        passed: Boolean(item.passed ?? item.met ?? item.result ?? item.status),
      }
    })
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([label, passed]) => ({ label, passed: Boolean(passed) }))
  }
  return [{ label: '尚未提供條件資料', passed: true }]
}

function normalizeAlphaScores(payload) {
  const mapping = {
    technical: '技術面',
    tech: '技術面',
    institutional: '法人籌碼',
    chip: '法人籌碼',
    sentiment: '情緒面',
    fundamental: '基本面',
    volume: '量能',
  }
  const source = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Object.entries(payload?.scores || payload || {}).map(([key, value]) => ({ key, value }))

  return source
    .map(item => ({
      label: mapping[item.key || item.name || item.label] || item.label || item.name || '未命名因子',
      value: normalizePercent(item.value ?? item.score ?? item.alpha_score),
    }))
    .filter(item => item.label)
}

function extractList(payload, keys = []) {
  if (Array.isArray(payload)) return payload
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function badgeClass(type) {
  return type === 'BUY' ? 'badge-buy' : type === 'SELL' ? 'badge-sell' : 'badge-hold'
}
</script>

<style scoped>
.signals-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header,
.signal-head,
.confidence-row,
.alpha-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header h1,
.section-header h2,
.signal-card h3 {
  margin-bottom: 4px;
}

.page-header p,
.section-header p,
.rule-content p,
.signal-card p,
.refresh-note,
.empty-state {
  color: var(--text-secondary);
}

.signal-tabs {
  display: flex;
  gap: 10px;
  border-bottom: none;
  margin-bottom: 0;
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
  border-color: var(--accent-blue);
  color: white;
}

.signals-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 20px;
}

.rule-content {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.signal-grid,
.alpha-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.signal-card {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.45);
}

.stock-name {
  font-size: 0.85rem;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 6px;
}

.confidence-row {
  margin: 16px 0 8px;
}

.conditions-list {
  margin-top: 14px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
}

.conditions-list li {
  display: flex;
  gap: 8px;
  align-items: center;
}

.conditions-list li.passed {
  color: #86efac;
}

.conditions-list li.failed {
  color: #fca5a5;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.progress-track.large {
  height: 10px;
  margin-top: 8px;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.progress-fill.badge-buy,
.badge-buy {
  background: var(--color-up);
  color: #fff;
}

.progress-fill.badge-sell,
.badge-sell {
  background: var(--color-down);
  color: #fff;
}

.progress-fill.badge-hold,
.badge-hold {
  background: var(--color-warning);
  color: #fff;
}

.progress-fill.alpha {
  background: linear-gradient(90deg, #38bdf8, #2563eb);
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
}

@media (max-width: 980px) {
  .signals-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .section-header,
  .signal-head,
  .confidence-row,
  .alpha-top {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 420px) {
  .signals-page {
    gap: var(--space-3);
  }
  .signal-card,
  .alpha-card,
  .card {
    padding: var(--space-3);
  }
  .confidence-bar-track {
    height: 6px;
  }
}
</style>
