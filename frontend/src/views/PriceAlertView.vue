<template>
  <div class="price-alert-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">🔔 觀測重點</span>
      設好價位、讓系統盯盤，不用自己一直盯著看盤軟體。漲破/跌破指定價位會推播 Telegram（需先在設定頁綁定 Bot）。
    </div>

    <section class="section-block" v-reveal>
      <h2>新增價格警報</h2>
      <div class="add-form">
        <input v-model="form.symbol" class="inp" placeholder="代碼 2330" @keyup.enter="addAlert" />
        <select v-model="form.direction" class="inp">
          <option value="above">漲破</option>
          <option value="below">跌破</option>
        </select>
        <input v-model.number="form.target_price" type="number" class="inp" placeholder="目標價" step="0.05" @keyup.enter="addAlert" />
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
            <tr><th>代碼</th><th>條件</th><th>目標價</th><th>現價</th><th>狀態</th><th>備註</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="a in alerts" :key="a.id">
              <td class="sym">{{ a.symbol }}</td>
              <td>{{ a.direction === 'above' ? '漲破' : '跌破' }}</td>
              <td>{{ fmt(a.target_price) }}</td>
              <td>{{ a.last_price != null ? fmt(a.last_price) : '—' }}</td>
              <td><span :class="a.triggered ? 'up' : 'muted'">{{ statusLabel(a) }}</span></td>
              <td class="muted">{{ a.note || '—' }}</td>
              <td><button class="del" @click="remove(a.id)" title="刪除">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">尚無警報。加入一筆代碼與目標價，系統會在盤中自動檢查。</p>
      <p class="disclaimer">※ 系統每 20 分鐘於盤中（週一~五 09:00–13:35）自動檢查，觸發後推播 Telegram 且僅推播一次（避免洗版）。需先在設定頁設定 TELEGRAM_BOT_TOKEN／CHAT_ID。本工具僅為價格提醒，非投資建議。</p>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const alerts = ref([])
const form = reactive({ symbol: '', direction: 'above', target_price: null, note: '' })
const formError = ref('')
const adding = ref(false)
const checking = ref(false)
const checkMsg = ref('')

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function statusLabel(a) { return a.triggered ? '✓ 已觸發' : (a.active ? '監控中' : '已停用') }

async function loadAlerts() {
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts`)
    const payload = await resp.json().catch(() => ({}))
    if (resp.ok && payload?.data) alerts.value = payload.data.items || []
  } catch { /* ignore */ }
}

async function addAlert() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  const target = Number(form.target_price)
  if (!symbol || !(target > 0)) {
    formError.value = '請填入代碼與有效的目標價（大於 0）。'
    return
  }
  adding.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/alerts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, direction: form.direction, target_price: target, note: form.note || '' }),
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
  try {
    await fetch(`${API_BASE}/api/v1/risk/alerts/${id}`, { method: 'DELETE' })
    alerts.value = alerts.value.filter(a => a.id !== id)
  } catch { /* ignore */ }
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
    await loadAlerts()
  } catch (e) {
    checkMsg.value = e?.message || '檢查失敗'
  } finally {
    checking.value = false
  }
}

onMounted(loadAlerts)
</script>

<style scoped>
.price-alert-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.head-row h3 { margin: 0; }
.muted { color: var(--text-muted); }
.small { font-size: 0.8rem; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.error-text { color: #ef4444; margin-top: 8px; }

.add-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.add-form .inp { width: 130px; }
.add-form .note-inp { width: 200px; }

.table-wrap { overflow-x: auto; margin-top: 14px; }
.alert-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.alert-table th, .alert-table td { text-align: right; padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.alert-table th:first-child, .alert-table td:first-child { text-align: left; }
.alert-table th { color: var(--text-muted); font-weight: 500; font-size: 0.76rem; }
.sym { font-weight: 600; }
.del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; }
.del:hover { color: #ef4444; }
.empty { padding: 16px 0; }
.up { color: #22c55e; }
.disclaimer { font-size: 0.74rem; color: var(--text-muted); margin-top: 12px; }
.btn-spinner { width: 14px; height: 14px; border-width: 2px; vertical-align: -2px; margin-right: 6px; }
</style>
