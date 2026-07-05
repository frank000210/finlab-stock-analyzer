<template>
  <div class="buzz-page">
    <PageFocusBanner text="觀察社群與新聞討論熱度及情緒，判斷市場是否過度樂觀或悲觀。" />

    <header class="page-header">
      <div>
        <h1>🔥 社群熱度分析</h1>
        <p class="subtitle">追蹤個股在 PTT、新聞、社群的討論度與情緒</p>
      </div>
      <div class="controls">
        <input v-model="symbol" placeholder="股票代號" class="input-symbol" @keyup.enter="fetchData" />
        <button class="btn btn-primary" @click="fetchData" :disabled="loading">
          {{ loading ? '搜尋中...' : '查詢熱度' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="card error-card">⚠️ {{ error }}</div>

    <div v-if="data" class="results">
      <!-- Buzz Score -->
      <section class="score-section">
        <div class="card buzz-score-card">
          <div class="buzz-gauge">
            <svg viewBox="0 0 120 70" class="gauge-svg">
              <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="var(--bg-tertiary)" stroke-width="10" stroke-linecap="round"/>
              <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" :stroke="gaugeColor" stroke-width="10" stroke-linecap="round"
                :stroke-dasharray="157" :stroke-dashoffset="157 - (data.buzz_score / 100) * 157"/>
            </svg>
            <div class="gauge-value">{{ data.buzz_score }}</div>
            <div class="gauge-label">熱度分數</div>
          </div>
          <div class="buzz-info">
            <span class="buzz-level" :class="'level-' + data.buzz_level">{{ data.buzz_level }}</span>
            <p class="buzz-desc">{{ data.buzz_description }}</p>
          </div>
        </div>

        <div class="card trend-card">
          <div class="trend-row">
            <span class="trend-icon">{{ data.trend === 'rising' ? '📈' : data.trend === 'falling' ? '📉' : '➡️' }}</span>
            <div>
              <div class="trend-label">趨勢</div>
              <div class="trend-value">{{ data.trend_label }}</div>
            </div>
          </div>
          <div class="trend-row">
            <span class="trend-icon">{{ data.sentiment === 'bullish' ? '🟢' : data.sentiment === 'bearish' ? '🔴' : '⚪' }}</span>
            <div>
              <div class="trend-label">情緒</div>
              <div class="trend-value">{{ data.sentiment_label }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- Volume Attention -->
      <section class="card" v-if="data.volume_attention">
        <h2>📊 成交量注意力</h2>
        <div class="vol-grid">
          <div class="vol-item">
            <span class="vol-label">量比 (近5日/20MA)</span>
            <span class="vol-value" :class="data.volume_attention.volume_ratio > 2 ? 'hot' : ''">
              {{ data.volume_attention.volume_ratio }}x
            </span>
          </div>
          <div class="vol-item">
            <span class="vol-label">5日均量</span>
            <span class="vol-value">{{ formatVol(data.volume_attention.avg_volume_5d) }}</span>
          </div>
          <div class="vol-item">
            <span class="vol-label">20日均量</span>
            <span class="vol-value">{{ formatVol(data.volume_attention.avg_volume_20d) }}</span>
          </div>
          <div class="vol-item">
            <span class="vol-label">爆量偵測</span>
            <span class="vol-value" :class="data.volume_attention.volume_surge ? 'hot' : ''">
              {{ data.volume_attention.volume_surge ? '⚡ 是' : '否' }}
            </span>
          </div>
        </div>
      </section>

      <!-- PTT -->
      <section class="card">
        <h2>💬 PTT 股板討論</h2>
        <div class="source-meta">
          <span>文章數: <strong>{{ data.ptt.post_count }}</strong></span>
          <span>看多: <strong class="positive">{{ data.ptt.bullish_count }}</strong></span>
          <span>看空: <strong class="negative">{{ data.ptt.bearish_count }}</strong></span>
        </div>
        <div class="posts-list" v-if="data.ptt.posts.length">
          <component
            :is="p.url ? 'a' : 'div'"
            v-for="(p, i) in data.ptt.posts"
            :key="i"
            class="post-item"
            :href="p.url || undefined"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span class="post-push" v-if="p.push_count">{{ p.push_count }}</span>
            <span class="post-title">{{ p.title }}</span>
            <span class="post-date">{{ p.date }}</span>
            <span class="ext-link" v-if="p.url">↗</span>
          </component>
        </div>
        <p v-else class="no-data">未搜尋到相關文章</p>
      </section>

      <!-- News -->
      <section class="card">
        <h2>📰 新聞曝光</h2>
        <div class="source-meta">
          <span>新聞篇數: <strong>{{ data.news.article_count }}</strong></span>
        </div>
        <div class="news-list" v-if="data.news.articles.length">
          <component
            :is="a.url ? 'a' : 'div'"
            v-for="(a, i) in data.news.articles"
            :key="i"
            class="news-item"
            :href="a.url || undefined"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span class="news-title">{{ a.title }}</span>
            <span class="news-source">{{ a.source }}</span>
            <span class="ext-link" v-if="a.url">↗</span>
          </component>
        </div>
        <p v-else class="no-data">未搜尋到相關新聞</p>
      </section>

      <!-- Fact Check -->
      <section class="card" v-if="data.fact_check">
        <h2>🔍 事實查核（台灣事實查核中心）</h2>
        <div class="source-meta">
          <span>相關查核/文章: <strong>{{ data.fact_check.check_count }}</strong></span>
          <a class="tfc-link" :href="data.fact_check.source_url" target="_blank" rel="noopener noreferrer">前往查核中心 ↗</a>
        </div>
        <div class="news-list" v-if="data.fact_check.items && data.fact_check.items.length">
          <a
            v-for="(f, i) in data.fact_check.items"
            :key="i"
            class="news-item"
            :href="f.url"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span class="fc-verdict" :class="verdictClass(f.verdict)">{{ f.verdict }}</span>
            <span class="news-title">{{ f.title }}</span>
            <span class="ext-link">↗</span>
          </a>
        </div>
        <p v-else class="no-data">查核中心目前沒有與本股票相關的查核報告</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { useChartTheme } from '../composables/useChartTheme'

const route = useRoute()
const stockStore = useStockStore()
const theme = useChartTheme()
const symbol = ref(route.params.symbol || stockStore.symbol)
const loading = ref(false)
const error = ref('')
const data = ref(null)

const gaugeColor = computed(() => {
  if (!data.value) return 'var(--text-muted)'
  const s = data.value.buzz_score
  if (s >= 80) return theme.down
  if (s >= 60) return theme.warn
  if (s >= 40) return theme.warn
  if (s >= 20) return theme.up
  return 'var(--text-muted)'
})

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/stocks/${symbol.value}/social-buzz`)
    const json = await res.json()
    if (json.success) {
      data.value = json.data
    } else {
      error.value = json.error || '查詢失敗'
    }
  } catch (e) {
    error.value = '無法連線到伺服器'
  } finally {
    loading.value = false
  }
}

function formatVol(v) {
  if (!v) return '0'
  if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M'
  if (v >= 1000) return (v / 1000).toFixed(0) + 'K'
  return v.toString()
}

function verdictClass(verdict) {
  if (!verdict) return 'fc-neutral'
  if (verdict.includes('錯誤')) return 'fc-false'
  if (verdict.includes('釐清') || verdict.includes('正確')) return 'fc-clarify'
  return 'fc-neutral'
}

onMounted(fetchData)
</script>

<style scoped>
.buzz-page { display: flex; flex-direction: column; gap: var(--space-5); }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-4); }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
.controls { display: flex; gap: 8px; align-items: center; }
.input-symbol { width: 90px; padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font-weight: 700; text-align: center; }
.error-card { color: var(--color-down); background: var(--down-soft); border: 1px solid rgba(239, 68, 68, 0.3); }

.score-section { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.buzz-score-card { display: flex; align-items: center; gap: 20px; }
.buzz-gauge { position: relative; text-align: center; }
.gauge-svg { width: 120px; height: 70px; }
.gauge-value { font-size: 2rem; font-weight: 800; margin-top: -10px; }
.gauge-label { font-size: 0.7rem; color: var(--text-muted); }
.buzz-info { flex: 1; }
.buzz-level { display: inline-block; padding: 3px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; margin-bottom: 8px; }
.level-極高 { background: var(--down-soft); color: var(--color-down); }
.level-高 { background: var(--warn-soft); color: #f97316; }
.level-中等 { background: var(--warn-soft); color: #eab308; }
.level-低 { background: var(--up-soft); color: #22c55e; }
.level-極低 { background: rgba(156, 163, 175, 0.15); color: var(--text-muted); }
.buzz-desc { font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; }

.trend-card { display: flex; flex-direction: column; gap: 16px; justify-content: center; }
.trend-row { display: flex; align-items: center; gap: 12px; }
.trend-icon { font-size: 1.5rem; }
.trend-label { font-size: 0.72rem; color: var(--text-muted); }
.trend-value { font-size: 0.9rem; font-weight: 600; }

.vol-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); }
.vol-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
.vol-label { font-size: 0.78rem; color: var(--text-muted); }
.vol-value { font-weight: 700; font-size: 0.9rem; }
.vol-value.hot { color: var(--color-down); }

.source-meta { display: flex; gap: 16px; margin-bottom: 12px; font-size: 0.82rem; color: var(--text-secondary); }
.positive { color: var(--accent-green); }
.negative { color: var(--accent-red); }

.posts-list, .news-list { display: flex; flex-direction: column; gap: 6px; }
.post-item, .news-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--bg-tertiary); border-radius: var(--radius-sm); font-size: 0.82rem; color: var(--text-primary); text-decoration: none; }
a.post-item:hover, a.news-item:hover { background: var(--bg-hover); }
a.post-item:hover .post-title, a.news-item:hover .news-title { color: var(--accent-blue); }
.ext-link { color: var(--text-muted); font-size: 0.75rem; flex-shrink: 0; }
.tfc-link { color: var(--accent-cyan); text-decoration: none; font-size: 0.8rem; margin-left: auto; }
.fc-verdict { flex-shrink: 0; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; }
.fc-false { background: var(--down-soft); color: var(--color-down); }
.fc-clarify { background: var(--up-soft); color: var(--color-up); }
.fc-neutral { background: rgba(100, 116, 139, 0.15); color: var(--text-muted); }
.post-push { background: var(--accent-blue); color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; min-width: 28px; text-align: center; }
.post-title, .news-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.post-date { font-size: 0.7rem; color: var(--text-muted); }
.news-source { font-size: 0.7rem; color: var(--text-muted); white-space: nowrap; }
.no-data { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .score-section { grid-template-columns: 1fr; }
  .buzz-score-card { flex-direction: column; text-align: center; }
}
@media (max-width: 420px) {
  .vol-grid { grid-template-columns: 1fr 1fr; }
  .source-meta { flex-direction: column; gap: 4px; }
}
</style>