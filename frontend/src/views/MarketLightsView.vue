<template>
  <div class="lights-view">
    <PageFocusBanner text="用三個實證等級標明的燈號判讀大盤體制：訊號矛盾時誠實顯示「僵持」，不硬湊假中性。" />

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>🚦 大盤多空儀表板 <InfoTooltip v-bind="metricGlossary.marketLights" /></h2>
          <p class="muted">趨勢（A 級實證）定體制，籌碼燈（B 級）做修正——體制為狀態描述，非漲跌預測。</p>
        </div>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <div v-if="loading && !data" class="loading-placeholder">
        <span class="loading-spinner" aria-hidden="true"></span>載入大盤資料中...
      </div>

      <template v-if="data">
        <!-- 綜合體制 banner -->
        <div class="combined-banner" :class="'regime-' + data.combined.regime">
          <div class="combined-main">
            <span class="combined-label">{{ data.combined.label }}</span>
            <span class="combined-conf">信心度：{{ confidenceLabel }}</span>
          </div>
          <p class="combined-narrative">{{ data.combined.narrative }}</p>
        </div>

        <!-- 三燈卡片 -->
        <div class="lights-grid">
          <!-- 趨勢燈 -->
          <article class="card light-card" v-if="data.lights.trend">
            <div class="light-head">
              <h3>趨勢燈 <InfoTooltip v-bind="metricGlossary.trendLight" /></h3>
              <span class="evidence-badge a">實證 A 級</span>
            </div>
            <div class="light-status" :class="'tone-' + data.lights.trend.tone">
              {{ data.lights.trend.above_ma200 ? '年線之上（多頭結構）' : '年線之下（空頭結構）' }}
            </div>
            <div class="light-stats">
              <span>0050：{{ data.lights.trend.close }}</span>
              <span>年線：{{ data.lights.trend.ma200 }}（{{ data.lights.trend.ma200_rising ? '上揚' : '走平/下彎' }}）</span>
              <span>20日動能：{{ data.lights.trend.mom20_pct >= 0 ? '+' : '' }}{{ data.lights.trend.mom20_pct }}%</span>
            </div>
            <p class="light-narrative">長期趨勢濾網：抓不到精準轉折，但能避開最深的回撤段。此燈為唯一自動連動作戰台風險係數（×{{ data.lights.trend.risk_mult }}）的燈。</p>
            <DataLineage :as-of="data.lights.trend.as_of" />
          </article>

          <!-- 外資期貨燈 -->
          <article class="card light-card" v-if="data.lights.foreign_futures">
            <div class="light-head">
              <h3>外資期貨燈 <InfoTooltip v-bind="metricGlossary.foreignFuturesLight" /></h3>
              <span class="evidence-badge b">實證 B 級</span>
            </div>
            <div class="light-status" :class="'tone-' + data.lights.foreign_futures.tone">
              {{ foreignStatusText }}
              <em v-if="data.lights.foreign_futures.settlement_week" class="settle-tag">結算週</em>
            </div>
            <div class="light-stats">
              <span>淨未平倉：{{ fmtYi(data.lights.foreign_futures.net_amount_yi) }} 億</span>
              <span v-if="data.lights.foreign_futures.rolling_percentile != null">近一年百分位：{{ data.lights.foreign_futures.rolling_percentile }}%</span>
              <span v-if="data.lights.foreign_futures.chg5_yi != null">5日變化：{{ data.lights.foreign_futures.chg5_yi >= 0 ? '+' : '' }}{{ fmtYi(data.lights.foreign_futures.chg5_yi) }} 億</span>
            </div>
            <svg v-if="foreignSpark" class="light-spark" viewBox="0 0 200 36" preserveAspectRatio="none">
              <polyline :points="foreignSpark" fill="none" stroke="currentColor" stroke-width="1.5" />
            </svg>
            <p class="light-narrative">{{ data.lights.foreign_futures.narrative }}</p>
            <DataLineage :as-of="data.lights.foreign_futures.as_of" />
            <p class="publish-note">{{ data.lights.foreign_futures.publish_note }}</p>
          </article>
          <article class="card light-card light-failed" v-else>
            <div class="light-head"><h3>外資期貨燈</h3><span class="evidence-badge b">實證 B 級</span></div>
            <p class="muted">資料暫時無法取得，本次判讀不含此燈。</p>
          </article>

          <!-- 融資燈 -->
          <article class="card light-card" v-if="data.lights.margin">
            <div class="light-head">
              <h3>融資燈 <InfoTooltip v-bind="metricGlossary.marginLight" /></h3>
              <span class="evidence-badge b">實證 B 級</span>
            </div>
            <div class="light-status" :class="'tone-' + data.lights.margin.tone">{{ marginStatusText }}</div>
            <div class="light-stats">
              <span>融資餘額：{{ fmtYi(data.lights.margin.balance_yi) }} 億</span>
              <span>單日：{{ data.lights.margin.d1_pct >= 0 ? '+' : '' }}{{ data.lights.margin.d1_pct }}%</span>
              <span>20日：{{ data.lights.margin.d20_pct >= 0 ? '+' : '' }}{{ data.lights.margin.d20_pct }}%</span>
            </div>
            <svg v-if="marginSpark" class="light-spark" viewBox="0 0 200 36" preserveAspectRatio="none">
              <polyline :points="marginSpark" fill="none" stroke="currentColor" stroke-width="1.5" />
            </svg>
            <p class="light-narrative">{{ data.lights.margin.narrative }}</p>
            <DataLineage :as-of="data.lights.margin.as_of" />
            <p class="publish-note">{{ data.lights.margin.publish_note }}</p>
          </article>
          <article class="card light-card light-failed" v-else>
            <div class="light-head"><h3>融資燈</h3><span class="evidence-badge b">實證 B 級</span></div>
            <p class="muted">資料暫時無法取得，本次判讀不含此燈。</p>
          </article>
        </div>

        <p class="disclaimer">
          ※ {{ data.calibration_note }}<br />
          ※ 本儀表板僅為市場狀態描述與風險參考，非投資建議。
        </p>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import DataLineage from '../components/DataLineage.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { useSparkline } from '../composables/useSparkline'
import { fetchWithRetry } from '../lib/apiFetch'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const data = ref(null)
const loading = ref(false)
const errorMessage = ref('')

const confidenceLabel = computed(() => {
  const c = data.value?.combined?.confidence
  return c === 'high' ? '高（三燈同向）' : c === 'medium' ? '中（籌碼燈無矛盾）' : '低（訊號矛盾中）'
})

const foreignStatusText = computed(() => {
  const s = data.value?.lights?.foreign_futures?.status
  return {
    extreme_short: '極端淨空（相對自身常態）',
    bullish_shift: '部位轉多（相對自身常態）',
    neutral: '常態區間',
    insufficient: '資料不足',
  }[s] || s
})

const marginStatusText = computed(() => {
  const s = data.value?.lights?.margin?.status
  return {
    shock: '斷頭潮（賣壓釋放中）',
    sharp_decline: '急減（去槓桿進行中）',
    stabilizing: '止穩（賣壓釋放尾聲）',
    overheated: '槓桿過熱',
    deleveraging: '持續去槓桿',
    normal: '常態區間',
  }[s] || s
})

const foreignValues = computed(() => (data.value?.lights?.foreign_futures?.history || []).map(h => h.value))
const { points: foreignSpark } = useSparkline(foreignValues, { width: 200, height: 36 })
const marginValues = computed(() => (data.value?.lights?.margin?.history || []).map(h => h.value))
const { points: marginSpark } = useSparkline(marginValues, { width: 200, height: 36 })

function fmtYi(v) {
  return v == null ? '—' : Math.abs(v) >= 1000
    ? Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
    : Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const resp = await fetchWithRetry(`${API_BASE}/api/v1/market/lights`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || !payload?.data) throw new Error(payload?.detail || '查詢失敗')
    data.value = payload.data
  } catch (e) {
    errorMessage.value = e?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.lights-view { display: flex; flex-direction: column; gap: 16px; }
.head-row h2 { margin: 0 0 4px; }
.muted { color: var(--text-muted); }

.loading-placeholder { display: flex; align-items: center; gap: 8px; font-size: 0.84rem; color: var(--text-muted); padding: 8px 0; }
.loading-placeholder .loading-spinner { width: 14px; height: 14px; border-width: 2px; }

.combined-banner { margin-top: 14px; border-radius: 14px; padding: 16px 18px; border: 1px solid var(--border-color); }
.combined-banner.regime-bull { border-color: rgba(16,185,129,0.5); background: rgba(16,185,129,0.07); }
.combined-banner.regime-bear { border-color: rgba(239,68,68,0.5); background: rgba(239,68,68,0.07); }
.combined-banner.regime-stalemate { border-color: rgba(245,158,11,0.5); background: rgba(245,158,11,0.07); }
.combined-main { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.combined-label { font-size: 1.5rem; font-weight: 800; }
.regime-bull .combined-label { color: #10b981; }
.regime-bear .combined-label { color: #ef4444; }
.regime-stalemate .combined-label { color: #f59e0b; }
.combined-conf { font-size: 0.8rem; color: var(--text-muted); }
.combined-narrative { margin: 8px 0 0; font-size: 0.86rem; line-height: 1.7; color: var(--text-secondary); }

.lights-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 14px; }
.light-card { display: flex; flex-direction: column; gap: 8px; padding: 16px; }
.light-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.light-head h3 { margin: 0; font-size: 0.95rem; }
.evidence-badge { font-size: 0.66rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.evidence-badge.a { background: rgba(16,185,129,0.15); color: #10b981; }
.evidence-badge.b { background: rgba(59,130,246,0.15); color: var(--accent-blue); }
.light-status { font-size: 1.02rem; font-weight: 700; }
.light-status.tone-good { color: #10b981; }
.light-status.tone-bad { color: #ef4444; }
.light-status.tone-warn { color: #f59e0b; }
.light-status.tone-flat { color: var(--text-secondary); }
.settle-tag { font-size: 0.66rem; font-style: normal; margin-left: 6px; padding: 1px 6px; border-radius: 6px; background: rgba(245,158,11,0.15); color: #f59e0b; vertical-align: middle; }
.light-stats { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 0.78rem; color: var(--text-muted); }
.light-spark { width: 100%; height: 36px; color: var(--accent-blue); opacity: 0.85; }
.light-narrative { margin: 0; font-size: 0.8rem; line-height: 1.65; color: var(--text-secondary); }
.publish-note { margin: 0; font-size: 0.7rem; color: var(--text-muted); }
.light-failed { opacity: 0.75; }
.disclaimer { margin-top: 14px; font-size: 0.72rem; color: var(--text-muted); line-height: 1.6; }
.error-text { color: #ef4444; font-size: 0.84rem; }
</style>
