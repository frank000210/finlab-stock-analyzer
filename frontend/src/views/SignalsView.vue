<template>
  <div class="signals-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">📡 觀測重點</span>
      把觀察清單變成<strong>每日行動清單</strong>：一眼看誰多頭排列、誰爆量、誰逼近停損或波段高低。
    </div>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>觀察清單訊號（Signals）</h2>
          <p class="muted">趨勢排列、RSI、量能、距波段高低與 ATR 停損距離，一次掃完。</p>
        </div>
        <div class="ctrl">
          <input v-model="symbolsInput" class="inp" placeholder="2330,2454,2317" />
          <button class="btn btn-primary" :disabled="loading" @click="load">
            <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>掃描
          </button>
        </div>
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="asOf" class="muted small">資料日 {{ asOf }}</p>

      <div v-if="items.length" class="cards">
        <div v-for="it in items" :key="it.symbol" class="scard" :class="{ err: !it.ok }">
          <div class="row1">
            <span v-if="it.ok && it.setup_total != null" class="score" :class="scoreClass(it.setup_total)" :title="it.setup_verdict">{{ it.setup_total }}</span>
            <span class="sym">{{ it.symbol }}<small class="nm" v-if="it.name"> {{ it.name }}</small></span>
            <template v-if="it.ok">
              <span class="price">{{ fmt(it.price) }}</span>
              <span class="chg" :class="it.chg_pct >= 0 ? 'up' : 'down'">{{ it.chg_pct >= 0 ? '+' : '' }}{{ it.chg_pct }}%</span>
            </template>
            <span v-else class="muted">{{ it.error }}</span>
          </div>
          <div v-if="it.ok" class="tags">
            <span v-for="(tag, i) in it.tags" :key="i" class="tag" :class="'tone-' + tag.tone">{{ tag.t }}</span>
          </div>
          <div v-if="it.ok" class="metrics">
            <span>RSI {{ it.rsi }}</span>
            <span v-if="it.vol_ratio != null">量 {{ it.vol_ratio }}×</span>
            <span>區間位置 {{ it.range_pos_pct }}%</span>
            <span v-if="it.stop_dist_pct != null">停損距 {{ it.stop_dist_pct }}%</span>
          </div>
        </div>
      </div>
      <p v-else-if="!loading" class="muted empty">觀察清單是空的或尚未掃描。先在關聯圖／決策面板加入標的，或在上方輸入代碼後按「掃描」。</p>
      <p class="disclaimer">※ 訊號為技術面客觀計算，非投資建議；請搭配自身判斷。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const symbolsInput = ref('')
const items = ref([])
const asOf = ref('')
const loading = ref(false)
const errorMessage = ref('')

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function scoreClass(total) { return total >= 70 ? 'good' : total >= 45 ? 'mid' : 'bad' }

function readWatchlist() {
  try {
    const raw = JSON.parse(localStorage.getItem('finlab_watchlist') || '[]')
    if (Array.isArray(raw)) return raw.map(s => String(typeof s === 'string' ? s : (s?.symbol || '')).trim().toUpperCase()).filter(Boolean)
  } catch { /* ignore */ }
  return []
}

async function load() {
  const syms = String(symbolsInput.value || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
  if (!syms.length) { errorMessage.value = '請輸入至少一個代碼，或先在其他頁面建立觀察清單。'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/watchlist-signals?symbols=${[...new Set(syms)].join(',')}`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || payload?.success === false) throw new Error(payload?.detail || '掃描失敗')
    items.value = payload.data?.items || []
    asOf.value = payload.data?.as_of || ''
  } catch (e) {
    items.value = []
    errorMessage.value = e?.message || '掃描失敗'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const wl = readWatchlist()
  symbolsInput.value = wl.length ? wl.join(',') : '2330,2454,2317'
  load()
})
</script>

<style scoped>
.signals-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2 { margin: 0 0 4px; }
.muted { color: var(--text-muted); } .small { font-size: 0.8rem; }
.ctrl { display: flex; gap: 8px; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; min-width: 220px; }
.error-text { color: #ef4444; margin-top: 8px; }
.btn-spinner { width: 14px; height: 14px; border-width: 2px; vertical-align: -2px; margin-right: 6px; }

.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 14px; }
.scard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.scard.err { opacity: 0.6; }
.row1 { display: flex; align-items: baseline; gap: 10px; }
.score { font-size: 0.95rem; font-weight: 800; min-width: 34px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; padding: 0 6px; }
.score.good { background: rgba(34,197,94,0.18); color: #22c55e; }
.score.mid { background: rgba(245,158,11,0.18); color: #f59e0b; }
.score.bad { background: rgba(239,68,68,0.18); color: #ef4444; }
.sym { font-size: 1.15rem; font-weight: 700; }
.sym .nm { font-size: 0.78rem; font-weight: 400; color: var(--text-muted); }
.price { font-size: 1.05rem; }
.chg { font-weight: 700; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 0.76rem; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border-color); }
.tone-up { color: #ef4444; border-color: rgba(239,68,68,0.5); }
.tone-down { color: #22c55e; border-color: rgba(34,197,94,0.5); }
.tone-warn { color: #f59e0b; border-color: rgba(245,158,11,0.5); }
.tone-flat { color: var(--text-muted); }
.metrics { display: flex; flex-wrap: wrap; gap: 12px; font-size: 0.78rem; color: var(--text-muted); }
.up { color: #ef4444; } .down { color: #22c55e; }
.empty { padding: 16px 0; }
.disclaimer { font-size: 0.74rem; color: var(--text-muted); margin-top: 12px; }
</style>
