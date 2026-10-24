<template>
  <aside class="tutor" :class="{ open }" data-testid="course-tutor" aria-label="AI 助教">
    <header class="tutor-head">
      <strong>🤖 AI 助教</strong>
      <span class="muted">{{ unitTitle }}</span>
      <button class="icon-btn" type="button" aria-label="關閉 AI 助教" @click="$emit('close')">✕</button>
    </header>

    <div ref="scroller" class="messages">
      <p v-if="!messages.length" class="hint">
        有不懂的地方直接問。測驗題我會先給提示；想看答案就說「我想看答案」。
      </p>
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <div v-if="m.role === 'assistant'" class="bubble md" v-html="renderChatMarkdown(m.content)"></div>
        <div v-else class="bubble">{{ m.content }}</div>
      </div>
      <div v-if="busy" class="msg assistant"><div class="bubble muted">思考中…（約需 15–40 秒）</div></div>
    </div>

    <div v-if="!available" class="unavailable">
      <p>AI 助教目前無法使用。你可以把問題直接帶到 Claude Code 問：</p>
      <button class="btn btn-secondary" type="button" @click="copyPrompt">{{ copied ? '已複製' : '複製提問內容' }}</button>
    </div>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <form class="composer" @submit.prevent="send">
      <textarea v-model="draft" class="inp" rows="2" maxlength="2000" placeholder="輸入問題，Enter 送出，Shift+Enter 換行"
                :disabled="busy" @keydown.enter.exact.prevent="send"></textarea>
      <button class="btn btn-primary" type="submit" :disabled="busy || !draft.trim()">送出</button>
    </form>
  </aside>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { courseFetch } from '../../lib/courseApi.js'
import { renderChatMarkdown } from '../../lib/courseMarkdown.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  unitId: { type: String, required: true },
  unitTitle: { type: String, default: '' },
  available: { type: Boolean, default: true },
  prefill: { type: String, default: '' },
})
defineEmits(['close'])

const messages = ref([])
const draft = ref('')
const busy = ref(false)
const error = ref('')
const copied = ref(false)
const scroller = ref(null)

watch(() => props.prefill, (val) => { if (val) draft.value = val })
watch(() => props.unitId, () => { messages.value = []; error.value = '' })

async function scrollToEnd() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

async function send() {
  const question = draft.value.trim()
  if (!question || busy.value) return
  if (!props.available) { error.value = 'AI 助教目前無法使用。'; return }
  const history = messages.value.slice(-6)
  messages.value.push({ role: 'user', content: question })
  draft.value = ''
  busy.value = true
  error.value = ''
  scrollToEnd()
  try {
    const res = await courseFetch('/tutor', { method: 'POST', body: { unit_id: props.unitId, question, history } })
    messages.value.push({ role: 'assistant', content: res.answer })
  } catch (e) {
    error.value = e.message
    // 失敗的問題放回輸入框，不用重打
    messages.value.pop()
    draft.value = question
  } finally {
    busy.value = false
    scrollToEnd()
  }
}

async function copyPrompt() {
  const text = `我正在學「${props.unitTitle}」這個單元。${draft.value || '（在這裡寫下你的問題）'}`
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch { /* 剪貼簿被拒絕時不處理 */ }
}
</script>

<style scoped>
.tutor {
  position: fixed; top: 0; right: 0; bottom: 0; width: min(420px, 100vw); z-index: 400;
  display: flex; flex-direction: column; background: var(--bg-secondary);
  border-left: 1px solid var(--border-color); box-shadow: -8px 0 24px rgba(0, 0, 0, 0.35);
  transform: translateX(100%); transition: transform 0.2s ease; visibility: hidden;
}
.tutor.open { transform: none; visibility: visible; }
@media (prefers-reduced-motion: reduce) { .tutor { transition: none; } }
.tutor-head { display: flex; align-items: center; gap: 8px; padding: 14px 16px; border-bottom: 1px solid var(--border-color); }
.tutor-head .muted { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted { color: var(--text-muted); font-size: 0.82rem; }
.icon-btn { background: none; border: 0; color: var(--text-secondary); cursor: pointer; font-size: 1rem; padding: 4px 8px; }
.messages { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.hint { color: var(--text-muted); font-size: 0.85rem; }
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 92%; padding: 9px 12px; border-radius: 12px; font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.msg.user .bubble { background: var(--accent-blue); color: #fff; }
.msg.assistant .bubble { background: var(--bg-elevated); color: var(--text-primary); }
.bubble.md { white-space: normal; }
.bubble.md :deep(pre) { background: var(--bg-well); padding: 8px; border-radius: 8px; overflow-x: auto; }
.bubble.md :deep(code) { font-size: 0.82rem; }
.bubble.md :deep(p) { margin: 0 0 6px; }
.unavailable { padding: 0 16px 8px; font-size: 0.85rem; color: var(--text-secondary); }
.error-text { color: var(--color-warning); font-size: 0.85rem; padding: 0 16px; margin: 0 0 6px; }
.composer { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border-color); align-items: flex-end; }
.composer textarea { flex: 1; resize: none; }
</style>
