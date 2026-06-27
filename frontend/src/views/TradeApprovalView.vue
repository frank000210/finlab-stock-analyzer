<template>
  <div class="approval-page">
    <div class="page-header">
      <div>
        <h1>交易核准中心</h1>
        <p>人工審核 AI 交易任務，控制最終下單決策</p>
      </div>
    </div>

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
import { onMounted, ref, watch } from 'vue'

const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''
const statuses = ['ALL', 'PENDING', 'APPROVED', 'REJECTED']
const selectedStatus = ref('ALL')
const trades = ref([])
const submittingId = ref('')

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
  try {
    await apiRequest('/api/v1/trade/approve', {
      method: 'POST',
      body: JSON.stringify({ task_id: trade.taskId, action }),
    })
    await loadTrades()
  } catch (error) {
    window.alert(error.message || '提交失敗')
  }
  submittingId.value = ''
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
  return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 }).format(Number(value || 0))
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
  background: #10b981;
}

.sell,
.rejected {
  background: #ef4444;
}

.hold,
.pending {
  background: #f59e0b;
}

.approve-btn {
  background: #10b981;
  color: white;
}

.reject-btn {
  background: #ef4444;
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
