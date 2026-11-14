<template>
  <div class="event-brief">
    <router-link class="eb-back" to="/events?tab=briefs">← 回事件簡報列表</router-link>

    <p v-if="error" class="eb-error" role="alert">{{ error }}</p>
    <p v-else-if="loading" class="muted">載入簡報中…</p>

    <template v-else-if="brief">
      <header class="eb-header">
        <div class="eb-title-line">
          <h1>{{ brief.title }}</h1>
          <span class="eb-flag warn">{{ brief.kind === 'shock' ? '突發事件' : '排定事件' }}</span>
          <span class="eb-flag" :class="{ warn: brief.status !== 'closed' }">{{ brief.status === 'closed' ? '已結束' : '發展中' }}</span>
        </div>
        <p class="eb-meta">事件日 {{ brief.event_date }}　資料截至 {{ brief.as_of }}<template v-if="brief.builtin">　隨程式版本發布</template></p>
        <p class="eb-summary">{{ brief.summary }}</p>
        <p class="eb-disclaimer">這是整理功課用的簡報，不是投資建議，也不預測漲跌。影響地圖與情境是「解讀」，可能是錯的——所以每一項都寫了機制與推翻條件。</p>
      </header>

      <details class="card eb-quality" data-testid="eb-quality">
        <summary>完整度 {{ quality.passed }}／{{ quality.total }}　事實 {{ quality.fact_count }} 則（官方 {{ quality.tier_counts['1'] }}、媒體 {{ quality.tier_counts['2'] }}、評論 {{ quality.tier_counts['3'] }}）<template v-if="quality.unconfirmed_count">　其中未證實 {{ quality.unconfirmed_count }} 則</template></summary>
        <ul class="eb-checks">
          <li v-for="i in quality.items" :key="i.key" :class="{ ok: i.ok }">
            <span class="eb-check-mark" aria-hidden="true">{{ i.ok ? '✓' : '✗' }}</span>
            <span>{{ i.label }}<span class="muted">　{{ i.detail }}</span></span>
          </li>
        </ul>
        <p class="muted small">完整度只檢查流程有沒有漏步驟，不代表觀點正確。</p>
      </details>

      <!-- 1 事實 -->
      <section class="card" data-testid="eb-facts">
        <h2>一、發生了什麼（事實，依來源分級）</h2>
        <ul class="eb-facts">
          <li v-for="(f, i) in brief.facts" :key="i" :class="{ unconfirmed: !f.confirmed }">
            <span class="eb-tier" :data-tier="f.tier">{{ TIER_LABEL[f.tier] }}</span>
            <span v-if="!f.confirmed" class="eb-flag bad">未證實</span>
            <span class="eb-fact-text">{{ f.text }}</span>
            <span class="eb-src">
              <a v-if="f.source_url" :href="f.source_url" target="_blank" rel="noopener noreferrer">{{ f.source_name }}</a>
              <template v-else>{{ f.source_name }}</template>
              <template v-if="f.date">　{{ f.date }}</template>
            </span>
          </li>
        </ul>
      </section>

      <!-- 2 預期對照 -->
      <section v-if="hasExpectation" class="card" data-testid="eb-expectation">
        <h2>二、預期對照（市場反應的是「落差」）</h2>
        <div class="eb-exp">
          <div><h3>事前已經反映了什麼</h3><p>{{ brief.expectation.before || '—' }}</p></div>
          <div><h3>實際發生什麼</h3><p>{{ brief.expectation.actual || '—' }}</p></div>
          <div class="gap"><h3>落差在哪裡</h3><p>{{ brief.expectation.gap || '—' }}</p></div>
        </div>
      </section>

      <!-- 3 影響地圖 -->
      <section v-if="brief.impact.length" class="card" data-testid="eb-impact">
        <h2>三、影響地圖（解讀，不是事實）</h2>
        <div v-for="g in impactGroups" :key="g.order" class="eb-order">
          <h3>{{ g.label }}</h3>
          <div class="eb-nodes">
            <article v-for="(n, i) in g.nodes" :key="i" class="eb-node">
              <div class="eb-node-head">
                <strong>{{ n.group }}</strong>
                <span class="eb-dir" :data-dir="n.direction">{{ DIR_LABEL[n.direction] }}</span>
                <span class="eb-conf">把握度：{{ CONF_LABEL[n.confidence] }}</span>
              </div>
              <p>{{ n.mechanism }}</p>
              <p v-if="n.lag" class="muted small">反映時間：{{ n.lag }}</p>
              <p v-if="n.symbols.length" class="eb-symbols">
                <template v-for="s in n.symbols" :key="s.symbol">
                  <router-link v-if="isTw(s.symbol)" :to="`/stocks/${s.symbol}`">{{ s.symbol }} {{ s.name }}</router-link>
                  <span v-else>{{ s.symbol }} {{ s.name }}</span>
                </template>
              </p>
            </article>
          </div>
        </div>
      </section>

      <!-- 4 價格反應 -->
      <section v-if="reactionAvailable" class="card" data-testid="eb-reaction">
        <h2>四、市場實際怎麼反應（事後量測）</h2>
        <p class="eb-lead">
          以 {{ brief.tw_base_date }} 收盤為基準，看影響地圖裡 {{ reactionCount }} 檔台股之後的漲跌、相對大盤的差、第一天的量能與均線位置。
          <template v-if="brief.episode_start">「事前」是從 {{ brief.episode_start }} 收盤到基準日，用來看事件前已經反映了多少。</template>
        </p>
        <div class="eb-actions">
          <button type="button" class="btn btn-primary" :disabled="reactionLoading" @click="loadReaction">
            <span v-if="reactionLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
            {{ reactionLoading ? '抓取日線中…' : (reaction ? '重新整理' : '計算價格反應') }}
          </button>
          <span v-if="reactionError" class="eb-error">{{ reactionError }}</span>
        </div>
        <template v-if="reaction">
          <div class="table-wrap">
            <table class="eb-table">
              <thead>
                <tr>
                  <th>標的</th><th class="col-group">族群</th>
                  <th v-if="brief.episode_start" class="num">事前</th>
                  <th v-if="brief.episode_start" class="num">事前最低</th>
                  <th class="num">事件後第 1 天</th><th class="num">至今</th><th class="num">至今 − 大盤</th>
                  <th class="num">第 1 天量能</th><th>均線位置</th>
                </tr>
              </thead>
              <tbody>
                <tr class="bench">
                  <td>加權指數</td><td class="muted col-group">基準</td>
                  <td v-if="brief.episode_start" class="num" :class="pctClass(reaction.bench.pre_pct)">{{ pct(reaction.bench.pre_pct) }}</td>
                  <td v-if="brief.episode_start" class="num" :class="pctClass(reaction.bench.pre_low_pct)">{{ pct(reaction.bench.pre_low_pct) }}</td>
                  <td class="num" :class="pctClass(reaction.bench.day1_pct)">{{ pct(reaction.bench.day1_pct) }}</td>
                  <td class="num" :class="pctClass(reaction.bench.latest_pct)">{{ pct(reaction.bench.latest_pct) }}</td>
                  <td class="num muted">—</td><td class="num muted">—</td>
                  <td>{{ maText(reaction.bench) }}</td>
                </tr>
                <tr v-for="r in reaction.rows" :key="r.symbol">
                  <td><router-link :to="`/stocks/${r.symbol}`">{{ r.symbol }} {{ r.name }}</router-link></td>
                  <td class="muted col-group">{{ r.group }}</td>
                  <template v-if="r.error">
                    <td class="muted" :colspan="brief.episode_start ? 7 : 5">{{ r.error }}</td>
                  </template>
                  <template v-else>
                    <td v-if="brief.episode_start" class="num" :class="pctClass(r.pre_pct)">{{ pct(r.pre_pct) }}</td>
                    <td v-if="brief.episode_start" class="num" :class="pctClass(r.pre_low_pct)">{{ pct(r.pre_low_pct) }}</td>
                    <td class="num" :class="pctClass(r.day1_pct)">{{ pct(r.day1_pct) }}</td>
                    <td class="num" :class="pctClass(r.latest_pct)">{{ pct(r.latest_pct) }}</td>
                    <td class="num" :class="pctClass(r.latest_excess)">{{ pct(r.latest_excess) }}</td>
                    <td class="num">{{ r.vol_ratio_day1 == null ? '—' : r.vol_ratio_day1.toFixed(2) + ' 倍' }}</td>
                    <td>{{ maText(r) }}</td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="muted small">
            資料到 {{ reaction.bench.latest_date || reaction.bench.base_date || reaction.as_of }}<template v-if="reaction.bench.days_since != null">，事件後 {{ reaction.bench.days_since }} 個交易日</template>。
            {{ reaction.note }} 量能是第 1 天成交量除以事件前 20 日均量。
            <template v-if="!reaction.complete">有部分標的沒抓到資料（可能是資料源額度用完），30 分鐘後再試。</template>
          </p>
          <p class="eb-callout">
            怎麼讀這張表：先看「事前」——如果事前已經跌很多，事件當天的反應通常比較小。再看「至今 − 大盤」——跟著大盤一起動的，多半不是這個事件造成的。
            一兩天的漲跌雜訊很大，不能拿來證明影響地圖是對的。
          </p>
        </template>
      </section>

      <!-- 5 情境 -->
      <section v-if="brief.scenarios.length" class="card" data-testid="eb-scenarios">
        <h2>五、三個情境（各自的觸發與推翻條件）</h2>
        <div class="eb-scen">
          <article v-for="s in orderedScenarios" :key="s.key" class="eb-scen-card" :data-key="s.key">
            <h3><span class="eb-scen-key">{{ SCEN_LABEL[s.key] }}</span>{{ s.title }}</h3>
            <p>{{ s.description }}</p>
            <h4>看到什麼代表往這裡走</h4>
            <ul><li v-for="(t, i) in s.triggers" :key="i">{{ t }}</li><li v-if="!s.triggers.length" class="muted">（沒寫）</li></ul>
            <h4>看到什麼代表這個情境不成立</h4>
            <ul><li v-for="(t, i) in s.invalidation" :key="i">{{ t }}</li><li v-if="!s.invalidation.length" class="muted">（沒寫）</li></ul>
            <template v-if="s.watch.length">
              <h4>要盯的東西</h4>
              <ul><li v-for="(t, i) in s.watch" :key="i">{{ t }}</li></ul>
            </template>
          </article>
        </div>
      </section>

      <!-- 6 後續日期＋未知 -->
      <section v-if="brief.key_dates.length || brief.open_questions.length" class="card eb-two" data-testid="eb-next">
        <div v-if="brief.key_dates.length">
          <h2>六、接下來的關鍵日期</h2>
          <ul class="eb-dates">
            <li v-for="(k, i) in sortedKeyDates" :key="i">
              <strong>{{ k.date }}</strong>
              <span v-if="k.tentative" class="eb-flag warn">暫定</span>
              <span>{{ k.label }}</span>
              <a v-if="k.source_url" :href="k.source_url" target="_blank" rel="noopener noreferrer">來源</a>
            </li>
          </ul>
          <router-link class="small" to="/events">在事件日曆裡看全部日期 →</router-link>
        </div>
        <div v-if="brief.open_questions.length">
          <h2>七、還不知道的事</h2>
          <ul class="eb-plain"><li v-for="(q, i) in brief.open_questions" :key="i">{{ q }}</li></ul>
        </div>
      </section>

      <!-- 8 各方觀點 -->
      <section v-if="brief.viewpoints.length" class="card" data-testid="eb-viewpoints">
        <h2>八、各方觀點（只記假設，不記目標價）</h2>
        <ul class="eb-views">
          <li v-for="(v, i) in brief.viewpoints" :key="i">
            <div class="eb-view-head">
              <span class="eb-dir" :data-stance="v.stance">{{ STANCE_LABEL[v.stance] }}</span>
              <a v-if="v.source_url" :href="v.source_url" target="_blank" rel="noopener noreferrer">{{ v.source }}</a>
              <strong v-else>{{ v.source }}</strong>
            </div>
            <p>{{ v.claim }}</p>
            <p v-if="v.assumptions" class="muted small">{{ v.assumptions }}</p>
          </li>
        </ul>
        <p class="muted small">想拆解某支影片或某篇文章的說法，用 <router-link to="/events?tab=claims">論點抽取</router-link>。</p>
      </section>

      <!-- 9 我的決策紀錄 -->
      <section class="card" data-testid="eb-decision">
        <h2>九、我的決策紀錄（動作之前先把話說死）</h2>
        <p class="eb-lead">
          只存在這台瀏覽器，伺服器不會收到。先寫下理由、最多願意賠多少、什麼情況算自己看錯、哪一天回頭檢討——事後才有東西可以對照。
          「不動作」也是一種決策，一樣值得記下來。具體一筆單的部位大小，用 <router-link to="/risk-sizing">部位風控</router-link> 算；成交後記到 <router-link to="/journal">交易日誌</router-link>。
        </p>
        <form class="eb-form" @submit.prevent="saveDecision">
          <label>我打算
            <select v-model="draft.action" class="inp" aria-label="我打算">
              <option v-for="a in DECISION_ACTIONS" :key="a.value" :value="a.value">{{ a.label }}</option>
            </select>
          </label>
          <label>最多可承受虧損（占總資金 %）
            <input v-model="draft.max_loss_pct" class="inp" type="number" min="0" max="100" step="0.1" placeholder="例如 1" />
          </label>
          <label>哪一天回頭檢討
            <input v-model="draft.review_date" class="inp" type="date" required />
          </label>
          <label class="wide">理由（我是根據哪個情境、哪些事實）
            <textarea v-model="draft.thesis" class="inp" rows="2" maxlength="600" required></textarea>
          </label>
          <label class="wide">什麼情況代表我看錯了（價位或事件都可以）
            <textarea v-model="draft.invalidation" class="inp" rows="2" maxlength="400" required></textarea>
          </label>
          <div class="eb-actions wide">
            <button class="btn btn-primary" type="submit">記下來</button>
            <span v-if="draftMsg" class="muted small" role="status">{{ draftMsg }}</span>
          </div>
        </form>

        <ul v-if="decisions.length" class="eb-decisions">
          <li v-for="d in decisions" :key="d.id" :class="{ due: isDue(d), reviewed: d.reviewed }" :data-decision-id="d.id">
            <div class="eb-dec-head">
              <strong>{{ actionLabel(d.action) }}</strong>
              <span class="muted small">{{ String(d.created_at).slice(0, 10) }} 記錄</span>
              <span v-if="d.max_loss_pct != null" class="small">最多賠 {{ d.max_loss_pct }}%</span>
              <span class="small">檢討日 {{ d.review_date }}</span>
              <span v-if="d.reviewed" class="eb-flag">已檢討</span>
              <span v-else-if="isDue(d)" class="eb-flag warn">到期待檢討</span>
            </div>
            <p><span class="muted">理由：</span>{{ d.thesis }}</p>
            <p><span class="muted">看錯的條件：</span>{{ d.invalidation }}</p>
            <p v-if="d.reviewed"><span class="muted">檢討：</span>{{ d.review_note || '（沒有寫）' }}</p>
            <div v-else class="eb-review">
              <input v-model="reviewNotes[d.id]" class="inp" maxlength="400" placeholder="檢討：結果如何？當初的理由成立嗎？下次要改什麼？" :aria-label="`檢討 ${d.created_at}`" />
              <button type="button" class="btn btn-secondary" @click="markReviewed(d)">標記已檢討</button>
            </div>
            <button type="button" class="eb-link-btn" @click="deleteDecision(d)">刪除</button>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { fetchWithRetry } from '../lib/apiFetch'
import {
  DECISION_ACTIONS, actionLabel, addDecision, decisionsFor, removeDecision, reviewDecision, todayIso,
} from '../lib/eventDecisions'

const TIER_LABEL = { 1: '官方第一手', 2: '媒體報導', 3: '評論／社群' }
const DIR_LABEL = { benefit: '可能受益', hurt: '可能受害', mixed: '有好有壞', unclear: '還看不出來' }
const CONF_LABEL = { high: '高', medium: '中', low: '低' }
const SCEN_LABEL = { base: '基準', bull: '樂觀', bear: '悲觀' }
const STANCE_LABEL = { bullish: '偏多', bearish: '偏空', neutral: '中性', unclear: '不明' }
const ORDER_LABEL = { 1: '直接影響', 2: '二階：供應鏈與客戶', 3: '三階：資金面、評價、政策' }

const route = useRoute()
const brief = ref(null)
const quality = ref({ passed: 0, total: 0, items: [], tier_counts: {}, fact_count: 0, unconfirmed_count: 0 })
const reactionAvailable = ref(false)
const reactionCount = ref(0)
const loading = ref(true)
const error = ref('')

const hasExpectation = computed(() => {
  const e = brief.value?.expectation || {}
  return Boolean(e.before || e.actual || e.gap)
})
const impactGroups = computed(() => [1, 2, 3]
  .map(order => ({ order, label: ORDER_LABEL[order], nodes: (brief.value?.impact || []).filter(n => n.order === order) }))
  .filter(g => g.nodes.length))
const orderedScenarios = computed(() => ['base', 'bull', 'bear']
  .map(k => (brief.value?.scenarios || []).find(s => s.key === k)).filter(Boolean))
const sortedKeyDates = computed(() => [...(brief.value?.key_dates || [])].sort((a, b) => a.date.localeCompare(b.date)))

function isTw(symbol) {
  return /^\d{4,6}[A-Z]?$/.test(String(symbol || ''))
}

async function loadBrief() {
  loading.value = true
  error.value = ''
  brief.value = null
  reaction.value = null
  reactionError.value = ''
  try {
    const res = await fetchWithRetry(`/api/v1/events/briefs/${encodeURIComponent(route.params.id)}`)
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(typeof json.detail === 'string' ? json.detail : '簡報載入失敗')
    brief.value = json.data.brief
    quality.value = json.data.quality
    reactionAvailable.value = Boolean(json.data.reaction_available)
    reactionCount.value = json.data.reaction_symbol_count || 0
    refreshDecisions()
  } catch (e) {
    error.value = e?.message || '簡報載入失敗'
  } finally {
    loading.value = false
  }
}

// ── 價格反應 ──
const reaction = ref(null)
const reactionLoading = ref(false)
const reactionError = ref('')

async function loadReaction() {
  reactionLoading.value = true
  reactionError.value = ''
  try {
    // 一次要抓十幾檔日線，可能要十幾秒；不重試，避免重複耗用資料源額度
    const res = await fetch(`/api/v1/events/briefs/${encodeURIComponent(route.params.id)}/reaction`)
    const json = await res.json().catch(() => ({}))
    if (!res.ok || !json.success) throw new Error(typeof json.detail === 'string' ? json.detail : '價格反應計算失敗')
    reaction.value = json.data
  } catch (e) {
    reactionError.value = e?.message || '價格反應計算失敗'
  } finally {
    reactionLoading.value = false
  }
}

function pct(v) {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}
function pctClass(v) {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}
function maText(r) {
  if (!r || r.above_ma20 == null) return '—'
  const a = r.above_ma20 ? '站上月線' : '跌破月線'
  if (r.above_ma60 == null) return a
  return `${a}、${r.above_ma60 ? '站上季線' : '跌破季線'}`
}

// ── 決策紀錄（localStorage） ──
const decisions = ref([])
const reviewNotes = reactive({})
const draft = reactive({ action: 'none', max_loss_pct: '', review_date: '', thesis: '', invalidation: '' })
const draftMsg = ref('')

function refreshDecisions() {
  decisions.value = brief.value ? decisionsFor(brief.value.id) : []
}
function isDue(d) {
  return !d.reviewed && d.review_date && d.review_date <= todayIso()
}
function saveDecision() {
  const item = addDecision({ ...draft, brief_id: brief.value.id, brief_title: brief.value.title })
  if (!item) {
    draftMsg.value = '存不進瀏覽器（可能是無痕模式或空間已滿）'
    return
  }
  draftMsg.value = `已記錄，${draft.review_date} 回來檢討`
  draft.thesis = ''
  draft.invalidation = ''
  draft.max_loss_pct = ''
  refreshDecisions()
}
function markReviewed(d) {
  reviewDecision(d.id, reviewNotes[d.id] || '')
  refreshDecisions()
}
function deleteDecision(d) {
  if (!window.confirm('確定刪除這筆決策紀錄嗎？瀏覽器是唯一的儲存位置，刪掉就救不回來。')) return
  removeDecision(d.id)
  refreshDecisions()
}

onMounted(loadBrief)
watch(() => route.params.id, (id, old) => { if (id && id !== old) loadBrief() })
</script>

<style scoped>
.event-brief { display: flex; flex-direction: column; gap: var(--space-4); }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }
.eb-back { font-size: 0.82rem; color: var(--accent-blue); text-decoration: none; }
.eb-error { color: var(--up); font-size: 0.85rem; margin: 0; }

.eb-title-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.eb-title-line h1 { margin: 0; text-wrap: balance; }
.eb-meta { margin: 6px 0; font-size: 0.8rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.eb-summary { margin: 0; font-size: 0.95rem; line-height: 1.8; max-width: 76ch; }
.eb-disclaimer { margin: 8px 0 0; font-size: 0.78rem; line-height: 1.7; color: var(--text-muted); max-width: 76ch; }
.eb-lead { margin: 0 0 10px; font-size: 0.86rem; line-height: 1.7; color: var(--text-secondary); max-width: 76ch; }
.eb-lead a, .event-brief section a { color: var(--accent-blue); }

.card h2 { margin: 0 0 10px; font-size: 1.02rem; }
.card h3 { margin: 0 0 6px; font-size: 0.88rem; }
.card h4 { margin: 10px 0 4px; font-size: 0.78rem; color: var(--text-muted); font-weight: 600; }

.eb-flag {
  font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
  border: 1px solid var(--border-color); color: var(--text-secondary);
}
.eb-flag.warn { background: var(--warn-soft); color: var(--warn); border-color: transparent; font-weight: 600; }
.eb-flag.bad { background: var(--up-soft); color: var(--up); border-color: transparent; font-weight: 700; }

/* 完整度 */
.eb-quality summary { cursor: pointer; font-size: 0.85rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.eb-checks { list-style: none; margin: 10px 0; padding: 0; display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; }
.eb-checks li { display: flex; gap: 8px; }
.eb-check-mark { color: var(--up); font-weight: 700; width: 1em; }
.eb-checks li.ok .eb-check-mark { color: var(--down); }

/* 事實 */
.eb-facts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.eb-facts li { display: grid; grid-template-columns: 6.2em 1fr; gap: 2px 10px; padding: 9px 0; border-top: 1px dashed var(--border-color); font-size: 0.86rem; line-height: 1.7; }
.eb-facts li:first-child { border-top: 0; }
.eb-facts li.unconfirmed .eb-fact-text { color: var(--text-secondary); }
.eb-tier { grid-row: span 3; font-size: 0.72rem; font-weight: 700; padding-top: 3px; color: var(--text-muted); }
.eb-tier[data-tier='1'] { color: var(--down); }
.eb-tier[data-tier='2'] { color: var(--accent-blue); }
.eb-facts .eb-flag { justify-self: start; }
.eb-src { font-size: 0.74rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }

/* 預期對照 */
.eb-exp { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
.eb-exp > div { font-size: 0.85rem; line-height: 1.75; }
.eb-exp > div p { margin: 0; }
.eb-exp .gap { padding: 10px 12px; border-radius: var(--radius-sm); background: var(--blue-soft); }

/* 影響地圖 */
.eb-order + .eb-order { margin-top: 14px; }
.eb-nodes { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.eb-node { border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 0.83rem; line-height: 1.7; }
.eb-node p { margin: 6px 0 0; }
.eb-node-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 8px; }
.eb-dir { font-size: 0.7rem; font-weight: 700; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border-color); color: var(--text-secondary); white-space: nowrap; }
.eb-dir[data-dir='benefit'], .eb-dir[data-stance='bullish'] { background: var(--up-soft); color: var(--up); border-color: transparent; }
.eb-dir[data-dir='hurt'], .eb-dir[data-stance='bearish'] { background: var(--down-soft); color: var(--down); border-color: transparent; }
.eb-dir[data-dir='mixed'] { background: var(--warn-soft); color: var(--warn); border-color: transparent; }
.eb-conf { font-size: 0.72rem; color: var(--text-muted); margin-left: auto; }
.eb-symbols { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 0.78rem; font-variant-numeric: tabular-nums; }

/* 價格反應 */
.eb-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 10px; }
/* 表格很寬：只讓表格自己左右捲，不要撐破整頁（手機） */
.table-wrap { overflow-x: auto; max-width: 100%; }
.event-brief > section { min-width: 0; }
.eb-table { font-size: 0.82rem; font-variant-numeric: tabular-nums; }
.eb-table th, .eb-table td { white-space: nowrap; }
.eb-table .num { text-align: right; }
.eb-table .col-group { white-space: normal; text-align: left; min-width: 7em; max-width: 11em; line-height: 1.4; }
.eb-table tr.bench td { font-weight: 700; border-bottom: 2px solid var(--border-color); }
.up { color: var(--up); }
.down { color: var(--down); }
.eb-callout { margin: 10px 0 0; padding: 10px 12px; border-radius: var(--radius-sm); background: var(--blue-soft); font-size: 0.82rem; line-height: 1.75; max-width: 80ch; }

/* 情境 */
.eb-scen { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.eb-scen-card { border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; font-size: 0.83rem; line-height: 1.7; }
.eb-scen-card p { margin: 0; }
.eb-scen-card ul { margin: 0; padding-left: 18px; }
.eb-scen-key { display: inline-block; margin-right: 8px; font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; background: var(--blue-soft); color: var(--accent-blue); vertical-align: middle; }
.eb-scen-card[data-key='bull'] .eb-scen-key { background: var(--up-soft); color: var(--up); }
.eb-scen-card[data-key='bear'] .eb-scen-key { background: var(--down-soft); color: var(--down); }

/* 日期與未知 */
.eb-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-5); }
.eb-dates, .eb-plain, .eb-views, .eb-decisions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem; line-height: 1.7; }
.eb-dates li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; }
.eb-dates strong { font-variant-numeric: tabular-nums; }
.eb-plain { list-style: disc; padding-left: 18px; gap: 4px; }

/* 觀點 */
.eb-views li { padding-top: 8px; border-top: 1px dashed var(--border-color); }
.eb-views li:first-child { border-top: 0; padding-top: 0; }
.eb-views p { margin: 4px 0 0; }
.eb-view-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }

/* 決策紀錄 */
.eb-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.eb-form label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.eb-form .wide { grid-column: 1 / -1; }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font: inherit; font-size: 0.86rem; }
.eb-decisions { margin-top: 14px; }
.eb-decisions li { border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 10px 12px; }
.eb-decisions li.due { border-color: var(--warn); }
.eb-decisions li.reviewed { opacity: 0.75; }
.eb-decisions p { margin: 4px 0 0; }
.eb-dec-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.eb-review { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.eb-review .inp { flex: 1 1 260px; }
.eb-link-btn { font: inherit; font-size: 0.74rem; background: none; border: 0; padding: 0; margin-top: 6px; color: var(--text-muted); cursor: pointer; text-decoration: underline; }

@media (max-width: 760px) {
  .eb-exp, .eb-scen, .eb-two, .eb-form { grid-template-columns: 1fr; }
  .eb-table .col-group { display: none; } /* 手機先看數字；族群在影響地圖裡已經有了 */
  .eb-facts li { grid-template-columns: 1fr; }
  .eb-tier { grid-row: auto; }
  .eb-conf { margin-left: 0; }
}
</style>
