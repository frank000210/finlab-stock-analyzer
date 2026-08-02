<template>
  <div class="kbqa-page">
    <PageFocusBanner text="向知識庫提問：查詢圖表公式、開發筆記、過去的決策脈絡，或任何已匯入的文件。" />

    <div v-if="!authStore.isAdmin" class="card login-gate">
      <p>此頁面需要管理員身份。請先登入再使用知識庫問答。</p>
    </div>

    <template v-else>
      <header class="page-header">
        <div>
          <h1>🧠 知識庫問答</h1>
          <p class="subtitle">查詢圖表公式、開發筆記、源碼說明，或任何已匯入知識庫的文件。</p>
        </div>
      </header>

      <section class="card ask-card">
        <div class="ask-row">
          <div class="question-wrap">
            <textarea
              v-model="question"
              class="inp question-input"
              rows="3"
              maxlength="500"
              placeholder="例如：凱利準則如何計算？ / Monte Carlo 毀滅門檻的公式？ / Portfolio Heat 的定義？"
              @keydown.enter.ctrl.prevent="askQuestion"
              @keydown.enter.meta.prevent="askQuestion"
            />
            <span class="char-count">{{ question.length }}/500</span>
          </div>
          <div class="ask-controls">
            <label class="field domain-field">
              <span>領域（選填）</span>
              <select v-model="domain" class="inp domain-select">
                <option value="">全部</option>
                <option v-for="d in domains" :key="d.domain" :value="d.domain">
                  {{ d.domain }}（{{ d.doc_count ?? d.count ?? '?' }}篇）
                </option>
              </select>
            </label>
            <button
              class="btn btn-primary ask-btn"
              :disabled="loading || !question.trim()"
              @click="askQuestion"
            >
              <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
              {{ loading ? '查詢中…' : '提問' }}
            </button>
          </div>
        </div>
        <p class="hint">Ctrl+Enter 快速送出</p>
        <p v-if="error" class="error-text">{{ error }}</p>
      </section>

      <section v-if="currentAnswer" class="card answer-card">
        <div class="answer-head">
          <span class="answer-q">Q: {{ currentAnswer.question }}</span>
          <span v-if="currentAnswer.domain" class="domain-tag">{{ currentAnswer.domain }}</span>
        </div>
        <div class="answer-body" v-html="renderedAnswer"></div>

        <div v-if="currentAnswer.citations?.length" class="citations">
          <h4>引用來源</h4>
          <ul>
            <li v-for="(c, i) in currentAnswer.citations" :key="i" class="citation-item">
              <span class="cite-idx">[{{ c.index ?? i + 1 }}]</span>
              <span class="cite-title">{{ c.title }}</span>
              <span v-if="c.source" class="cite-source muted">— {{ c.source }}</span>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="history.length" class="card history-card">
        <div class="section-head compact">
          <h2>本次問答記錄</h2>
          <button class="btn btn-ghost xs-btn" @click="history = []">清除</button>
        </div>
        <ul class="history-list">
          <li
            v-for="(h, i) in history"
            :key="i"
            class="history-item"
            :class="{ active: h === currentAnswer }"
            @click="selectHistory(h)"
          >
            <span class="hist-q">{{ h.question }}</span>
            <span v-if="h.domain" class="domain-tag xs">{{ h.domain }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { useAuthStore } from '../stores/auth.js'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const authStore = useAuthStore()

const question = ref('')
const domain = ref('')
const domains = ref([])
const loading = ref(false)
const error = ref('')
const currentAnswer = ref(null)
const history = ref([])

onMounted(async () => {
  if (!authStore.isAdmin) return
  try {
    const r = await fetch(`${API_BASE}/api/v1/kb/domains`, { headers: authStore.getAuthHeaders() })
    if (r.ok) {
      const data = await r.json()
      domains.value = data.data || []
    }
  } catch {}
})

async function askQuestion() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const body = { question: q }
    if (domain.value) body.domain = domain.value
    const r = await fetch(`${API_BASE}/api/v1/kb/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authStore.getAuthHeaders() },
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const msg = await r.json().catch(() => ({}))
      error.value = msg.detail || `伺服器錯誤 ${r.status}`
      return
    }
    const data = await r.json()
    const entry = {
      question: q,
      domain: domain.value || null,
      answer: data.answer || '（無答案）',
      citations: data.citations || [],
      steps: data.steps || [],
    }
    history.value.unshift(entry)
    currentAnswer.value = entry
    question.value = ''
  } catch (e) {
    error.value = `網路錯誤：${e.message}`
  } finally {
    loading.value = false
  }
}

function selectHistory(h) {
  currentAnswer.value = h
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function markdownToHtml(md) {
  if (!md) return ''
  return escapeHtml(md)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#{3} (.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2} (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]+?<\/li>)/g, '<ul>$1</ul>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(?!<[hulo])(.+)$/gm, '<p>$1</p>')
    .replace(/<p><\/p>/g, '')
}

const renderedAnswer = computed(() => {
  if (!currentAnswer.value) return ''
  return markdownToHtml(currentAnswer.value.answer)
})
</script>

<style scoped>
.kbqa-page { display: flex; flex-direction: column; gap: 20px; }

.page-header { margin-bottom: 4px; }
.page-header h1 { font-size: 1.5rem; margin: 0 0 4px; }
.subtitle { color: var(--text-muted); font-size: 0.88rem; margin: 0; }

.login-gate { padding: 32px; text-align: center; color: var(--text-muted); }

.ask-card { display: flex; flex-direction: column; gap: 10px; }
.ask-row { display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }
.question-wrap { flex: 1; min-width: 260px; position: relative; }
.question-input { width: 100%; resize: vertical; font-size: 0.95rem; }
.char-count { position: absolute; bottom: 8px; right: 10px; font-size: 0.72rem; color: var(--text-muted); pointer-events: none; }

.ask-controls { display: flex; flex-direction: column; gap: 8px; min-width: 160px; }
.domain-field { display: flex; flex-direction: column; gap: 4px; }
.domain-field > span { font-size: 0.78rem; color: var(--text-muted); }
.domain-select { font-size: 0.88rem; }
.ask-btn { align-self: flex-end; width: 100%; }

.hint { font-size: 0.75rem; color: var(--text-muted); margin: 0; }

.answer-card { display: flex; flex-direction: column; gap: 14px; }
.answer-head { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); }
.answer-q { font-size: 0.88rem; font-weight: 600; color: var(--text-primary); flex: 1; }

.answer-body { font-size: 0.92rem; line-height: 1.7; }
.answer-body :deep(h1),
.answer-body :deep(h2),
.answer-body :deep(h3) { margin: 12px 0 6px; font-size: 1rem; }
.answer-body :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
  background: var(--surface-secondary, rgba(0,0,0,0.06));
  border-radius: 4px;
  padding: 1px 5px;
}
.answer-body :deep(ul) { padding-left: 20px; }
.answer-body :deep(li) { margin: 3px 0; }
.answer-body :deep(p) { margin: 6px 0; }
.answer-body :deep(strong) { font-weight: 700; }

.citations { border-top: 1px solid var(--border-color); padding-top: 10px; }
.citations h4 { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.citations ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.citation-item { font-size: 0.82rem; display: flex; gap: 6px; align-items: baseline; }
.cite-idx { color: var(--accent-blue); font-weight: 700; flex: 0 0 auto; }
.cite-title { font-weight: 500; }
.cite-source { font-size: 0.78rem; }

.domain-tag { font-size: 0.72rem; background: var(--accent-soft, rgba(79,140,255,0.12)); color: var(--accent-blue); border-radius: 999px; padding: 2px 9px; font-weight: 600; white-space: nowrap; flex: 0 0 auto; }
.domain-tag.xs { font-size: 0.66rem; padding: 1px 7px; }

.history-card { }
.section-head.compact { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-head h2 { font-size: 0.88rem; margin: 0; }
.xs-btn { font-size: 0.78rem; padding: 4px 10px; }

.history-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 1px; }
.history-item {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 7px 10px; border-radius: 8px; cursor: pointer;
  font-size: 0.85rem;
  border: 1px solid transparent;
}
.history-item:hover { background: var(--surface-secondary, rgba(0,0,0,0.04)); }
.history-item.active { border-color: var(--accent-blue); background: var(--accent-soft, rgba(79,140,255,0.06)); }
.hist-q { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); }
</style>
