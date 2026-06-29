<template>
  <div class="chip-page">
    <header class="page-header">
      <div class="header-titles">
        <h1>籌碼分析</h1>
        <p class="subtitle">主力法人動向 · 大戶 / 散戶持股結構 · 大戶進出記錄</p>
      </div>
      <div class="controls">
        <input
          v-model="symbol"
          placeholder="股票代號"
          class="input-symbol"
          @keyup.enter="fetchData"
        />
        <button class="btn btn-primary" @click="fetchData" :disabled="loading">
          {{ loading ? '分析中…' : '重新分析' }}
        </button>
      </div>
    </header>

    <div v-if="loading && !data" class="loading-state card">
      <div class="spinner"></div>
      <span>正在彙整集保與法人籌碼資料…</span>
    </div>

    <div v-if="error" class="card error-card">{{ error }}</div>

    <div v-if="data" class="results">
      <!-- ===== 籌碼健診（綜合研判 hero） ===== -->
      <section v-if="chipHealth" class="card health-card">
        <div class="health-head">
          <div class="health-score" :class="'tone-' + chipHealth.tone">
            <span class="health-num">{{ chipHealth.scorePct }}</span>
            <span class="health-unit">/ 100</span>
          </div>
          <div class="health-meta">
            <span class="health-title">籌碼健診 · 綜合研判</span>
            <p class="health-verdict">{{ chipHealth.verdict }}</p>
            <div class="health-gauge">
              <div class="health-gauge-fill" :class="'tone-' + chipHealth.tone"
                   :style="{ width: chipHealth.scorePct + '%' }"></div>
              <span class="health-gauge-mid"></span>
            </div>
          </div>
        </div>
        <p v-if="synthesis" class="health-narrative">{{ synthesis.text }}</p>
        <div class="health-factors">
          <div v-for="f in chipHealth.factors" :key="f.label" class="health-factor">
            <div class="hf-top">
              <span class="hf-label">{{ f.label }}</span>
              <span class="hf-note" :class="f.score > 8 ? 'tone-up' : f.score < -8 ? 'tone-down' : 'tone-flat'">{{ f.note }}</span>
            </div>
            <div class="hf-bar">
              <span class="hf-bar-zero"></span>
              <span class="hf-bar-fill" :class="f.score >= 0 ? 'pos' : 'neg'"
                    :style="f.score >= 0
                      ? { left: '50%', width: (f.score / 2) + '%' }
                      : { right: '50%', width: (Math.abs(f.score) / 2) + '%' }"></span>
            </div>
          </div>
        </div>
        <p class="health-foot">綜合 集保結構、法人動向、同步買、主力成本、融資維持率、短線投機 等面向加權評分（50 為中性）。</p>
      </section>

      <section v-if="dist" class="verdict-grid">
        <div class="card verdict-card">
          <div class="verdict-head">
            <span class="verdict-tag" :class="verdictClass">{{ dist.verdict }}</span>
            <span class="verdict-date">資料日 {{ formatDate(dist.data_date) }}</span>
          </div>
          <p class="verdict-desc">{{ dist.verdict_description }}</p>
          <div class="signal-chips" v-if="dist.signals.length">
            <span
              v-for="(s, i) in dist.signals"
              :key="i"
              class="signal-chip"
              :class="'dir-' + s.direction"
            >
              <span class="dot"></span>{{ s.label }}
            </span>
          </div>
        </div>

        <div class="card score-card" :class="scoreTone">
          <span class="score-cap">籌碼分數</span>
          <span class="score-num num">{{ dist.score > 0 ? '+' : '' }}{{ dist.score }}</span>
          <div class="score-track">
            <div class="score-mid"></div>
            <div
              class="score-marker"
              :style="{ left: ((dist.score + 100) / 2) + '%' }"
            ></div>
          </div>
          <div class="score-legend"><span>分散 −100</span><span>集中 +100</span></div>
        </div>
      </section>

      <!-- ===== 主力成本區 ===== -->
      <section v-if="cost" class="card">
        <div class="card-head">
          <h2>主力成本區</h2>
          <span class="verdict-tag sm" :class="costTagClass">{{ cost.cost_verdict }}</span>
        </div>
        <div class="cost-grid">
          <div class="cost-metric">
            <span class="cm-key">主力估計成本</span>
            <span class="cm-val num">{{ cost.cost !== null ? cost.cost : '—' }}</span>
          </div>
          <div class="cost-metric">
            <span class="cm-key">目前股價</span>
            <span class="cm-val num">{{ cost.last_close }}</span>
          </div>
          <div class="cost-metric">
            <span class="cm-key">乖離率</span>
            <span class="cm-val num" :class="changeTone(cost.deviation)">
              {{ cost.deviation !== null ? (cost.deviation > 0 ? '+' : '') + cost.deviation + '%' : '—' }}
            </span>
          </div>
          <div class="cost-metric">
            <span class="cm-key">籌碼集中度</span>
            <span class="cm-val num" :class="changeTone(cost.concentration)">
              {{ cost.concentration > 0 ? '+' : '' }}{{ cost.concentration }}%
            </span>
          </div>
        </div>
        <div v-if="cost.cost !== null" class="cost-track" aria-hidden="true">
          <div class="ct-line"></div>
          <div class="ct-cost"><span>主力成本</span></div>
          <div class="ct-price" :style="{ left: pricePos + '%' }" :class="cost.cost_tone">
            <span>現價</span>
          </div>
        </div>
        <p class="cost-desc">{{ cost.cost_description }}</p>
        <p class="cost-desc">{{ cost.conc_description }}</p>
      </section>

      <!-- ===== 主力同步買 / 融資維持率 ===== -->
      <section v-if="syncBuy || marginRatio" class="signal-grid">
        <!-- 外資 + 投信同步買 -->
        <div v-if="syncBuy" class="card sig-card">
          <div class="card-head">
            <h2>外資 ＋ 投信同步</h2>
            <span class="verdict-tag sm" :class="syncTagClass">{{ syncBuy.verdict }}</span>
          </div>
          <div class="sig-stats">
            <div class="sig-stat">
              <span class="ss-key">近 {{ syncBuy.window }} 日同步買</span>
              <span class="ss-val num">{{ syncBuy.sync_buy_days }} 日</span>
            </div>
            <div class="sig-stat">
              <span class="ss-key">連續同步買</span>
              <span class="ss-val num" :class="syncBuy.sync_streak >= 3 ? 'tone-up' : ''">{{ syncBuy.sync_streak }} 日</span>
            </div>
            <div class="sig-stat">
              <span class="ss-key">近 5 日合計</span>
              <span class="ss-val num" :class="changeTone(syncBuy.combined_5d)">
                {{ syncBuy.combined_5d > 0 ? '+' : '' }}{{ formatInt(syncBuy.combined_5d) }}
              </span>
            </div>
          </div>
          <div class="sync-strip" aria-hidden="true">
            <span
              v-for="(d, i) in syncBuy.daily"
              :key="i"
              class="sync-cell"
              :class="'sc-' + d.sync"
              :title="d.date"
            ></span>
          </div>
          <p class="sig-desc">{{ syncBuy.description }}</p>
        </div>

        <!-- 融資維持率 -->
        <div v-if="marginRatio" class="card sig-card">
          <div class="card-head">
            <h2>融資維持率估算</h2>
            <span class="verdict-tag sm" :class="marginTagClass">{{ marginRatio.risk }}</span>
          </div>
          <div class="maint-hero">
            <span class="mh-val num" :class="marginRatio.tone">{{ marginRatio.maintenance_ratio }}%</span>
            <span class="mh-cap">估計整戶維持率</span>
          </div>
          <div class="maint-track" aria-hidden="true">
            <div class="mt-zone mt-danger"></div>
            <div class="mt-zone mt-warn"></div>
            <div class="mt-zone mt-safe"></div>
            <div class="mt-marker" :style="{ left: maintPos + '%' }"></div>
            <span class="mt-tick mt-tick-call">130%</span>
            <span class="mt-tick mt-tick-init">167%</span>
          </div>
          <div class="sig-stats">
            <div class="sig-stat">
              <span class="ss-key">融資估計成本</span>
              <span class="ss-val num">{{ marginRatio.est_cost }}</span>
            </div>
            <div class="sig-stat">
              <span class="ss-key">推估斷頭價</span>
              <span class="ss-val num tone-down">{{ marginRatio.margin_call_price }}</span>
            </div>
            <div class="sig-stat">
              <span class="ss-key">距斷頭緩衝</span>
              <span class="ss-val num" :class="marginRatio.buffer_pct < 10 ? 'tone-down' : 'tone-up'">
                {{ marginRatio.buffer_pct }}%
              </span>
            </div>
          </div>
          <p class="sig-desc">{{ marginRatio.description }}</p>
          <p class="sig-foot">{{ marginRatio.balance_trend }} · {{ marginRatio.cost_basis }}</p>
        </div>
      </section>

      <!-- ===== 股價疊加籌碼趨勢 ===== -->
      <section v-if="hasTrend" class="card">
        <div class="card-head">
          <h2>股價 × 主力籌碼趨勢</h2>
          <span class="verdict-tag sm tag-flat">近 30 日</span>
        </div>
        <div ref="trendChartEl" class="trend-chart"></div>
        <div class="trend-legend">
          <span class="tl-item"><i class="tl-line tl-price"></i>收盤價</span>
          <span class="tl-item"><i class="tl-line tl-cum"></i>法人累積淨買超（右軸）</span>
          <span v-if="cost && cost.cost !== null" class="tl-item"><i class="tl-line tl-cost"></i>主力估計成本 {{ cost.cost }}</span>
        </div>
        <p class="cost-desc">紅綠線為三大法人逐日累積淨買賣超（籌碼流向），與股價同步上揚代表主力買盤推升；虛線為主力估計成本，可觀察現價相對主力成本的位置。</p>
      </section>

      <!-- ===== 短線投機籌碼（當沖 / 隔日沖） ===== -->
      <section v-if="dayTrade" class="card">
        <div class="card-head">
          <h2>短線投機籌碼（當沖 / 隔日沖）</h2>
          <span class="verdict-tag sm" :class="dtTagClass">{{ dayTrade.verdict }}</span>
        </div>
        <div class="dt-grid">
          <div class="dt-hero">
            <span class="dt-val num" :class="dtTagClass">{{ dayTrade.ratio_5d !== null ? dayTrade.ratio_5d + '%' : '—' }}</span>
            <span class="dt-cap">近 5 日平均當沖比</span>
          </div>
          <div class="dt-bars" aria-hidden="true">
            <span
              v-for="(d, i) in dayTrade.daily"
              :key="i"
              class="dt-bar"
              :class="d.ratio >= 35 ? 'dtb-hot' : d.ratio >= 20 ? 'dtb-warm' : 'dtb-calm'"
              :style="{ height: Math.max(6, Math.min(100, (d.ratio || 0) * 2)) + '%' }"
              :title="d.date + '：' + (d.ratio ?? '—') + '%'"
            ></span>
          </div>
        </div>
        <div class="sig-stats">
          <div class="sig-stat">
            <span class="ss-key">最新當沖比</span>
            <span class="ss-val num">{{ dayTrade.ratio_latest !== null ? dayTrade.ratio_latest + '%' : '—' }}</span>
          </div>
          <div class="sig-stat">
            <span class="ss-key">較前波變化</span>
            <span class="ss-val num" :class="changeTone(dayTrade.trend_delta)">
              {{ dayTrade.trend_delta !== null ? (dayTrade.trend_delta > 0 ? '+' : '') + dayTrade.trend_delta + 'pt' : '—' }}
            </span>
          </div>
          <div class="sig-stat">
            <span class="ss-key">當沖客近 5 日淨額</span>
            <span class="ss-val num" :class="changeTone(dayTrade.net_5d)">
              {{ (dayTrade.net_5d / 1e8).toFixed(2) }} 億
            </span>
          </div>
        </div>
        <p class="sig-desc">{{ dayTrade.description }}</p>
        <p class="sig-foot">{{ dayTrade.net_label }}</p>
      </section>

      <!-- ===== 持股結構 ===== -->
      <section v-if="dist" class="card">
        <div class="card-head">
          <h2>大戶 / 散戶持股結構</h2>
          <span class="holders-pill">股東 {{ formatInt(dist.total_holders) }} 人</span>
        </div>

        <div class="struct-bar" role="img" aria-label="持股結構分布">
          <div
            class="struct-seg seg-retail"
            :style="{ width: dist.structure.retail.percent + '%' }"
            :title="`散戶 ${dist.structure.retail.percent}%`"
          ></div>
          <div
            class="struct-seg seg-general"
            :style="{ width: generalPct + '%' }"
            :title="`一般投資人 ${generalPct}%`"
          ></div>
          <div
            class="struct-seg seg-mid"
            :style="{ width: dist.structure.mid.percent + '%' }"
            :title="`中實戶 ${dist.structure.mid.percent}%`"
          ></div>
          <div
            class="struct-seg seg-whale"
            :style="{ width: dist.structure.whale.percent + '%' }"
            :title="`大戶 ${dist.structure.whale.percent}%`"
          ></div>
        </div>

        <div class="struct-cards">
          <div class="struct-card">
            <span class="sc-key"><span class="swatch sw-retail"></span>散戶 (&lt;10 張)</span>
            <span class="sc-val num">{{ dist.structure.retail.percent }}%</span>
            <span class="sc-sub num">{{ formatInt(dist.structure.retail.people) }} 人</span>
          </div>
          <div class="struct-card">
            <span class="sc-key"><span class="swatch sw-mid"></span>中實戶 (50–400 張)</span>
            <span class="sc-val num">{{ dist.structure.mid.percent }}%</span>
            <span class="sc-sub num">{{ formatInt(dist.structure.mid.people) }} 人</span>
          </div>
          <div class="struct-card">
            <span class="sc-key"><span class="swatch sw-whale"></span>大戶 (&gt;400 張)</span>
            <span class="sc-val num">{{ dist.structure.whale.percent }}%</span>
            <span class="sc-sub num">{{ formatInt(dist.structure.whale.people) }} 人</span>
          </div>
          <div class="struct-card highlight">
            <span class="sc-key">千張大戶 (&gt;1000 張)</span>
            <span class="sc-val num">{{ dist.structure.mega.percent }}%</span>
            <span class="sc-sub num">{{ formatInt(dist.structure.mega.people) }} 人</span>
          </div>
        </div>
        <p v-if="dist.structure.mega.percent >= 60" class="caveat">
          ⚠️ 此股千張大戶比例極高，多含政府基金、ETF 與外資保管專戶等被動持股，
          並非全為主動操作籌碼。請以「<strong>千張大戶週變化</strong>」作為進出訊號，勿單看絕對水位判多空。
        </p>
      </section>

      <!-- ===== 散戶籌碼 ===== -->
      <section v-if="dist || marginSummary" class="card">
        <div class="card-head">
          <h2>散戶籌碼</h2>
          <span class="muted-note">集保持股 + 融資融券（散戶代理指標）</span>
        </div>
        <div class="retail-cards">
          <div v-if="dist" class="retail-card">
            <span class="rc-key">散戶持股比例</span>
            <span class="rc-val num">{{ dist.structure.retail.percent }}%</span>
            <span class="rc-sub num">{{ formatInt(dist.structure.retail.people) }} 人（&lt;10 張）</span>
          </div>
          <div v-if="marginSummary" class="retail-card">
            <span class="rc-key">融資餘額</span>
            <span class="rc-val num">{{ formatInt(marginSummary.margin_balance_latest) }} 張</span>
            <span class="rc-sub num" :class="changeTone(marginSummary.margin_change_5d)">
              5 日 {{ marginSummary.margin_change_5d > 0 ? '+' : '' }}{{ formatInt(marginSummary.margin_change_5d) }} 張
            </span>
          </div>
          <div v-if="marginSummary" class="retail-card">
            <span class="rc-key">融券餘額</span>
            <span class="rc-val num">{{ formatInt(marginSummary.short_balance_latest) }} 張</span>
            <span class="rc-sub num" :class="changeTone(marginSummary.short_change_5d)">
              5 日 {{ marginSummary.short_change_5d > 0 ? '+' : '' }}{{ formatInt(marginSummary.short_change_5d) }} 張
            </span>
          </div>
        </div>
        <p class="retail-hint">
          {{ retailHint }}
        </p>
      </section>

      <!-- ===== 大戶進出記錄 ===== -->
      <section v-if="dist" class="card">
        <div class="card-head">
          <h2>大戶進出記錄</h2>
          <span class="muted-note">週變化（集保每週更新）</span>
        </div>

        <div v-if="dist.movements && dist.movements.length" class="move-table">
          <div class="move-row move-head">
            <span>週別</span>
            <span>千張大戶</span>
            <span>週變化</span>
            <span>大戶人數</span>
            <span>股東總數</span>
          </div>
          <div v-for="m in [...dist.movements].reverse()" :key="m.date" class="move-row">
            <span class="num">{{ formatDate(m.date) }}</span>
            <span class="num">{{ m.mega_pct }}%</span>
            <span class="num" :class="changeTone(m.mega_pct_change)">
              {{ m.mega_pct_change > 0 ? '+' : '' }}{{ m.mega_pct_change }}%
            </span>
            <span class="num" :class="changeTone(m.mega_people_change)">
              {{ m.mega_people_change > 0 ? '+' : '' }}{{ formatInt(m.mega_people_change) }}
            </span>
            <span class="num" :class="changeTone(-m.holders_change)">
              {{ m.holders_change > 0 ? '+' : '' }}{{ formatInt(m.holders_change) }}
            </span>
          </div>
        </div>
        <div v-else class="empty-trend">
          <p>已記錄本週快照，趨勢資料每週累積中。</p>
          <p class="muted-note">下次集保更新後即可顯示大戶進出週變化（已累積 {{ dist.history_weeks }} 週）。</p>
        </div>
      </section>

      <!-- ===== 持股分級分布 ===== -->
      <section v-if="dist" class="card">
        <div class="card-head"><h2>持股分級分布</h2></div>
        <div class="level-list">
          <div v-for="lv in dist.distribution" :key="lv.level" class="level-row">
            <span class="level-label">{{ lv.label }}</span>
            <div class="level-bar-track">
              <div
                class="level-bar"
                :class="levelTone(lv.level)"
                :style="{ width: barScale(lv.percent) + '%' }"
              ></div>
            </div>
            <span class="level-pct num">{{ lv.percent }}%</span>
            <span class="level-people num">{{ formatInt(lv.people) }} 人</span>
          </div>
        </div>
      </section>

      <!-- ===== 主力法人動向 ===== -->
      <section v-if="major" class="card">
        <div class="card-head">
          <h2>主力法人動向</h2>
          <span class="verdict-tag sm" :class="majorVerdictClass">{{ major.verdict }}</span>
        </div>
        <p class="verdict-desc">{{ major.verdict_description }}</p>

        <div class="flow-cards" v-if="major.institutional_flow && major.institutional_flow.summary">
          <div class="flow-card">
            <span class="fc-key">外資 5 日</span>
            <span class="fc-val num" :class="changeTone(major.institutional_flow.summary.foreign_5d)">
              {{ formatNet(major.institutional_flow.summary.foreign_5d) }}
            </span>
          </div>
          <div class="flow-card">
            <span class="fc-key">外資 20 日</span>
            <span class="fc-val num" :class="changeTone(major.institutional_flow.summary.foreign_20d)">
              {{ formatNet(major.institutional_flow.summary.foreign_20d) }}
            </span>
          </div>
          <div class="flow-card">
            <span class="fc-key">投信 5 日</span>
            <span class="fc-val num" :class="changeTone(major.institutional_flow.summary.trust_5d)">
              {{ formatNet(major.institutional_flow.summary.trust_5d) }}
            </span>
          </div>
          <div class="flow-card">
            <span class="fc-key">外資連續</span>
            <span class="fc-val num">{{ major.institutional_flow.summary.foreign_streak }} 日</span>
          </div>
        </div>

        <div class="signal-chips" v-if="major.signals && major.signals.length">
          <span
            v-for="(s, i) in major.signals"
            :key="i"
            class="signal-chip"
            :class="'dir-' + s.direction"
          >
            <span class="dot"></span>{{ s.label }}
          </span>
        </div>
      </section>

      <div v-if="distError && !dist" class="card warn-card">
        集保股權分散資料暫時無法取得：{{ distError }}
      </div>

      <footer class="chip-footer">
        資料來源：集保結算所 (TDCC) 股權分散表（每週更新）、FinMind 三大法人與融資融券。
        本頁分析僅供研究參考，不構成投資建議，投資人應自行評估風險。
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { createChart } from 'lightweight-charts'
import { useStockStore } from '../stores/stock.js'

const route = useRoute()
const stockStore = useStockStore()
const symbol = ref(route.params.symbol || stockStore.symbol)
const loading = ref(false)
const error = ref('')
const data = ref(null)

const dist = computed(() => data.value?.distribution || null)
const major = computed(() => data.value?.major_players || null)
const distError = computed(() => data.value?.distribution_error || '')

const marginSummary = computed(() => major.value?.margin_analysis?.summary || null)
const cost = computed(() => data.value?.major_cost || null)
const syncBuy = computed(() => data.value?.sync_buy || null)
const marginRatio = computed(() => data.value?.margin_ratio || null)
const dayTrade = computed(() => data.value?.day_trade || null)
const dtTagClass = computed(() => toneClass(dayTrade.value?.tone))

// 股價 × 法人累積淨買超 趨勢資料 (複用 volume_price.indicators + institutional_flow)
const trendChartEl = ref(null)
let trendChart = null
let trendRO = null

const trendData = computed(() => {
  const mp = major.value
  if (!mp) return null
  const vp = mp.volume_price?.indicators || []
  const inst = mp.institutional_flow || {}
  if (vp.length < 5) return null
  const fmap = Object.fromEntries((inst.foreign || []).map(d => [d.date, d.net]))
  const tmap = Object.fromEntries((inst.trust || []).map(d => [d.date, d.net]))
  const dmap = Object.fromEntries((inst.dealer || []).map(d => [d.date, d.net]))
  let cum = 0
  const price = []
  const cumNet = []
  for (const d of vp) {
    price.push({ time: d.date, value: d.close })
    cum += (fmap[d.date] || 0) + (tmap[d.date] || 0) + (dmap[d.date] || 0)
    cumNet.push({ time: d.date, value: Math.round(cum / 1000) }) // 千股
  }
  return { price, cumNet }
})
const hasTrend = computed(() => !!trendData.value)

function destroyTrendChart() {
  if (trendRO) { try { trendRO.disconnect() } catch {} trendRO = null }
  if (trendChart) { try { trendChart.remove() } catch {} trendChart = null }
}

function renderTrendChart() {
  destroyTrendChart()
  const el = trendChartEl.value
  const td = trendData.value
  if (!el || !td) return
  const width = el.clientWidth || 800
  trendChart = createChart(el, {
    width,
    height: 280,
    layout: { background: { color: 'transparent' }, textColor: '#94a3b8' },
    grid: {
      vertLines: { color: 'rgba(51, 65, 85, 0.25)' },
      horzLines: { color: 'rgba(51, 65, 85, 0.25)' },
    },
    rightPriceScale: { borderColor: '#334155' },
    leftPriceScale: { borderColor: '#334155', visible: true },
    timeScale: { borderColor: '#334155' },
    crosshair: { vertLine: { color: '#475569' }, horzLine: { color: '#475569' } },
  })
  // 收盤價（左軸）
  const priceSeries = trendChart.addLineSeries({
    color: '#38bdf8', lineWidth: 2, priceScaleId: 'left',
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
  })
  priceSeries.setData(td.price)
  // 法人累積淨買超（右軸）
  const lastCum = td.cumNet.length ? td.cumNet[td.cumNet.length - 1].value : 0
  const cumSeries = trendChart.addLineSeries({
    color: lastCum >= 0 ? '#22c55e' : '#ef4444', lineWidth: 2, priceScaleId: 'right',
    priceFormat: { type: 'volume' },
  })
  cumSeries.setData(td.cumNet)
  // 主力估計成本（虛線）
  const c = cost.value
  if (c && c.cost !== null && c.cost !== undefined) {
    priceSeries.createPriceLine({
      price: c.cost, color: '#f59e0b', lineWidth: 1, lineStyle: 2,
      axisLabelVisible: true, title: '主力成本',
    })
  }
  trendChart.timeScale().fitContent()
  trendRO = new ResizeObserver(() => {
    if (trendChart && el.clientWidth) trendChart.applyOptions({ width: el.clientWidth })
  })
  trendRO.observe(el)
}

watch(trendData, async () => {
  await nextTick()
  if (hasTrend.value) renderTrendChart()
  else destroyTrendChart()
})
onBeforeUnmount(destroyTrendChart)

const toneClass = (t) => (t === 'up' ? 'tag-up' : t === 'down' ? 'tag-down' : 'tag-flat')
const syncTagClass = computed(() => toneClass(syncBuy.value?.tone))
const marginTagClass = computed(() => toneClass(marginRatio.value?.tone))
// 維持率刻度條：130% 斷頭線在左、167% 初始在中、220%+ 在右
const maintPos = computed(() => {
  const r = marginRatio.value?.maintenance_ratio
  if (r === null || r === undefined) return 0
  return Math.max(2, Math.min(98, ((r - 110) / (230 - 110)) * 100))
})

const costTagClass = computed(() => {
  const t = cost.value?.cost_tone
  return t === 'up' ? 'tag-up' : t === 'down' ? 'tag-down' : 'tag-flat'
})
const pricePos = computed(() => {
  // position of current price on a ±15% cost track (cost = 50%)
  const d = cost.value?.deviation
  if (d === null || d === undefined) return 50
  return Math.max(4, Math.min(96, 50 + (d / 15) * 50))
})

const retailHint = computed(() => {
  const m = marginSummary.value
  if (!m) return '散戶持股比例越低、籌碼越穩定；融資餘額快速增加常為散戶追高訊號。'
  if (m.margin_change_5d > 0) {
    return '近 5 日融資餘額增加，散戶買盤轉強——股價同步走高時需留意追高風險。'
  }
  if (m.margin_change_5d < 0) {
    return '近 5 日融資餘額減少，散戶部位收斂——若股價同步上漲為健康的籌碼換手。'
  }
  return '融資餘額持平，散戶情緒中性。'
})

const chipHealth = computed(() => {
  // 後端已計算則優先採用（單一真實來源），否則前端就地計算作為後備
  const backend = data.value?.chip_health
  if (backend && backend.factors && backend.factors.length) {
    return { scorePct: backend.score, tone: backend.tone, verdict: backend.verdict, factors: backend.factors }
  }
  const d = dist.value, mp = major.value, sb = syncBuy.value
  const c = cost.value, mr = marginRatio.value, dt = dayTrade.value
  const factors = []
  const push = (label, score, note) => factors.push({ label, score: Math.max(-100, Math.min(100, Math.round(score))), note })

  if (d) push('集保結構', d.score, d.verdict)
  if (mp) push('法人動向', mp.score, mp.verdict)
  if (sb) {
    const s = sb.verdict.includes('同步買') ? 60 : sb.verdict.includes('偏多') ? 40
      : sb.verdict.includes('偏空') ? -50 : 0
    push('外資投信同步', s, sb.verdict)
  }
  if (c && c.deviation != null) {
    const s = c.deviation > 5 ? 40 : c.deviation < -5 ? -40 : 0
    push('主力成本', s, c.cost_verdict)
  }
  if (mr && mr.maintenance_ratio != null) {
    const s = mr.risk.includes('斷頭') ? -55 : mr.risk.includes('偏低') ? -25
      : mr.risk.includes('獲利') ? 15 : 0
    push('融資維持率', s, mr.risk)
  }
  if (dt && dt.ratio_5d != null) {
    const s = dt.verdict.includes('極熱') ? -40 : dt.verdict.includes('偏熱') ? -20
      : dt.verdict.includes('穩定') ? 20 : 0
    push('短線投機', s, dt.verdict)
  }
  if (!factors.length) return null

  const weights = { 集保結構: 1.2, 法人動向: 1.5, 外資投信同步: 1.0, 主力成本: 1.0, 融資維持率: 0.8, 短線投機: 0.8 }
  let wsum = 0, total = 0
  for (const f of factors) { const w = weights[f.label] || 1; total += f.score * w; wsum += w }
  const avg = wsum ? total / wsum : 0
  const scorePct = Math.round(Math.max(0, Math.min(100, 50 + avg / 2)))

  let tone, verdict
  if (scorePct >= 65) { tone = 'up'; verdict = '籌碼面整體偏多，主力與結構面同步支撐。' }
  else if (scorePct >= 55) { tone = 'up'; verdict = '籌碼面略偏多，多方訊號占優但力道有限。' }
  else if (scorePct >= 45) { tone = 'flat'; verdict = '籌碼面多空拉鋸，方向未明，宜搭配技術面確認。' }
  else if (scorePct >= 35) { tone = 'down'; verdict = '籌碼面略偏空，主力調節或結構鬆動跡象浮現。' }
  else { tone = 'down'; verdict = '籌碼面整體偏空，多項指標同步示警，宜保守。' }

  return { scorePct, tone, verdict, factors }
})

const synthesis = computed(() => {
  const d = dist.value
  const mp = major.value
  if (!d && !mp) return null
  const chipUp = d ? d.score >= 10 : null
  const chipDown = d ? d.score <= -10 : null
  const mpUp = mp ? mp.score >= 10 : null
  const mpDown = mp ? mp.score <= -10 : null

  const megaTrend = d?.movements?.length ? d.movements[d.movements.length - 1].mega_pct_change : null
  const trendTxt = megaTrend === null ? ''
    : megaTrend > 0 ? `千張大戶近一週增加 ${megaTrend.toFixed(2)}%，`
    : megaTrend < 0 ? `千張大戶近一週減少 ${Math.abs(megaTrend).toFixed(2)}%，` : ''

  const chipPart = d ? `集保結構${d.verdict}（大戶 ${d.structure.whale.percent}%、散戶 ${d.structure.retail.percent}%）` : ''
  const mpPart = mp ? `近期法人${mp.verdict}` : ''

  let tone = 'flat', icon = '⚖️', verdict = ''
  if (chipUp && mpUp) { tone = 'up'; icon = '🟢'; verdict = '籌碼面與法人動向同步偏多，買方訊號一致。' }
  else if (chipDown && mpDown) { tone = 'down'; icon = '🔴'; verdict = '籌碼面與法人動向同步偏空，賣壓明顯，宜保守。' }
  else if ((chipUp && mpDown) || (chipDown && mpUp)) {
    tone = 'flat'; icon = '⚠️'
    verdict = '長線集保結構與短線法人買賣方向分歧——集保反映中長期持股、法人反映短線進出，建議以股價趨勢與千張大戶週變化作最後確認。'
  } else {
    verdict = '籌碼訊號中性，方向未明，建議搭配技術面與基本面綜合判斷。'
  }

  const text = [trendTxt + chipPart, mpPart].filter(Boolean).join('；') + '。' + verdict

  // 補上其餘面向的關鍵風險／加分，使敘述與綜合評分一致
  const risks = []
  const cc = cost.value
  if (cc && cc.deviation != null && cc.deviation < -5) risks.push('主力成本套牢')
  const mrr = marginRatio.value
  if (mrr && mrr.risk) {
    if (mrr.risk.includes('斷頭')) risks.push('融資瀕臨斷頭')
    else if (mrr.risk.includes('偏低')) risks.push('融資維持率偏低')
  }
  const dtt = dayTrade.value
  if (dtt && dtt.verdict) {
    if (dtt.verdict.includes('極熱')) risks.push('短線投機極熱')
    else if (dtt.verdict.includes('偏熱')) risks.push('短線投機偏熱')
  }
  const positives = []
  if (cc && cc.deviation != null && cc.deviation > 5) positives.push('主力成本獲利')
  const sbb = syncBuy.value
  if (sbb && sbb.verdict && (sbb.verdict.includes('同步買') || sbb.verdict.includes('偏多'))) positives.push('外資投信同步偏多')

  let caveat = ''
  if (risks.length) caveat = ` 惟${risks.join('、')}等面向影響整體評分，宜留意風險。`
  else if (positives.length) caveat = ` 另${positives.join('、')}，為籌碼結構加分。`

  return { tone, icon, text: text + caveat }
})

const generalPct = computed(() => {
  if (!dist.value) return 0
  const s = dist.value.structure
  const used = s.retail.percent + s.mid.percent + s.whale.percent
  return Math.max(0, Math.round((100 - used) * 100) / 100)
})

const verdictClass = computed(() => tagClass(dist.value?.verdict))
const majorVerdictClass = computed(() => tagClass(major.value?.verdict))
const scoreTone = computed(() => {
  const sc = dist.value?.score || 0
  return sc > 10 ? 'tone-up' : sc < -10 ? 'tone-down' : 'tone-flat'
})

function tagClass(v) {
  if (!v) return 'tag-flat'
  if (['籌碼集中', '偏多', '拉抬'].includes(v)) return 'tag-up'
  if (['籌碼分散', '偏空', '出貨'].includes(v)) return 'tag-down'
  return 'tag-flat'
}

function changeTone(v) {
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

function levelTone(lv) {
  const n = parseInt(lv)
  if (n <= 3) return 'lt-retail'
  if (n >= 12) return 'lt-whale'
  if (n >= 9) return 'lt-mid'
  return 'lt-general'
}

function barScale(pct) {
  // log-ish scale so small retail levels stay visible vs the dominant mega level
  return Math.min(100, Math.sqrt(pct / 100) * 100)
}

function formatInt(v) {
  if (v === null || v === undefined) return '0'
  return Number(v).toLocaleString('en-US')
}

function formatNet(v) {
  if (!v) return '0'
  const abs = Math.abs(v)
  const sign = v > 0 ? '+' : '-'
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(1) + '億'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '萬'
  return sign + abs.toLocaleString('en-US')
}

function formatDate(d) {
  if (!d) return ''
  const s = String(d)
  if (s.length === 8) return `${s.slice(0, 4)}/${s.slice(4, 6)}/${s.slice(6, 8)}`
  return s
}

async function fetchData() {
  if (!symbol.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${symbol.value}/chip-analysis`)
    const json = await res.json()
    if (json.success) {
      data.value = json.data
      if (symbol.value && symbol.value !== stockStore.symbol) {
        stockStore.setStock(symbol.value, stockStore.name)
      }
      if (!json.data.distribution && !json.data.major_players) {
        error.value = json.data.distribution_error || '查無此股票的籌碼資料'
      }
    } else {
      error.value = json.detail || '分析失敗'
    }
  } catch (e) {
    error.value = '無法連線到伺服器'
  } finally {
    loading.value = false
  }
}

watch(() => route.params.symbol, (s) => {
  if (s && s !== symbol.value) {
    symbol.value = s
    fetchData()
  }
})

onMounted(fetchData)
</script>

<style scoped>
.chip-page { display: flex; flex-direction: column; gap: var(--space-5); }

.page-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  flex-wrap: wrap; gap: var(--space-4);
}
.header-titles h1 { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.controls { display: flex; gap: 8px; align-items: center; }
.input-symbol {
  width: 110px; padding: 9px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border-color); background: var(--bg-secondary);
  color: var(--text-primary); font-weight: 700; text-align: center;
  font-variant-numeric: tabular-nums;
}
.input-symbol:focus { outline: none; border-color: var(--accent-blue); }

.loading-state { display: flex; align-items: center; gap: 14px; color: var(--text-muted); }
.spinner {
  width: 22px; height: 22px; border-radius: 50%;
  border: 2.5px solid var(--border-color); border-top-color: var(--accent-blue);
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }

.error-card { color: var(--accent-red); border-color: rgba(239,68,68,0.4); }
.warn-card { color: var(--text-muted); border-color: rgba(234,179,8,0.4); }

.results { display: flex; flex-direction: column; gap: var(--space-5); }

/* ---- 籌碼健診（綜合研判 hero） ---- */
.health-card { display: flex; flex-direction: column; gap: 16px; }
.health-head { display: flex; gap: 18px; align-items: center; }
.health-score { display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-width: 96px; padding: 12px 8px; border-radius: var(--radius-sm); background: var(--bg-tertiary); }
.health-num { font-size: 2.4rem; font-weight: 800; line-height: 1; }
.health-unit { font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; }
.health-score.tone-up .health-num { color: var(--accent-green); }
.health-score.tone-down .health-num { color: var(--accent-red); }
.health-score.tone-flat .health-num { color: #eab308; }
.health-meta { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.health-title { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.04em; color: var(--text-muted); }
.health-verdict { font-size: 0.92rem; line-height: 1.55; color: var(--text-primary); }
.health-narrative { font-size: 0.86rem; line-height: 1.7; color: var(--text-secondary); padding: 12px 14px;
  background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.health-gauge { position: relative; height: 8px; border-radius: 4px; background: var(--bg-tertiary); overflow: hidden; }
.health-gauge-fill { position: absolute; left: 0; top: 0; height: 100%; border-radius: 4px; transition: width 0.5s cubic-bezier(0.22,1,0.36,1); }
.health-gauge-fill.tone-up { background: linear-gradient(90deg, rgba(34,197,94,0.5), var(--accent-green)); }
.health-gauge-fill.tone-down { background: linear-gradient(90deg, rgba(239,68,68,0.5), var(--accent-red)); }
.health-gauge-fill.tone-flat { background: linear-gradient(90deg, rgba(234,179,8,0.5), #eab308); }
.health-gauge-mid { position: absolute; left: 50%; top: -2px; width: 1px; height: 12px; background: var(--text-muted); opacity: 0.5; }
.health-factors { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 20px; }
.health-factor { display: flex; flex-direction: column; gap: 5px; }
.hf-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.hf-label { font-size: 0.8rem; font-weight: 600; color: var(--text-primary); }
.hf-note { font-size: 0.72rem; color: var(--text-muted); text-align: right; }
.hf-note.tone-up { color: var(--accent-green); }
.hf-note.tone-down { color: var(--accent-red); }
.hf-bar { position: relative; height: 6px; border-radius: 3px; background: var(--bg-tertiary); }
.hf-bar-zero { position: absolute; left: 50%; top: -1px; width: 1px; height: 8px; background: var(--border-color); }
.hf-bar-fill { position: absolute; top: 0; height: 100%; border-radius: 3px; transition: width 0.4s ease; }
.hf-bar-fill.pos { background: var(--accent-green); }
.hf-bar-fill.neg { background: var(--accent-red); }
.health-foot { font-size: 0.72rem; line-height: 1.55; color: var(--text-muted); }
@media (max-width: 640px) {
  .health-factors { grid-template-columns: 1fr; }
  .health-head { gap: 12px; }
  .health-score { min-width: 80px; }
  .health-num { font-size: 2rem; }
}


/* ---- caveat ---- */
.caveat { margin-top: 14px; padding: 12px 14px; background: rgba(234,179,8,0.07); border: 1px solid rgba(234,179,8,0.25); border-radius: var(--radius-sm); font-size: 0.8rem; line-height: 1.6; color: var(--text-secondary); }
.caveat strong { color: var(--text-primary); }

/* ---- retail chips ---- */
.retail-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.retail-card { display: flex; flex-direction: column; gap: 5px; padding: 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.rc-key { font-size: 0.76rem; color: var(--text-muted); }
.rc-val { font-size: 1.4rem; font-weight: 800; }
.rc-sub { font-size: 0.72rem; color: var(--text-muted); }
.rc-sub.up { color: var(--accent-red); }
.rc-sub.down { color: var(--accent-green); }
.retail-hint { margin-top: 14px; font-size: 0.8rem; line-height: 1.6; color: var(--text-secondary); }

.chip-footer { font-size: 0.72rem; line-height: 1.6; color: var(--text-muted); padding: 4px 2px; border-top: 1px solid var(--border-color); padding-top: 14px; }

/* ---- 主力成本區 ---- */
.cost-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.cost-metric { display: flex; flex-direction: column; gap: 5px; padding: 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.cm-key { font-size: 0.76rem; color: var(--text-muted); }
.cm-val { font-size: 1.5rem; font-weight: 800; }
.cm-val.up { color: var(--accent-green); }
.cm-val.down { color: var(--accent-red); }
.cost-track { position: relative; height: 46px; margin: 10px 0 18px; }
.ct-line { position: absolute; top: 30px; left: 0; right: 0; height: 3px; background: var(--bg-tertiary); border-radius: 2px; }
.ct-line::before { content: ''; position: absolute; left: 50%; top: -3px; width: 2px; height: 9px; background: var(--text-muted); transform: translateX(-50%); }
.ct-cost { position: absolute; left: 50%; top: 30px; transform: translate(-50%, -100%); font-size: 0.68rem; color: var(--text-muted); white-space: nowrap; }
.ct-price { position: absolute; top: 30px; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; background: var(--accent-blue); box-shadow: 0 0 0 3px var(--bg-secondary); transition: left 0.5s ease; }
.ct-price.up { background: var(--accent-green); }
.ct-price.down { background: var(--accent-red); }
.ct-price span { position: absolute; top: 16px; left: 50%; transform: translateX(-50%); font-size: 0.68rem; color: var(--text-secondary); white-space: nowrap; }
@media (prefers-reduced-motion: reduce) { .ct-price { transition: none; } }
.cost-desc { font-size: 0.84rem; line-height: 1.6; color: var(--text-secondary); margin-top: 6px; }

/* ---- 進階訊號：同步買 / 維持率 ---- */
.signal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.sig-card { display: flex; flex-direction: column; }
.sig-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 4px 0 14px; }
.sig-stat { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.ss-key { font-size: 0.72rem; color: var(--text-muted); }
.ss-val { font-size: 1.18rem; font-weight: 800; }
.ss-val.up, .ss-val.tone-up { color: var(--accent-green); }
.ss-val.down, .ss-val.tone-down { color: var(--accent-red); }
.sig-desc { font-size: 0.84rem; line-height: 1.6; color: var(--text-secondary); margin-top: auto; }
.sig-foot { font-size: 0.72rem; color: var(--text-muted); margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-color); }

/* 同步買熱力條 */
.sync-strip { display: flex; gap: 4px; margin-bottom: 14px; }
.sync-cell { flex: 1; height: 18px; border-radius: 3px; background: var(--bg-tertiary); }
.sync-cell.sc-buy { background: var(--accent-green); }
.sync-cell.sc-sell { background: var(--accent-red); }

/* 維持率 */
.maint-hero { display: flex; flex-direction: column; align-items: center; gap: 2px; margin-bottom: 14px; }
.mh-val { font-size: 2.4rem; font-weight: 800; line-height: 1; }
.mh-val.up { color: var(--accent-green); }
.mh-val.down { color: var(--accent-red); }
.mh-val.flat { color: var(--accent-blue); }
.mh-cap { font-size: 0.74rem; color: var(--text-muted); }
.maint-track { position: relative; height: 12px; border-radius: 6px; overflow: hidden; margin: 6px 0 26px; display: flex; }
.mt-zone { height: 100%; }
.mt-danger { width: 17%; background: rgba(239,68,68,0.55); }
.mt-warn { width: 31%; background: rgba(234,179,8,0.5); }
.mt-safe { flex: 1; background: rgba(34,197,94,0.45); }
.mt-marker { position: absolute; top: -3px; width: 4px; height: 18px; border-radius: 2px; background: var(--text-primary); transform: translateX(-50%); box-shadow: 0 0 0 2px var(--bg-secondary); transition: left 0.5s ease; }
.mt-tick { position: absolute; top: 15px; font-size: 0.62rem; color: var(--text-muted); transform: translateX(-50%); font-variant-numeric: tabular-nums; }
.mt-tick-call { left: 17%; }
.mt-tick-init { left: 47.5%; }
@media (prefers-reduced-motion: reduce) { .mt-marker { transition: none; } }

/* ---- 股價 × 籌碼趨勢圖 ---- */
.trend-chart { width: 100%; height: 280px; }
.trend-legend { display: flex; flex-wrap: wrap; gap: 16px; margin: 12px 0 4px; }
.tl-item { display: inline-flex; align-items: center; gap: 7px; font-size: 0.76rem; color: var(--text-secondary); }
.tl-line { width: 18px; height: 3px; border-radius: 2px; }
.tl-price { background: #38bdf8; }
.tl-cum { background: #22c55e; }
.tl-cost { background: #f59e0b; border-top: 1px dashed #f59e0b; height: 0; }

/* ---- 短線投機籌碼（當沖/隔日沖） ---- */
.dt-grid { display: grid; grid-template-columns: 160px 1fr; gap: 16px; align-items: stretch; margin-bottom: 14px; }
.dt-hero { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.dt-val { font-size: 2rem; font-weight: 800; line-height: 1; }
.dt-val.tag-up { color: var(--accent-green); background: none; border: none; padding: 0; }
.dt-val.tag-down { color: var(--accent-red); background: none; border: none; padding: 0; }
.dt-val.tag-flat { color: var(--accent-blue); background: none; border: none; padding: 0; }
.dt-cap { font-size: 0.74rem; color: var(--text-muted); }
.dt-bars { display: flex; align-items: flex-end; gap: 3px; padding: 10px; background: var(--bg-tertiary); border-radius: var(--radius-sm); min-height: 90px; }
.dt-bar { flex: 1; border-radius: 2px 2px 0 0; background: var(--accent-blue); transition: height 0.4s ease; }
.dtb-calm { background: rgba(59,130,246,0.55); }
.dtb-warm { background: rgba(234,179,8,0.7); }
.dtb-hot { background: rgba(239,68,68,0.8); }
@media (prefers-reduced-motion: reduce) { .dt-bar { transition: none; } }

/* ---- verdict ---- */
.verdict-grid { display: grid; grid-template-columns: 1.8fr 1fr; gap: var(--space-4); }
.verdict-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.verdict-tag {
  font-size: 1.05rem; font-weight: 800; padding: 5px 14px; border-radius: 999px;
  border: 1px solid transparent;
}
.verdict-tag.sm { font-size: 0.82rem; padding: 3px 11px; }
.tag-up { color: var(--accent-green); background: rgba(34,197,94,0.12); border-color: rgba(34,197,94,0.3); }
.tag-down { color: var(--accent-red); background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.3); }
.tag-flat { color: var(--accent-blue); background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.3); }
.verdict-date { font-size: 0.72rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.verdict-desc { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 14px; }

.signal-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.signal-chip {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 0.78rem; padding: 6px 12px; border-radius: 999px;
  background: var(--bg-tertiary); border: 1px solid var(--border-color);
}
.signal-chip .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); }
.dir-bullish .dot { background: var(--accent-green); }
.dir-bearish .dot { background: var(--accent-red); }
.dir-caution .dot { background: #eab308; }

.score-card { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; }
.score-cap { font-size: 0.78rem; color: var(--text-muted); }
.score-num { font-size: 2.6rem; font-weight: 800; line-height: 1; }
.tone-up .score-num { color: var(--accent-green); }
.tone-down .score-num { color: var(--accent-red); }
.tone-flat .score-num { color: var(--accent-blue); }
.score-track { position: relative; width: 100%; height: 6px; border-radius: 3px; background: var(--bg-tertiary); margin-top: 6px; }
.score-mid { position: absolute; left: 50%; top: -2px; width: 1px; height: 10px; background: var(--border-color); }
.score-marker { position: absolute; top: 50%; width: 12px; height: 12px; border-radius: 50%; background: var(--text-primary); transform: translate(-50%, -50%); box-shadow: 0 0 0 3px var(--bg-secondary); }
.score-legend { display: flex; justify-content: space-between; width: 100%; font-size: 0.65rem; color: var(--text-muted); }

/* ---- card heads ---- */
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 16px; }
.card-head h2 { font-size: 1.05rem; font-weight: 700; }
.holders-pill { font-size: 0.74rem; color: var(--text-muted); background: var(--bg-tertiary); padding: 4px 11px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.muted-note { font-size: 0.72rem; color: var(--text-muted); }

/* ---- structure bar ---- */
.struct-bar { display: flex; height: 30px; border-radius: var(--radius-sm); overflow: hidden; background: var(--bg-tertiary); margin-bottom: 18px; }
.struct-seg { height: 100%; transition: width 0.5s var(--ease-out, ease); min-width: 0; }
.seg-retail { background: #f59e0b; }
.seg-general { background: #64748b; }
.seg-mid { background: #3b82f6; }
.seg-whale { background: #22c55e; }
@media (prefers-reduced-motion: reduce) { .struct-seg { transition: none; } }

.struct-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.struct-card { display: flex; flex-direction: column; gap: 4px; padding: 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); border: 1px solid transparent; }
.struct-card.highlight { border-color: rgba(34,197,94,0.35); background: rgba(34,197,94,0.06); }
.sc-key { display: flex; align-items: center; gap: 6px; font-size: 0.76rem; color: var(--text-muted); }
.swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }
.sw-retail { background: #f59e0b; }
.sw-mid { background: #3b82f6; }
.sw-whale { background: #22c55e; }
.sc-val { font-size: 1.5rem; font-weight: 800; }
.sc-sub { font-size: 0.72rem; color: var(--text-muted); }

/* ---- movements table ---- */
.move-table { font-size: 0.82rem; }
.move-row { display: grid; grid-template-columns: 1.2fr 1fr 1fr 1fr 1fr; gap: 8px; padding: 9px 4px; border-bottom: 1px solid var(--bg-tertiary); align-items: center; }
.move-head { font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color); font-size: 0.74rem; }
.move-row .up { color: var(--accent-green); }
.move-row .down { color: var(--accent-red); }
.empty-trend { text-align: center; padding: 22px; color: var(--text-secondary); }
.empty-trend p { margin: 2px 0; }

/* ---- level distribution ---- */
.level-list { display: flex; flex-direction: column; gap: 7px; }
.level-row { display: grid; grid-template-columns: 130px 1fr 64px 92px; gap: 12px; align-items: center; font-size: 0.78rem; }
.level-label { color: var(--text-secondary); }
.level-bar-track { height: 14px; background: var(--bg-tertiary); border-radius: 4px; overflow: hidden; }
.level-bar { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.lt-retail { background: #f59e0b; }
.lt-general { background: #64748b; }
.lt-mid { background: #3b82f6; }
.lt-whale { background: #22c55e; }
.level-pct { text-align: right; font-weight: 700; }
.level-people { text-align: right; color: var(--text-muted); }
@media (prefers-reduced-motion: reduce) { .level-bar { transition: none; } }

/* ---- institutional flow ---- */
.flow-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 14px 0 16px; }
.flow-card { display: flex; flex-direction: column; gap: 5px; padding: 13px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.fc-key { font-size: 0.74rem; color: var(--text-muted); }
.fc-val { font-size: 1.15rem; font-weight: 800; }
.fc-val.up { color: var(--accent-green); }
.fc-val.down { color: var(--accent-red); }

@media (max-width: 860px) {
  .verdict-grid { grid-template-columns: 1fr; }
  .signal-grid { grid-template-columns: 1fr; }
  .dt-grid { grid-template-columns: 1fr; }
  .struct-cards, .flow-cards { grid-template-columns: repeat(2, 1fr); }
  .retail-cards { grid-template-columns: 1fr; }
  .cost-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 520px) {
  .page-header { flex-direction: column; align-items: stretch; }
  .controls { justify-content: space-between; }
  .move-row { grid-template-columns: 1.1fr 0.9fr 0.9fr 0.9fr; }
  .move-row span:nth-child(5), .move-head span:nth-child(5) { display: none; }
  .level-row { grid-template-columns: 92px 1fr 52px; }
  .level-people { display: none; }
}
</style>
