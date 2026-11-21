<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import api from '../api.js'

// html:false -- any raw HTML in the LLM's answer is escaped to literal
// text rather than parsed as markup, so a malicious/injected answer can't
// render arbitrary tags via v-html.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const route = useRoute()

const notebooks = ref([])
const domain = ref(typeof route.query.domain === 'string' ? route.query.domain : '')
const question = ref('')
const loading = ref(false)
const turns = ref([])
const threadEndRef = ref(null)

let turnSeq = 0
let conversationSeq = 0

watch(
  () => route.query.domain,
  (val) => {
    domain.value = typeof val === 'string' ? val : ''
  },
)

const domainOptions = computed(() => {
  const list = notebooks.value.map((nb) => ({
    domain: nb.domain,
    doc_count: nb.doc_count,
  }))
  if (domain.value && !list.some((item) => item.domain === domain.value)) {
    list.unshift({ domain: domain.value, doc_count: null })
  }
  return list
})

const completedTurnCount = computed(
  () => turns.value.filter((t) => t.status === 'done').length,
)

// PP7: step type labels
const stepLabel = { rewrite: '查詢改寫', kb: '知識庫', web: '網路搜尋', fetch: '網頁讀取' }
const stepIcon  = { rewrite: '✏️', kb: '📚', web: '🌐', fetch: '🔗' }

function renderMarkdown(text) {
  return text ? md.render(text) : ''
}

function isExternalUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value.trim())
}

function getCitationSnippet(c) {
  return c?.snippet || c?.excerpt || c?.content || ''
}

function toggleCitation(turn, index) {
  turn.expandedCitationIndex = turn.expandedCitationIndex === index ? null : index
}

function getExpandedCitation(turn) {
  if (turn.expandedCitationIndex === null || turn.expandedCitationIndex === undefined) return null
  return turn.citations.find((c) => c.index === turn.expandedCitationIndex) || null
}

function scrollToLatest() {
  nextTick(() => {
    threadEndRef.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

onMounted(async () => {
  try {
    const { data } = await api.get('/notebooks')
    if (Array.isArray(data)) {
      notebooks.value = data
    }
  } catch {
    // 領域清單抓取失敗時仍保留「全部領域」與 URL 預選領域
  }
})

async function ask() {
  const trimmedQuestion = question.value.trim()
  if (!trimmedQuestion || loading.value) return

  const activeConv = conversationSeq
  const selectedDomain = domain.value.trim()

  // PP6: build history payload from up to last 3 completed Q&A turns (6 messages)
  const historyPayload = turns.value
    .filter((t) => t.status === 'done')
    .flatMap((t) => [
      { role: 'user', content: t.question },
      { role: 'assistant', content: t.answer },
    ])
    .slice(-6)

  const newTurn = {
    id: ++turnSeq,
    question: trimmedQuestion,
    domain: selectedDomain,
    status: 'loading',
    answer: '',
    citations: [],
    steps: [],
    question_id: null,
    rating: null,
    errorMessage: '',
    stepsOpen: false,
    expandedCitationIndex: null,
  }

  turns.value.push(newTurn)
  const reactiveTurn = turns.value[turns.value.length - 1]
  question.value = ''
  loading.value = true
  scrollToLatest()

  try {
    const { data } = await api.post('/ask', {
      question: trimmedQuestion,
      domain: selectedDomain || undefined,
      history: historyPayload,
    })

    // 若使用者在等待回應期間已清除對話，忽略過期回應
    if (activeConv !== conversationSeq) return

    reactiveTurn.status = 'done'
    reactiveTurn.answer = data.answer || ''
    reactiveTurn.citations = data.citations || []
    reactiveTurn.steps = data.steps || []
    reactiveTurn.question_id = data.question_id || null
    reactiveTurn.stepsOpen = reactiveTurn.steps.length > 1
    scrollToLatest()
  } catch (e) {
    if (activeConv !== conversationSeq) return
    reactiveTurn.status = 'error'
    reactiveTurn.errorMessage = e.response?.data?.detail || '問答失敗，請稍後再試'
  } finally {
    if (activeConv === conversationSeq) {
      loading.value = false
    }
  }
}

function clearConversation() {
  conversationSeq += 1
  turns.value = []
  loading.value = false
}

// PP7: 👍/👎 feedback
async function sendRating(turn, rating) {
  if (!turn || !turn.question_id || turn.rating !== null) return
  try {
    await api.post(`/ask/feedback?question_id=${encodeURIComponent(turn.question_id)}`, { rating })
    turn.rating = rating
  } catch {
    // non-critical; silently ignore
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>問答</h1>
      <p>根據知識庫內容回答問題，答案附可展開的引用來源，支援連續追問。</p>
    </div>

    <!-- 對話串（保留所有歷史問答，新提問在底部追加） -->
    <section v-if="turns.length" class="chat-thread" aria-label="問答對話紀錄" data-testid="chat-thread">
      <div class="thread-bar">
        <span class="history-badge">
          💬 共 {{ turns.length }} 輪對話<template v-if="completedTurnCount">（追問自動帶入近期上下文）</template>
        </span>
        <button
          type="button"
          class="btn-ghost"
          data-testid="clear-chat-btn"
          @click="clearConversation"
          title="清除對話歷史"
        >清除對話</button>
      </div>

      <article v-for="turn in turns" :key="turn.id" class="chat-turn" data-testid="chat-turn">
        <!-- 使用者問題氣泡 -->
        <div class="msg-user-row">
          <div class="msg-user" data-testid="user-bubble">
            <div class="msg-user-meta">
              <span class="q-label">Q</span>
              <span v-if="turn.domain" class="domain-tag">{{ turn.domain }}</span>
            </div>
            <p class="msg-user-text">{{ turn.question }}</p>
          </div>
        </div>

        <!-- 助理回答／思考中氣泡 -->
        <div class="card answer-card msg-assistant" :class="{ 'is-loading': turn.status === 'loading' }">
          <div v-if="turn.status === 'loading'" class="thinking-row" role="status" aria-live="polite" data-testid="thinking-bubble">
            <div class="typing" aria-hidden="true"><span></span><span></span><span></span></div>
            <span class="thinking-text">思考中…</span>
          </div>

          <p v-else-if="turn.status === 'error'" class="error-text turn-error" role="alert">
            {{ turn.errorMessage }}
          </p>

          <template v-else>
            <h3 class="answer-heading">答案</h3>
            <div class="answer-text" v-html="renderMarkdown(turn.answer)"></div>

            <!-- PP5: clickable expandable citations -->
            <div v-if="turn.citations.length" class="citations">
              <span class="label citations-label">引用來源（點擊展開完整出處）</span>
              <div class="chips">
                <button
                  v-for="c in turn.citations"
                  :key="c.index"
                  type="button"
                  class="chip"
                  :class="{ active: turn.expandedCitationIndex === c.index }"
                  :aria-expanded="turn.expandedCitationIndex === c.index ? 'true' : 'false'"
                  :title="c.source ? `${c.title} — ${c.source}` : c.title"
                  @click="toggleCitation(turn, c.index)"
                >
                  <span class="cite-idx">[{{ c.index }}]</span>
                  <span class="chip-title">{{ c.title }}</span>
                </button>
              </div>

              <div
                v-if="getExpandedCitation(turn)"
                class="citation-detail"
                data-testid="citation-detail"
              >
                <div class="citation-detail-head">
                  <div class="citation-detail-title">
                    <span class="cite-idx">[{{ getExpandedCitation(turn).index }}]</span>
                    <strong>{{ getExpandedCitation(turn).title }}</strong>
                  </div>
                  <button
                    type="button"
                    class="citation-close"
                    aria-label="收合引用詳情"
                    @click="turn.expandedCitationIndex = null"
                  >×</button>
                </div>
                <div v-if="getExpandedCitation(turn).source" class="citation-source">
                  <span class="citation-source-label">出處：</span>
                  <a
                    v-if="isExternalUrl(getExpandedCitation(turn).source)"
                    :href="getExpandedCitation(turn).source"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="citation-link"
                  >{{ getExpandedCitation(turn).source }}</a>
                  <code v-else class="citation-path">{{ getExpandedCitation(turn).source }}</code>
                </div>
                <p v-if="getCitationSnippet(getExpandedCitation(turn))" class="citation-snippet">
                  {{ getCitationSnippet(getExpandedCitation(turn)) }}
                </p>
                <p
                  v-else-if="!getExpandedCitation(turn).source"
                  class="citation-empty-note"
                >
                  此引用僅包含文件標題資訊。
                </p>
              </div>
            </div>

            <!-- PP7: search steps (collapsible) -->
            <div v-if="turn.steps.length" class="steps-section">
              <button type="button" class="steps-toggle" @click="turn.stepsOpen = !turn.stepsOpen">
                <span>🔍 搜尋過程（{{ turn.steps.length }} 步）</span>
                <span class="chevron" :class="{ open: turn.stepsOpen }">▾</span>
              </button>
              <div v-if="turn.stepsOpen" class="steps-list">
                <div v-for="(s, i) in turn.steps" :key="i" class="step-item">
                  <span class="step-icon">{{ stepIcon[s.type] || '•' }}</span>
                  <span class="step-label">{{ stepLabel[s.type] || s.type }}</span>
                  <span class="step-query">{{ s.query }}</span>
                  <span v-if="s.hits > 0" class="step-hits">{{ s.hits }} 筆</span>
                </div>
              </div>
            </div>

            <!-- PP7: 👍/👎 feedback -->
            <div v-if="turn.question_id" class="feedback-row">
              <span class="feedback-label">這個答案是否有幫助？</span>
              <button
                type="button"
                class="thumb-btn"
                :class="{ active: turn.rating === 1 }"
                :disabled="turn.rating !== null"
                @click="sendRating(turn, 1)"
                title="有幫助"
              >👍</button>
              <button
                type="button"
                class="thumb-btn"
                :class="{ active: turn.rating === -1 }"
                :disabled="turn.rating !== null"
                @click="sendRating(turn, -1)"
                title="沒幫助"
              >👎</button>
              <span v-if="turn.rating !== null" class="feedback-thanks">
                {{ turn.rating === 1 ? '謝謝你的回饋！' : '感謝，將持續改善。' }}
              </span>
            </div>
          </template>
        </div>
      </article>
      <div ref="threadEndRef" aria-hidden="true"></div>
    </section>

    <!-- 提問輸入卡片 -->
    <div class="card ask-card">
      <div class="ask-top">
        <div class="field domain-field">
          <label class="label" for="ask-domain">限定領域</label>
          <select id="ask-domain" v-model="domain" data-testid="domain-select">
            <option value="">全部領域</option>
            <option v-for="opt in domainOptions" :key="opt.domain" :value="opt.domain">
              {{ opt.doc_count !== null ? `${opt.domain}（${opt.doc_count} 篇）` : opt.domain }}
            </option>
          </select>
        </div>
      </div>

      <div class="field question-field">
        <label class="label" for="ask-question">{{ turns.length ? '繼續追問' : '問題' }}</label>
        <textarea
          id="ask-question"
          v-model="question"
          :placeholder="turns.length ? '輸入追問內容…' : '輸入問題…'"
          rows="3"
          @keydown.ctrl.enter.prevent="ask"
          @keydown.meta.enter.prevent="ask"
        ></textarea>
      </div>

      <div class="ask-actions">
        <span class="shortcut-hint">
          按 <kbd>Ctrl</kbd> / <kbd>⌘</kbd> + <kbd>Enter</kbd> 快速送出
        </span>
        <button type="button" @click="ask" :disabled="!question.trim() || loading">
          {{ loading ? '思考中…' : '提問' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-thread {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 20px;
}

.thread-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.chat-turn {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg-user-row {
  display: flex;
  justify-content: flex-end;
}

.msg-user {
  max-width: min(86%, 640px);
  padding: 12px 16px;
  border-radius: 14px 14px 4px 14px;
  background: var(--accent-dim);
  border: 1px solid color-mix(in srgb, var(--accent) 34%, var(--border));
  color: var(--text);
  animation: fade-in 0.2s ease;
}

.msg-user-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.domain-tag {
  font-size: 11px;
  font-family: var(--mono);
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-dim);
}

.msg-user-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

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

.question-field {
  margin-bottom: 12px;
}

.ask-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.shortcut-hint {
  font-size: 12px;
  color: var(--text-faint);
}

.shortcut-hint kbd {
  display: inline-block;
  padding: 1px 5px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-dim);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
}

.btn-ghost {
  background: transparent;
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
  background: var(--surface-2);
  color: var(--text);
}

.history-badge {
  font-size: 12px;
  color: var(--text-faint);
}

.answer-card {
  animation: fade-in 0.2s ease;
}

.answer-heading {
  margin-bottom: 8px;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.thinking-text {
  font-size: 13px;
  color: var(--text-dim);
}

.turn-error {
  margin-top: 0;
}

.q-label {
  font-size: 11px;
  font-weight: 700;
  background: var(--accent);
  color: var(--on-accent);
  border-radius: 4px;
  padding: 2px 6px;
  flex-shrink: 0;
}

.answer-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 16px;
  overflow-wrap: anywhere;
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
  display: block;
  overflow-x: auto;
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

.citations-label {
  margin-bottom: 8px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-dim);
  max-width: min(280px, 100%);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.chip:hover {
  border-color: var(--accent);
  background: var(--accent-dim);
  color: var(--text);
}

.chip.active {
  border-color: var(--accent);
  background: var(--accent-dim);
  color: var(--text);
  font-weight: 500;
}

.chip:active {
  transform: none;
}

.chip-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite-idx {
  color: var(--accent);
  font-weight: 600;
  flex-shrink: 0;
}

.citation-detail {
  margin-top: 10px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
  animation: fade-in 0.15s ease;
}

.citation-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.citation-detail-title {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.citation-close {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-dim);
  border-radius: var(--radius-sm);
  padding: 0 7px;
  font-size: 15px;
  line-height: 1.4;
  flex-shrink: 0;
}

.citation-close:hover {
  background: var(--surface);
  color: var(--text);
}

.citation-source {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.citation-source-label {
  color: var(--text-faint);
}

.citation-path {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text);
  background: var(--surface);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  word-break: break-all;
}

.citation-link {
  color: var(--accent);
  text-decoration: underline;
  word-break: break-all;
}

.citation-snippet {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.citation-empty-note {
  font-size: 12px;
  color: var(--text-faint);
}

/* PP7: search steps */
.steps-section {
  margin-top: 12px;
  margin-bottom: 12px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.steps-toggle {
  background: transparent;
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
  background: transparent;
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
  min-width: 0;
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
  min-width: 0;
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
  flex-wrap: wrap;
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
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  transition: border-color 0.15s, background 0.15s;
}

.thumb-btn:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: var(--accent);
}

.thumb-btn.active {
  border-color: var(--accent);
  background: var(--accent-dim);
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

@media (max-width: 600px) {
  .msg-user {
    max-width: 96%;
  }

  .ask-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .shortcut-hint {
    text-align: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .typing span,
  .answer-card,
  .msg-user,
  .citation-detail,
  .chevron,
  .chip {
    animation: none;
    transition: none;
  }
}
</style>
