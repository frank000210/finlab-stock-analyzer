<template>
  <div class="approval-page">
    <PageFocusBanner text="審核 AI 交易提案：核准即寫入交易日誌成為紙上交易（不會真實下單），練習把關與追蹤成效。" />

    <div class="page-header">
      <div>
        <h1>交易核准中心</h1>
        <p>人工審核 AI 交易提案 🧾 紙上交易——核准後記入交易日誌，不會送出真實委託</p>
      </div>
    </div>

    <p v-if="logMsg" class="log-msg">{{ logMsg }}</p>

    <div class="tabs filter-tabs">
      <button
        v-for="status in statuses"
        :key="status"
        class="tab-button"
        :class="{ active: selectedStatus === status }"
        @click="selectedStatus = status"
      >
        {{ status }}
      </button>
    </div>

    <div v-if="trades.length" class="trade-grid">
      <article v-for="trade in trades" :key="trade.id" class="card trade-card">
        <div class="trade-head">
          <div>
            <h2>{{ trade.symbol }}</h2>
            <p>{{ trade.createdAt }}</p>
          </div>
          <div class="status-row">
            <span class="badge" :class="typeClass(trade.type)">{{ trade.type }}</span>
            <span class="badge" :class="statusClass(trade.status)">{{ trade.status }}</span>
          </div>
        </div>

        <div class="trade-metrics">
          <div>
            <span class="label">信心度</span>
            <strong>{{ trade.confidence }}%</strong>
          </div>
          <div>
            <span class="label">數量</span>
            <strong>{{ trade.quantity }}</strong>
          </div>
          <div>
            <span class="label">預估價格</span>
            <strong>{{ trade.estimatedPrice }}</strong>
          </div>
        </div>

        <div class="reason-box">
          <span class="label">決策說明</span>
          <p>{{ trade.reasoning }}</p>
        </div>

        <div v-if="trade.status === 'PENDING'" class="action-row">
          <button class="btn approve-btn" @click="submitDecision(trade, 'approve')" :disabled="submittingId === trade.id">核准</button>
          <button class="btn reject-btn" @click="submitDecision(trade, 'reject')" :disabled="submittingId === trade.id">拒絕</button>
        </div>
      </article>
    </div>
    <div v-else class="card empty-state">目前沒有符合條件的交易任務</div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { onMounted, ref, watch } from 'vue'
import { loadJournal, saveJournal } from '../lib/tradeMath'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const statuses = ['ALL', 'PENDING', 'APPROVED', 'REJECTED']
const selectedStatus = ref('ALL')
const trades = ref([])
const submittingId = ref('')
const logMsg = ref('')

onMounted(loadTrades)

watch(selectedStatus, async () => {
  await loadTrades()
})

async function loadTrades() {
  try {
    const payload = await apiRequest(`/api/v1/trade/pending?status=${selectedStatus.value}`)
    trades.value = normalizeTrades(payload)
  } catch {
    trades.value = []
  }
}

async function submitDecision(trade, action) {
  submittingId.value = trade.id
  logMsg.value = ''
  try {
    await apiRequest('/api/v1/trade/approve', {
      method: 'POST',
      body: JSON.stringify({ task_id: trade.taskId, action }),
    })
    // C1 接真實流程：過去「核准」只翻後端記憶體裡的狀態旗標，核准了什麼都
    // 不會發生。現在核准即寫入交易日誌成為紙上交易（與作戰台「記錄」同一
    // 條路），之後平倉就進 R 值統計、也被風控監控的真實回撤/熔斷看到。
    if (action === 'approve') await logToJournal(trade)
    await loadTrades()
  } catch (error) {
    window.alert(error.message || '提交失敗')
  }
  submittingId.value = ''
}

async function logToJournal(trade) {
  const entry = Number(trade.rawPrice)
  if (!(entry > 0)) {
    logMsg.value = `已核准 ${trade.symbol}，但提案沒有有效價格，未寫入日誌。`
    return
  }
  const side = trade.type === 'SELL' ? 'short' : 'long'
  // 停損比照作戰台/部位風控的「穩健」慣例：2×ATR；查不到 ATR 退 5%。
  let dist = entry * 0.05
  try {
    const payload = await apiRequest(`/api/v1/risk/sizing/${encodeURIComponent(trade.symbol)}`)
    if (Number(payload?.atr) > 0) dist = 2 * Number(payload.atr)
  } catch { /* 用 5% fallback */ }
  const stop = Math.round((side === 'short' ? entry + dist : entry - dist) * 100) / 100
  const journal = loadJournal()
  if (journal.some(t => t.status === 'open' && t.symbol === trade.symbol && t.side === side)) {
    logMsg.value = `已核准 ${trade.symbol}；交易日誌已有同方向進行中部位，未重複寫入。`
    return
  }
  journal.unshift({
    id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    symbol: trade.symbol, name: trade.symbol, side, entry, stop, target: null,
    lots: Math.max(1, Math.floor((Number(trade.rawQuantity) || 0) / 1000)),
    tag: 'AI核准', openDate: new Date().toISOString().slice(0, 10),
    status: 'open', exit: null, exitDate: null,
  })
  saveJournal(journal)
  logMsg.value = `已核准 ${trade.symbol} 並記錄到交易日誌（紙上交易：進場 ${entry}、停損 ${stop}）。到「交易日誌」平倉即納入統計。`
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.detail || 'API 請求失敗')
  return payload?.data ?? payload
}

function normalizeTrades(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.trades)
        ? payload.trades
        : []
  return list.map((item, index) => ({
    id: item.id || item.task_id || `trade-${index}`,
    taskId: item.task_id || item.id || `trade-${index}`,
    symbol: item.symbol || item.stock_symbol || 'N/A',
    type: String(item.type || item.signal || item.action || 'HOLD').toUpperCase(),
    status: String(item.status || 'PENDING').toUpperCase(),
    confidence: normalizePercent(item.confidence),
    quantity: item.quantity ?? item.qty ?? 0,
    rawQuantity: Number(item.quantity ?? item.qty ?? 0),
    rawPrice: Number(item.estimated_price ?? item.estimatedPrice ?? item.price ?? 0),
    estimatedPrice: formatCurrency(item.estimated_price ?? item.estimatedPrice ?? item.price ?? 0),
    reasoning: item.reasoning || item.reason || '無決策說明',
    createdAt: formatTime(item.created_at || item.createdAt || item.timestamp),
  }))
}

function normalizePercent(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)))
}

function formatCurrency(value) {
  return `NT$ ${new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format(Number(value || 0))}`
}

function formatTime(value) {
  if (!value) return '未提供時間'
  return String(value).replace('T', ' ').slice(0, 16)
}

function typeClass(type) {
  return type === 'BUY' ? 'buy' : type === 'SELL' ? 'sell' : 'hold'
}

function statusClass(status) {
  return status === 'APPROVED' ? 'approved' : status === 'REJECTED' ? 'rejected' : 'pending'
}
</script>

<style scoped>
.approval-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header p,
.trade-head p,
.label,
.reason-box p,
.empty-state {
  color: var(--text-secondary);
}

.log-msg {
  color: #22c55e;
  font-size: 0.88rem;
}

.filter-tabs {
  display: flex;
  gap: 10px;
  border-bottom: none;
  margin-bottom: 0;
}

.tab-button {
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.tab-button.active {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: white;
}

.trade-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}

.trade-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.trade-head,
.status-row,
.action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.trade-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.trade-metrics div,
.reason-box {
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.reason-box p {
  margin-top: 8px;
  line-height: 1.5;
}

.badge {
  padding: 5px 10px;
  border-radius: 999px;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.buy,
.approved {
  background: var(--color-up);
}

.sell,
.rejected {
  background: var(--color-down);
}

.hold,
.pending {
  background: var(--color-warning);
}

.approve-btn {
  background: var(--up-soft);
  color: var(--color-up);
}

.approve-btn:hover:not(:disabled) {
  background: var(--color-up);
  color: white;
}

.reject-btn {
  background: var(--down-soft);
  color: var(--color-down);
}

.reject-btn:hover:not(:disabled) {
  background: var(--color-down);
  color: white;
}

@media (max-width: 640px) {
  .trade-head,
  .status-row,
  .action-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .trade-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
