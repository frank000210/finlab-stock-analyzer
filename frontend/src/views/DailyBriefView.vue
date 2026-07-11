<template>
  <div class="daily-brief-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">📋 觀測重點</span>
      收盤後的市場體制、觀察清單重點與警示，網頁上直接看，不用等 Telegram 推播才知道內容。
    </div>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>盤後日報</h2>
          <p class="muted" v-if="brief">
            <span v-if="brief.as_of">資料日期 {{ brief.as_of }}</span>
            <span v-if="brief.count != null"> · {{ brief.count }} 檔觀察中</span>
          </p>
        </div>
        <div class="actions">
          <button class="btn" :disabled="loading" @click="loadBrief">
            <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>重新產生
          </button>
          <button class="btn btn-primary" :disabled="sending || !brief?.text" @click="sendNow">
            <span v-if="sending" class="loading-spinner btn-spinner" aria-hidden="true"></span>推播到 Telegram
          </button>
        </div>
      </div>
      <p v-if="error" class="error-text">{{ error }}</p>
      <p v-if="sendMsg" class="muted small">{{ sendMsg }}</p>

      <pre v-if="brief && brief.text" class="brief-text">{{ brief.text }}</pre>
      <p v-else-if="brief && !brief.text" class="muted empty">{{ brief.note || '尚無日報內容。' }}</p>

      <p class="disclaimer">※ 排程每個平日收盤後（預設 15:35 台灣時間）自動產生並推播；這裡的「重新產生」是隨叫隨到版，內容相同。僅為訊號摘要，非投資建議。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const brief = ref(null)
const loading = ref(false)
const error = ref('')
const sending = ref(false)
const sendMsg = ref('')

async function loadBrief() {
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/daily-brief`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || '取得日報失敗')
    brief.value = payload.data
  } catch (e) {
    error.value = e?.message || '取得日報失敗'
  } finally {
    loading.value = false
  }
}

async function sendNow() {
  sending.value = true
  sendMsg.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/daily-brief/send`, { method: 'POST' })
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || '推播失敗')
    const d = payload.data
    sendMsg.value = d.sent ? '✓ 已推播到 Telegram。' : '未推播：' + (d.error || '')
  } catch (e) {
    sendMsg.value = e?.message || '推播失敗'
  } finally {
    sending.value = false
  }
}

onMounted(loadBrief)
</script>

<style scoped>
.daily-brief-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2 { margin: 0 0 4px; }
.actions { display: flex; gap: 8px; }
.brief-text {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 14px 16px;
  margin-top: 14px;
  font-size: 0.88rem;
  line-height: 1.6;
  font-family: inherit;
}
</style>
