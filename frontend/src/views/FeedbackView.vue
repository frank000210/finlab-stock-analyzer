<template>
  <div class="feedback-page">
    <PageFocusBanner text="有想法、發現 bug、或希望增加什麼功能都可以留言。意見會作為後續自主優化循環的參考依據，處理完成後也會回覆在這裡。" />

    <header class="page-header">
      <div>
        <h1>💡 使用者意見收集</h1>
        <p class="subtitle">送出的意見會保留在下方列表，狀態更新後可以回來查看處理結果</p>
      </div>
    </header>

    <section class="card form-card">
      <div class="form-grid">
        <label class="field">
          <span>類型</span>
          <select v-model="form.category" class="inp">
            <option value="bug">🐛 問題回報</option>
            <option value="feature">✨ 功能建議</option>
            <option value="other">💬 其他</option>
          </select>
        </label>
        <label class="field">
          <span>相關頁面（選填）</span>
          <input v-model="form.page" class="inp" placeholder="例如：投組風險、交易日誌" />
        </label>
      </div>
      <label class="field">
        <span>內容</span>
        <textarea v-model="form.content" class="inp" rows="4" maxlength="2000" placeholder="請描述你遇到的問題或想法..."></textarea>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" :disabled="submitting || !form.content.trim()" @click="submitFeedback">
          <span v-if="submitting" class="loading-spinner btn-spinner" aria-hidden="true"></span>
          {{ submitting ? '送出中…' : '送出意見' }}
        </button>
        <span v-if="submitError" class="error-text">{{ submitError }}</span>
        <span v-if="submitOk" class="success-text">已送出，謝謝！</span>
      </div>
    </section>

    <section class="card list-card">
      <div class="section-head compact">
        <div><h2>意見列表</h2></div>
        <select v-model="statusFilter" class="inp xs-select" aria-label="依狀態篩選" @change="loadFeedback">
          <option value="">全部狀態</option>
          <option value="open">待處理</option>
          <option value="in_progress">處理中</option>
          <option value="resolved">已完成</option>
        </select>
      </div>

      <div v-if="loading" class="empty-state">載入中…</div>
      <div v-else-if="!items.length" class="empty-state">目前還沒有意見，成為第一個留言的人吧！</div>
      <ul v-else class="feedback-list">
        <li v-for="item in items" :key="item._id" class="feedback-item">
          <div class="item-head">
            <span class="badge" :class="`badge-${item.category}`">{{ categoryLabel(item.category) }}</span>
            <span v-if="item.page" class="muted small">{{ item.page }}</span>
            <span class="status-pill" :class="`status-${item.status}`">{{ statusLabel(item.status) }}</span>
            <span class="muted small time">{{ formatTime(item.created_at) }}</span>
          </div>
          <p class="item-content">{{ item.content }}</p>
          <div v-if="item.response" class="item-response">
            <strong>回覆：</strong>{{ item.response }}
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const form = ref({ category: 'other', page: '', content: '' })
const submitting = ref(false)
const submitError = ref('')
const submitOk = ref(false)

const items = ref([])
const loading = ref(false)
const statusFilter = ref('')

function categoryLabel(c) {
  return { bug: '🐛 問題回報', feature: '✨ 功能建議', other: '💬 其他' }[c] || c
}
function statusLabel(s) {
  return { open: '待處理', in_progress: '處理中', resolved: '已完成' }[s] || s
}
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d) ? '' : d.toLocaleString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadFeedback() {
  loading.value = true
  try {
    const qs = statusFilter.value ? `?status=${statusFilter.value}` : ''
    const resp = await fetch(`${API_BASE}/api/v1/feedback${qs}`)
    const payload = await resp.json().catch(() => ({}))
    items.value = payload?.data || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function submitFeedback() {
  const content = form.value.content.trim()
  if (!content) return
  submitting.value = true
  submitError.value = ''
  submitOk.value = false
  try {
    const resp = await fetch(`${API_BASE}/api/v1/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: form.value.category, page: form.value.page.trim() || null, content }),
    })
    if (!resp.ok) {
      const payload = await resp.json().catch(() => ({}))
      throw new Error(payload?.detail || '送出失敗')
    }
    form.value.content = ''
    form.value.page = ''
    submitOk.value = true
    loadFeedback()
  } catch (e) {
    submitError.value = e?.message || '送出失敗'
  } finally {
    submitting.value = false
  }
}

onMounted(loadFeedback)
</script>

<style scoped>
.feedback-page { display: flex; flex-direction: column; gap: 16px; }
.page-header h1 { margin: 0 0 4px; }
.subtitle { color: var(--text-secondary); margin: 0; }

.form-card { display: flex; flex-direction: column; gap: 10px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); width: 100%; }
.form-actions { display: flex; align-items: center; gap: 10px; }
.error-text { color: #ef4444; font-size: 0.84rem; }
.success-text { color: #10b981; font-size: 0.84rem; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.list-card { display: flex; flex-direction: column; gap: 10px; }
.xs-select { padding: 6px 8px; font-size: 0.8rem; width: auto; }
.empty-state { color: var(--text-secondary); padding: 20px 0; text-align: center; }

.feedback-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.feedback-item { border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 10px 12px; background: var(--bg-secondary); }
.item-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.item-content { margin: 0; white-space: pre-wrap; word-break: break-word; }
.item-response { margin-top: 8px; padding: 8px 10px; border-radius: 8px; background: var(--bg-well, rgba(16,185,129,0.08)); border: 1px solid rgba(16,185,129,0.3); font-size: 0.88rem; }
.time { margin-left: auto; }

.badge { padding: 2px 8px; border-radius: 999px; font-size: 0.76rem; background: var(--bg-well, rgba(148,163,184,0.15)); }
.status-pill { padding: 2px 8px; border-radius: 999px; font-size: 0.76rem; }
.status-open { background: rgba(234,179,8,0.15); color: #eab308; }
.status-in_progress { background: rgba(59,130,246,0.15); color: #3b82f6; }
.status-resolved { background: rgba(16,185,129,0.15); color: #10b981; }
</style>
