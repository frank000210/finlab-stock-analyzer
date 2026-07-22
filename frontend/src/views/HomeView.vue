<template>
  <div class="home-page">
    <section class="hero-section">
      <div class="hero-orb hero-orb-blue"></div>
      <div class="hero-orb hero-orb-purple"></div>

      <div class="hero-copy">
        <p class="hero-badge">專為台股投資研究打造的智慧工作台</p>
        <h1>AI 驅動的台股分析平台</h1>
        <p class="hero-subtitle">
          技術面、基本面、籌碼面三維度智慧分析，助你做出明智投資決策
        </p>
      </div>

      <form class="hero-search" @submit.prevent="search">
        <div class="search-field">
          <span class="search-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M21 21L16.65 16.65M18 10.5C18 14.6421 14.6421 18 10.5 18C6.35786 18 3 14.6421 3 10.5C3 6.35786 6.35786 3 10.5 3C14.6421 3 18 6.35786 18 10.5Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
          <input
            v-model="searchQuery"
            type="text"
            class="hero-input"
            placeholder="輸入股票代碼或名稱，例如 2330 或 台積電"
            aria-label="搜尋台股"
          />
        </div>
        <button type="submit" class="search-submit">立即分析</button>
      </form>

      <div class="hero-actions">
        <RouterLink to="/decision" class="hero-action hero-action-primary">🎯 今日決策</RouterLink>
        <RouterLink to="/stocks/2330" class="hero-action hero-action-secondary">📊 台積電分析</RouterLink>
      </div>

      <div class="hero-pillars" aria-label="核心分析維度">
        <span>技術面</span>
        <span>基本面</span>
        <span>籌碼面</span>
      </div>
    </section>

    <section class="section-block" v-reveal>
      <div class="section-heading">
        <div>
          <h2>用一個首頁，快速進入完整研究流程</h2>
          <p>從搜尋、判讀到策略驗證，為台股投資決策提供機構級分析視角。</p>
        </div>
      </div>

      <div class="feature-grid">
        <article
          v-for="(feature, index) in featureCards"
          :key="feature.title"
          v-reveal="{ delay: index * 70 }"
          class="feature-card"
          :class="{ 'is-featured': feature.featured }"
        >
          <div class="feature-icon" :class="`icon-tone-${feature.tone}`">{{ feature.icon }}</div>
          <h3>{{ feature.title }}</h3>
          <p>{{ feature.description }}</p>
          <ul v-if="feature.points" class="feature-points">
            <li v-for="point in feature.points" :key="point">{{ point }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="section-block quick-start-panel" v-reveal>
      <div class="section-heading section-heading-split">
        <div>
          <h2>快速開始</h2>
          <p>從熱門台股代碼切入，立即查看技術、基本與籌碼訊號。</p>
        </div>
        <RouterLink to="/decision" class="text-link">前往今日決策</RouterLink>
      </div>

      <div class="chip-list">
        <button
          v-for="symbol in quickStartSymbols"
          :key="symbol"
          type="button"
          class="symbol-chip"
          @click="goToStock(symbol)"
        >
          <span class="chip-symbol">{{ symbol }}</span>
          <span class="chip-name">{{ stockNames[symbol] || '立即分析' }}</span>
        </button>
      </div>
    </section>

    <section class="section-block recent-panel" v-reveal>
      <div class="section-heading section-heading-split">
        <div>
          <h2>最近瀏覽的股票</h2>
          <p>延續你上一輪的研究進度，快速回到剛剛關注的標的。</p>
        </div>
        <div v-if="recentStocks.length" class="recent-actions">
          <button type="button" class="text-link text-button" @click="refreshRecentStocks">
            重新整理
          </button>
          <button type="button" class="text-link text-button danger" @click="clearAllRecent">
            清空
          </button>
        </div>
      </div>

      <div v-if="recentStocks.length" class="recent-grid">
        <div v-for="stock in recentStocks" :key="stock.symbol" class="recent-card-wrap">
          <RouterLink :to="`/stocks/${stock.symbol}`" class="recent-card">
            <div class="recent-topline">
              <div>
                <p class="recent-symbol">{{ stock.symbol }}</p>
                <p class="recent-name">{{ stock.name }}</p>
              </div>
              <span class="recent-badge">最近瀏覽</span>
            </div>

            <div class="recent-price-row">
              <span class="recent-price">{{ stock.priceText }}</span>
              <span :class="['recent-change', `trend-${stock.trend}`]">{{ stock.changeText }}</span>
            </div>

            <p class="recent-note">{{ stock.note }}</p>
          </RouterLink>
          <button
            type="button"
            class="recent-remove"
            :aria-label="`從最近瀏覽移除 ${stock.symbol}`"
            @click.stop.prevent="removeRecent(stock.symbol)"
          >✕</button>
        </div>
      </div>

      <div v-else class="recent-empty">
        <p>尚無最近瀏覽紀錄，從上方搜尋列或快速開始代碼展開第一輪研究。</p>
      </div>
    </section>

    <footer class="version-footer" v-if="versionInfo">
      <span>版本 v{{ versionInfo.version }}</span>
      <span v-if="versionInfo.buildTimeText">· 更新於 {{ versionInfo.buildTimeText }}</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStockStore } from '../stores/stock.js'
import { fetchLivePrices, clearLivePriceCache } from '../lib/livePriceCache'

const router = useRouter()
const stockStore = useStockStore()
const searchQuery = ref('')
const recentStockItems = ref([])
const versionInfo = ref(null)

const stockNames = {
  '1101': '台泥',
  '2303': '聯電',
  '2317': '鴻海',
  '2330': '台積電',
  '2454': '聯發科',
  '2603': '長榮',
  '2882': '國泰金',
  '2891': '中信金'
}

const quickStartSymbols = ['2330', '2317', '2454', '2303', '2882', '2603']

const featureCards = [
  {
    icon: '🎯',
    title: 'AI 決策信號',
    description: '整合技術、基本、籌碼三大維度加權評分，即時生成 BUY / HOLD / SELL 建議與信心度。',
    featured: true,
    tone: 'blue',
    points: ['三維加權綜合評分', '即時買賣建議與信心度', '逐檔主力成本 × 籌碼健診徽章']
  },
  {
    icon: '📈',
    title: '技術指標分析',
    description: 'K線、MA、RSI、MACD 完整技術圖表',
    tone: 'cyan',
  },
  {
    icon: '🧪',
    title: '策略回測',
    description: '四大策略歷史驗證，績效一目了然',
    tone: 'purple',
  },
  {
    icon: '🛡️',
    title: '風控監控',
    description: 'MDD 追蹤、斷路器保護',
    tone: 'warn',
  },
  {
    icon: '📰',
    title: '新聞可信度',
    description: 'AI 五層新聞分析，辨別市場噪音',
    tone: 'up',
  },
  {
    icon: '⚡',
    title: '即時數據',
    description: '台股價格、法人進出、月營收追蹤',
    tone: 'blue',
  }
]

const recentStocks = computed(() => recentStockItems.value)

function search() {
  const query = searchQuery.value.trim()
  if (!query) {
    return
  }

  // If input is numeric (stock code), navigate directly
  if (/^\d{4,6}$/.test(query)) {
    stockStore.setStock(query, stockNames[query] || '')
    router.push(`/stocks/${query}`)
    return
  }

  // If input is text (stock name), resolve via API
  fetch(`/api/v1/stocks/search?q=${encodeURIComponent(query)}`)
    .then(r => r.json())
    .then(res => {
      const items = res?.data?.items || res?.items || []
      const match = items.find(i => i.name_zh === query || i.name === query) || items[0]
      if (match && match.symbol) {
        stockStore.setStock(match.symbol, match.name_zh || match.name || query)
        router.push(`/stocks/${match.symbol}`)
      } else {
        stockStore.setStock(query, '')
        router.push(`/stocks/${encodeURIComponent(query)}`)
      }
    })
    .catch(() => {
      stockStore.setStock(query, '')
      router.push(`/stocks/${encodeURIComponent(query)}`)
    })
}

function goToStock(symbol) {
  stockStore.setStock(symbol, stockNames[symbol] || '')
  router.push(`/stocks/${symbol}`)
}

function refreshRecentStocks() {
  // Z8：fetchLivePrices() 有 60 秒快取，使用者按「重新整理」是明確要求拿
  // 最新報價，先清快取再查，不然可能在 60 秒內悄悄回傳舊資料。
  clearLivePriceCache()
  loadRecentStocks()
}

function loadRecentStocks() {
  try {
    const raw = localStorage.getItem('recentStocks')
    const parsed = JSON.parse(raw || '[]')
    recentStockItems.value = Array.isArray(parsed)
      ? parsed
          .map(normalizeRecentStock)
          .filter(Boolean)
          .slice(0, 6)
      : []
  } catch {
    recentStockItems.value = []
  }
  refreshLivePrices()
}

// Y4：saveRecent()（AnalysisView.vue）只存 {symbol, name}，從來沒有存過
// 價格，導致這裡永遠顯示「等待同步報價」的假占位文字。改成頁面載入時
// 直接查即時報價補上；只更新價格，漲跌%沒有可靠來源就維持原本誠實的
// 「最近檢視」文字，不去湊一個假的漲跌幅。
async function refreshLivePrices() {
  const symbols = recentStockItems.value.map(s => s.symbol)
  if (!symbols.length) return
  try {
    const result = await fetchLivePrices(symbols)
    recentStockItems.value = recentStockItems.value.map(stock => {
      const price = result[stock.symbol]?.price
      return price == null ? stock : { ...stock, priceText: formatPrice(price) }
    })
  } catch {
    // 抓不到即時報價就維持原本的「等待同步報價」文字，不讓整個清單壞掉
  }
}

function removeRecent(symbol) {
  let parsed = []
  try { parsed = JSON.parse(localStorage.getItem('recentStocks') || '[]') } catch { parsed = [] }
  const next = parsed.filter(item => {
    const sym = typeof item === 'string' ? item : (item?.symbol || item?.code || '')
    return String(sym).trim() !== symbol
  })
  localStorage.setItem('recentStocks', JSON.stringify(next))
  loadRecentStocks()
}

function clearAllRecent() {
  if (!window.confirm('確定要清空最近瀏覽紀錄嗎？')) return
  localStorage.removeItem('recentStocks')
  loadRecentStocks()
}

function normalizeRecentStock(item) {
  // Handle both old format (string) and new format (object)
  const rawSymbol = typeof item === 'string'
    ? item
    : String(item?.symbol || item?.code || '').trim()

  // Skip non-numeric symbols (Chinese names stored by old code)
  if (!rawSymbol || !/^\d{4,6}$/.test(rawSymbol)) {
    return null
  }

  const symbol = rawSymbol
  const numericPrice = toNumber(item?.price ?? item?.close ?? item?.lastPrice)
  const numericChange = toNumber(item?.change ?? item?.delta)
  const numericChangePct = toNumber(item?.changePct ?? item?.pct ?? item?.percent)
  const hasPrice = numericPrice !== null
  const hasChange = numericChange !== null
  const hasChangePct = numericChangePct !== null
  const trendValue = hasChange ? numericChange : hasChangePct ? numericChangePct : 0

  return {
    symbol,
    name: (typeof item === 'object' ? item?.name || item?.name_zh : '') || stockNames[symbol] || '台股個股',
    priceText: hasPrice ? formatPrice(numericPrice) : '等待同步報價',
    changeText: hasChange || hasChangePct ? formatChange(numericChange, numericChangePct) : '最近檢視',
    trend: trendValue > 0 ? 'up' : trendValue < 0 ? 'down' : 'flat',
    note: item?.note || item?.updatedAt || '重新開啟三維度分析總覽'
  }
}

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatPrice(value) {
  const decimals = value >= 100 ? 1 : 2
  return `NT$ ${value.toLocaleString('zh-TW', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

function formatChange(change, changePct) {
  const parts = []

  if (change !== null) {
    const signedChange = change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2)
    parts.push(signedChange)
  }

  if (changePct !== null) {
    const signedPct = changePct > 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`
    parts.push(`(${signedPct})`)
  }

  return parts.join(' ')
}

function handleStorageChange(event) {
  if (!event || event.key === 'recentStocks') {
    loadRecentStocks()
  }
}

function formatBuildTime(iso) {
  try {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return null
    return date.toLocaleString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  } catch {
    return null
  }
}

async function loadVersionInfo() {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    versionInfo.value = {
      version: data?.version || '—',
      buildTimeText: data?.build_time ? formatBuildTime(data.build_time) : null,
    }
  } catch {
    versionInfo.value = null
  }
}

onMounted(() => {
  loadRecentStocks()
  loadVersionInfo()
  window.addEventListener('storage', handleStorageChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('storage', handleStorageChange)
})
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: clamp(32px, 6vw, 72px);
  padding-bottom: clamp(24px, 4vw, 48px);
}

.hero-section,
.section-block {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  box-shadow: var(--shadow-lg);
}

.hero-section {
  padding: clamp(40px, 7vw, 88px);
  background:
    radial-gradient(circle at 18% 20%, rgba(59, 130, 246, 0.22), transparent 34%),
    radial-gradient(circle at 85% 15%, rgba(139, 92, 246, 0.2), transparent 30%),
    linear-gradient(135deg, var(--bg-primary) 0%, #111a34 46%, #1b1b3a 100%);
}

.hero-copy {
  position: relative;
  z-index: 1;
  max-width: 760px;
  margin: 0 auto;
  text-align: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  border-radius: 999px;
  margin-bottom: 20px;
  color: var(--text-primary);
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(59, 130, 246, 0.24);
}

.hero-section h1 {
  margin: 0;
  font-size: clamp(2.8rem, 7vw, 5.5rem);
  letter-spacing: -0.035em;
  line-height: 0.96;
  text-wrap: balance;
}

.hero-subtitle {
  max-width: 34rem;
  margin: 20px auto 0;
  font-size: clamp(1rem, 2vw, 1.2rem);
  color: var(--text-secondary);
  text-wrap: pretty;
}

.hero-search {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: center;
  max-width: 860px;
  margin: 36px auto 0;
}

.search-field {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-height: 72px;
  padding: 0 22px;
  border-radius: calc(var(--radius-xl) - 2px);
  background: rgba(11, 17, 33, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.24);
  box-shadow: 0 20px 60px rgba(11, 17, 33, 0.35);
}

.search-icon {
  display: inline-flex;
  color: var(--text-secondary);
}

.search-icon svg {
  width: 24px;
  height: 24px;
}

.hero-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 1.08rem;
}

.hero-input::placeholder {
  color: var(--text-secondary);
}

.search-submit,
.hero-action,
.symbol-chip,
.text-button {
  transition:
    transform var(--transition-base),
    border-color var(--transition-base),
    box-shadow var(--transition-base),
    background var(--transition-base),
    color var(--transition-base);
}

.search-submit {
  min-height: 72px;
  padding: 0 28px;
  border: 1px solid transparent;
  border-radius: calc(var(--radius-xl) - 2px);
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 18px 36px rgba(59, 130, 246, 0.28);
}

.hero-actions {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
  margin-top: 24px;
}

.hero-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 0 22px;
  border-radius: var(--radius-lg);
  text-decoration: none;
  font-weight: 700;
}

.hero-action-primary {
  color: var(--text-primary);
  background: var(--bg-elevated);
  border: 1px solid rgba(59, 130, 246, 0.28);
}

.hero-action-secondary {
  color: var(--text-primary);
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.hero-pillars {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 30px;
}

.hero-pillars span {
  padding: 10px 16px;
  border-radius: 999px;
  color: var(--text-secondary);
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.hero-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(10px);
  opacity: 0.85;
  pointer-events: none;
}

.hero-orb-blue {
  top: -80px;
  left: -40px;
  width: 220px;
  height: 220px;
  background: rgba(59, 130, 246, 0.18);
  animation: floatBlue 16s ease-in-out infinite;
}

.hero-orb-purple {
  right: -20px;
  bottom: -90px;
  width: 260px;
  height: 260px;
  background: rgba(139, 92, 246, 0.16);
  animation: floatPurple 18s ease-in-out infinite;
}

.section-block {
  padding: clamp(32px, 5vw, 48px);
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}

.section-heading h2 {
  margin: 0;
  font-size: clamp(1.8rem, 3vw, 2.4rem);
  text-wrap: balance;
}

.section-heading p {
  max-width: 44rem;
  margin-top: 10px;
}

.section-heading-split {
  align-items: center;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: 1fr;
  gap: 20px;
}

.feature-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 190px;
  padding: 28px;
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(31, 45, 71, 0.92), rgba(26, 37, 64, 0.96));
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

/* Bento：主特色卡放大為 2×2，建立層次而非等大方格 */
.feature-card.is-featured {
  grid-column: span 2;
  grid-row: span 2;
  padding: 36px;
  background:
    radial-gradient(120% 120% at 0% 0%, rgba(59, 130, 246, 0.22), transparent 55%),
    linear-gradient(165deg, rgba(31, 45, 71, 0.96), rgba(20, 29, 47, 0.98));
  border-color: rgba(59, 130, 246, 0.32);
}

.feature-card.is-featured .feature-icon {
  width: 64px;
  height: 64px;
  font-size: 1.8rem;
  margin-bottom: 22px;
}

.feature-card.is-featured h3 {
  font-size: 1.7rem;
}

.feature-card.is-featured p {
  max-width: 46ch;
  color: var(--text-secondary);
}

.feature-points {
  list-style: none;
  margin: auto 0 0;
  padding: 18px 0 0;
  display: grid;
  gap: 10px;
}

.feature-points li {
  position: relative;
  padding-left: 26px;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.feature-points li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 0.5em;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent-cyan, #3b82f6);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.16);
}

.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  margin-bottom: 18px;
  border-radius: 16px;
  background: rgba(59, 130, 246, 0.12);
  font-size: 1.4rem;
}

/* 色塊圖示:每張特色卡用不同色調的光暈邊框做視覺分群，取代原本統一藍色 */
.icon-tone-blue { background: rgba(59, 130, 246, 0.14); box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.3); }
.icon-tone-cyan { background: rgba(6, 182, 212, 0.14); box-shadow: inset 0 0 0 1px rgba(6, 182, 212, 0.3); }
.icon-tone-purple { background: rgba(139, 92, 246, 0.14); box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.3); }
.icon-tone-warn { background: var(--warn-soft); box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.3); }
.icon-tone-up { background: var(--up-soft); box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.3); }

.feature-card h3 {
  margin: 0;
  font-size: 1.15rem;
}

.feature-card p {
  margin-top: 10px;
}

.quick-start-panel {
  background:
    linear-gradient(180deg, rgba(26, 37, 64, 0.92), rgba(20, 29, 47, 0.98));
}

.text-link,
.text-button {
  color: var(--accent-cyan);
  text-decoration: none;
  font-weight: 600;
}

.text-button {
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.symbol-chip {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  padding: 0 18px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.chip-symbol {
  font-weight: 800;
}

.chip-name {
  color: var(--text-secondary);
  font-size: 0.92rem;
}

.recent-panel {
  background:
    radial-gradient(circle at 100% 0%, rgba(6, 182, 212, 0.08), transparent 28%),
    linear-gradient(180deg, rgba(26, 37, 64, 0.96), rgba(11, 17, 33, 0.98));
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.recent-actions {
  display: flex;
  gap: 14px;
}
.text-button.danger {
  color: #ef4444;
}

.recent-card-wrap {
  position: relative;
}

.recent-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
  border-radius: var(--radius-lg);
  text-decoration: none;
  background: rgba(20, 29, 47, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: var(--shadow-md);
}

.recent-remove {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(20, 29, 47, 0.95);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.78rem;
  line-height: 1;
  z-index: 1;
}
.recent-remove:hover {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.4);
}

.recent-topline {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.recent-symbol {
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--text-primary);
}

.recent-name {
  margin-top: 2px;
  color: var(--text-secondary);
}

.recent-badge {
  align-self: flex-start;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
}

.recent-price-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}

.recent-price {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.recent-change {
  font-size: 0.95rem;
  font-weight: 700;
}

.recent-note {
  color: var(--text-secondary);
}

.recent-empty {
  padding: 32px;
  border-radius: var(--radius-lg);
  background: rgba(20, 29, 47, 0.88);
  border: 1px dashed rgba(148, 163, 184, 0.2);
}

.trend-up {
  color: var(--color-up);
}

.trend-down {
  color: var(--color-down);
}

.trend-flat {
  color: var(--text-secondary);
}

@media (prefers-reduced-motion: no-preference) {
  .feature-card:hover,
  .recent-card:hover,
  .symbol-chip:hover,
  .hero-action:hover,
  .search-submit:hover,
  .text-button:hover {
    transform: translateY(-3px);
  }

  .feature-card:hover,
  .recent-card:hover {
    border-color: rgba(139, 92, 246, 0.34);
    box-shadow:
      0 18px 48px rgba(11, 17, 33, 0.32),
      0 0 0 1px rgba(139, 92, 246, 0.16),
      0 0 24px rgba(59, 130, 246, 0.16);
  }

  .symbol-chip:hover,
  .hero-action:hover,
  .text-button:hover {
    border-color: rgba(59, 130, 246, 0.3);
    box-shadow: 0 14px 30px rgba(11, 17, 33, 0.24);
  }

  .search-submit:hover {
    box-shadow: 0 24px 44px rgba(59, 130, 246, 0.34);
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-orb,
  .feature-card,
  .recent-card,
  .symbol-chip,
  .hero-action,
  .search-submit,
  .text-button {
    animation: none;
    transition: none;
  }
}

@media (max-width: 900px) {
  .hero-search {
    flex-direction: column;
  }

  .search-field,
  .search-submit {
    width: 100%;
  }

  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .feature-card.is-featured {
    grid-column: span 2;
    grid-row: span 1;
  }
}

@media (max-width: 640px) {
  .hero-section,
  .section-block {
    border-radius: var(--radius-lg);
  }

  .hero-section {
    padding: 32px 24px;
  }

  .hero-section h1 {
    font-size: clamp(2.4rem, 14vw, 4rem);
  }

  .hero-search {
    margin-top: 28px;
  }

  .search-field,
  .search-submit {
    min-height: 64px;
  }

  .section-heading,
  .recent-topline,
  .recent-price-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .feature-card.is-featured {
    grid-column: span 1;
    grid-row: span 1;
    padding: 28px;
  }

  .feature-card.is-featured h3 {
    font-size: 1.4rem;
  }

  .chip-list {
    gap: 12px;
  }

  .symbol-chip {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 420px) {
  .hero-section {
    padding: 24px 16px;
  }

  .hero-section h1 {
    font-size: clamp(1.8rem, 12vw, 2.8rem);
  }

  .search-field,
  .search-submit {
    min-height: 52px;
    font-size: 0.9rem;
  }

  .search-submit {
    padding: 0 20px;
  }

  .section-block {
    padding: 16px;
  }

  .recent-item {
    padding: 10px 0;
  }
}

.version-footer {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.78rem;
  opacity: 0.7;
}

@keyframes floatBlue {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(18px, 14px, 0) scale(1.05);
  }
}

@keyframes floatPurple {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-18px, -14px, 0) scale(1.07);
  }
}
</style>
