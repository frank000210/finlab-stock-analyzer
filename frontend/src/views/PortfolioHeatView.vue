<template>
  <div class="portfolio-heat-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">🔥 觀測重點</span>
      單筆控好，還會被「同時壓太多、又高度相關」的部位殺死。這裡盯的是整個投組的<strong>總風險熱度</strong>與<strong>產業集中度</strong>。
    </div>

    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>投組總風險（Portfolio Heat）</h2>
          <p class="muted">把每個部位的「風險金額」加總，控管總曝險不超過帳戶的安全上限。</p>
        </div>
        <label class="acct">帳戶資金 (TWD)
          <input v-model.number="account" type="number" min="0" step="10000" class="inp" @change="save" />
        </label>
      </div>

      <!-- 總覽 -->
      <div class="summary-cards">
        <div class="scard heat" :class="heatLevel">
          <span class="slabel">總風險熱度</span>
          <strong class="sval">{{ totalHeat.toFixed(2) }}%</strong>
          <span class="shint">{{ heatText }}</span>
          <span v-if="journalOnlyPositions.length" class="shint">
            含交易日誌 {{ journalOnlyPositions.length }} 檔進行中部位（{{ journalHeatPct.toFixed(2) }}%）
          </span>
        </div>
        <div class="scard"><span class="slabel">部位數</span><strong class="sval">{{ positions.length }}</strong></div>
        <div class="scard"><span class="slabel">總部位金額</span><strong class="sval">{{ fmtInt(totalValue) }}</strong><span class="shint">佔資金 {{ deployedPct.toFixed(1) }}%</span></div>
        <div class="scard"><span class="slabel">未實現損益</span><strong class="sval" :class="totalUnrealized >= 0 ? 'up' : 'down'">{{ fmtInt(totalUnrealized) }}</strong></div>
      </div>
      <div v-if="positions.length" class="notify-row">
        <button class="btn" :disabled="notifying" @click="notifyRisk">🔔 推播風險摘要</button>
        <span v-if="notifyMsg" class="muted small">{{ notifyMsg }}</span>
      </div>
    </section>

    <section class="section-block" v-reveal>
      <h3>新增部位</h3>
      <div class="add-form">
        <input v-model="form.symbol" class="inp" placeholder="代碼 2330" @keyup.enter="addPosition" />
        <input v-model.number="form.entry" type="number" class="inp" placeholder="進場價" step="0.05" @keyup.enter="addPosition" />
        <input v-model.number="form.stop" type="number" class="inp" placeholder="停損價" step="0.05" @keyup.enter="addPosition" />
        <input v-model.number="form.lots" type="number" class="inp" placeholder="張數" min="1" step="1" @keyup.enter="addPosition" />
        <button class="btn btn-primary" @click="addPosition">加入</button>
        <button class="btn" :disabled="importing" @click="importFromWatchlist">
          <span v-if="importing" class="loading-spinner btn-spinner" aria-hidden="true"></span>從觀察清單匯入
        </button>
        <button v-if="positions.length" class="btn" @click="clearAll">清空</button>
        <button v-if="positions.length" class="btn" @click="exportPositionsCsv">📥 匯出 CSV</button>
      </div>
      <p v-if="formError" class="error-text">{{ formError }}</p>
      <p v-if="importMsg" class="muted import-msg">{{ importMsg }}</p>

      <div class="table-wrap" v-if="positions.length">
        <table class="pos-table">
          <thead>
            <tr>
              <th>代碼</th><th>產業</th><th>進場</th><th>停損</th><th>張數</th>
              <th>部位金額</th><th>風險金額</th><th>風險%</th><th>未實現</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in positions" :key="p.symbol + '-' + i">
              <td class="sym">
                {{ p.symbol }}<small>{{ p.name && p.name !== p.symbol ? ' ' + p.name : '' }}</small>
                <span v-if="p.enrichFailed && !p.price" class="enrich-warn" title="查價失敗，現價暫時是 0，風險/相關性計算會低估這筆部位——建議重新整理頁面重試">⚠現價未知</span>
              </td>
              <td class="muted">{{ p.industry || '—' }}</td>
              <td>{{ fmt(p.entry) }}</td>
              <td>{{ fmt(p.stop) }}</td>
              <td>{{ p.lots }}</td>
              <td>{{ fmtInt(posValue(p)) }}</td>
              <td>{{ fmtInt(posRisk(p)) }}</td>
              <td><strong :class="{ warn: posRiskPct(p) > 2 }">{{ posRiskPct(p).toFixed(2) }}%</strong></td>
              <td :class="posUnreal(p) >= 0 ? 'up' : 'down'">{{ p.price ? fmtInt(posUnreal(p)) : '—' }}</td>
              <td><button class="del" @click="remove(i)" title="移除" aria-label="移除部位">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">尚無部位。加入幾檔持股，看看你的總熱度與產業集中度。</p>

      <!-- E1：交易日誌進行中部位（唯讀）——避免同一檔部位分別記在兩處時，
           總風險熱度只看得到手動加的這半、低估真實曝險。這裡的部位不能在
           本頁編輯/刪除，請到「交易日誌」調整；也不參與情境壓測/相關性
           (缺現價與產業資料)，只計入總風險熱度，維持頁面其餘功能不變。 -->
      <div v-if="journalOnlyPositions.length" class="table-wrap journal-positions">
        <p class="muted small">交易日誌進行中部位（唯讀，已計入總風險熱度；如與上方手動部位重複，請以手動部位為準並到交易日誌調整）</p>
        <table class="pos-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>張數</th><th>風險金額</th><th>風險%</th></tr></thead>
          <tbody>
            <tr v-for="p in journalOnlyPositions" :key="p.symbol + '-' + p.id">
              <td class="sym">{{ p.symbol }}<small>{{ p.name && p.name !== p.symbol ? ' ' + p.name : '' }}</small></td>
              <td :class="p.side === 'long' ? 'up' : 'down'">{{ p.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(p.entry) }}</td>
              <td>{{ fmt(p.stop) }}</td>
              <td>{{ p.lots }}</td>
              <td>{{ fmtInt(riskAmount(p)) }}</td>
              <td>{{ (account > 0 ? riskAmount(p) / account * 100 : 0).toFixed(2) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block" v-reveal v-if="sectorHeat.length">
      <h3>產業集中度（依風險金額）</h3>
      <div class="sector-bars">
        <div v-for="s in sectorHeat" :key="s.industry" class="sector-row">
          <span class="sname">{{ s.industry }}</span>
          <div class="bar-track"><div class="bar-fill" :class="{ warn: s.pct > 50 }" :style="{ width: Math.min(s.pct, 100) + '%' }"></div></div>
          <span class="spct">{{ s.pct.toFixed(0) }}%</span>
        </div>
      </div>
      <ul class="checklist">
        <li :class="totalHeat <= 6 ? 'ok' : 'bad'">{{ totalHeat <= 6 ? '✓' : '✗' }} 總熱度 {{ totalHeat.toFixed(1) }}%（建議 ≤ 6%）</li>
        <li :class="maxSectorPct <= 50 ? 'ok' : 'bad'">{{ maxSectorPct <= 50 ? '✓' : '✗' }} 單一產業佔風險 {{ maxSectorPct.toFixed(0) }}%（避免集中，建議 ≤ 50%）</li>
      </ul>
      <p class="disclaimer">※ 風險金額＝張數×1000×|進場−停損|。本工具僅為風險試算，非投資建議。</p>
    </section>

    <section class="section-block" v-reveal v-if="positions.length">
      <h3>情境壓測（Stress Test）</h3>
      <p class="muted">停損單是「正常盤況」下的防線；重挫或跳空時常常來不及成交。這裡試算幾種極端情境下投組會虧多少，抓的是最壞情況，不是日常波動。</p>
      <div class="scenario-tabs">
        <button
          v-for="s in scenarios" :key="s.key" class="btn scenario-btn"
          :class="{ active: selectedScenario === s.key }"
          @click="selectedScenario = s.key"
        >{{ s.label }}</button>
      </div>
      <div class="summary-cards">
        <div class="scard"><span class="slabel">情境總虧損</span><strong class="sval down">{{ fmtInt(stressResult.totalLoss) }}</strong><span class="shint">佔部位市值 {{ stressResult.lossPctValue.toFixed(1) }}%</span></div>
        <div class="scard"><span class="slabel">佔帳戶資金</span><strong class="sval" :class="Math.abs(stressResult.lossPctAccount) > 10 ? 'down' : ''">{{ stressResult.lossPctAccount.toFixed(1) }}%</strong></div>
        <div class="scard"><span class="slabel">正常停損預期虧損</span><strong class="sval">{{ fmtInt(stressResult.totalRiskAmount) }}</strong><span class="shint">若停損都正常成交</span></div>
      </div>
      <div class="table-wrap">
        <table class="stress-table">
          <thead><tr><th>代碼</th><th>現值</th><th>情境價</th><th>情境虧損</th></tr></thead>
          <tbody>
            <tr v-for="r in stressResult.rows" :key="r.symbol">
              <td class="sym">{{ r.symbol }}</td>
              <td>{{ fmtInt(r.curValue) }}</td>
              <td>{{ fmt(r.shockedPrice) }}</td>
              <td class="down">{{ fmtInt(r.loss) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="stress-insight" v-if="stressResult.gapRatio > 1.5">
        ⚠ 這個情境的虧損（{{ fmtInt(Math.abs(stressResult.totalLoss)) }}）是你正常停損預期虧損（{{ fmtInt(stressResult.totalRiskAmount) }}）的 {{ stressResult.gapRatio.toFixed(1) }} 倍——代表重挫/跳空時，停損很可能來不及擋在設定價位，實際虧損會比你以為的「最多賠多少」更慘。
      </p>
      <p class="disclaimer">※ 情境為假設性試算（假設全投組同步下跌，未考慮實際 beta 差異），非市場預測，非投資建議。</p>
    </section>

    <section class="section-block" v-reveal v-if="positions.length >= 2">
      <div class="head-row">
        <div>
          <h3>相關風險（Correlation）<InfoTooltip v-bind="metricGlossary.correlation" /></h3>
          <p class="muted">產業分類看不出的「隱性同一注」：不同產業卻高度連動的部位，靠報酬相關矩陣才抓得到。</p>
        </div>
        <button class="btn btn-primary" :disabled="corrLoading" @click="analyzeCorrelation">
          <span v-if="corrLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>分析相關性
        </button>
      </div>
      <p v-if="corrError" class="error-text">{{ corrError }}</p>

      <template v-if="corr">
        <div class="summary-cards">
          <div class="scard"><span class="slabel">平均相關（越低越分散）</span><strong class="sval" :class="{ warn: corr.avg_abs_corr > 0.6 }">{{ corr.avg_abs_corr.toFixed(2) }}</strong><span class="shint">近 {{ corr.days }} 日報酬</span></div>
        </div>

        <div v-if="corr.high_pairs.length" class="high-pairs">
          <div v-for="hp in corr.high_pairs" :key="hp.a + '-' + hp.b" class="hp-warn">
            ⚠ {{ hp.a }} × {{ hp.b }} 相關 {{ hp.corr.toFixed(2) }} — 實質同一注，別當成兩個獨立部位
          </div>
        </div>
        <p v-else class="ok-text">✓ 無高相關對（≥ {{ corr.high_threshold }}），分散度良好</p>

        <div class="corr-matrix">
          <table>
            <thead><tr><th></th><th v-for="s in corr.symbols" :key="s">{{ s }}</th></tr></thead>
            <tbody>
              <tr v-for="(row, i) in corr.matrix" :key="i">
                <th>{{ corr.symbols[i] }}</th>
                <td v-for="(v, j) in row" :key="j" :style="{ background: i === j ? 'transparent' : corrColor(v) }">{{ i === j ? '—' : v.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <MetricScale
          class="corr-scale"
          :min="0" :max="1" :value="maxPosCorr ?? 0"
          :zones="[{ to: 0.5, tone: 'good' }, { to: 0.7, tone: 'warn' }, { to: 1, tone: 'bad' }]"
          :thresholds="[{ value: 0.7, label: '0.7 高度相關' }]"
          left-label="0" right-label="1" :decimals="2"
        />
        <p class="corr-narrative">
          最高正相關組合{{ maxPosCorrPair ? `：${maxPosCorrPair}` : '' }} = {{ (maxPosCorr ?? 0).toFixed(2) }}，{{ (maxPosCorr ?? 0) >= 0.7 ? '超過 0.7 視為高度相關，同時持有難以分散風險。' : '低於 0.7，尚在可接受範圍。' }}
        </p>

        <ul class="checklist">
          <li :class="(maxPosCorr ?? 0) < 0.7 ? 'ok' : 'bad'">{{ (maxPosCorr ?? 0) < 0.7 ? '✓' : '✗' }} 最高正相關 {{ (maxPosCorr ?? 0).toFixed(2) }}（建議 &lt; 0.7，避免隱性集中）</li>
        </ul>
      </template>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { loadJournal, riskAmount, JOURNAL_KEY } from '../lib/tradeMath'
import InfoTooltip from '../components/InfoTooltip.vue'
import MetricScale from '../components/MetricScale.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { fetchSizingData } from '../lib/livePriceCache'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'
import { loadWatchlist } from '../lib/watchlist'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const LS_POS = 'portfolio_heat_positions'
const LS_ACCT = 'portfolio_heat_account'

const account = ref(1000000)
const positions = ref([])
const form = reactive({ symbol: '', entry: null, stop: null, lots: 1 })
const formError = ref('')

const corr = ref(null)
const corrLoading = ref(false)
const corrError = ref('')
const importMsg = ref('')
const importing = ref(false)
const notifyMsg = ref('')
const notifying = ref(false)

async function notifyRisk() {
  notifying.value = true
  notifyMsg.value = '推播中…'
  const lines = [
    '📊 投組風險摘要',
    `總熱度 ${totalHeat.value.toFixed(1)}%（${positions.value.length} 檔）`,
    `部位金額 ${fmtInt(totalValue.value)}（佔資金 ${deployedPct.value.toFixed(1)}%）`,
    `未實現 ${fmtInt(totalUnrealized.value)}`,
  ]
  const hp = corr.value?.high_pairs || []
  if (hp.length) lines.push('⚠ 高相關：' + hp.map(p => `${p.a}×${p.b} ${p.corr.toFixed(2)}`).join('、'))
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/notify`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: lines.join('\n') }),
    })
    const p = await resp.json().catch(() => ({}))
    notifyMsg.value = p.sent ? '✓ 已推播到 Telegram。' : '未推播：' + (p.error || '請先在後端設定 TELEGRAM_BOT_TOKEN / CHAT_ID。')
  } catch (e) {
    notifyMsg.value = '推播失敗：' + (e?.message || '')
  } finally {
    notifying.value = false
  }
}

function posShares(p) { return (Number(p.lots) || 0) * 1000 }
function posValue(p) { return posShares(p) * (Number(p.entry) || 0) }
function posRisk(p) { return posShares(p) * Math.abs((Number(p.entry) || 0) - (Number(p.stop) || 0)) }
function posRiskPct(p) { return account.value > 0 ? posRisk(p) / account.value * 100 : 0 }
function posUnreal(p) { return p.price ? posShares(p) * (Number(p.price) - Number(p.entry)) : 0 }

// Y5：部位表匯出，投組風險頁原本完全沒有匯出功能
function exportPositionsCsv() {
  const cols = ['代碼', '名稱', '產業', '進場', '停損', '張數', '部位金額', '風險金額', '風險%', '未實現損益']
  const rows = positions.value.map(p => [
    p.symbol, p.name || '', p.industry || '', p.entry, p.stop, p.lots,
    Math.round(posValue(p)), Math.round(posRisk(p)), posRiskPct(p).toFixed(2),
    p.price ? Math.round(posUnreal(p)) : '',
  ])
  downloadCsv(timestampedFilename('portfolio-heat'), cols, rows)
}

// E1：交易日誌的進行中部位若跟這頁手動記的不是同一批，總熱度只算手動部位
// 會低估真實曝險。用代碼去重（手動部位優先，視為同一檔的權威記錄），只把
// 日誌裡「這頁沒有」的代碼之風險金額併入總熱度。
// F3：loadJournal() 讀 localStorage 不是 reactive 的，日誌在別的分頁變動
// 時這頁不會自動跟上——用一個純計數的 ref 建立依賴，storage 事件觸發時
// 遞增它，讓 computed 重新求值（沿用風控監控頁 B2 的同一套模式）。
const journalVersion = ref(0)
function onJournalStorage(e) {
  if (!e.key || e.key === JOURNAL_KEY) journalVersion.value++
}
const journalOnlyPositions = computed(() => {
  journalVersion.value // eslint-disable-line no-unused-expressions
  const tracked = new Set(positions.value.map(p => String(p.symbol || '').trim().toUpperCase()))
  return loadJournal().filter(t => t.status === 'open' && !tracked.has(String(t.symbol || '').trim().toUpperCase()))
})
const journalRiskAmount = computed(() => journalOnlyPositions.value.reduce((a, t) => a + riskAmount(t), 0))
const journalHeatPct = computed(() => (account.value > 0 ? journalRiskAmount.value / account.value * 100 : 0))

const totalHeat = computed(() => positions.value.reduce((a, p) => a + posRiskPct(p), 0) + journalHeatPct.value)
const totalValue = computed(() => positions.value.reduce((a, p) => a + posValue(p), 0))
const deployedPct = computed(() => (account.value > 0 ? totalValue.value / account.value * 100 : 0))
const totalUnrealized = computed(() => positions.value.reduce((a, p) => a + posUnreal(p), 0))
const heatLevel = computed(() => (totalHeat.value > 10 ? 'danger' : totalHeat.value > 6 ? 'warn' : 'safe'))
const heatText = computed(() => (totalHeat.value > 10 ? '危險：總曝險過高' : totalHeat.value > 6 ? '偏高：留意加碼' : '安全區間'))

const sectorHeat = computed(() => {
  const byInd = {}
  let total = 0
  for (const p of positions.value) {
    const r = posRisk(p)
    total += r
    const key = p.industry || '未分類'
    byInd[key] = (byInd[key] || 0) + r
  }
  if (total <= 0) return []
  return Object.entries(byInd)
    .map(([industry, r]) => ({ industry, pct: r / total * 100 }))
    .sort((a, b) => b.pct - a.pct)
})
const maxSectorPct = computed(() => (sectorHeat.value.length ? sectorHeat.value[0].pct : 0))

// B8：情境壓測——假設整體市場（或個股）瞬間下跌，投組會虧多少。用現價（沒有
// 現價時退回進場價）套用情境跌幅；「停損全數跳空觸發」則直接以各自停損價
// 計算，模擬跳空導致停損沒能在設定價位成交、直接跌破的最壞情況。
const SCENARIOS = [
  { key: 'mkt10', label: '大盤重挫 -10%', shockPct: -10 },
  { key: 'mkt20', label: '大盤重挫 -20%（熊市）', shockPct: -20 },
  { key: 'crash30', label: '個股閃崩 -30%（地雷股）', shockPct: -30 },
  { key: 'stopAll', label: '停損全數跳空觸發', shockPct: null },
]
const scenarios = SCENARIOS
const selectedScenario = ref('mkt10')

const stressResult = computed(() => {
  const sc = SCENARIOS.find(s => s.key === selectedScenario.value) || SCENARIOS[0]
  const rows = positions.value.map(p => {
    const shares = posShares(p)
    const curPrice = Number(p.price) || Number(p.entry) || 0
    const shockedPrice = sc.key === 'stopAll'
      ? (Number(p.stop) || curPrice)
      : curPrice * (1 + sc.shockPct / 100)
    const curValue = shares * curPrice
    const loss = shares * (shockedPrice - curPrice)
    return { symbol: p.symbol, curValue, shockedPrice, loss }
  })
  const totalLoss = rows.reduce((a, r) => a + r.loss, 0)
  const totalCurValue = rows.reduce((a, r) => a + r.curValue, 0)
  const totalRiskAmount = positions.value.reduce((a, p) => a + posRisk(p), 0)
  const lossPctValue = totalCurValue > 0 ? totalLoss / totalCurValue * 100 : 0
  const lossPctAccount = account.value > 0 ? totalLoss / account.value * 100 : 0
  const gapRatio = totalRiskAmount > 0 ? Math.abs(totalLoss) / totalRiskAmount : 0
  return { rows, totalLoss, totalRiskAmount, lossPctValue, lossPctAccount, gapRatio }
})

function fmt(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }

function save() {
  localStorage.setItem(LS_POS, JSON.stringify(positions.value))
  localStorage.setItem(LS_ACCT, String(account.value))
}

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(LS_POS) || '[]')
    if (Array.isArray(raw)) positions.value = raw
    const a = Number(localStorage.getItem(LS_ACCT))
    if (a > 0) account.value = a
  } catch { /* ignore */ }
}

async function addPosition() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  const entry = Number(form.entry)
  const stop = Number(form.stop)
  const lots = Math.floor(Number(form.lots) || 0)
  if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop) {
    formError.value = '請填入代碼、有效的進場/停損價（不可相等）與至少 1 張。'
    return
  }
  const pos = reactive({ symbol, name: symbol, industry: '', entry, stop, lots, price: 0, enrichFailed: false })
  positions.value.push(pos)
  save()
  form.symbol = ''; form.entry = null; form.stop = null; form.lots = 1
  // best-effort enrichment (name / industry / current price)
  // P4：改走共用的 livePriceCache，跟交易日誌/風控監控/分析頁共用同一份
  // /risk/sizing 快取，同一檔股票在不同頁面之間不用重複打 FinMind。
  const data = await fetchSizingData(symbol)
  if (data) {
    pos.name = data.name || symbol
    pos.industry = data.industry || '未分類'
    pos.price = data.price || 0
    save()
  } else {
    // P7：查價失敗時 price 會停在 0，若不提示，使用者可能誤把它當成真的
    // 0 元部位，悄悄混進風險熱度/相關性計算。
    pos.enrichFailed = true
    formError.value = `${symbol} 補齊名稱/現價失敗，部位已加入但現價暫時顯示為 0，可稍後重新整理頁面重試。`
  }
}

function remove(i) {
  const p = positions.value[i]
  if (!window.confirm(`確定要刪除部位「${p?.symbol || ''}」嗎？`)) return
  positions.value.splice(i, 1); save(); if (positions.value.length < 2) corr.value = null
}
function clearAll() {
  if (!window.confirm(`確定要清空全部 ${positions.value.length} 筆投組部位嗎？`)) return
  positions.value = []; save(); corr.value = null
}

// One-click import: pull the shared watchlist (關聯圖／決策面板 use the same
// 'finlab_watchlist' key), auto-fill entry=price and an ATR-based stop.
async function importFromWatchlist() {
  importMsg.value = ''
  const syms = loadWatchlist()
  if (!syms.length) { importMsg.value = '觀察清單是空的，先到關聯圖或決策面板加入標的。'; return }
  const existing = new Set(positions.value.map(p => p.symbol))
  const toAdd = syms.filter(s => !existing.has(s))
  if (!toAdd.length) { importMsg.value = '觀察清單標的都已在投組內。'; return }

  importing.value = true
  try {
    const results = await Promise.all(toAdd.map(async (symbol) => {
      try {
        const d = await fetchSizingData(symbol)
        if (!d) return null
        const moderate = (d.suggested_stops || []).find(s => s.label === '穩健')
        const stop = moderate ? moderate.stop_price : Math.round((d.price - d.atr * 2) * 100) / 100
        return { symbol, name: d.name || symbol, industry: d.industry || '未分類', entry: d.price, stop, lots: 1, price: d.price }
      } catch { return null }
    }))
    const added = results.filter(Boolean)
    positions.value.push(...added)
    save()
    const failed = toAdd.length - added.length
    importMsg.value = `已匯入 ${added.length} 檔${failed ? `（${failed} 檔查無資料略過）` : ''}：進場=現價、停損=ATR 穩健停損、預設 1 張，請再自行調整。`
    if (positions.value.length >= 2) analyzeCorrelation()
  } finally {
    importing.value = false
  }
}

const maxPosCorr = computed(() => {
  if (!corr.value?.pairs?.length) return null
  return Math.max(...corr.value.pairs.map(p => p.corr))
})
const maxPosCorrPair = computed(() => {
  if (!corr.value?.pairs?.length) return ''
  const top = corr.value.pairs.reduce((a, b) => (b.corr > a.corr ? b : a))
  return `${top.a} × ${top.b}`
})

function corrColor(v) {
  if (v == null || isNaN(v)) return 'transparent'
  const a = Math.min(Math.abs(v), 1) * 0.75
  return v >= 0 ? `rgba(239, 68, 68, ${a})` : `rgba(79, 140, 255, ${a})`
}

async function analyzeCorrelation() {
  const syms = [...new Set(positions.value.map(p => p.symbol))]
  if (syms.length < 2) { corrError.value = '至少需要 2 檔部位'; corr.value = null; return }
  corrLoading.value = true
  corrError.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/v1/risk/correlation?symbols=${syms.join(',')}`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || payload?.success === false) throw new Error(payload?.detail || '相關性計算失敗')
    corr.value = payload.data
  } catch (e) {
    corr.value = null
    corrError.value = e?.message || '相關性計算失敗'
  } finally {
    corrLoading.value = false
  }
}

onMounted(() => {
  load()
  if (positions.value.length >= 2) analyzeCorrelation()
  window.addEventListener('storage', onJournalStorage)
})
onBeforeUnmount(() => window.removeEventListener('storage', onJournalStorage))
</script>

<style scoped>
.portfolio-heat-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2 { margin: 0 0 4px; }
.acct { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-muted); }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }

.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
.scard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; }
.slabel { font-size: 0.76rem; color: var(--text-muted); }
.sval { font-size: 1.6rem; }
.shint { font-size: 0.74rem; color: var(--text-muted); }
.scard.heat.safe { border-color: #22c55e; }
.scard.heat.warn { border-color: #f59e0b; }
.scard.heat.danger { border-color: #ef4444; }
.scard.heat.safe .sval { color: #22c55e; }
.scard.heat.warn .sval { color: #f59e0b; }
.scard.heat.danger .sval { color: #ef4444; }

.add-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.add-form .inp { width: 130px; }

.table-wrap { overflow-x: auto; margin-top: 14px; }
.pos-table, .stress-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.pos-table th, .pos-table td, .stress-table th, .stress-table td { text-align: right; padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.pos-table th:first-child, .pos-table td:first-child, .pos-table th:nth-child(2), .pos-table td:nth-child(2),
.stress-table th:first-child, .stress-table td:first-child { text-align: left; }
.pos-table th, .stress-table th { color: var(--text-muted); font-weight: 500; font-size: 0.76rem; }
.sym small { color: var(--text-muted); }
.enrich-warn { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; }
.del:hover { color: #ef4444; }
strong.warn { color: #f59e0b; }

.sector-bars { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.sector-row { display: grid; grid-template-columns: 120px 1fr 48px; align-items: center; gap: 10px; }
.sname { font-size: 0.82rem; }
.bar-track { background: var(--bg-well); border-radius: 999px; height: 10px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent-blue); border-radius: 999px; }
.bar-fill.warn { background: #f59e0b; }
.spct { font-size: 0.8rem; text-align: right; color: var(--text-muted); }

.import-msg { margin-top: 8px; font-size: 0.82rem; }
.journal-positions { margin-top: 18px; }
.journal-positions .small { font-size: 0.8rem; margin-bottom: 6px; }
.notify-row { margin-top: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.high-pairs { display: flex; flex-direction: column; gap: 6px; margin: 12px 0; }
.hp-warn { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; border-radius: 10px; padding: 8px 12px; font-size: 0.86rem; }
.corr-matrix { overflow-x: auto; margin-top: 12px; }
.corr-scale { margin-top: 14px; max-width: 360px; }
.corr-narrative { font-size: 0.78rem; color: var(--text-secondary); margin: 8px 0 0; line-height: 1.5; }
.corr-matrix table { border-collapse: collapse; font-size: 0.82rem; }
.corr-matrix th, .corr-matrix td { padding: 8px 12px; text-align: center; border: 1px solid var(--border-color); min-width: 56px; }
.corr-matrix thead th, .corr-matrix tbody th { color: var(--text-muted); font-weight: 500; background: var(--bg-well); }

.scenario-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.scenario-btn.active { background: var(--accent-blue); color: #fff; border-color: var(--accent-blue); }
.stress-insight { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; border-radius: 10px; padding: 10px 12px; font-size: 0.86rem; margin-top: 12px; }
</style>
