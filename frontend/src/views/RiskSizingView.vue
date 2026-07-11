<template>
  <div class="risk-sizing-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">🎯 觀測重點</span>
      先定停損與單筆風險，再回推部位大小。紀律先於方向——這是把勝率轉成長期獲利的關鍵。
    </div>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>部位風控試算（Position Sizing）</h2>
          <p class="muted">以 ATR 波動度定停損、以單筆風險回推張數，並檢視風報比與期望值。</p>
        </div>
        <div class="symbol-box">
          <input v-model="symbolInput" class="inp" placeholder="股票代碼，例如 2330" @keyup.enter="loadMarket" />
          <button class="btn btn-primary" :disabled="loading" @click="loadMarket">
            <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>查詢
          </button>
        </div>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <!-- 市場資料 -->
      <div class="market-cards" v-if="market">
        <div class="mcard">
          <span class="mlabel">{{ market.symbol }} {{ market.name }} 現價</span>
          <strong class="mval">{{ fmt(market.price) }}</strong>
          <DataLineage :as-of="market.as_of" :source="market.source" />
          <a class="tv-link" :href="tvChartUrl(market.symbol)" target="_blank" rel="noopener nofollow">在 TradingView 開啟 ↗</a>
        </div>
        <div class="mcard">
          <span class="mlabel">ATR({{ market.atr_period }}) 每日波動</span>
          <strong class="mval">{{ fmt(market.atr) }}</strong>
          <span class="mhint">≈ {{ market.atr_pct }}%／日</span>
        </div>
        <div class="mcard">
          <span class="mlabel">ATR 停損建議（點擊套用）</span>
          <div class="stop-chips">
            <button
              v-for="s in market.suggested_stops"
              :key="s.label"
              type="button"
              class="chip"
              :class="{ active: Number(stop) === s.stop_price }"
              @click="stop = s.stop_price"
            >{{ s.label }} {{ fmt(s.stop_price) }}<small>(-{{ s.distance_pct }}%)</small></button>
          </div>
        </div>
      </div>

      <div v-if="market && market.setup" class="setup-panel">
        <div class="setup-head">
          <div class="setup-score" :class="setupClass(market.setup.total)">
            <strong>{{ market.setup.total }}</strong><span>/100</span>
          </div>
          <div>
            <div class="setup-verdict" :class="setupClass(market.setup.total)">進場評分：{{ market.setup.verdict }}</div>
            <div class="muted small">趨勢/風報比/量能/RSI 綜合 · 目標波段高 {{ market.setup.target }} · R:R≈{{ market.setup.rr }}</div>
          </div>
        </div>
        <div class="setup-components">
          <div v-for="c in market.setup.components" :key="c.name" class="comp">
            <div class="comp-top"><span>{{ c.name }}</span><strong>{{ c.score }}/{{ c.max }}</strong></div>
            <div class="comp-bar"><div class="comp-fill" :style="{ width: (c.score / c.max * 100) + '%' }"></div></div>
            <span class="comp-note muted">{{ c.note }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="section-block sizing-grid" v-reveal>
      <!-- 輸入 -->
      <div class="inputs">
        <h3>試算條件</h3>
        <label class="field"><span>帳戶資金 (TWD)</span>
          <input v-model.number="account" type="number" min="0" step="10000" class="inp" /></label>
        <label class="field"><span>單筆風險 (% 資金)</span>
          <input v-model.number="riskPct" type="number" min="0.1" max="100" step="0.1" class="inp" /></label>
        <label class="field"><span>進場價</span>
          <input v-model.number="entry" type="number" min="0" step="0.05" class="inp" /></label>
        <label class="field"><span>停損價</span>
          <input v-model.number="stop" type="number" min="0" step="0.05" class="inp" /></label>
        <label class="field"><span>目標價（選填）</span>
          <input v-model.number="target" type="number" min="0" step="0.05" class="inp" /></label>
        <p class="hint-inline muted">勝率／盈虧比在下方「凱利」區設定（可算期望值與建議風險%）。</p>
      </div>

      <!-- 結果 -->
      <div class="results">
        <h3>試算結果 <small class="muted">{{ directionLabel }}</small></h3>
        <div v-if="!valid" class="muted empty">請輸入有效的資金、進場價與停損價（停損不可等於進場）。</div>
        <template v-else>
          <div class="rgrid">
            <div class="rcard hl">
              <span>建議部位</span>
              <strong>{{ lots }} 張<small v-if="lots > 0"> ({{ fmtInt(lots * 1000) }} 股)</small></strong>
              <em v-if="lots === 0" class="warn">資金不足一張，零股約 {{ fmtInt(oddShares) }} 股</em>
            </div>
            <div class="rcard"><span>每股風險</span><strong>{{ fmt(perShareRisk) }}</strong></div>
            <div class="rcard"><span>風險預算 (資金×{{ riskPct }}%)</span><strong>{{ fmtInt(riskBudget) }}</strong></div>
            <div class="rcard"><span>實際風險金額</span><strong :class="{ warn: capitalAtRisk > riskBudget * 1.02 }">{{ fmtInt(capitalAtRisk) }}</strong></div>
            <div class="rcard"><span>部位金額</span><strong>{{ fmtInt(positionValue) }}</strong></div>
            <div class="rcard"><span>佔資金比重</span><strong :class="{ warn: pctOfAccount > 30 }">{{ pctOfAccount.toFixed(1) }}%</strong></div>
            <div class="rcard" v-if="target"><span>風報比 R:R</span><strong :class="rrClass">1 : {{ rr.toFixed(2) }}</strong></div>
            <div class="rcard" v-if="target"><span>達標獲利</span><strong class="up">{{ fmtInt(profitAtTarget) }}</strong></div>
            <div class="rcard" v-if="expectancyR !== null"><span>期望值 / 筆</span><strong :class="expectancyR >= 0 ? 'up' : 'warn'">{{ expectancyR.toFixed(2) }} R（{{ fmtInt(expectancyMoney) }}）</strong></div>
          </div>

          <h4>紀律檢查</h4>
          <ul class="checklist">
            <li :class="riskPct <= 2 ? 'ok' : 'bad'">{{ riskPct <= 2 ? '✓' : '✗' }} 單筆風險 {{ riskPct }}%（建議 ≤ 2%）</li>
            <li v-if="target" :class="rr >= 2 ? 'ok' : 'bad'">{{ rr >= 2 ? '✓' : '✗' }} 風報比 1:{{ rr.toFixed(2) }}（建議 ≥ 1:2）</li>
            <li :class="pctOfAccount <= 30 ? 'ok' : 'bad'">{{ pctOfAccount <= 30 ? '✓' : '✗' }} 單一部位佔資金 {{ pctOfAccount.toFixed(1) }}%（避免過度集中，建議 ≤ 30%）</li>
            <li v-if="existingPositions.length || journalOnlyCount" :class="projectedHeatPct <= 6 ? 'ok' : 'bad'">
              {{ projectedHeatPct <= 6 ? '✓' : '✗' }} 加上這筆後投組總風險熱度 {{ projectedHeatPct.toFixed(1) }}%（含投組風險頁 {{ existingPositions.length }} 筆既有部位{{ journalOnlyCount ? `、交易日誌 ${journalOnlyCount} 筆進行中部位` : '' }}，建議 ≤ 6%）
            </li>
          </ul>
          <p class="disclaimer">※ 本工具僅為風險試算，非投資建議；停損/目標請自行判斷。</p>
        </template>
      </div>
    </section>

    <section class="section-block kelly-block" v-reveal>
      <div class="head-row">
        <div>
          <h3>凱利部位建議（Kelly）</h3>
          <p class="muted">用「勝率 × 盈虧比」推估數學最優下注比例。實務取<strong>半凱利</strong>降低波動——全凱利太猛，回檔會很痛。</p>
        </div>
        <div class="bt-import">
          <select v-model="btStrategy" class="inp">
            <option value="ma_crossover">MA 交叉</option>
            <option value="macd_trend">MACD 趨勢</option>
            <option value="bollinger_breakout">布林突破</option>
            <option value="rsi_reversion">RSI 反轉</option>
          </select>
          <button class="btn" :disabled="btLoading" @click="loadFromBacktest">
            <span v-if="btLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>從回測帶入
          </button>
          <button class="btn" @click="loadFromJournal" title="用你交易日誌的實戰勝率／盈虧比">從交易日誌帶入</button>
        </div>
      </div>
      <p v-if="btError" class="error-text">{{ btError }}</p>

      <div class="kelly-grid">
        <label class="field"><span>勝率 %</span>
          <input v-model.number="winRate" type="number" min="0" max="100" step="1" class="inp" /></label>
        <label class="field"><span>盈虧比（獲利因子 PF）</span>
          <input v-model.number="profitFactor" type="number" min="0" step="0.1" class="inp" /></label>
      </div>

      <div class="rgrid" v-if="kelly > 0">
        <div class="rcard"><span>全凱利比例</span><strong>{{ (kelly * 100).toFixed(1) }}%</strong></div>
        <div class="rcard hl"><span>建議單筆風險（半凱利）</span><strong>{{ suggestedRiskPct.toFixed(1) }}%</strong></div>
        <div class="rcard apply-cell"><button class="btn btn-primary" @click="applyKelly">套用到單筆風險%</button></div>
      </div>
      <p v-else class="muted empty">此勝率／盈虧比沒有數學優勢（凱利 ≤ 0），不建議加碼——先把策略練到有正期望值。</p>
      <p class="disclaimer">※ 凱利＝勝率×(PF−1)/PF。全凱利波動大，建議取半凱利，且仍以總風控上限為準。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import DataLineage from '../components/DataLineage.vue'
import { loadJournal, journalWinStats, riskAmount as journalRiskAmount, kellyFraction, JOURNAL_KEY } from '../lib/tradeMath'
import { tvChartUrl } from '../lib/tradingview'

const route = useRoute()
const stockStore = useStockStore()

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const symbolInput = ref(stockStore.symbol || '2330')
const market = ref(null)
const loading = ref(false)
const errorMessage = ref('')

const account = ref(1000000)
const riskPct = ref(1)
const entry = ref(0)
const stop = ref(0)
const target = ref(0)
const winRate = ref(0)
const profitFactor = ref(0)
const btStrategy = ref('ma_crossover')
const btLoading = ref(false)
const btError = ref('')

const perShareRisk = computed(() => Math.abs((entry.value || 0) - (stop.value || 0)))
const valid = computed(() => account.value > 0 && entry.value > 0 && stop.value > 0 && perShareRisk.value > 0)
const riskBudget = computed(() => (account.value || 0) * (riskPct.value || 0) / 100)
const rawShares = computed(() => (perShareRisk.value > 0 ? riskBudget.value / perShareRisk.value : 0))
const lots = computed(() => Math.floor(rawShares.value / 1000))
const shares = computed(() => lots.value * 1000)
const oddShares = computed(() => Math.floor(rawShares.value))
const positionValue = computed(() => shares.value * (entry.value || 0))
const capitalAtRisk = computed(() => shares.value * perShareRisk.value)
const pctOfAccount = computed(() => (account.value > 0 ? positionValue.value / account.value * 100 : 0))
const rewardPerShare = computed(() => (target.value ? Math.abs(target.value - (entry.value || 0)) : 0))
const rr = computed(() => (perShareRisk.value > 0 && target.value ? rewardPerShare.value / perShareRisk.value : 0))
const profitAtTarget = computed(() => shares.value * rewardPerShare.value)
const expectancyR = computed(() => {
  if (!winRate.value || !target.value || rr.value <= 0) return null
  const p = Math.min(Math.max(winRate.value / 100, 0), 1)
  return p * rr.value - (1 - p) * 1
})
const expectancyMoney = computed(() => (expectancyR.value === null ? 0 : expectancyR.value * capitalAtRisk.value))

// F6 加碼後總風險熱度預覽：部位風控頁只算單一部位，看不到「這筆若真的
// 加進投組，總曝險會變成多少」——常常是單筆算得漂漂亮亮，加總後才發現
// 投組已經超過建議上限。讀取投組風險頁（Portfolio Heat）既有部位，排除
// 同代碼舊部位（假設是換單，不是疊加），算出加上這筆後的投組總風險熱度。
const existingPositions = ref([])
function loadExistingPositions() {
  try {
    const raw = JSON.parse(localStorage.getItem('portfolio_heat_positions') || '[]')
    if (Array.isArray(raw)) existingPositions.value = raw
  } catch { /* ignore */ }
}
// E1：投組風險頁只顯示手動記的部位，交易日誌裡的進行中部位（同代碼沒有
// 重複記在投組風險頁時）也是真實曝險，一併算進「加上這筆後」的預覽，避免
// 低估。用代碼去重：投組風險頁的手動記錄視為權威版本，日誌只補它沒有的。
// F3：loadJournal() 讀 localStorage 不是 reactive 的，日誌在別的分頁變動
// 時這頁不會自動跟上——用一個純計數的 ref 建立依賴，storage 事件觸發時
// 遞增它（沿用風控監控頁 B2 的同一套模式）。
const journalVersion = ref(0)
function onJournalStorage(e) {
  if (!e.key || e.key === JOURNAL_KEY) journalVersion.value++
}
const journalOnlyForHeat = computed(() => {
  journalVersion.value // eslint-disable-line no-unused-expressions
  const sym = String(symbolInput.value || '').trim().toUpperCase()
  const manualSymbols = new Set(existingPositions.value.map(p => String(p.symbol || '').trim().toUpperCase()))
  return loadJournal()
    .filter(t => t.status === 'open')
    .filter(t => String(t.symbol || '').trim().toUpperCase() !== sym)
    .filter(t => !manualSymbols.has(String(t.symbol || '').trim().toUpperCase()))
})
const journalOnlyCount = computed(() => journalOnlyForHeat.value.length)
const existingRiskAmount = computed(() => {
  const sym = String(symbolInput.value || '').trim().toUpperCase()
  const manualRisk = existingPositions.value
    .filter(p => String(p.symbol || '').trim().toUpperCase() !== sym)
    .reduce((a, p) => a + (Number(p.lots) || 0) * 1000 * Math.abs((Number(p.entry) || 0) - (Number(p.stop) || 0)), 0)
  const journalRisk = journalOnlyForHeat.value.reduce((a, t) => a + journalRiskAmount(t), 0)
  return manualRisk + journalRisk
})
const projectedHeatPct = computed(() => (account.value > 0 ? (existingRiskAmount.value + capitalAtRisk.value) / account.value * 100 : 0))
const directionLabel = computed(() => {
  if (!valid.value) return ''
  return (entry.value > stop.value) ? '做多情境' : '做空情境'
})
const rrClass = computed(() => (rr.value >= 2 ? 'up' : rr.value > 0 ? 'warn' : ''))

// Kelly: f* = W*(PF-1)/PF, derived from win rate + profit factor.
const kelly = computed(() => kellyFraction((winRate.value || 0) / 100, profitFactor.value || 0))
const suggestedRiskPct = computed(() => Math.min(kelly.value * 0.5 * 100, 10))

function applyKelly() {
  if (suggestedRiskPct.value > 0) riskPct.value = Math.round(suggestedRiskPct.value * 10) / 10
}

// Use YOUR real stats from the trade journal, not a backtest.
function loadFromJournal() {
  btError.value = ''
  const closed = loadJournal().filter(t => t.status === 'closed')
  if (!closed.length) { btError.value = '交易日誌尚無已平倉紀錄，先去記錄幾筆交易。'; return }
  const stats = journalWinStats(closed)
  winRate.value = Math.round(stats.winRate * 100)
  profitFactor.value = Math.round(stats.profitFactor * 100) / 100
  if (closed.length < 20) btError.value = `已帶入你 ${closed.length} 筆實戰統計；樣本 <20 筆，凱利僅供參考。`
}

async function loadFromBacktest() {
  const sym = String(symbolInput.value || market.value?.symbol || '').trim().toUpperCase()
  if (!sym) { btError.value = '請先查詢一檔股票'; return }
  btLoading.value = true
  btError.value = ''
  try {
    const end = new Date()
    const start = new Date(); start.setFullYear(start.getFullYear() - 5)
    const iso = (d) => d.toISOString().slice(0, 10)
    const resp = await fetch(`${API_BASE}/api/v1/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: sym, strategy_id: btStrategy.value, params: {},
        date_range: { start: iso(start), end: iso(end) }, capital: account.value || 1000000,
      }),
    })
    const payload = await resp.json().catch(() => ({}))
    const perf = payload?.data?.performance
    if (!resp.ok || !perf) throw new Error(payload?.detail || '回測失敗')
    if (!perf.total_trades) throw new Error('此策略在該區間無交易，換一個策略或標的')
    winRate.value = Math.round((perf.win_rate || 0) * 100)
    profitFactor.value = perf.profit_factor || 0
  } catch (e) {
    btError.value = e?.message || '回測失敗'
  } finally {
    btLoading.value = false
  }
}

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }
function setupClass(total) { return total >= 70 ? 'good' : total >= 45 ? 'mid' : 'bad' }

async function loadMarket() {
  const sym = String(symbolInput.value || '').trim().toUpperCase()
  if (!sym) { errorMessage.value = '請輸入股票代碼'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/sizing/${sym}`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || payload?.success === false) {
      throw new Error(payload?.detail || '查詢失敗')
    }
    market.value = payload.data
    // 預設帶入現價與「穩健」ATR 停損
    entry.value = market.value.price
    const moderate = (market.value.suggested_stops || []).find(s => s.label === '穩健')
    stop.value = moderate ? moderate.stop_price : Math.round((market.value.price - market.value.atr * 2) * 100) / 100
  } catch (e) {
    market.value = null
    errorMessage.value = e?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

// Shared risk config: keep account size + per-trade risk% in sync with the
// 投組風險 / 作戰台 pages (same localStorage keys).
watch([account, riskPct], () => {
  if (account.value > 0) localStorage.setItem('portfolio_heat_account', String(account.value))
  if (riskPct.value > 0) localStorage.setItem('finlab_risk_pct', String(riskPct.value))
})

// 側欄搜尋切換全站目前個股時，這頁的代號欄位跟著換並重新查詢
// （「頁面內容也連動顯示股票 A」）。
watch(() => stockStore.symbol, (sym) => {
  if (sym && sym !== symbolInput.value) {
    symbolInput.value = sym
    loadMarket()
  }
})

onMounted(() => {
  const a = Number(localStorage.getItem('portfolio_heat_account')); if (a > 0) account.value = a
  const rp = Number(localStorage.getItem('finlab_risk_pct')); if (rp > 0) riskPct.value = rp
  const q = route.query.symbol
  if (q) symbolInput.value = String(q).trim().toUpperCase()
  loadExistingPositions()
  loadMarket()
  window.addEventListener('storage', onJournalStorage)
})
onBeforeUnmount(() => window.removeEventListener('storage', onJournalStorage))
</script>

<style scoped>
.risk-sizing-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2 { margin: 0 0 4px; }
.symbol-box { display: flex; gap: 8px; }
.inp {
  background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary);
  border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; width: 100%;
}

.market-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }
.mcard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; }
.mlabel { font-size: 0.78rem; color: var(--text-muted); }
.mval { font-size: 1.5rem; }
.mhint { font-size: 0.74rem; color: var(--text-muted); }
.tv-link { color: var(--accent-blue); font-size: 0.74rem; text-decoration: none; }
.tv-link:hover { text-decoration: underline; }
.stop-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: var(--bg-hover); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 999px; padding: 4px 10px; font-size: 0.78rem; cursor: pointer; }
.chip small { color: var(--text-muted); margin-left: 4px; }
.chip.active { border-color: var(--accent-blue); color: var(--accent-blue); }

.sizing-grid { display: grid; grid-template-columns: 320px 1fr; gap: 20px; }
@media (max-width: 900px) { .sizing-grid { grid-template-columns: 1fr; } }
.inputs h3, .results h3 { margin-top: 0; }
.field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; font-size: 0.82rem; color: var(--text-muted); }

.rgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.rcard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.rcard span { font-size: 0.76rem; color: var(--text-muted); }
.rcard strong { font-size: 1.15rem; }
.rcard.hl { border-color: var(--accent-blue); }
.rcard.hl strong { font-size: 1.5rem; color: var(--accent-blue); }
.rcard .warn, strong.warn { color: #f59e0b; }
.warn.up { color: #f59e0b; }
.kelly-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 12px 0; max-width: 520px; }
.bt-import { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.apply-cell { align-items: center; justify-content: center; }

.setup-panel { margin-top: 16px; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px; background: var(--card-bg); }
.setup-head { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.setup-score { display: flex; align-items: baseline; gap: 2px; }
.setup-score strong { font-size: 2.2rem; line-height: 1; }
.setup-score span { color: var(--text-muted); font-size: 0.9rem; }
.setup-score.good strong, .setup-verdict.good { color: #22c55e; }
.setup-score.mid strong, .setup-verdict.mid { color: #f59e0b; }
.setup-score.bad strong, .setup-verdict.bad { color: #ef4444; }
.setup-verdict { font-size: 1.1rem; font-weight: 700; }
.small { font-size: 0.78rem; }
.setup-components { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 14px; }
.comp { display: flex; flex-direction: column; gap: 4px; }
.comp-top { display: flex; justify-content: space-between; font-size: 0.82rem; }
.comp-bar { background: var(--bg-well); border-radius: 999px; height: 8px; overflow: hidden; }
.comp-fill { height: 100%; background: var(--accent-blue); border-radius: 999px; }
.comp-note { font-size: 0.74rem; }
</style>
