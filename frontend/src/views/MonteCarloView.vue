<template>
  <div class="mc-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">🎲 觀測重點</span>
      同一套勝率，運氣好壞會走出天差地別的資金曲線。用蒙地卡羅壓力測試你的<strong>風險%</strong>——先確認不會在噪音裡先陣亡。
    </div>

    <section class="section-block mc-grid" v-reveal>
      <div class="inputs">
        <h2>風險模擬（Monte Carlo）</h2>
        <p class="muted">固定比例下注，模擬多條資金路徑，看報酬分布、最大回撤與破產機率。</p>
        <label class="field"><span>勝率 %</span><input v-model.number="winRate" type="number" min="0" max="100" step="1" class="inp" /></label>
        <label class="field"><span>盈虧比 R（賺賠比）</span><input v-model.number="payoff" type="number" min="0.1" step="0.1" class="inp" /></label>
        <label class="field"><span>單筆風險 %</span><input v-model.number="riskPct" type="number" min="0.1" max="100" step="0.1" class="inp" /></label>
        <label class="field"><span>交易筆數</span><input v-model.number="trades" type="number" min="10" max="1000" step="10" class="inp" /></label>
        <label class="field"><span>破產門檻（資金回撤 %）</span><input v-model.number="ruinPct" type="number" min="10" max="90" step="5" class="inp" /></label>
        <label class="field"><span>模擬次數</span><input v-model.number="sims" type="number" min="200" max="5000" step="200" class="inp" /></label>
        <button class="btn btn-primary" @click="run">執行模擬</button>
        <p class="edge muted" v-if="edgeText">{{ edgeText }}</p>
      </div>

      <div class="results">
        <h3>模擬結果 <small class="muted" v-if="result">（{{ result.sims }} 條路徑 × {{ result.trades }} 筆）</small></h3>
        <div v-if="!result" class="muted empty">設定參數後點「執行模擬」。</div>
        <template v-else>
          <div class="rgrid">
            <div class="rcard" :class="ruinClass"><span>破產機率（回撤≥{{ ruinPct }}%）</span><strong :class="ruinClass">{{ (result.ruinProb * 100).toFixed(1) }}%</strong></div>
            <div class="rcard"><span>獲利機率</span><strong :class="result.profitableProb >= 0.5 ? 'up' : 'down'">{{ (result.profitableProb * 100).toFixed(1) }}%</strong></div>
            <div class="rcard"><span>中位數報酬</span><strong :class="result.median >= 0 ? 'up' : 'down'">{{ pct(result.median) }}</strong></div>
            <div class="rcard"><span>差路徑 (p5) / 好路徑 (p95)</span><strong><span :class="result.p5 >= 0 ? 'up' : 'down'">{{ pct(result.p5) }}</span> / <span class="up">{{ pct(result.p95) }}</span></strong></div>
            <div class="rcard"><span>平均最大回撤</span><strong class="warn">{{ (result.avgMaxDD * 100).toFixed(1) }}%</strong></div>
            <div class="rcard"><span>最差單條回撤</span><strong class="warn">{{ (result.worstDD * 100).toFixed(1) }}%</strong></div>
          </div>

          <div class="hist">
            <span class="slabel">最終報酬分布</span>
            <svg class="hist-svg" :viewBox="`0 0 ${histW} ${histH}`" preserveAspectRatio="none">
              <line :x1="zeroX" y1="0" :x2="zeroX" :y2="histH" class="hist-zero" />
              <rect v-for="(b, i) in result.hist" :key="i"
                :x="b.x" :y="histH - b.h" :width="b.w" :height="b.h"
                :class="b.mid >= 0 ? 'bar-up' : 'bar-down'" />
            </svg>
            <div class="hist-axis"><span>{{ pct(result.min) }}</span><span>0%</span><span>{{ pct(result.max) }}</span></div>
          </div>

          <ul class="checklist">
            <li :class="result.ruinProb <= 0.05 ? 'ok' : 'bad'">{{ result.ruinProb <= 0.05 ? '✓' : '✗' }} 破產機率 {{ (result.ruinProb * 100).toFixed(1) }}%（建議 ≤ 5%；太高就把風險% 調低）</li>
          </ul>
          <p class="disclaimer">※ 固定比例下注模擬，隨機序列每次略有不同。本工具僅為風險試算，非投資建議。</p>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const winRate = ref(50)
const payoff = ref(2)
const riskPct = ref(2)
const trades = ref(100)
const ruinPct = ref(50)
const sims = ref(1000)
const result = ref(null)

const edgeText = computed(() => {
  const w = winRate.value / 100, r = payoff.value
  const ev = w * r - (1 - w) // expectancy in R
  if (!(r > 0) || w <= 0) return ''
  return ev > 0
    ? `每筆期望值 +${ev.toFixed(2)} R（正期望，長期有利）`
    : `每筆期望值 ${ev.toFixed(2)} R（負期望，再多筆數也難翻身）`
})

const histW = 600, histH = 160
const zeroX = computed(() => {
  if (!result.value) return 0
  const { min, max } = result.value
  const range = (max - min) || 1
  return ((0 - min) / range) * histW
})
const ruinClass = computed(() => {
  if (!result.value) return ''
  return result.value.ruinProb > 0.05 ? 'danger' : 'ok-card'
})

function pct(v) { return (v == null || isNaN(v)) ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' }

function quantile(sorted, q) {
  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base]
}

function run() {
  const w = Math.min(Math.max(winRate.value / 100, 0), 1)
  const r = Math.max(payoff.value || 0, 0)
  const risk = Math.max(riskPct.value || 0, 0) / 100
  const N = Math.max(10, Math.floor(trades.value || 0))
  const S = Math.max(200, Math.floor(sims.value || 0))
  const ruinLevel = 1 - Math.min(Math.max(ruinPct.value || 0, 1), 99) / 100

  const finals = []
  const maxDDs = []
  let ruined = 0
  let worstDD = 0
  for (let s = 0; s < S; s += 1) {
    let eq = 1, peak = 1, mdd = 0, hitRuin = false
    for (let t = 0; t < N; t += 1) {
      eq *= (Math.random() < w) ? (1 + risk * r) : (1 - risk)
      if (eq > peak) peak = eq
      const dd = (peak - eq) / peak
      if (dd > mdd) mdd = dd
      if (eq <= ruinLevel) hitRuin = true
    }
    finals.push(eq - 1)
    maxDDs.push(mdd)
    if (hitRuin) ruined += 1
    if (mdd > worstDD) worstDD = mdd
  }
  const sorted = [...finals].sort((a, b) => a - b)
  const min = sorted[0], max = sorted[sorted.length - 1]

  // histogram (30 bins)
  const bins = 30
  const range = (max - min) || 1
  const counts = new Array(bins).fill(0)
  for (const v of finals) {
    let idx = Math.floor(((v - min) / range) * bins)
    if (idx >= bins) idx = bins - 1
    if (idx < 0) idx = 0
    counts[idx] += 1
  }
  const maxCount = Math.max(...counts, 1)
  const bw = histW / bins
  const hist = counts.map((c, i) => ({
    x: i * bw, w: Math.max(bw - 1, 1), h: (c / maxCount) * histH,
    mid: min + (i + 0.5) * (range / bins),
  }))

  result.value = {
    sims: S, trades: N,
    ruinProb: ruined / S,
    profitableProb: finals.filter(v => v > 0).length / S,
    median: quantile(sorted, 0.5),
    p5: quantile(sorted, 0.05),
    p95: quantile(sorted, 0.95),
    avgMaxDD: maxDDs.reduce((a, b) => a + b, 0) / maxDDs.length,
    worstDD, min, max, hist,
  }
}
</script>

<style scoped>
.mc-view { display: flex; flex-direction: column; gap: 16px; }
.mc-grid { display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
@media (max-width: 900px) { .mc-grid { grid-template-columns: 1fr; } }
.inputs h2 { margin: 0 0 4px; } .results h3 { margin-top: 0; }
.muted { color: var(--text-muted); }
.field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; font-size: 0.82rem; color: var(--text-muted); }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.edge { margin-top: 10px; font-size: 0.82rem; }

.rgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.rcard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.rcard span { font-size: 0.76rem; color: var(--text-muted); }
.rcard strong { font-size: 1.2rem; }
.rcard.danger { border-color: #ef4444; } .rcard.danger strong { color: #ef4444; }
.rcard.ok-card { border-color: #22c55e; }
.up { color: #ef4444; } .down { color: #22c55e; } .warn, strong.warn { color: #f59e0b; }
.empty { padding: 20px 0; }

.hist { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.slabel { font-size: 0.76rem; color: var(--text-muted); }
.hist-svg { width: 100%; height: 160px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.bar-up { fill: rgba(239, 68, 68, 0.75); } .bar-down { fill: rgba(34, 197, 94, 0.75); }
.hist-zero { stroke: var(--text-muted); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 3 3; }
.hist-axis { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); }
.checklist { list-style: none; padding: 0; margin: 12px 0 0; }
.checklist li { font-size: 0.86rem; } .checklist li.ok { color: #22c55e; } .checklist li.bad { color: #f59e0b; }
.disclaimer { font-size: 0.74rem; color: var(--text-muted); margin-top: 12px; }
</style>
