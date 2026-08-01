<script setup>
import { ref } from 'vue'
import api from '../api.js'

const domain = ref('')
const question = ref('')
const answer = ref('')
const citations = ref([])
const loading = ref(false)
const error = ref('')
const asked = ref(false)

async function ask() {
  error.value = ''
  answer.value = ''
  citations.value = []
  loading.value = true
  asked.value = true
  try {
    const { data } = await api.post('/ask', { question: question.value, domain: domain.value || undefined })
    answer.value = data.answer
    citations.value = data.citations
  } catch (e) {
    error.value = e.response?.data?.detail || '問答失敗'
  } finally {
    loading.value = false
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
      <div class="field">
        <label class="label">限定領域（留空 = 全部）</label>
        <input v-model="domain" placeholder="例如 patent" />
      </div>
      <div class="field">
        <label class="label">問題</label>
        <textarea v-model="question" placeholder="輸入問題…" rows="3"></textarea>
      </div>
      <button @click="ask" :disabled="!question || loading">
        {{ loading ? '思考中…' : '提問' }}
      </button>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="loading" class="card answer-card">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>

    <div v-else-if="asked && answer" class="card answer-card">
      <h3>答案</h3>
      <p class="answer-text">{{ answer }}</p>
      <div v-if="citations.length" class="citations">
        <span class="label" style="margin-bottom: 8px; display: block">引用來源</span>
        <div class="chips">
          <span v-for="(c, i) in citations" :key="i" class="chip" :title="c.source">
            {{ c.title }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-card {
  margin-bottom: 16px;
}

.answer-card {
  animation: fade-in 0.2s ease;
}

.answer-text {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  margin-bottom: 16px;
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
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

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
  .answer-card {
    animation: none;
  }
}
</style>
