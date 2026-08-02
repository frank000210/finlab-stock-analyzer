<script setup>
import { ref, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import api from '../api.js'

// html:false -- any raw HTML in the LLM's answer is escaped to literal
// text rather than parsed as markup, so a malicious/injected answer can't
// render arbitrary tags via v-html.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const domain = ref('')
const question = ref('')
const loading = ref(false)
const error = ref('')

// PP7: current answer metadata
const currentAnswer = ref(null)  // { question, answer, citations, steps, question_id, rating }

// PP6: conversation history (previous turns, oldest first)
const history = ref([])           // [{ role: 'user'|'assistant', content: string }]

// PP7: search steps panel toggle
const stepsOpen = ref(false)

const renderedAnswer = computed(() =>
  currentAnswer.value ? md.render(currentAnswer.value.answer) : ''
)

// PP7: step type labels
const stepLabel = { rewrite: '查詢改寫', kb: '知識庫', web: '網路搜尋', fetch: '網頁讀取' }
const stepIcon  = { rewrite: '✏️', kb: '📚', web: '🌐', fetch: '🔗' }

async function ask() {
  if (!question.value.trim() || loading.value) return
  error.value = ''
  loading.value = true
  stepsOpen.value = false

  // PP6: build history payload from previous turns
  const historyPayload = history.value.slice(-6)  // at most last 3 Q&A turns (6 messages)

  try {
    const { data } = await api.post('/ask', {
      question: question.value.trim(),
      domain: domain.value.trim() || undefined,
      history: historyPayload,   // PP6
    })

    // PP6: push current Q → history before replacing currentAnswer
    if (currentAnswer.value) {
      history.value.push(
        { role: 'user',      content: currentAnswer.value.question },
        { role: 'assistant', content: currentAnswer.value.answer },
      )
    }

    currentAnswer.value = {
      question: question.value.trim(),
      answer: data.answer,
      citations: data.citations || [],
      steps: data.steps || [],        // PP7
      question_id: data.question_id,  // PP7
      rating: null,
    }
    question.value = ''
    stepsOpen.value = (data.steps || []).length > 1  // auto-open if more than initial KB step
  } catch (e) {
    error.value = e.response?.data?.detail || '問答失敗，請稍後再試'
  } finally {
    loading.value = false
  }
}

function clearConversation() {
  history.value = []
  currentAnswer.value = null
  error.value = ''
}

// PP7: 👍/👎 feedback
async function sendRating(rating) {
  if (!currentAnswer.value || currentAnswer.value.rating !== null) return
  try {
    await api.post(`/ask/feedback?question_id=${currentAnswer.value.question_id}`, { rating })
    currentAnswer.value.rating = rating
  } catch {
    // non-critical; silently ignore
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>問答</h1>
      <p>根據知識庫內容回答問題，答案附引用來源。</p>
    </div>

    <div class="card ask-card">
      <div class="ask-top">
        <div class="field domain-field">
          <label class="label">限定領域（留空 = 全部）</label>
          <input v-model="domain" placeholder="例如 patent" />
        </div>
        <button
          v-if="history.length || currentAnswer"
          class="btn-ghost"
          @click="clearConversation"
          title="清除對話歷史"
        >清除對話</button>
      </div>
      <!-- PP6: history badge -->
      <div v-if="history.length" class="history-badge">
        💬 對話已包含前 {{ history.length / 2 | 0 }} 輪問答
      </div>
      <div class="field">
        <label class="label">問題</label>
        <textarea
          v-model="question"
          placeholder="輸入問題…"
          rows="3"
          @keydown.ctrl.enter="ask"
          @keydown.meta.enter="ask"
        ></textarea>
      </div>
      <button @click="ask" :disabled="!question.trim() || loading">
        {{ loading ? '思考中…' : '提問' }}
      </button>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <!-- Loading state -->
    <div v-if="loading" class="card answer-card">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>

    <!-- Answer card -->
    <div v-else-if="currentAnswer" class="card answer-card">
      <div class="answer-question">
        <span class="q-label">Q</span>
        <span>{{ currentAnswer.question }}</span>
      </div>

      <h3>答案</h3>
      <div class="answer-text" v-html="renderedAnswer"></div>

      <!-- PP5: citations -->
      <div v-if="currentAnswer.citations.length" class="citations">
        <span class="label" style="margin-bottom: 8px; display: block">引用來源</span>
        <div class="chips">
          <span
            v-for="c in currentAnswer.citations"
            :key="c.index"
            class="chip"
            :title="c.source || c.title"
          >
            <span class="cite-idx">[{{ c.index }}]</span> {{ c.title }}
          </span>
        </div>
      </div>

      <!-- PP7: search steps (collapsible) -->
      <div v-if="currentAnswer.steps.length" class="steps-section">
        <button class="steps-toggle" @click="stepsOpen = !stepsOpen">
          <span>🔍 搜尋過程（{{ currentAnswer.steps.length }} 步）</span>
          <span class="chevron" :class="{ open: stepsOpen }">▾</span>
        </button>
        <div v-if="stepsOpen" class="steps-list">
          <div v-for="(s, i) in currentAnswer.steps" :key="i" class="step-item">
            <span class="step-icon">{{ stepIcon[s.type] || '•' }}</span>
            <span class="step-label">{{ stepLabel[s.type] || s.type }}</span>
            <span class="step-query">{{ s.query }}</span>
            <span v-if="s.hits > 0" class="step-hits">{{ s.hits }} 筆</span>
          </div>
        </div>
      </div>

      <!-- PP7: 👍/👎 feedback -->
      <div class="feedback-row">
        <span class="feedback-label">這個答案是否有幫助？</span>
        <button
          class="thumb-btn"
          :class="{ active: currentAnswer.rating === 1 }"
          :disabled="currentAnswer.rating !== null"
          @click="sendRating(1)"
          title="有幫助"
        >👍</button>
        <button
          class="thumb-btn"
          :class="{ active: currentAnswer.rating === -1 }"
          :disabled="currentAnswer.rating !== null"
          @click="sendRating(-1)"
          title="沒幫助"
        >👎</button>
        <span v-if="currentAnswer.rating !== null" class="feedback-thanks">
          {{ currentAnswer.rating === 1 ? '謝謝你的回饋！' : '感謝，將持續改善。' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-card {
  margin-bottom: 16px;
}

.ask-top {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 4px;
}

.domain-field {
  flex: 1;
}

.btn-ghost {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-dim);
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-ghost:hover {
  border-color: var(--text-dim);
  color: var(--text);
}

.history-badge {
  font-size: 12px;
  color: var(--text-faint);
  margin-bottom: 8px;
}

.answer-card {
  animation: fade-in 0.2s ease;
}

.answer-question {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.q-label {
  font-size: 11px;
  font-weight: 700;
  background: var(--accent);
  color: #fff;
  border-radius: 4px;
  padding: 2px 6px;
  flex-shrink: 0;
  margin-top: 1px;
}

.answer-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 16px;
}

.answer-text :deep(h1),
.answer-text :deep(h2),
.answer-text :deep(h3) {
  color: var(--text);
  margin: 16px 0 8px;
}

.answer-text :deep(h1:first-child),
.answer-text :deep(h2:first-child),
.answer-text :deep(h3:first-child) {
  margin-top: 0;
}

.answer-text :deep(p) {
  color: var(--text);
  margin: 0 0 10px;
}

.answer-text :deep(strong) {
  color: var(--text);
  font-weight: 600;
}

.answer-text :deep(ul),
.answer-text :deep(ol) {
  margin: 0 0 10px;
  padding-left: 20px;
}

.answer-text :deep(li) {
  margin-bottom: 4px;
}

.answer-text :deep(code) {
  background: var(--surface-2);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: var(--mono);
  font-size: 13px;
}

.answer-text :deep(pre) {
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 12px;
  overflow-x: auto;
  margin: 0 0 10px;
}

.answer-text :deep(pre code) {
  background: none;
  padding: 0;
}

.answer-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0 0 10px;
  font-size: 13px;
}

.answer-text :deep(th),
.answer-text :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.answer-text :deep(th) {
  background: var(--surface-2);
  color: var(--text-dim);
}

.answer-text :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}

.answer-text :deep(blockquote) {
  border-left: 2px solid var(--border);
  padding-left: 12px;
  color: var(--text-dim);
  margin: 0 0 10px;
}

.answer-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 12px 0;
}

/* citations */
.citations {
  margin-bottom: 12px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-dim);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-idx {
  color: var(--accent);
  font-weight: 600;
  margin-right: 3px;
}

/* PP7: search steps */
.steps-section {
  margin-top: 12px;
  margin-bottom: 12px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.steps-toggle {
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
  font-size: 12px;
  padding: 0;
}

.steps-toggle:hover {
  color: var(--text);
}

.chevron {
  display: inline-block;
  transition: transform 0.15s;
  font-size: 14px;
}

.chevron.open {
  transform: rotate(180deg);
}

.steps-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}

.step-icon {
  flex-shrink: 0;
}

.step-label {
  font-weight: 600;
  flex-shrink: 0;
  min-width: 64px;
}

.step-query {
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.step-hits {
  flex-shrink: 0;
  color: var(--text-faint);
  font-size: 11px;
}

/* PP7: feedback */
.feedback-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.feedback-label {
  font-size: 12px;
  color: var(--text-dim);
  margin-right: 4px;
}

.thumb-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  transition: border-color 0.15s, background 0.15s;
}

.thumb-btn:hover:not(:disabled) {
  border-color: var(--accent);
}

.thumb-btn.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}

.thumb-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.feedback-thanks {
  font-size: 12px;
  color: var(--text-dim);
  margin-left: 4px;
}

/* typing animation */
.typing {
  display: flex;
  gap: 5px;
  padding: 6px 0;
}

.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-faint);
  animation: bounce 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .typing span,
  .answer-card,
  .chevron {
    animation: none;
    transition: none;
  }
}
</style>
