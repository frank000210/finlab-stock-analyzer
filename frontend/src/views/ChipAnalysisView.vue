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
      <!-- ===== 綜合研判 ===== -->
      <section v-if="synthesis" class="card synth-card" :class="'synth-' + synthesis.tone">
        <span class="synth-icon">{{ synthesis.icon }}</span>
        <div class="synth-body">
          <span class="synth-title">綜合研判</span>
          <p class="synth-text">{{ synthesis.text }}</p>
        </div>
      </section>

      <!-- ===== 籌碼總評 ===== -->
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
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
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
  return { tone, icon, text }
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

/* ---- synthesis banner ---- */
.synth-card { display: flex; gap: 14px; align-items: flex-start; border-width: 1px; }
.synth-up { border-color: rgba(34,197,94,0.4); background: rgba(34,197,94,0.05); }
.synth-down { border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.05); }
.synth-flat { border-color: rgba(234,179,8,0.4); background: rgba(234,179,8,0.05); }
.synth-icon { font-size: 1.4rem; line-height: 1.3; }
.synth-body { display: flex; flex-direction: column; gap: 4px; }
.synth-title { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.04em; color: var(--text-muted); }
.synth-text { font-size: 0.92rem; line-height: 1.6; color: var(--text-primary); }

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
  .struct-cards, .flow-cards { grid-template-columns: repeat(2, 1fr); }
  .retail-cards { grid-template-columns: 1fr; }
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
