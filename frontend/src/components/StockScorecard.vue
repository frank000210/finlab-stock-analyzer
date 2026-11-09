<template>
  <section class="scorecard" data-testid="scorecard" aria-label="個股評分卡">
    <div class="sc-head">
      <div class="sc-title">
        <h2>個股評分卡 <InfoTooltip v-bind="metricGlossary.stockScorecard" /></h2>
        <span v-if="card && card.applicable" class="muted small" data-testid="scorecard-meta">{{ metaLine }}</span>
      </div>
      <div v-if="card && card.applicable" class="sc-summary">
        <span class="sc-total" data-testid="scorecard-total" :title="`通過 ${card.total.passed} 項、可判定 ${card.total.decidable} 項（滿分 30）`">
          <b>{{ card.total.passed }}</b><i>/ {{ card.total.decidable }}</i>
        </span>
        <span class="sc-label" :class="`tone-${card.label.tone}`" data-testid="scorecard-label" :title="card.label.note">{{ card.label.text }}</span>
      </div>
    </div>

    <p v-if="loading && !card" class="sc-state muted" data-testid="scorecard-loading">評分卡計算中…（第一次查這檔需要幾秒）</p>
    <div v-else-if="error && !card" class="sc-state sc-error" data-testid="scorecard-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-secondary xs" data-testid="scorecard-retry" @click="$emit('retry')">重試</button>
    </div>
    <p v-else-if="card && !card.applicable" class="sc-state muted" data-testid="scorecard-na">
      {{ card.reason }} <RouterLink v-if="/ETF/.test(card.reason || '')" to="/etf-compare">前往 ETF 比較</RouterLink>
    </p>

    <template v-else-if="card">
      <div class="sc-grid">
        <div v-for="d in card.dimensions" :key="d.key" class="sc-dim" :data-testid="`sc-dim-${d.key}`">
          <header class="sc-dim-head">
            <h3>{{ d.label }}</h3>
            <span class="sc-dim-score" :data-testid="`sc-dim-score-${d.key}`" :class="{ thin: d.score10 == null }">
              <template v-if="d.score10 != null"><b>{{ d.passed }}</b>/{{ d.decidable }}</template>
              <template v-else>資料不足</template>
            </span>
          </header>
          <p class="sc-dim-sub muted small">{{ dimSub(d) }}</p>
          <ul class="sc-items">
            <li v-for="it in d.items" :key="it.id" class="sc-item" :class="`is-${it.status}`"
                :data-testid="`sc-item-${it.id}`" :data-status="it.status">
              <span class="sc-ico" aria-hidden="true">{{ ICON[it.status] }}</span>
              <div class="sc-body">
                <span class="sc-name"><span class="sr-only">{{ STATUS_TEXT[it.status] }}：</span>{{ it.label }}</span>
                <span v-if="it.value && it.value !== '—'" class="sc-value">{{ it.value }}</span>
                <span v-if="it.threshold" class="sc-th">門檻：{{ it.threshold }}</span>
                <span v-if="it.note" class="sc-note">{{ it.note }}</span>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <ul v-if="card.flags && card.flags.length" class="sc-flags" aria-label="提醒旗標（不計分）">
        <li v-for="f in card.flags" :key="f.id" class="sc-flag" :class="`tone-${f.tone}`" data-testid="sc-flag" :data-flag="f.id">{{ f.text }}</li>
      </ul>
      <p class="sc-foot muted small">
        {{ card.label.note }}　✓＝符合門檻、✗＝不符合、—＝資料不足或不適用（不計入分母，不是 0 分）。旗標只提醒、不計分。
      </p>
    </template>
  </section>
</template>

<script setup>
// 個股三面向評分卡（基本面／技術面／籌碼面各 10 項檢核）的呈現元件。
// 資料由 AnalysisView 向 /api/v1/analysis/{symbol}/scorecard 取得後傳進來——因為「AI 決策評分」
// 也要用同一份結果的通過率，兩處必須共用一份資料。這裡只負責顯示。
import { computed } from 'vue'
import InfoTooltip from './InfoTooltip.vue'
import { metricGlossary } from '../lib/metricGlossary'

const props = defineProps({
  card: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
defineEmits(['retry'])

const ICON = { pass: '✓', fail: '✗', na: '—' }
const STATUS_TEXT = { pass: '符合', fail: '不符合', na: '不適用' }

const metaLine = computed(() => {
  const m = props.card?.meta || {}
  const parts = []
  if (m.financial_period) parts.push(`財報 ${m.financial_period}`)
  if (m.revenue_month) parts.push(`月營收 ${m.revenue_month}`)
  if (m.price_date) parts.push(`價格 ${m.price_date}`)
  return parts.join('・')
})

function dimSub(d) {
  const na = d.total - d.decidable
  const bits = []
  if (d.score10 != null) bits.push(`面向分數 ${d.score10.toFixed(1)} / 10`)
  if (na > 0) bits.push(`${na} 項不適用`)
  if (d.key === 'fundamental' && d.period) bits.push(`財報 ${d.period}`)
  return bits.join('・') || ' '
}
</script>

<style scoped>
.scorecard { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.sc-head { display: flex; align-items: center; justify-content: space-between; gap: 12px 20px; flex-wrap: wrap; }
.sc-title { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sc-title h2 { margin: 0; font-size: 1.05rem; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.sc-summary { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sc-total { display: inline-flex; align-items: baseline; gap: 4px; font-variant-numeric: tabular-nums; }
.sc-total b { font-size: 1.9rem; line-height: 1; color: var(--text-primary, #f1f5f9); }
.sc-total i { font-style: normal; color: var(--text-muted); font-size: 0.95rem; }
.sc-label { padding: 4px 12px; border-radius: 999px; font-weight: 700; font-size: 0.9rem; border: 1px solid var(--border-color); }
.sc-label.tone-up { color: var(--accent-blue); border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.12); }
.sc-label.tone-warn { color: var(--color-warning); border-color: rgba(245, 158, 11, 0.5); background: rgba(245, 158, 11, 0.1); }
.sc-label.tone-down { color: var(--text-secondary); border-color: var(--border-color); background: var(--bg-well, rgba(148, 163, 184, 0.08)); }
.sc-label.tone-flat { color: var(--text-secondary); }

.sc-state { margin: 0; padding: 26px 12px; text-align: center; border: 1px dashed var(--border-color); border-radius: var(--radius-sm, 8px); }
.sc-error { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; color: var(--color-warning); }

.sc-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.sc-dim { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border: 1px solid var(--border-color); border-radius: var(--radius-sm, 8px); background: var(--bg-well, rgba(148, 163, 184, 0.04)); min-width: 0; }
.sc-dim-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.sc-dim-head h3 { margin: 0; font-size: 0.98rem; }
.sc-dim-score { font-variant-numeric: tabular-nums; color: var(--text-secondary); }
.sc-dim-score b { font-size: 1.35rem; color: var(--text-primary, #f1f5f9); }
.sc-dim-score.thin { font-size: 0.82rem; color: var(--color-warning); }
.sc-dim-sub { margin: 0; min-height: 1.2em; }

.sc-items { list-style: none; margin: 4px 0 0; padding: 0; display: flex; flex-direction: column; gap: 7px; }
.sc-item { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; font-size: 0.86rem; }
.sc-ico { width: 20px; height: 20px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 700; line-height: 1; margin-top: 1px; }
.is-pass .sc-ico { background: var(--accent-blue); color: #fff; }
.is-fail .sc-ico { background: transparent; color: var(--text-muted); border: 1px solid var(--border-color); }
.is-na .sc-ico { background: transparent; color: var(--text-muted); }
.is-na .sc-name { color: var(--text-muted); }
.sc-body { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.sc-name { color: var(--text-primary, #f1f5f9); }
.is-fail .sc-name { color: var(--text-secondary); }
.sc-value { color: var(--text-secondary); font-size: 0.8rem; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.sc-th, .sc-note { color: var(--text-muted); font-size: 0.74rem; }

.sc-flags { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.sc-flag { padding: 7px 12px; border-radius: var(--radius-sm, 8px); font-size: 0.84rem; line-height: 1.55; border: 1px solid var(--border-color); }
.sc-flag.tone-warn { background: rgba(245, 158, 11, 0.1); border-color: rgba(245, 158, 11, 0.35); }
.sc-flag.tone-info { background: rgba(59, 130, 246, 0.1); border-color: rgba(59, 130, 246, 0.3); }
.sc-foot { margin: 0; line-height: 1.6; }
.btn.xs { padding: 5px 12px; font-size: 0.78rem; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

@media (max-width: 960px) {
  .sc-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
