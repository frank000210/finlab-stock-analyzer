<script setup>
import { ref } from 'vue'
import api from '../api.js'

const domain = ref('')
const question = ref('')
const answer = ref('')
const citations = ref([])
const loading = ref(false)
const error = ref('')

async function ask() {
  error.value = ''
  answer.value = ''
  citations.value = []
  loading.value = true
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
  <h1>問答</h1>
  <label>限定領域（留空 = 全部） <input v-model="domain" placeholder="例如 patent" /></label>
  <textarea v-model="question" placeholder="輸入問題" rows="3" style="width: 100%"></textarea>
  <button @click="ask" :disabled="!question || loading">{{ loading ? '思考中…' : '提問' }}</button>

  <p v-if="error" style="color: red">{{ error }}</p>
  <div v-if="answer">
    <h2>答案</h2>
    <p>{{ answer }}</p>
    <h3>引用來源</h3>
    <ul>
      <li v-for="(c, i) in citations" :key="i">{{ c.title }} — {{ c.source }}</li>
    </ul>
  </div>
</template>
