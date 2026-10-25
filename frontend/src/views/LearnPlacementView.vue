<template>
  <div class="learn-page narrow">
    <router-link to="/learn" class="back">← 回學習中心</router-link>
    <header class="page-header">
      <h1>🧭 程度檢測</h1>
      <p class="subtitle">每題對應一個單元。某單元的題目全對，代表你已具備該單元的概念，可以從後面的單元開始。答錯沒關係，這份檢測不計分。</p>
    </header>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <div v-if="!quiz && !error" class="empty-state">載入中…</div>

    <section v-if="result" class="card result-card" data-testid="placement-result">
      <h2>建議從「{{ titleOf(result.recommended_start) }}」開始</h2>
      <p v-if="result.known_units.length" class="muted">已具備：{{ result.known_units.map(titleOf).join('、') }}</p>
      <p v-else class="muted">建議從核心模組的第一個單元依序學習。</p>
      <p v-if="!auth.isLoggedIn" class="muted">登入後再做一次，系統會記住你的建議起點。</p>
      <router-link :to="`/learn/u/${result.recommended_start}`" class="btn btn-primary">前往 {{ titleOf(result.recommended_start) }}</router-link>
    </section>

    <CourseQuiz v-if="quiz" :quiz="quiz" submit-path="/placement" title="12 題檢測"
                :section-links="false" :show-login-hint="false" :show-result="false" @graded="onGraded" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import CourseQuiz from '../components/course/CourseQuiz.vue'
import { courseFetch } from '../lib/courseApi.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const quiz = ref(null)
const catalog = ref(null)
const result = ref(null)
const error = ref('')

function titleOf(id) {
  const u = catalog.value?.units.find(x => x.id === id)
  return u ? `${u.code} ${u.title}` : id
}

function onGraded(res) {
  // 檢測的批改結果格式跟一般測驗不同（沒有 results），直接顯示建議
  result.value = res
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(async () => {
  try {
    const [q, c] = await Promise.all([courseFetch('/placement'), courseFetch('/catalog')])
    quiz.value = q
    catalog.value = c
  } catch (e) {
    error.value = e.message
  }
})
</script>

<style scoped>
.learn-page { padding: 24px; margin: 0 auto; }
.narrow { max-width: 820px; }
.back { color: var(--text-muted); text-decoration: none; font-size: 0.85rem; }
.page-header h1 { margin: 10px 0 6px; font-size: 1.4rem; }
.subtitle { color: var(--text-secondary); line-height: 1.6; margin: 0 0 18px; }
.muted { color: var(--text-muted); font-size: 0.88rem; }
.error-text { color: var(--color-warning); }
.result-card { margin-bottom: 18px; border-color: var(--color-warning); }
.result-card h2 { margin: 0 0 8px; font-size: 1.1rem; }
@media (max-width: 640px) { .learn-page { padding: 16px; } }
</style>
