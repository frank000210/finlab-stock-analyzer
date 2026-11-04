<template>
  <details class="dist" data-testid="dist-source" :data-symbol="symbol">
    <summary>
      配息來源（收益／資本利得／收益平準金／本金）
      <span v-if="agg" class="agg-tag" :class="'a-' + agg.level" data-testid="dist-summary-tag">
        {{ aggIcon }} 已有 {{ agg.n }} 次資料・非收益來源 {{ pctText(agg.nonIncome) }}
      </span>
      <span v-else class="muted small">尚無資料</span>
    </summary>

    <p class="muted small intro">
      一檔高股息 ETF 的配息，可能來自成分股股利與利息（比較持久），也可能來自已實現資本利得、收益平準金甚至本金（市場轉弱時會先縮水）。
      這個比例只寫在各投信的「收益分配公告」裡，免費資料源沒有，所以不是自動算的：
      本站收錄的資料一律附公告連結；沒有的，可以對照投信公告自己填，只存在你的瀏覽器。
    </p>

    <div class="legend">
      <span v-for="p in PARTS" :key="p.key" class="lg"><i class="sw" :style="{ background: p.color }"></i>{{ p.label }}</span>
    </div>

    <ul class="rows">
      <li v-for="r in rows" :key="r.date" class="row" :data-date="r.date" :data-kind="r.kind">
        <div class="r-head">
          <span class="r-date">{{ r.date }} 除息</span>
          <span class="r-amt">配 {{ r.amount.toFixed(3) }} 元</span>
          <span v-if="r.kind === 'curated'" class="badge">收錄</span>
          <span v-else-if="r.kind === 'personal'" class="badge mine">我填的</span>
        </div>

        <template v-if="r.per_unit && editing !== r.date">
          <div class="stack" role="img" :aria-label="stackLabel(r.per_unit)">
            <template v-for="p in PARTS" :key="p.key">
              <span v-if="share(r.per_unit, p.key) > 0" class="seg"
                :style="{ width: share(r.per_unit, p.key) * 100 + '%', background: p.color }"
                :title="p.label + ' ' + pctText(share(r.per_unit, p.key), 1)">
                <template v-if="share(r.per_unit, p.key) >= 0.12">{{ pctText(share(r.per_unit, p.key)) }}</template>
              </span>
            </template>
          </div>
          <p class="r-detail small">
            <span v-for="p in PARTS" :key="p.key" class="dt">{{ p.short }} {{ Number(r.per_unit[p.key]).toFixed(3) }}</span>
          </p>
          <p v-if="isMismatch(r)" class="warn small" data-testid="dist-mismatch">
            ⚠ 四項合計 {{ total(r.per_unit).toFixed(3) }} 元，和除息紀錄的配息 {{ r.amount.toFixed(3) }} 元差太多，請確認填的是同一次配息、單位是「每單位、元」。
          </p>
          <p v-if="r.kind === 'curated'" class="small muted">
            來源：<a :href="r.source_url" target="_blank" rel="noopener noreferrer">{{ r.source }}</a>（公告日 {{ r.as_of }}）
          </p>
          <p v-if="r.kind === 'personal'" class="small">
            <button type="button" class="link" @click="startEdit(r)">修改</button>・<button type="button" class="link" data-testid="dist-clear" @click="clearPersonal(r.date)">清除</button>
          </p>
        </template>

        <!-- novalidate：驗證由 parseForm 統一處理，錯誤訊息才會顯示在表單裡（原生驗證泡泡會擋掉送出） -->
        <form v-else-if="editing === r.date" class="form" novalidate @submit.prevent="save(r)" data-testid="dist-form">
          <label v-for="p in PARTS" :key="p.key" class="fld">
            <span>{{ p.short }}</span>
            <input v-model="form[p.key]" type="number" min="0" step="0.001" inputmode="decimal" :data-part="p.key" />
          </label>
          <div class="f-actions">
            <button type="submit" class="btn xs" data-testid="dist-save">儲存</button>
            <button type="button" class="btn xs ghost" @click="cancel">取消</button>
          </div>
          <p v-if="formError" class="warn small" data-testid="dist-error">{{ formError }}</p>
          <p class="muted small">單位：每受益權單位、元，照投信公告的「配息組成」填；沒有的項目留空。</p>
        </form>

        <p v-else class="small">
          <button type="button" class="link" data-testid="dist-fill" @click="startEdit(r)">填寫這一次的來源</button>
        </p>
      </li>
    </ul>

    <p v-if="agg" class="verdict small" :class="'a-' + agg.level" data-testid="dist-verdict">
      {{ aggIcon }} 合併來看：收益 {{ pctText(agg.shares.income) }}、資本利得 {{ pctText(agg.shares.gain) }}、收益平準金 {{ pctText(agg.shares.equalization) }}、本金 {{ pctText(agg.shares.principal) }}。{{ LEVEL_TEXT[agg.level] }}
    </p>
    <p class="muted small">到投信官網該檔 ETF 的「收益分配」或「配息公告」，找「配息組成」。判斷門檻：非收益來源 > {{ pctText(NON_INCOME_LEVELS[0]) }} 留意、> {{ pctText(NON_INCOME_LEVELS[1]) }} 偏弱，有任何本金至少留意。</p>
  </details>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  PARTS, LEVEL_TEXT, NON_INCOME_LEVELS, total, shares, summarize, mismatch, pctText,
  loadPersonal, savePersonal, parseForm,
} from '../../lib/distributionSource'

const props = defineProps({
  symbol: { type: String, required: true },
  payouts: { type: Array, default: () => [] }, // [{ date, amount }]，除息日與每單位配息（來自配息體檢）
  curated: { type: Array, default: () => [] }, // 後端收錄的資料 [{ ex_date, per_unit, source, source_url, as_of }]
})

const SHOW_LAST = 4
const personal = ref(loadPersonal())
const editing = ref('')
const form = reactive({ income: '', gain: '', equalization: '', principal: '' })
const formError = ref('')

watch(() => props.symbol, () => { editing.value = ''; personal.value = loadPersonal() })

const rows = computed(() => {
  const curated = Object.fromEntries((props.curated || []).map(e => [e.ex_date, e]))
  const mine = personal.value[props.symbol] || {}
  return props.payouts.slice(-SHOW_LAST).reverse().map((p) => {
    const c = curated[p.date]
    if (c) return { date: p.date, amount: p.amount, kind: 'curated', per_unit: c.per_unit, source: c.source, source_url: c.source_url, as_of: c.as_of }
    if (mine[p.date]) return { date: p.date, amount: p.amount, kind: 'personal', per_unit: mine[p.date] }
    return { date: p.date, amount: p.amount, kind: 'none', per_unit: null }
  })
})

const agg = computed(() => summarize(rows.value.filter(r => r.per_unit).map(r => r.per_unit)))
const aggIcon = computed(() => ({ good: '✓', warn: '!', bad: '✗' }[agg.value?.level] || ''))

const share = (pu, key) => (shares(pu) || {})[key] || 0
const isMismatch = r => mismatch(r.per_unit, r.amount)
const stackLabel = pu => PARTS.map(p => `${p.short} ${pctText(share(pu, p.key), 0)}`).join('、')

function startEdit(r) {
  editing.value = r.date
  formError.value = ''
  for (const p of PARTS) form[p.key] = r.per_unit ? String(r.per_unit[p.key] ?? '') : ''
}

function cancel() { editing.value = ''; formError.value = '' }

function save(r) {
  const parsed = parseForm(form)
  if (parsed.error) { formError.value = parsed.error; return }
  const all = loadPersonal()
  all[props.symbol] = { ...(all[props.symbol] || {}), [r.date]: parsed.value }
  savePersonal(all)
  personal.value = all
  cancel()
}

function clearPersonal(date) {
  const all = loadPersonal()
  if (all[props.symbol]) {
    delete all[props.symbol][date]
    if (!Object.keys(all[props.symbol]).length) delete all[props.symbol]
  }
  savePersonal(all)
  personal.value = all
}
</script>

<style scoped>
.dist { margin-top: 12px; border-top: 1px dashed var(--border-color); padding-top: 10px; font-size: 0.84rem; }
.dist summary { cursor: pointer; font-weight: 600; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
.agg-tag { font-size: 0.74rem; font-weight: 600; padding: 1px 9px; border-radius: 999px; border: 1px solid currentColor; }
.a-good { color: var(--color-down); }
.a-warn { color: var(--color-warning); }
.a-bad { color: var(--color-up); }
.intro { margin: 8px 0; line-height: 1.55; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 6px 0 8px; font-size: 0.74rem; color: var(--text-muted); }
.lg { display: inline-flex; align-items: center; gap: 5px; }
.sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.rows { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.row { padding: 8px 10px; border: 1px solid var(--border-color); border-radius: 10px; }
.r-head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
.r-date { font-weight: 600; }
.r-amt { color: var(--text-muted); }
.badge { font-size: 0.68rem; padding: 0 7px; border-radius: 999px; border: 1px solid var(--accent-blue); color: var(--accent-blue); }
.badge.mine { border-color: var(--text-muted); color: var(--text-muted); }
.stack { display: flex; height: 20px; border-radius: 6px; overflow: hidden; margin: 6px 0 4px; background: var(--bg-card); }
.seg { display: inline-flex; align-items: center; justify-content: center; font-size: 0.68rem; color: #0b1220; font-weight: 700; min-width: 2px; }
.r-detail { display: flex; flex-wrap: wrap; gap: 2px 14px; margin: 2px 0; color: var(--text-muted); }
.warn { color: var(--color-warning); margin: 4px 0; }
.form { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: flex-end; margin-top: 6px; }
.fld { display: flex; flex-direction: column; gap: 2px; font-size: 0.74rem; color: var(--text-muted); }
.fld input { width: 92px; background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 8px; padding: 5px 8px; font-size: 0.84rem; }
.f-actions { display: flex; gap: 6px; }
.form > p { flex-basis: 100%; margin: 0; }
.link { background: none; border: none; padding: 0; color: var(--accent-blue); cursor: pointer; font-size: inherit; text-decoration: underline; }
.verdict { margin: 10px 0 4px; font-weight: 600; line-height: 1.55; }
.btn.xs { padding: 4px 12px; font-size: 0.78rem; }
.muted { color: var(--text-muted); }
.small { font-size: 0.8rem; }
p { margin: 4px 0; }
</style>
