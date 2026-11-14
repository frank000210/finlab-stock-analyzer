<template>
  <div class="event-desk">
    <PageFocusBanner text="把事實、解讀、決策分開。這裡幫你把功課做完整，不預測漲跌。" />

    <header class="page-header">
      <h1>事件研究台</h1>
      <p class="subtitle">事件日曆（什麼時候會有事）、事件簡報（發生了什麼、影響誰、接下來看什麼）、論點抽取（別人的說法靠什麼假設）。</p>
    </header>

    <router-link v-if="due.length" class="ev-due" :to="`/events/briefs/${due[0].brief_id}`" data-testid="ev-due">
      有 {{ due.length }} 筆決策紀錄到了你自己訂的檢討日 → 回去對照當初寫的理由
    </router-link>

    <div class="tabs" role="tablist" aria-label="事件研究台分頁">
      <button
        v-for="t in TABS" :key="t.key" type="button" role="tab" class="tab ev-tab"
        :class="{ active: tab === t.key }" :aria-selected="tab === t.key" :data-tab="t.key"
        @click="setTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <!-- ───────── 日曆 ───────── -->
    <section v-show="tab === 'calendar'" class="ev-section" data-testid="ev-calendar">
      <div class="ev-filters" role="group" aria-label="事件類別篩選">
        <button
          v-for="(label, key) in categories" :key="key" type="button" class="ev-chip"
          :class="{ on: !hidden.has(key) }" :aria-pressed="!hidden.has(key)" @click="toggleCategory(key)"
        >{{ label }}</button>
      </div>

      <p v-if="calError" class="ev-error" role="alert">{{ calError }}</p>
      <p v-else-if="calLoading" class="muted">載入日曆中…</p>
      <template v-else>
        <p v-if="!groupedEvents.length" class="muted">這個範圍內沒有符合篩選的事件。</p>
        <div v-for="g in groupedEvents" :key="g.month" class="card ev-month">
          <h2>{{ g.label }}</h2>
          <ul class="ev-list">
            <li
              v-for="e in g.items" :key="e.id" class="ev-row"
              :class="{ past: e.days_away < 0, today: e.days_away === 0 }" :data-event-id="e.id"
            >
              <div class="ev-date">
                <strong>{{ md(e.date) }}</strong>
                <span>週{{ e.weekday }}</span>
                <span v-if="e.end_date" class="ev-date-end">～{{ md(e.end_date) }}</span>
              </div>
              <div class="ev-body">
                <div class="ev-title-line">
                  <span class="ev-title"><span class="ev-imp" :aria-label="`重要性 ${e.importance}／3`" :title="`重要性 ${e.importance}／3`">{{ '●'.repeat(e.importance) }}</span>{{ e.title }}</span>
                  <span class="ev-cat" :data-cat="e.category">{{ e.category_label }}</span>
                  <span v-if="e.tentative" class="ev-flag">暫定</span>
                  <span class="ev-away" :class="{ soon: e.days_away >= 0 && e.days_away <= 7 }">{{ awayText(e.days_away) }}</span>
                </div>
                <p v-if="e.time_note" class="ev-note">{{ e.time_note }}</p>
                <p v-if="e.tw_reaction_date" class="ev-note ev-react">台股最快 {{ md(e.tw_reaction_date) }} 才會反應</p>
                <p v-if="e.note" class="ev-note muted">{{ e.note }}</p>
                <div class="ev-links">
                  <a v-if="e.source_url" :href="e.source_url" target="_blank" rel="noopener noreferrer">來源：{{ e.source_name || '連結' }}</a>
                  <router-link v-if="e.brief_id" :to="`/events/briefs/${e.brief_id}`">事件簡報：{{ e.brief_title }}</router-link>
                  <button v-if="isAdmin && e.origin === 'custom'" type="button" class="ev-link-btn" @click="removeCustom(e)">刪除這筆自訂事件</button>
                </div>
              </div>
            </li>
          </ul>
        </div>
        <p class="ev-foot">
          內建日期查證於 {{ calMeta.verified_on || '—' }}，每一筆都附官方來源；「法定公告期限」是依法規推算，不是個別公司的實際公告日。
          美國時間的事件都落在台股收盤之後，所以另外標出台股最快的反應日（依
          <a v-if="calMeta.holiday_source_url" :href="calMeta.holiday_source_url" target="_blank" rel="noopener noreferrer">交易所公告的休市日</a>
          計算，涵蓋到 {{ (calMeta.holiday_covers || [])[1] || '—' }}）。個別公司的法說會日期沒有可合規批次取得的官方來源，需要時請管理員手動新增。
        </p>
      </template>

      <details v-if="isAdmin" class="card ev-admin">
        <summary>新增自訂事件（管理員）</summary>
        <form class="ev-form" @submit.prevent="addCustom">
          <label>日期<input v-model="custom.date" type="date" class="inp" required /></label>
          <label class="wide">標題<input v-model="custom.title" class="inp" maxlength="120" placeholder="例如：台積電第 4 季法說會" required /></label>
          <label>類別
            <select v-model="custom.category" class="inp">
              <option v-for="c in CUSTOM_CATEGORIES" :key="c" :value="c">{{ categories[c] || c }}</option>
            </select>
          </label>
          <label>重要性
            <select v-model.number="custom.importance" class="inp">
              <option :value="1">1</option><option :value="2">2</option><option :value="3">3</option>
            </select>
          </label>
          <label class="wide">來源網址（選填）<input v-model="custom.source_url" class="inp" placeholder="https://…" /></label>
          <label class="wide">時間說明（選填）<input v-model="custom.time_note" class="inp" maxlength="200" /></label>
          <label class="check"><input v-model="custom.us_time" type="checkbox" /> 美國時間的事件（台股隔一個交易日才反應）</label>
          <div class="ev-form-actions">
            <button class="btn btn-primary" type="submit" :disabled="customBusy">新增</button>
            <span v-if="customMsg" class="muted">{{ customMsg }}</span>
          </div>
        </form>
      </details>
    </section>

    <!-- ───────── 事件簡報 ───────── -->
    <section v-show="tab === 'briefs'" class="ev-section" data-testid="ev-briefs">
      <p class="ev-lead">
        每份簡報固定六塊：分級的事實、預期對照、影響地圖、三個情境（含推翻條件）、後續日期、還不知道的事。
        「完整度」只檢查流程有沒有漏步驟，不代表觀點正確。
      </p>
      <p v-if="briefError" class="ev-error" role="alert">{{ briefError }}</p>
      <p v-else-if="briefLoading" class="muted">載入簡報中…</p>
      <p v-else-if="!briefs.length" class="muted">還沒有事件簡報。</p>
      <router-link
        v-for="b in briefs" :key="b.id" :to="`/events/briefs/${b.id}`" class="card ev-brief-card" :data-brief-id="b.id"
      >
        <div class="ev-brief-head">
          <h2>{{ b.title }}</h2>
          <span class="ev-flag" :class="b.kind">{{ b.kind === 'shock' ? '突發事件' : '排定事件' }}</span>
          <span class="ev-flag" :class="b.status">{{ b.status === 'closed' ? '已結束' : '發展中' }}</span>
        </div>
        <p class="ev-brief-meta">
          事件日 {{ b.event_date }}　資料截至 {{ b.as_of }}　完整度 {{ b.quality_passed }}／{{ b.quality_total }}
          <template v-if="b.unconfirmed_count">　未證實的說法 {{ b.unconfirmed_count }} 則</template>
          <template v-if="b.next_key_date">　下一個關鍵日 {{ b.next_key_date }}</template>
        </p>
        <p class="ev-brief-summary">{{ b.summary }}</p>
      </router-link>

      <details v-if="isAdmin" class="card ev-admin" data-testid="ev-editor">
        <summary>新增或修改簡報（管理員，JSON）</summary>
        <p class="muted small">先載入空白模板，照欄位填好後按「檢查格式」，沒有錯誤再存檔。內建簡報（隨程式版本發布）不能在這裡覆寫。</p>
        <div class="ev-form-actions">
          <button type="button" class="btn btn-secondary" @click="loadTemplate">載入空白模板</button>
          <button type="button" class="btn btn-secondary" :disabled="!editor.text.trim() || editor.busy" @click="validateDraft">檢查格式</button>
          <button type="button" class="btn btn-primary" :disabled="!editor.text.trim() || editor.busy" @click="saveDraft">存檔</button>
        </div>
        <textarea v-model="editor.text" class="inp ev-json" rows="16" spellcheck="false" aria-label="簡報 JSON"></textarea>
        <ul v-if="editor.guide" class="ev-guide">
          <li v-for="(text, key) in editor.guide" :key="key"><code>{{ key }}</code>　{{ text }}</li>
        </ul>
        <p v-if="editor.msg" :class="editor.ok ? 'ev-ok' : 'ev-error'" role="status">{{ editor.msg }}</p>
        <ul v-if="editor.errors.length" class="ev-errors">
          <li v-for="(e, i) in editor.errors" :key="i">{{ e }}</li>
        </ul>
      </details>
    </section>

    <!-- ───────── 論點抽取 ───────── -->
    <section v-show="tab === 'claims'" class="ev-section" data-testid="ev-claims">
      <div class="card ev-claims-form">
        <p class="ev-lead">
          貼上財經影片的逐字稿或文章，AI 會拆成一條一條的論點，並標出每一條靠什麼假設、講者有沒有說「什麼情況下他會改口」。
          每條論點都附原句，系統會核對原句是否真的出現在你貼的文字裡——對不上的會標出來。
        </p>
        <p class="muted small">取得逐字稿：YouTube 影片說明欄的「顯示轉錄稿」，全選複製後貼上。本站不會自動抓取影片內容。</p>
        <label class="field">來源（選填，方便你自己辨識）
          <input v-model="claims.source" class="inp" maxlength="80" placeholder="例如：某頻道 11/13 直播" />
        </label>
        <label class="field">逐字稿或文章內容
          <textarea v-model="claims.text" class="inp" rows="9" placeholder="貼上文字（至少 200 字，最多 20,000 字）"></textarea>
        </label>
        <div class="ev-form-actions">
          <button type="button" class="btn btn-primary" :disabled="!canExtract" @click="extractClaims">
            <span v-if="claims.busy" class="loading-spinner btn-spinner" aria-hidden="true"></span>
            {{ claims.busy ? '抽取中（約 20～40 秒）…' : '抽出論點' }}
          </button>
          <span class="muted small">{{ claims.text.trim().length.toLocaleString() }} 字</span>
          <span v-if="!aiConfigured" class="muted small">AI 服務尚未設定，這個功能暫時無法使用。</span>
        </div>
        <p v-if="claims.error" class="ev-error" role="alert">{{ claims.error }}</p>
      </div>

      <div v-if="claims.result" class="card ev-claims-result" data-testid="ev-claims-result">
        <p class="ev-claims-stats">
          整體傾向：<strong>{{ claims.result.stance }}</strong>　共 {{ claims.result.stats.total }} 條論點
          原句對得上 {{ claims.result.stats.quote_verified }} 條<template v-if="claims.result.stats.quote_unverified">、<strong class="ev-bad">對不上 {{ claims.result.stats.quote_unverified }} 條</strong></template>
          有說推翻條件的 {{ claims.result.stats.with_invalidation }} 條
        </p>
        <p v-if="claims.result.stats.total && !claims.result.stats.with_invalidation" class="ev-warn">
          講者沒有為任何一條論點說明「什麼情況下會改變看法」。沒有推翻條件的預測，事後無法檢驗。
        </p>
        <ol class="ev-claim-list">
          <li v-for="(c, i) in claims.result.claims" :key="i" class="ev-claim">
            <div class="ev-claim-head">
              <span class="ev-flag" :class="c.kind">{{ KIND_LABEL[c.kind] }}</span>
              <strong>{{ c.claim }}</strong>
            </div>
            <blockquote v-if="c.quote" :class="['ev-quote', c.quote_match]">
              「{{ c.quote }}」
              <span class="ev-quote-tag">{{ QUOTE_LABEL[c.quote_match] }}</span>
            </blockquote>
            <p v-else class="ev-quote none"><span class="ev-quote-tag">AI 沒有附原句，這條無法核對</span></p>
            <dl class="ev-claim-meta">
              <template v-if="c.assumptions.length"><dt>靠什麼假設</dt><dd>{{ c.assumptions.join('；') }}</dd></template>
              <dt>推翻條件</dt><dd :class="{ muted: !c.invalidation }">{{ c.invalidation || '講者沒說' }}</dd>
              <template v-if="c.horizon"><dt>時間範圍</dt><dd>{{ c.horizon }}</dd></template>
              <template v-if="c.check_how"><dt>怎麼驗證</dt><dd>{{ c.check_how }}</dd></template>
            </dl>
          </li>
        </ol>
        <div v-if="claims.result.missing.length" class="ev-missing">
          <strong>講者沒有交代的事</strong>
          <ul><li v-for="(m, i) in claims.result.missing" :key="i">{{ m }}</li></ul>
        </div>
        <p class="ev-foot">AI 只負責拆解與整理，不判斷講者對錯，也不是投資建議。數字與說法請回原始來源查證。</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { fetchWithRetry } from '../lib/apiFetch'
import { useAiStatus } from '../composables/useAiStatus'
import { useAuthStore } from '../stores/auth.js'
import { dueDecisions } from '../lib/eventDecisions'

const TABS = [
  { key: 'calendar', label: '事件日曆' },
  { key: 'briefs', label: '事件簡報' },
  { key: 'claims', label: '論點抽取' },
]
const CUSTOM_CATEGORIES = ['custom', 'earnings', 'company', 'policy', 'macro_us', 'fed']
const KIND_LABEL = { fact: '事實陳述', forecast: '預測', opinion: '意見' }
const QUOTE_LABEL = {
  exact: '原文找得到',
  approx: '原文有近似的句子（斷句不同）',
  none: '原文找不到這句——可能是 AI 改寫或編造，請自己回去核對',
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
const { aiConfigured, checkAiConfigured } = useAiStatus()

const tab = ref(TABS.some(t => t.key === route.query.tab) ? route.query.tab : 'calendar')
function setTab(key) {
  tab.value = key
  router.replace({ query: { ...route.query, tab: key === 'calendar' ? undefined : key } })
}
watch(() => route.query.tab, (q) => {
  tab.value = TABS.some(t => t.key === q) ? q : 'calendar'
})

const due = ref([])

// ── 日曆 ──
const events = ref([])
const calMeta = ref({})
const categories = ref({})
const calLoading = ref(true)
const calError = ref('')
const hidden = ref(new Set())

function toggleCategory(key) {
  const next = new Set(hidden.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  hidden.value = next
}

const groupedEvents = computed(() => {
  const groups = new Map()
  for (const e of events.value) {
    if (hidden.value.has(e.category)) continue
    const month = e.date.slice(0, 7)
    if (!groups.has(month)) groups.set(month, [])
    groups.get(month).push(e)
  }
  return [...groups.entries()].map(([month, items]) => ({
    month, items, label: `${month.slice(0, 4)} 年 ${Number(month.slice(5, 7))} 月`,
  }))
})

function md(iso) {
  if (!iso) return ''
  return `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`
}
function awayText(n) {
  if (n === 0) return '今天'
  if (n === 1) return '明天'
  if (n > 1) return `${n} 天後`
  return `已過 ${-n} 天`
}

async function loadCalendar() {
  calLoading.value = true
  calError.value = ''
  try {
    const res = await fetchWithRetry('/api/v1/events/calendar')
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || '日曆載入失敗')
    events.value = json.data.events || []
    calMeta.value = json.data.meta || {}
    categories.value = json.data.meta?.categories || {}
  } catch (e) {
    calError.value = e?.message || '日曆載入失敗'
  } finally {
    calLoading.value = false
  }
}

const custom = reactive({ date: '', title: '', category: 'custom', importance: 2, source_url: '', time_note: '', us_time: false })
const customBusy = ref(false)
const customMsg = ref('')

function detailText(json, fallback) {
  const d = json?.detail
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map(x => x.msg || '').filter(Boolean).join('；') || fallback
  return d.message || fallback
}

async function addCustom() {
  customBusy.value = true
  customMsg.value = ''
  try {
    const res = await fetch('/api/v1/events/calendar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...auth.getAuthHeaders() },
      body: JSON.stringify(custom),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(detailText(json, '新增失敗'))
    customMsg.value = '已新增'
    custom.title = ''
    custom.source_url = ''
    custom.time_note = ''
    await loadCalendar()
  } catch (e) {
    customMsg.value = e?.message || '新增失敗'
  } finally {
    customBusy.value = false
  }
}

async function removeCustom(e) {
  if (!window.confirm(`確定刪除自訂事件「${e.title}」嗎？`)) return
  try {
    const res = await fetch(`/api/v1/events/calendar/${encodeURIComponent(e.id)}`, {
      method: 'DELETE', headers: auth.getAuthHeaders(),
    })
    if (!res.ok) throw new Error(detailText(await res.json().catch(() => ({})), '刪除失敗'))
    await loadCalendar()
  } catch (err) {
    calError.value = err?.message || '刪除失敗'
  }
}

// ── 簡報 ──
const briefs = ref([])
const briefLoading = ref(true)
const briefError = ref('')

async function loadBriefs() {
  briefLoading.value = true
  briefError.value = ''
  try {
    const res = await fetchWithRetry('/api/v1/events/briefs')
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || '簡報載入失敗')
    briefs.value = json.data || []
  } catch (e) {
    briefError.value = e?.message || '簡報載入失敗'
  } finally {
    briefLoading.value = false
  }
}

const editor = reactive({ text: '', guide: null, msg: '', ok: false, errors: [], busy: false })

function parseDraft() {
  editor.errors = []
  try {
    const obj = JSON.parse(editor.text)
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) throw new Error('最外層必須是一個物件')
    return obj
  } catch (e) {
    editor.ok = false
    editor.msg = `JSON 語法錯誤：${e.message}`
    return null
  }
}

async function loadTemplate() {
  try {
    const res = await fetchWithRetry('/api/v1/events/briefs/template')
    const json = await res.json()
    editor.text = JSON.stringify(json.data.template, null, 2)
    editor.guide = json.data.guide
    editor.msg = ''
    editor.errors = []
  } catch {
    editor.ok = false
    editor.msg = '模板載入失敗'
  }
}

async function validateDraft() {
  const obj = parseDraft()
  if (!obj) return false
  editor.busy = true
  try {
    const res = await fetch('/api/v1/events/briefs/validate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj),
    })
    const json = await res.json()
    const d = json.data || {}
    editor.ok = Boolean(d.valid)
    editor.errors = d.errors || []
    editor.msg = d.valid
      ? `格式正確。完整度 ${d.quality.passed}／${d.quality.total}` +
        (d.quality.passed < d.quality.total
          ? `，還缺：${d.quality.items.filter(i => !i.ok).map(i => i.label).join('、')}`
          : '')
      : `有 ${editor.errors.length} 個格式問題`
    return editor.ok
  } catch {
    editor.ok = false
    editor.msg = '檢查失敗，請稍後再試'
    return false
  } finally {
    editor.busy = false
  }
}

async function saveDraft() {
  const obj = parseDraft()
  if (!obj) return
  editor.busy = true
  try {
    const res = await fetch(`/api/v1/events/briefs/${encodeURIComponent(obj.id || '')}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...auth.getAuthHeaders() },
      body: JSON.stringify(obj),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) {
      editor.ok = false
      editor.errors = json?.detail?.errors || []
      editor.msg = detailText(json, '存檔失敗')
      return
    }
    editor.ok = true
    editor.msg = '已存檔'
    await Promise.all([loadBriefs(), loadCalendar()])
  } catch {
    editor.ok = false
    editor.msg = '存檔失敗，請稍後再試'
  } finally {
    editor.busy = false
  }
}

// ── 論點抽取 ──
const claims = reactive({ source: '', text: '', busy: false, error: '', result: null })
const canExtract = computed(() => aiConfigured.value && !claims.busy && claims.text.trim().length >= 200)

async function extractClaims() {
  claims.busy = true
  claims.error = ''
  claims.result = null
  try {
    // 會等 LLM 回應（20～40 秒），不套重試包裝：重試只會讓人等更久、重複耗用額度
    const res = await fetch('/api/v1/events/claims/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: claims.text, source: claims.source }),
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok || !json.success) throw new Error(detailText(json, '論點抽取失敗'))
    claims.result = json.data
  } catch (e) {
    claims.error = e?.message || '論點抽取失敗'
  } finally {
    claims.busy = false
  }
}

onMounted(() => {
  due.value = dueDecisions()
  loadCalendar()
  loadBriefs()
  checkAiConfigured()
})
</script>

<style scoped>
.event-desk { display: flex; flex-direction: column; gap: var(--space-4); }
.page-header h1 { margin: 0 0 4px; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin: 0; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; }

.ev-due {
  display: block; padding: 10px 14px; border-radius: var(--radius-sm);
  background: var(--warn-soft); color: var(--warn); border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  font-size: 0.85rem; font-weight: 600; text-decoration: none;
}
.tabs { margin-bottom: 0; flex-wrap: wrap; }
.ev-tab { background: none; border: 0; border-bottom: 2px solid transparent; font: inherit; font-size: 0.88rem; }
.ev-tab.active { color: var(--accent-blue); border-bottom-color: var(--accent-blue); font-weight: 600; }
.ev-section { display: flex; flex-direction: column; gap: var(--space-4); }
.ev-lead { margin: 0; font-size: 0.88rem; line-height: 1.7; color: var(--text-secondary); max-width: 72ch; }
.ev-error { color: var(--up); font-size: 0.85rem; margin: 0; }
.ev-ok { color: var(--down); font-size: 0.85rem; margin: 0; }
.ev-warn {
  margin: 0; padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.84rem;
  background: var(--warn-soft); color: var(--warn);
}
.ev-foot { font-size: 0.76rem; line-height: 1.7; color: var(--text-muted); margin: 0; max-width: 80ch; }

/* 篩選 */
.ev-filters { display: flex; flex-wrap: wrap; gap: 6px; }
.ev-chip {
  font: inherit; font-size: 0.78rem; padding: 4px 10px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border-color); background: transparent; color: var(--text-muted);
}
.ev-chip.on { background: var(--blue-soft); color: var(--accent-blue); border-color: color-mix(in srgb, var(--blue) 45%, transparent); font-weight: 600; }

/* 日曆列 */
.ev-month h2 { margin: 0 0 8px; font-size: 1rem; }
.ev-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.ev-row { display: grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 10px 0; border-top: 1px dashed var(--border-color); }
.ev-row:first-child { border-top: 0; }
.ev-row.past { opacity: 0.6; }
.ev-row.today { background: var(--blue-soft); margin: 0 -8px; padding-left: 8px; padding-right: 8px; border-radius: var(--radius-sm); }
.ev-date { display: flex; flex-direction: column; font-size: 0.78rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.ev-date strong { font-size: 1.05rem; color: var(--text-primary); }
.ev-body { min-width: 0; }
.ev-title-line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 8px; }
.ev-imp { color: var(--warn); font-size: 0.6rem; letter-spacing: 1px; margin-right: 6px; vertical-align: middle; }
.ev-title { font-weight: 700; font-size: 0.92rem; }
.ev-cat, .ev-flag {
  font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
  border: 1px solid var(--border-color); color: var(--text-secondary);
}
.ev-cat[data-cat='fed'], .ev-cat[data-cat='macro_us'] { background: var(--blue-soft); color: var(--accent-blue); border-color: transparent; }
.ev-cat[data-cat='earnings'], .ev-cat[data-cat='company'] { background: var(--warn-soft); color: var(--warn); border-color: transparent; }
.ev-flag { background: var(--warn-soft); color: var(--warn); border-color: transparent; font-weight: 600; }
.ev-flag.scheduled, .ev-flag.closed, .ev-flag.opinion { background: transparent; color: var(--text-secondary); border-color: var(--border-color); }
.ev-flag.fact { background: var(--blue-soft); color: var(--accent-blue); }
.ev-away { margin-left: auto; font-size: 0.74rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.ev-away.soon { color: var(--warn); font-weight: 700; }
.ev-note { margin: 3px 0 0; font-size: 0.8rem; line-height: 1.6; color: var(--text-secondary); }
.ev-react { color: var(--accent-blue); }
.ev-links { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 4px; font-size: 0.76rem; }
.ev-links a { color: var(--accent-blue); }
.ev-link-btn { font: inherit; font-size: 0.76rem; background: none; border: 0; padding: 0; color: var(--up); cursor: pointer; text-decoration: underline; }

/* 簡報卡 */
.ev-brief-card { display: block; text-decoration: none; color: inherit; }
.ev-brief-card:hover { border-color: var(--accent-blue); }
.ev-brief-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.ev-brief-head h2 { margin: 0; font-size: 1.05rem; }
.ev-brief-meta { margin: 6px 0; font-size: 0.78rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.ev-brief-summary { margin: 0; font-size: 0.86rem; line-height: 1.7; color: var(--text-secondary); max-width: 80ch; }

/* 管理員表單 */
.ev-admin summary { cursor: pointer; font-weight: 600; font-size: 0.88rem; }
.ev-form { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
.ev-form label, .field { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-secondary); }
.ev-form label.wide { grid-column: span 2; }
.ev-form label.check { grid-column: 1 / -1; flex-direction: row; align-items: center; gap: 6px; }
.ev-form-actions { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 8px 0; }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); font: inherit; font-size: 0.86rem; }
.ev-json { width: 100%; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.78rem; line-height: 1.5; }
.ev-guide, .ev-errors { margin: 8px 0 0; padding-left: 18px; font-size: 0.78rem; line-height: 1.7; color: var(--text-secondary); }
.ev-errors { color: var(--up); }

/* 論點 */
.ev-claims-form { display: flex; flex-direction: column; gap: 10px; }
.ev-claims-result { display: flex; flex-direction: column; gap: 12px; }
.ev-claims-stats { margin: 0; font-size: 0.86rem; }
.ev-bad { color: var(--up); }
.ev-claim-list { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 14px; }
.ev-claim-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; font-size: 0.9rem; }
.ev-quote { margin: 6px 0; padding: 6px 10px; border-left: 3px solid var(--border-color); font-size: 0.82rem; color: var(--text-secondary); line-height: 1.6; }
.ev-quote.exact { border-left-color: var(--down); }
.ev-quote.approx { border-left-color: var(--warn); }
.ev-quote.none { border-left-color: var(--up); }
.ev-quote-tag { display: block; font-size: 0.72rem; margin-top: 2px; color: var(--text-muted); }
.ev-quote.none .ev-quote-tag { color: var(--up); font-weight: 600; }
.ev-claim-meta { display: grid; grid-template-columns: 6.5em 1fr; gap: 2px 10px; margin: 0; font-size: 0.8rem; line-height: 1.6; }
.ev-claim-meta dt { color: var(--text-muted); }
.ev-claim-meta dd { margin: 0; }
.ev-missing { font-size: 0.82rem; }
.ev-missing ul { margin: 4px 0 0; padding-left: 18px; line-height: 1.7; }

@media (max-width: 640px) {
  .ev-row { grid-template-columns: 64px 1fr; gap: 8px; }
  .ev-away { margin-left: 0; }
  .ev-form { grid-template-columns: 1fr 1fr; }
  .ev-form label.wide { grid-column: 1 / -1; }
}
</style>
