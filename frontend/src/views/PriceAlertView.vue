<template>
  <div class="price-alert-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">🔔 觀測重點</span>
      設好條件、讓系統盯盤，不用自己一直盯著看盤軟體。條件觸發會推播 Telegram（需先在設定頁綁定 Bot）。
    </div>

    <section class="section-block" v-reveal>
      <h2>新增警報</h2>
      <div class="add-form">
        <input v-model="form.symbol" class="inp" placeholder="代碼 2330" @keyup.enter="addAlert" />
        <select v-model="form.alert_type" class="inp">
          <option v-if="notifPrefs.price" value="price">價格</option>
          <option v-if="notifPrefs.signal" value="volume_spike">成交量異常</option>
          <option v-if="notifPrefs.signal" value="rsi_extreme">RSI 極端值</option>
        </select>
        <p v-if="!notifPrefs.price && !notifPrefs.signal" class="error-text">
          設定頁的通知偏好目前全部關閉，請先到「⚙️ 設定」開啟至少一種通知類型。
        </p>
        <select v-if="form.alert_type === 'price'" v-model="form.direction" class="inp">
          <option value="above">漲破</option>
          <option value="below">跌破</option>
        </select>
        <select v-else-if="form.alert_type === 'rsi_extreme'" v-model="form.direction" class="inp">
          <option value="above">超買（RSI ≥ 70）</option>
          <option value="below">超賣（RSI ≤ 30）</option>
        </select>
        <input
          v-if="form.alert_type === 'price'"
          v-model.number="form.target_price"
          type="number" class="inp" placeholder="目標價" step="0.05" @keyup.enter="addAlert"
        />
        <span v-else class="muted small threshold-hint">{{ thresholdHint }}</span>
        <input v-model="form.note" class="inp note-inp" placeholder="備註（選填）" @keyup.enter="addAlert" />
        <button class="btn btn-primary" :disabled="adding" @click="addAlert">加入</button>
      </div>
      <p v-if="formError" class="error-text">{{ formError }}</p>
    </section>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <h3>警報清單（{{ alerts.length }}）</h3>
        <button class="btn" :disabled="checking" @click="checkNow">
          <span v-if="checking" class="loading-spinner btn-spinner" aria-hidden="true"></span>立即檢查
        </button>
      </div>
      <p v-if="checkMsg" class="muted small">{{ checkMsg }}</p>

      <div class="table-wrap" v-if="alerts.length">
        <table class="alert-table">
          <thead>
            <tr><th>代碼</th><th>類型</th><th>條件</th><th>現價</th><th>狀態</th><th>備註</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="a in alerts" :key="a.id">
              <td class="sym">{{ a.symbol }}</td>
              <td>{{ typeLabel(a.alert_type) }}</td>
              <td>{{ conditionLabel(a) }}</td>
              <td>{{ a.last_price != null ? fmt(a.last_price) : '—' }}</td>
              <td><span :class="a.triggered ? 'ok-text' : 'muted'">{{ statusLabel(a) }}</span></td>
              <td class="muted">{{ a.note || '—' }}</td>
              <td><button class="del" @click="remove(a.id)" title="刪除" aria-label="刪除警報">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">尚無警報。加入一筆條件，系統會在盤中自動檢查。</p>
      <p class="disclaimer">※ 系統每 20 分鐘於盤中（週一~五 09:00–13:35）自動檢查，觸發後推播 Telegram 且僅推播一次（避免洗版）。需先在設定頁設定 TELEGRAM_BOT_TOKEN／CHAT_ID。成交量異常／RSI 門檻與全站訊號掃描（作戰台/訊號頁）用同一套標準：成交量 ≥20 日均量 1.5 倍、RSI ≥70 超買 /≤30 超賣。本工具僅為提醒，非投資建議。</p>
    </section>

    <!-- Y3：警報歷史中心——原本觸發後只把同一筆警報標成已觸發，沒有時間序列可查 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <h3>觸發歷史</h3>
        <button class="btn xs" :disabled="historyLoading" @click="loadHistory">
          <span v-if="historyLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>重新整理
        </button>
      </div>
      <div class="table-wrap" v-if="history.length">
        <table class="alert-table">
          <thead>
            <tr><th>時間</th><th>代碼</th><th>類型</th><th>觸發時數值</th><th>備註</th></tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.id + h.triggered_at">
              <td class="muted">{{ formatTime(h.triggered_at) }}</td>
              <td class="sym">{{ h.symbol }}</td>
              <td>{{ typeLabel(h.alert_type) }}</td>
              <td>{{ historyValueLabel(h) }}</td>
              <td class="muted">{{ h.note || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">尚無觸發紀錄。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { loadNotificationPrefs } from '../lib/notificationPrefs'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// Y2：設定頁的通知偏好決定這裡能選哪些警報類型
const notifPrefs = ref(loadNotificationPrefs())
const alerts = ref([])
const history = ref([])
const historyLoading = ref(false)
const form = reactive({
  symbol: '',
  alert_type: notifPrefs.value.price ? 'price' : (notifPrefs.value.signal ? 'volume_spike' : 'price'),
  direction: 'above', target_price: null, note: '',
})
const formError = ref('')
const adding = ref(false)
const checking = ref(false)
const checkMsg = ref('')

const thresholdHint = computed(() => {
  if (form.alert_type === 'volume_spike') return '門檻：成交量 ≥ 20 日均量 1.5 倍'
  if (form.alert_type === 'rsi_extreme') return form.direction === 'above' ? '門檻：RSI ≥ 70' : '門檻：RSI ≤ 30'
  return ''
})

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function statusLabel(a) { return a.triggered ? '✓ 已觸發' : (a.active ? '監控中' : '已停用') }
function typeLabel(t) { return { price: '價格', volume_spike: '成交量異常', rsi_extreme: 'RSI 極端值' }[t] || t }
function conditionLabel(a) {
  if (a.alert_type === 'volume_spike') return '≥ 1.5× 均量'
  if (a.alert_type === 'rsi_extreme') return a.direction === 'above' ? 'RSI ≥ 70' : 'RSI ≤ 30'
  return `${a.direction === 'above' ? '漲破' : '跌破'} ${fmt(a.target_price)}`
}
function historyValueLabel(h) {
  if (h.alert_type === 'volume_spike') return `${h.vol_ratio}× 均量（價 ${fmt(h.price)}）`
  if (h.alert_type === 'rsi_extreme') return `RSI ${h.rsi}（價 ${fmt(h.price)}）`
  return `價 ${fmt(h.price)}`
}
function formatTime(iso) {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 16)
}

async function loadAlerts() {
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts`)
    const payload = await resp.json().catch(() => ({}))
    if (resp.ok && payload?.data) alerts.value = payload.data.items || []
  } catch { /* ignore */ }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts/history?limit=50`)
    const payload = await resp.json().catch(() => ({}))
    if (resp.ok && payload?.data) history.value = payload.data.items || []
  } catch {
    // 歷史是附加資訊，抓不到不影響警報清單本身
  } finally {
    historyLoading.value = false
  }
}

async function addAlert() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  if (!symbol) {
    formError.value = '請填入股票代碼。'
    return
  }
  if (form.alert_type === 'price' && !(Number(form.target_price) > 0)) {
    formError.value = '價格警報請填入有效的目標價（大於 0）。'
    return
  }
  adding.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol, alert_type: form.alert_type, direction: form.direction,
        target_price: form.alert_type === 'price' ? Number(form.target_price) : null,
        note: form.note || '',
      }),
    })
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || '新增失敗')
    alerts.value.push(payload.data)
    form.symbol = ''
    form.target_price = null
    form.note = ''
  } catch (e) {
    formError.value = e?.message || '新增失敗'
  } finally {
    adding.value = false
  }
}

async function remove(id) {
  if (!window.confirm('確定要刪除這則警報嗎？')) return
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('刪除失敗')
    alerts.value = alerts.value.filter(a => a.id !== id)
  } catch {
    formError.value = '刪除失敗，請稍後再試。'
  }
}

async function checkNow() {
  checking.value = true
  checkMsg.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts/check`, { method: 'POST' })
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || '檢查失敗')
    const d = payload.data
    checkMsg.value = `已檢查 ${d.checked} 檔股票，觸發 ${d.triggered} 筆警報。`
    await Promise.all([loadAlerts(), loadHistory()])
  } catch (e) {
    checkMsg.value = e?.message || '檢查失敗'
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  notifPrefs.value = loadNotificationPrefs() // 每次進頁重讀，反映使用者在設定頁的最新偏好
  loadAlerts()
  loadHistory()
})
</script>

<style scoped>
.price-alert-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.head-row h3 { margin: 0; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }

.add-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.add-form .inp { width: 130px; }
.add-form .note-inp { width: 200px; }
.threshold-hint { white-space: nowrap; }
.small { font-size: 0.78rem; }

.table-wrap { overflow-x: auto; margin-top: 14px; }
.alert-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.alert-table th, .alert-table td { text-align: right; padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.alert-table th:first-child, .alert-table td:first-child { text-align: left; }
.alert-table th { color: var(--text-muted); font-weight: 500; font-size: 0.76rem; }
.sym { font-weight: 600; }
.del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; }
.del:hover { color: #ef4444; }
</style>
