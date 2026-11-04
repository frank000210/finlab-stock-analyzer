<template>
  <div class="div-health" data-testid="div-health">
    <p v-if="!items.length" class="muted small" data-testid="div-health-empty">
      所選標的近 5 年都沒有除息紀錄（不配息或尚未配息），配息體檢不適用。
    </p>

    <article
      v-for="row in items"
      :key="row.symbol"
      class="hc"
      :data-symbol="row.symbol"
      :data-verdict="row.health.verdict"
    >
      <header class="hc-head">
        <span class="hc-title">
          <i class="dot" :style="{ background: colorOf(row.symbol) }"></i>
          <strong>{{ row.symbol }}</strong> <span class="nm">{{ row.name }}</span>
          <span v-if="row.health.freq_label" class="freq">{{ row.health.freq_label }}</span>
        </span>
        <span class="verdict" :class="'v-' + row.health.verdict" data-testid="health-verdict">
          {{ verdictIcon(row.health.verdict) }} {{ row.health.verdict_label }}
        </span>
      </header>

      <p v-if="!row.health.enough" class="muted small hc-reason" data-testid="health-reason">{{ row.health.reason }}</p>

      <template v-else>
        <div class="kpis">
          <div class="kpi"><span>現價殖利率</span><strong>{{ pct(row.health.yield_now) }}</strong></div>
          <div class="kpi"><span>常態殖利率 <small>（用近 12 月均價）</small></span><strong>{{ pct(row.health.yield_norm) }}</strong></div>
          <div class="kpi" :class="'k-' + levelOf(row, 'inflation')">
            <span>膨脹倍數</span><strong>{{ row.health.inflation == null ? '—' : row.health.inflation.toFixed(2) + '×' }}</strong>
          </div>
        </div>

        <div v-if="row.health.scenarios" class="scen" data-testid="health-scenarios">
          <span class="scen-title">若之後都照最近 4 次的水準配（{{ row.health.scenarios.freq_label }}，以現價換算）</span>
          <span class="scen-item"><em>保守</em>{{ pct(row.health.scenarios.conservative) }}</span>
          <span class="scen-item"><em>中性</em>{{ pct(row.health.scenarios.neutral) }}</span>
          <span class="scen-item"><em>最近一次年化</em>{{ pct(row.health.scenarios.last_annualized) }}</span>
        </div>

        <ul class="checks">
          <li v-for="c in row.health.checks" :key="c.key" class="check" :class="'c-' + c.level" :data-check="c.key" :data-level="c.level">
            <span class="c-icon" aria-hidden="true">{{ levelIcon(c.level) }}</span>
            <span class="c-body"><strong>{{ c.label }}</strong>：{{ c.text }}</span>
          </li>
        </ul>

        <div class="payouts" :aria-label="row.symbol + ' 最近 ' + row.health.payouts.length + ' 次配息'">
          <span class="payouts-title">最近 {{ row.health.payouts.length }} 次配息（元）</span>
          <div class="bars">
            <div v-for="p in row.health.payouts" :key="p.date" class="bar-wrap" :title="p.date + '：' + p.amount + ' 元'">
              <span class="bar-val">{{ p.amount.toFixed(2) }}</span>
              <span class="bar" :style="{ height: barHeight(row, p.amount) + 'px', background: colorOf(row.symbol) }"></span>
              <span class="bar-date">{{ p.date.slice(2, 7).replace('-', '/') }}</span>
            </div>
          </div>
        </div>
      </template>

      <slot name="extra" :row="row" />
    </article>

    <details v-if="items.length && thresholds" class="method">
      <summary>判斷門檻與算法</summary>
      <ul>
        <li><strong>殖利率膨脹</strong>：近 12 個月均價 ÷ 現價（等於現價殖利率 ÷ 常態殖利率）。&gt; {{ thresholds.inflation[0].toFixed(2) }} 留意、&gt; {{ thresholds.inflation[1].toFixed(2) }} 偏弱。</li>
        <li><strong>配息穩定度</strong>：最近 {{ thresholds.recent_n }} 次配息金額的變異係數（標準差 ÷ 平均）。&gt; {{ pct(thresholds.cv[0], 0) }} 留意、&gt; {{ pct(thresholds.cv[1], 0) }} 偏弱。</li>
        <li><strong>近期趨勢</strong>：最近一次 ÷ 去年同期（找不到去年同期才比前 4 次平均；台股配息有季節性，所以優先比同期）。&lt; {{ thresholds.trend[0].toFixed(2) }} 留意、&lt; {{ thresholds.trend[1].toFixed(2) }} 偏弱。</li>
        <li><strong>吃本金</strong>：近 {{ thresholds.principal_years }} 年價格跌幅 ÷ 配息貢獻（含息報酬 − 價格報酬）。&gt; {{ pct(thresholds.erosion[0], 0) }} 留意、&gt; {{ pct(thresholds.erosion[1], 0) }} 偏弱；填息成功率低於 {{ pct(thresholds.fill_weak_rate, 0) }} 再加重一級。</li>
        <li><strong>總評</strong>：任一項偏弱、或三項以上留意＝偏弱；一～兩項留意＝留意；都沒事＝穩定。配息少於 {{ thresholds.min_payouts }} 次或近 12 個月沒配息，顯示「資料不足」，不硬判。</li>
        <li><strong>情境殖利率</strong>：用最近 4 次配息（保守取最低、中性取中位數），乘上年配次數，除以現價。</li>
      </ul>
      <p class="muted small">這是把歷史資料換個角度看，不是預測，也不是投資建議。看不到配息的「來源」（股利、資本利得、收益平準金、本金），那要看各投信的配息公告。</p>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  colorOf: { type: Function, default: () => '#94a3b8' },
  thresholds: { type: Object, default: null },
})

// 只顯示有配息、且後端有算出體檢的標的（舊快取或 mock 沒有 health 時直接略過，不報錯）
const items = computed(() => props.rows.filter(r => r.health && r.dividends && r.dividends.pays_dividend))

const pct = (x, d = 1) => (x == null ? '—' : (x * 100).toFixed(d) + '%')
const levelOf = (row, key) => (row.health.checks.find(c => c.key === key) || {}).level || 'na'
const VERDICT_ICON = { steady: '✓', watch: '!', weak: '✗', unknown: '?' }
const LEVEL_ICON = { good: '✓', warn: '!', bad: '✗', na: '–' }
const verdictIcon = v => VERDICT_ICON[v] || '?'
const levelIcon = l => LEVEL_ICON[l] || '–'

function barHeight(row, amount) {
  const max = Math.max(...row.health.payouts.map(p => p.amount), 0.0001)
  return Math.max(4, Math.round((amount / max) * 44))
}
</script>

<style scoped>
.div-health { display: flex; flex-direction: column; gap: 14px; }
.hc { border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; background: var(--bg-well, rgba(148, 163, 184, 0.05)); }
.hc-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.hc-title { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.nm { color: var(--text-muted); font-size: 0.86rem; }
.freq { font-size: 0.72rem; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border-color); color: var(--text-muted); }

/* 紅／綠在這個站是漲跌色；總評用「圖示＋文字＋顏色」三重表達，不單靠顏色 */
.verdict { font-weight: 700; font-size: 0.86rem; padding: 3px 12px; border-radius: 999px; border: 1px solid transparent; }
.v-steady { color: var(--color-down); border-color: currentColor; background: rgba(16, 185, 129, 0.1); }
.v-watch { color: var(--color-warning); border-color: currentColor; background: rgba(245, 158, 11, 0.1); }
.v-weak { color: var(--color-up); border-color: currentColor; background: rgba(239, 68, 68, 0.1); }
.v-unknown { color: var(--text-muted); border-color: var(--border-color); }
.hc-reason { margin: 0; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 10px; }
.kpi { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); }
.kpi span { font-size: 0.74rem; color: var(--text-muted); }
.kpi span small { font-size: 0.68rem; }
.kpi strong { font-size: 1.15rem; }
.kpi.k-warn { border-color: var(--color-warning); }
.kpi.k-bad { border-color: var(--color-up); }

.scen { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; font-size: 0.84rem; margin-bottom: 10px; }
.scen-title { color: var(--text-muted); font-size: 0.78rem; flex-basis: 100%; }
.scen-item em { font-style: normal; color: var(--text-muted); margin-right: 6px; font-size: 0.78rem; }
.scen-item { font-weight: 600; }

.checks { list-style: none; padding: 0; margin: 0 0 10px; display: flex; flex-direction: column; gap: 6px; }
.check { display: flex; gap: 8px; font-size: 0.84rem; line-height: 1.5; }
.c-icon { flex: 0 0 18px; font-weight: 800; text-align: center; }
.c-good .c-icon { color: var(--color-down); }
.c-warn .c-icon { color: var(--color-warning); }
.c-bad .c-icon { color: var(--color-up); }
.c-na .c-icon, .c-na .c-body { color: var(--text-muted); }

.payouts-title { font-size: 0.76rem; color: var(--text-muted); }
.bars { display: flex; align-items: flex-end; gap: 10px; margin-top: 6px; min-height: 80px; overflow-x: auto; padding-bottom: 2px; }
.bar-wrap { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 40px; }
.bar { width: 18px; border-radius: 3px 3px 0 0; opacity: 0.85; display: block; }
.bar-val { font-size: 0.68rem; color: var(--text-primary); }
.bar-date { font-size: 0.66rem; color: var(--text-muted); }

.method { font-size: 0.82rem; }
.method summary { cursor: pointer; color: var(--text-muted); }
.method ul { margin: 8px 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
.muted { color: var(--text-muted); }
.small { font-size: 0.8rem; }
</style>
