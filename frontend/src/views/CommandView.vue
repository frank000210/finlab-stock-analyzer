<template>
  <div class="command-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">⚡ 觀測重點</span>
      一頁跑完你的一天：觀察清單<strong>依進場評分排名</strong>，直接給出在你風險%下該買<strong>幾張</strong>。看得到，就下得了手。
    </div>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>作戰儀表板（Command）</h2>
          <p class="muted">評分 + 訊號 + 依 ATR 停損回推的建議張數，一次到位。</p>
        </div>
        <div class="ctrl">
          <label class="mini">資金<input v-model.number="account" type="number" min="0" step="10000" class="inp w130" @change="saveCfg" /></label>
          <label class="mini">風險%<input v-model.number="riskPct" type="number" min="0.1" max="100" step="0.1" class="inp w70" @change="saveCfg" /></label>
          <span v-if="kellyRisk && kellyRisk.pct" class="kelly-hint">實戰半凱利建議 {{ kellyRisk.pct.toFixed(1) }}%（{{ kellyRisk.count }} 筆）<button type="button" class="link-btn" @click="applyKellyRisk">套用</button></span>
          <input v-model="symbolsInput" class="inp w200" placeholder="2330,2454,2317" />
          <button class="btn btn-primary" :disabled="loading" @click="scan">
            <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>掃描
          </button>
        </div>
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="logMsg" class="log-msg">{{ logMsg }}</p>

      <div v-if="regime" class="regime-strip" :class="'regime-' + regime.regime">
        <strong>市場體制：{{ regime.label }}</strong>
        <span class="rg-detail">0050 {{ regime.close }} vs 年線 {{ regime.ma200 }}（{{ regime.above_ma200 ? '站上' : '跌破' }}、年線{{ regime.ma200_rising ? '上揚' : '下彎' }}）· 20日動能 {{ regime.mom20_pct >= 0 ? '+' : '' }}{{ regime.mom20_pct }}%</span>
        <label class="rg-apply">
          <input type="checkbox" v-model="applyRegime" @change="saveCfg" />
          套用風險係數 ×{{ regime.risk_mult }}
          <em v-if="applyRegime">→ 有效單筆風險 {{ effRiskPct.toFixed(2) }}%</em>
        </label>
      </div>

      <div v-if="corr && corr.high_pairs && corr.high_pairs.length" class="corr-warn">
        <div v-for="hp in corr.high_pairs" :key="hp.a + '-' + hp.b">
          ⚠ {{ hp.a }} × {{ hp.b }} 相關 {{ hp.corr.toFixed(2) }} — 這兩檔實質同一注，別各下滿倉、重複曝險
        </div>
      </div>

      <div v-if="rows.length" class="summary">
        <span>掃描 {{ okRows.length }} 檔 · 資料日 {{ asOf }}</span>
        <span :class="totalHeat > 6 ? 'warn' : 'ok'">若全數各下 1 注，總風險熱度 {{ totalHeat.toFixed(1) }}%（建議 ≤ 6%）</span>
      </div>

      <div v-if="rows.length" class="table-wrap">
        <table class="cmd-table">
          <thead>
            <tr><th>評分</th><th>代碼</th><th>現價</th><th>漲跌</th><th>訊號</th><th>停損距</th><th>建議張數</th><th>1R 風險</th><th>動作</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.symbol" :class="{ dim: !r.ok }">
              <td><span v-if="r.ok && r.setup_total != null" class="score" :class="scoreClass(r.setup_total)" :title="r.setup_verdict">{{ r.setup_total }}</span><span v-else>—</span></td>
              <td class="sym">{{ r.symbol }}</td>
              <td>{{ r.ok ? fmt(r.price) : '—' }}</td>
              <td v-if="r.ok" :class="r.chg_pct >= 0 ? 'up' : 'down'">{{ r.chg_pct >= 0 ? '+' : '' }}{{ r.chg_pct }}%</td>
              <td v-else class="muted">{{ r.error }}</td>
              <td class="tags">
                <span v-for="(t, i) in (r.tags || [])" :key="i" class="tag" :class="'tone-' + t.tone">{{ t.t }}</span>
              </td>
              <td>{{ r.ok && r.stop_dist_pct != null ? r.stop_dist_pct + '%' : '—' }}</td>
              <td><strong>{{ r.ok ? lots(r) + ' 張' : '—' }}</strong><small v-if="r.ok && lots(r) === 0" class="muted"> (零股 {{ oddShares(r) }})</small></td>
              <td>{{ r.ok ? fmtInt(riskAmount(r)) : '—' }}</td>
              <td><button v-if="r.ok && lots(r) > 0" class="btn xs" @click="logTrade(r)">記錄</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="!loading" class="muted empty">觀察清單為空或尚未掃描。先在關聯圖／決策面板加入標的，或在上方輸入代碼後按「掃描」。</p>
      <p class="disclaimer">※ 建議張數＝(資金×風險%) ÷ (現價×停損距%)，取整張。本工具僅為風險試算，非投資建議。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const account = ref(1000000)
const riskPct = ref(1)
const symbolsInput = ref('')
const rows = ref([])
const asOf = ref('')
const loading = ref(false)
const errorMessage = ref('')
const logMsg = ref('')
const corr = ref(null)

// B5 市場體制：進攻/中性/防守 × 風險係數（套用時縮放有效單筆風險）
const regime = ref(null)
const applyRegime = ref(true)
const effRiskPct = computed(() => {
  const base = Number(riskPct.value) || 0
  return applyRegime.value && regime.value ? base * regime.value.risk_mult : base
})

async function loadRegime() {
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/market-regime`)
    const payload = await resp.json().catch(() => ({}))
    if (resp.ok && payload?.data) regime.value = payload.data
  } catch { /* best-effort */ }
}

const okRows = computed(() => rows.value.filter(r => r.ok))

const journalTrades = ref([])
const kellyRisk = computed(() => {
  const closed = journalTrades.value.filter(t => t.status === 'closed')
  if (closed.length < 3) return null
  const pps = (t) => { const d = Number(t.exit) - Number(t.entry); return t.side === 'short' ? -d : d }
  const pnl = (t) => (Number(t.lots) || 0) * 1000 * pps(t)
  const pnls = closed.map(pnl)
  const gw = pnls.filter(p => p > 0).reduce((a, b) => a + b, 0)
  const gl = Math.abs(pnls.filter(p => p < 0).reduce((a, b) => a + b, 0))
  const w = pnls.filter(p => p > 0).length / closed.length
  const pf = gl > 0 ? gw / gl : 99.99
  if (w <= 0 || pf <= 1) return { pct: null, count: closed.length }
  const kelly = w * (pf - 1) / pf
  return { pct: Math.min(kelly * 0.5 * 100, 10), count: closed.length }
})
function applyKellyRisk() {
  if (kellyRisk.value?.pct) { riskPct.value = Math.round(kellyRisk.value.pct * 10) / 10; saveCfg() }
}

function riskPerShare(r) { return (Number(r.price) || 0) * (Number(r.stop_dist_pct) || 0) / 100 }
function budget() { return (Number(account.value) || 0) * effRiskPct.value / 100 }
function rawShares(r) { const rps = riskPerShare(r); return rps > 0 ? budget() / rps : 0 }
function lots(r) { return Math.floor(rawShares(r) / 1000) }
function oddShares(r) { return Math.floor(rawShares(r)) }
function riskAmount(r) { return lots(r) * 1000 * riskPerShare(r) }

const totalHeat = computed(() => {
  if (!account.value) return 0
  return okRows.value.reduce((a, r) => a + riskAmount(r), 0) / account.value * 100
})

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }
function scoreClass(total) { return total >= 70 ? 'good' : total >= 45 ? 'mid' : 'bad' }

function saveCfg() {
  localStorage.setItem('portfolio_heat_account', String(account.value))
  localStorage.setItem('finlab_risk_pct', String(riskPct.value))
  localStorage.setItem('finlab_apply_regime', applyRegime.value ? '1' : '0')
}

// One click: log the planned trade (entry=price, ATR-based stop, suggested
// lots) as an open trade in the journal.
function logTrade(r) {
  const l = lots(r)
  if (!(l >= 1)) return
  const entry = Number(r.price)
  const stop = Math.round(entry * (1 - (Number(r.stop_dist_pct) || 0) / 100) * 100) / 100
  let journal = []
  try { const raw = JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'); if (Array.isArray(raw)) journal = raw } catch { /* ignore */ }
  journal.unshift({
    id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    symbol: r.symbol, name: r.symbol, side: 'long', entry, stop, target: null,
    lots: l, tag: r.trend || '', openDate: new Date().toISOString().slice(0, 10),
    status: 'open', exit: null, exitDate: null,
  })
  localStorage.setItem('finlab_trade_journal', JSON.stringify(journal))
  logMsg.value = `已記錄 ${r.symbol} ${l} 張到交易日誌（進場 ${entry}、停損 ${stop}），到「交易日誌」平倉即納入統計。`
}

function readWatchlist() {
  try {
    const raw = JSON.parse(localStorage.getItem('finlab_watchlist') || '[]')
    if (Array.isArray(raw)) return raw.map(s => String(typeof s === 'string' ? s : (s?.symbol || '')).trim().toUpperCase()).filter(Boolean)
  } catch { /* ignore */ }
  return []
}

async function scan() {
  const syms = [...new Set(String(symbolsInput.value || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean))]
  if (!syms.length) { errorMessage.value = '請輸入至少一個代碼。'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/watchlist-signals?symbols=${syms.join(',')}`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || payload?.success === false) throw new Error(payload?.detail || '掃描失敗')
    rows.value = payload.data?.items || []
    asOf.value = payload.data?.as_of || ''
    analyzeCorr()
  } catch (e) {
    rows.value = []
    errorMessage.value = e?.message || '掃描失敗'
  } finally {
    loading.value = false
  }
}

async function analyzeCorr() {
  corr.value = null
  const syms = [...new Set(okRows.value.map(r => r.symbol))]
  if (syms.length < 2) return
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/correlation?symbols=${syms.join(',')}`)
    const payload = await resp.json().catch(() => ({}))
    if (resp.ok && payload?.data) corr.value = payload.data
  } catch { /* best-effort */ }
}

onMounted(() => {
  try { const raw = JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'); if (Array.isArray(raw)) journalTrades.value = raw } catch { /* ignore */ }
  const a = Number(localStorage.getItem('portfolio_heat_account')); if (a > 0) account.value = a
  const rp = Number(localStorage.getItem('finlab_risk_pct')); if (rp > 0) riskPct.value = rp
  applyRegime.value = localStorage.getItem('finlab_apply_regime') !== '0'
  const wl = readWatchlist()
  symbolsInput.value = wl.length ? wl.join(',') : '2330,2454,2317'
  loadRegime()
  scan()
})
</script>

<style scoped>
.command-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2 { margin: 0 0 4px; }
.muted { color: var(--text-muted); }
.ctrl { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.mini { display: inline-flex; align-items: center; gap: 4px; font-size: 0.8rem; color: var(--text-muted); }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.w130 { width: 130px; } .w70 { width: 70px; } .w200 { width: 200px; }
.error-text { color: #ef4444; margin-top: 8px; }
.btn-spinner { width: 14px; height: 14px; border-width: 2px; vertical-align: -2px; margin-right: 6px; }

.regime-strip {
  margin-top: 12px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.84rem;
}
.regime-offense { border-color: rgba(239,68,68,0.45); background: rgba(239,68,68,0.08); }
.regime-offense strong { color: #ef4444; }
.regime-neutral { border-color: rgba(245,158,11,0.45); background: rgba(245,158,11,0.08); }
.regime-neutral strong { color: #f59e0b; }
.regime-defense { border-color: rgba(59,130,246,0.45); background: rgba(59,130,246,0.08); }
.regime-defense strong { color: #3b82f6; }
.rg-detail { color: var(--text-muted); }
.rg-apply { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; margin-left: auto; }
.rg-apply em { font-style: normal; color: var(--text-primary); font-weight: 600; }

.summary { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 14px 0 6px; font-size: 0.84rem; color: var(--text-muted); }
.summary .warn { color: #f59e0b; } .summary .ok { color: #22c55e; }

.table-wrap { overflow-x: auto; }
.cmd-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.cmd-table th, .cmd-table td { text-align: right; padding: 9px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.cmd-table th:nth-child(2), .cmd-table td:nth-child(2), .cmd-table th:nth-child(5), .cmd-table td:nth-child(5) { text-align: left; }
.cmd-table th { color: var(--text-muted); font-weight: 500; font-size: 0.74rem; }
.tr.dim, tr.dim { opacity: 0.55; }
.sym { font-weight: 700; }
.score { font-weight: 800; min-width: 32px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; padding: 2px 6px; }
.score.good { background: rgba(34,197,94,0.18); color: #22c55e; }
.score.mid { background: rgba(245,158,11,0.18); color: #f59e0b; }
.score.bad { background: rgba(239,68,68,0.18); color: #ef4444; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font-size: 0.72rem; padding: 2px 7px; border-radius: 999px; border: 1px solid var(--border-color); }
.tone-up { color: #ef4444; } .tone-down { color: #22c55e; } .tone-warn { color: #f59e0b; } .tone-flat { color: var(--text-muted); }
.up { color: #ef4444; } .down { color: #22c55e; }
.empty { padding: 16px 0; }
.btn.xs { padding: 4px 10px; font-size: 0.78rem; }
.log-msg { margin-top: 8px; color: #22c55e; font-size: 0.84rem; }
.corr-warn { margin: 12px 0 0; display: flex; flex-direction: column; gap: 6px; }
.corr-warn div { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.4); color: #f87171; border-radius: 10px; padding: 8px 12px; font-size: 0.84rem; }
.kelly-hint { font-size: 0.78rem; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px; }
.link-btn { background: none; border: none; color: var(--accent-blue); cursor: pointer; padding: 0 2px; font-size: 0.78rem; }
.disclaimer { font-size: 0.74rem; color: var(--text-muted); margin-top: 12px; }
</style>
