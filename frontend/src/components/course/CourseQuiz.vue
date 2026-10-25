<template>
  <section class="card quiz-card" data-testid="course-quiz">
    <div class="quiz-head">
      <h2>{{ title }}</h2>
      <span class="muted">{{ quiz.questions.length }} 題 · 答對 {{ Math.round(quiz.pass_ratio * 100) }}% 以上通過</span>
    </div>

    <ol class="questions">
      <li v-for="(q, qi) in quiz.questions" :key="q.id" class="question"
          :class="resultFor(q.id) ? (resultFor(q.id).correct ? 'is-right' : 'is-wrong') : ''">
        <p class="q-text">{{ q.question }}</p>
        <div class="options" role="radiogroup" :aria-label="`第 ${qi + 1} 題`">
          <label v-for="(opt, oi) in q.options" :key="oi" class="option"
                 :class="{ chosen: answers[q.id] === oi, answer: resultFor(q.id) && !resultFor(q.id).correct && resultFor(q.id).answer === oi }">
            <input type="radio" :name="`${idPrefix}-${q.id}`" :value="oi" v-model="answers[q.id]" :disabled="busy" />
            <span>{{ opt }}</span>
          </label>
        </div>
        <div v-if="resultFor(q.id) && !resultFor(q.id).correct" class="feedback">
          <p v-if="resultFor(q.id).explain">💡 {{ resultFor(q.id).explain }}</p>
          <div class="feedback-actions">
            <button v-if="resultFor(q.id).section && sectionLinks" class="link-btn" type="button"
                    @click="$emit('goto-section', resultFor(q.id).section)">
              回到「{{ resultFor(q.id).section }}」複習
            </button>
            <button v-if="tutorEnabled" class="link-btn" type="button" @click="askTutor(q, resultFor(q.id))">
              請 AI 助教講解
            </button>
          </div>
        </div>
      </li>
    </ol>

    <div class="quiz-actions">
      <button class="btn btn-primary" type="button" :disabled="busy || !allAnswered" @click="submit">
        {{ busy ? '批改中…' : (result ? '重新送出' : '送出答案') }}
      </button>
      <button v-if="result" class="btn btn-secondary" type="button" @click="reset">清除重作</button>
      <span v-if="!allAnswered && !result" class="muted">還有 {{ quiz.questions.length - answeredCount }} 題未作答</span>
    </div>

    <div v-if="result && showResult" class="result" :class="result.passed ? 'pass' : 'fail'" role="status" data-testid="quiz-result">
      <strong>{{ result.passed ? '🎉 通過！' : '再接再厲' }}</strong>
      答對 {{ result.correct }} / {{ result.total }} 題
      <span v-if="result.saved">· 已記錄進度（最佳 {{ Math.round((result.best ?? result.ratio) * 100) }}%）</span>
      <span v-else-if="!result.saved && showLoginHint">· 登入後才會記錄成績</span>
    </div>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { courseFetch } from '../../lib/courseApi.js'

const props = defineProps({
  quiz: { type: Object, required: true },
  submitPath: { type: String, required: true },
  title: { type: String, default: '單元測驗' },
  sectionLinks: { type: Boolean, default: true },
  tutorEnabled: { type: Boolean, default: false },
  showLoginHint: { type: Boolean, default: true },
  showResult: { type: Boolean, default: true },
})
const emit = defineEmits(['graded', 'goto-section', 'ask-tutor'])

const idPrefix = Math.random().toString(36).slice(2, 8)
const answers = reactive({})
const result = ref(null)
const busy = ref(false)
const error = ref('')

const answeredCount = computed(() => props.quiz.questions.filter(q => answers[q.id] !== undefined).length)
const allAnswered = computed(() => answeredCount.value === props.quiz.questions.length)

function resultFor(id) {
  return result.value?.results?.find(r => r.id === id) || null
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    result.value = await courseFetch(props.submitPath, { method: 'POST', body: { answers: { ...answers } } })
    emit('graded', result.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function reset() {
  for (const key of Object.keys(answers)) delete answers[key]
  result.value = null
}

function askTutor(q, r) {
  const chosen = r.chosen !== undefined && r.chosen !== null ? q.options[r.chosen] : '（未作答）'
  emit('ask-tutor', `我在測驗題「${q.question}」選了「${chosen}」，但正確答案是「${q.options[r.answer]}」。可以幫我解釋為什麼嗎？`)
}
</script>

<style scoped>
.quiz-card h2 { margin: 0; font-size: 1.05rem; }
.quiz-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.muted { color: var(--text-muted); font-size: 0.82rem; }
.questions { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 16px; }
.question { padding: 12px 14px; border-radius: 10px; background: var(--bg-well); border: 1px solid var(--border-color); }
.question.is-right { border-color: rgba(16, 185, 129, 0.45); }
.question.is-wrong { border-color: rgba(245, 158, 11, 0.55); }
.q-text { margin: 0 0 8px; font-weight: 600; color: var(--text-primary); }
.options { display: flex; flex-direction: column; gap: 6px; }
.option {
  display: flex; gap: 8px; align-items: flex-start; padding: 7px 10px; border-radius: 8px;
  cursor: pointer; border: 1px solid transparent; color: var(--text-secondary); font-size: 0.9rem;
}
.option:hover { background: var(--bg-hover); }
.option.chosen { border-color: var(--accent-blue); color: var(--text-primary); }
.option.answer { border-color: var(--color-down); background: var(--down-soft); }
.option input { margin-top: 3px; }
.feedback { margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary); }
.feedback p { margin: 0 0 6px; }
.feedback-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.link-btn { background: none; border: 0; padding: 0; color: var(--accent-cyan); cursor: pointer; font: inherit; text-decoration: underline; }
.quiz-actions { display: flex; gap: 10px; align-items: center; margin-top: 16px; flex-wrap: wrap; }
.result { margin-top: 12px; padding: 10px 12px; border-radius: 10px; font-size: 0.9rem; }
.result.pass { background: var(--down-soft); color: var(--text-primary); }
.result.fail { background: var(--warn-soft); color: var(--text-primary); }
.error-text { color: var(--color-warning); font-size: 0.85rem; }
</style>
