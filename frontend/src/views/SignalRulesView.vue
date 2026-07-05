<template>
  <div class="rules-page">
    <PageFocusBanner text="管理訊號觸發規則與門檻，讓自動化提醒符合策略邏輯。" />

    <div class="page-header">
      <div>
        <h1>信號規則編輯器</h1>
        <p>建立、測試與切換自訂 Python 信號腳本</p>
      </div>
      <button class="btn btn-primary" @click="loadRules">重新載入</button>
    </div>

    <section class="grid-layout">
      <article class="card form-card">
        <div class="section-header">
          <div>
            <h2>新增規則</h2>
            <p>以 Python 腳本定義 AI 交易信號</p>
          </div>
        </div>
        <form class="rule-form" @submit.prevent="createRule">
          <label>
            規則名稱
            <input v-model="newRule.name" class="form-input" placeholder="例如：突破量價策略" />
          </label>
          <label>
            規則描述
            <input v-model="newRule.description" class="form-input" placeholder="描述規則使用情境" />
          </label>
          <label>
            Python 腳本
            <textarea v-model="newRule.script" class="form-input code-input" rows="14"></textarea>
          </label>
          <div class="button-row">
            <button class="btn btn-primary" type="submit" :disabled="saving">{{ saving ? '建立中...' : '建立規則' }}</button>
            <button class="btn btn-secondary" type="button" @click="testRule(newRule.script, 'draft')" :disabled="testingTarget === 'draft'">
              {{ testingTarget === 'draft' ? '測試中...' : '測試腳本' }}
            </button>
          </div>
        </form>
      </article>

      <article class="card result-card">
        <div class="section-header">
          <div>
            <h2>測試結果</h2>
            <p>即時查看 signal / confidence / conditions / reasoning</p>
          </div>
        </div>
        <div v-if="testResult" class="test-result">
          <div class="result-head">
            <span class="badge" :class="signalClass(testResult.signal)">{{ testResult.signal }}</span>
            <strong>{{ testResult.confidence }}%</strong>
          </div>
          <p>{{ testResult.reasoning }}</p>
          <ul>
            <li v-for="condition in testResult.conditions" :key="condition.label">
              {{ condition.passed ? '✓' : '✕' }} {{ condition.label }}
            </li>
          </ul>
        </div>
        <div v-else class="empty-state">尚未執行測試</div>
      </article>
    </section>

    <section class="rules-list">
      <article v-for="rule in rules" :key="rule.id" class="card rule-card">
        <div class="rule-head">
          <div>
            <h2>{{ rule.name }}</h2>
            <p>{{ rule.description || '尚無描述' }}</p>
          </div>
          <div class="badge-row">
            <span class="badge active-badge" v-if="rule.isActive">啟用中</span>
            <span class="badge default-badge" v-if="rule.isDefault">預設</span>
          </div>
        </div>

        <div v-if="editingId === rule.id" class="edit-panel">
          <label>
            名稱
            <input v-model="editDrafts[rule.id].name" class="form-input" />
          </label>
          <label>
            描述
            <input v-model="editDrafts[rule.id].description" class="form-input" />
          </label>
          <label>
            腳本
            <textarea v-model="editDrafts[rule.id].script" class="form-input code-input" rows="12"></textarea>
          </label>
          <div class="button-row">
            <button class="btn btn-primary" @click="saveEdit(rule.id)">儲存</button>
            <button class="btn btn-secondary" @click="testRule(editDrafts[rule.id].script, rule.id)" :disabled="testingTarget === rule.id">測試</button>
            <button class="btn btn-ghost" @click="editingId = ''">取消</button>
          </div>
        </div>
        <pre v-else class="script-preview">{{ rule.script }}</pre>

        <div class="button-row wrap">
          <button class="btn btn-secondary" @click="startEdit(rule)">{{ editingId === rule.id ? '編輯中' : '編輯' }}</button>
          <button class="btn" :class="rule.isActive ? 'btn-warning' : 'btn-success'" @click="toggleActive(rule)">
            {{ rule.isActive ? '停用' : '啟用' }}
          </button>
          <button class="btn btn-danger" @click="deleteRule(rule)">刪除</button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { onMounted, ref } from 'vue'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const defaultScript = `def generate_signal(context):
    signal = 'HOLD'
    confidence = 0.5
    conditions = [
        {'label': '量價確認', 'passed': True},
        {'label': '風險限制', 'passed': True},
    ]
    reasoning = '請在此撰寫自訂信號邏輯。'
    return {
        'signal': signal,
        'confidence': confidence,
        'conditions': conditions,
        'reasoning': reasoning,
    }`

const rules = ref([])
const editDrafts = ref({})
const editingId = ref('')
const saving = ref(false)
const testingTarget = ref('')
const testResult = ref(null)
const newRule = ref({
  name: '',
  description: '',
  script: defaultScript,
})

onMounted(loadRules)

async function loadRules() {
  try {
    const payload = await apiRequest('/api/v1/signal-rules')
    rules.value = normalizeRules(payload)
    const drafts = {}
    for (const rule of rules.value) {
      drafts[rule.id] = { name: rule.name, description: rule.description, script: rule.script }
    }
    editDrafts.value = drafts
  } catch {
    rules.value = []
    editDrafts.value = {}
  }
}

async function createRule() {
  saving.value = true
  try {
    await apiRequest('/api/v1/signal-rules', {
      method: 'POST',
      body: JSON.stringify(newRule.value),
    })
    newRule.value = { name: '', description: '', script: defaultScript }
    await loadRules()
  } catch (error) {
    window.alert(error.message || '建立失敗')
  }
  saving.value = false
}

function startEdit(rule) {
  editingId.value = rule.id
  if (!editDrafts.value[rule.id]) {
    editDrafts.value[rule.id] = { name: rule.name, description: rule.description, script: rule.script }
  }
}

async function saveEdit(ruleId) {
  try {
    await apiRequest(`/api/v1/signal-rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(editDrafts.value[ruleId]),
    })
    editingId.value = ''
    await loadRules()
  } catch (error) {
    window.alert(error.message || '儲存失敗')
  }
}

async function toggleActive(rule) {
  try {
    if (rule.isActive) {
      await apiRequest(`/api/v1/signal-rules/${rule.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: rule.name,
          description: rule.description,
          script: rule.script,
          is_active: false,
        }),
      })
    } else {
      await apiRequest(`/api/v1/signal-rules/${rule.id}/activate`, { method: 'POST' })
    }
    await loadRules()
  } catch (error) {
    window.alert(error.message || '切換狀態失敗')
  }
}

async function deleteRule(rule) {
  if (!window.confirm(`確定要刪除規則「${rule.name}」嗎？`)) return
  try {
    await apiRequest(`/api/v1/signal-rules/${rule.id}`, { method: 'DELETE' })
    await loadRules()
  } catch (error) {
    window.alert(error.message || '刪除失敗')
  }
}

async function testRule(script, target) {
  testingTarget.value = String(target)
  try {
    const payload = await apiRequest('/api/v1/signal-rules/test', {
      method: 'POST',
      body: JSON.stringify({ script }),
    })
    testResult.value = normalizeTestResult(payload)
  } catch (error) {
    window.alert(error.message || '測試失敗')
  }
  testingTarget.value = ''
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

function normalizeRules(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.rules)
        ? payload.rules
        : []
  return list.map((item, index) => ({
    id: item.id || item.rule_id || `rule-${index}`,
    name: item.name || `規則 ${index + 1}`,
    description: item.description || '',
    script: item.script || item.code || defaultScript,
    isActive: Boolean(item.is_active ?? item.isActive),
    isDefault: Boolean(item.is_default ?? item.isDefault),
  }))
}

function normalizeTestResult(payload) {
  const conditions = Array.isArray(payload?.conditions)
    ? payload.conditions.map((item, index) => ({
        label: item.label || item.name || item.condition || `條件 ${index + 1}`,
        passed: Boolean(item.passed ?? item.met ?? item.result ?? item.status),
      }))
    : payload?.conditions && typeof payload.conditions === 'object'
      ? Object.entries(payload.conditions).map(([label, passed]) => ({ label, passed: Boolean(passed) }))
      : []
  return {
    signal: String(payload?.signal || payload?.type || 'HOLD').toUpperCase(),
    confidence: normalizePercent(payload?.confidence),
    reasoning: payload?.reasoning || payload?.reason || '沒有測試說明',
    conditions,
  }
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function signalClass(signal) {
  return signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'hold'
}
</script>

<style scoped>
.rules-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header,
.rule-head,
.result-head,
.button-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header p,
.section-header p,
.rule-head p,
.empty-state,
.test-result p,
.test-result li {
  color: var(--text-secondary);
}

.grid-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 20px;
}

.rule-form,
.edit-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.rule-form label,
.edit-panel label {
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

.code-input,
.script-preview {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  line-height: 1.5;
}

.script-preview {
  margin-top: 16px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.45);
  white-space: pre-wrap;
  overflow-x: auto;
}

.button-row.wrap {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 16px;
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-primary);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-success {
  background: var(--color-up);
  color: white;
}

.btn-warning {
  background: var(--color-warning);
  color: white;
}

.btn-danger {
  background: var(--color-down);
  color: white;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.badge-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  padding: 5px 10px;
  border-radius: 999px;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.active-badge,
.buy {
  background: var(--color-up);
}

.default-badge,
.hold {
  background: var(--color-warning);
}

.sell {
  background: var(--color-down);
}

.test-result {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.test-result ul {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 980px) {
  .grid-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .section-header,
  .rule-head,
  .result-head,
  .button-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
