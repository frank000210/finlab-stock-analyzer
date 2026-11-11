<template>
  <div class="bg-view">
    <header class="bg-hero" data-testid="guide-hero">
      <p class="eyebrow">建站教學</p>
      <h1>從零開始，做出一個自己的網站</h1>
      <p class="lead">
        這一頁用 FinLab（你現在看的這個網站）當真實範例，說明它怎麼從一個想法，變成 24 小時都連得上的網站。
        你<strong>不需要會寫程式</strong>：要做的只有申請帳號、做決定、驗收；寫程式與設定主機交給 AI。
      </p>
      <ul class="chips">
        <li>給非 IT 人員</li>
        <li>約 {{ META.readMinutes }} 分鐘讀完</li>
        <li>官方資料查證：{{ META.checkedOn }}</li>
      </ul>
      <div class="hero-actions">
        <button class="btn btn-primary" @click="goTo('github')">從申請 GitHub 開始</button>
        <button class="btn" data-testid="print-btn" @click="printPage"><Printer :size="15" aria-hidden="true" />列印／存成 PDF</button>
      </div>
    </header>

    <section class="card quick" data-testid="quick-summary" aria-labelledby="quick-h">
      <h2 id="quick-h">只想看懂、不想動手？看這 30 秒</h2>
      <ul>
        <li v-for="(q, i) in QUICK" :key="i" v-html="richText(q)"></li>
      </ul>
    </section>

    <div class="bg-layout">
      <nav class="bg-toc" :class="{ open: tocOpen }" aria-label="本頁章節" data-testid="toc">
        <button class="toc-toggle" type="button" :aria-expanded="tocOpen" @click="tocOpen = !tocOpen">
          章節與進度
          <ChevronDown :size="16" class="toc-chev" aria-hidden="true" />
        </button>
        <div class="toc-body">
          <div class="toc-progress" data-testid="overall-progress">
            <div class="toc-progress-text">
              <span>我的進度</span>
              <b>{{ overall.done }} / {{ overall.total }}</b>
            </div>
            <div class="bar" role="progressbar" aria-label="完成進度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="overall.pct">
              <i :style="{ width: overall.pct + '%' }"></i>
            </div>
            <button v-if="overall.done" class="link-btn" type="button" data-testid="reset-progress" @click="resetProgress">清除勾選</button>
          </div>
          <ol class="toc-list">
            <li v-for="(c, i) in CHAPTERS" :key="c.id">
              <a
                :href="'#' + c.id"
                data-testid="toc-link"
                :class="{ active: activeId === c.id }"
                :aria-current="activeId === c.id ? 'true' : undefined"
                @click.prevent="goTo(c.id)"
              >
                <span class="toc-no">{{ i + 1 }}</span>
                <span class="toc-title">{{ c.title }}</span>
                <span v-if="c.track" class="toc-prog">{{ chapterProgress[c.id].done }}/{{ chapterProgress[c.id].total }}</span>
              </a>
            </li>
          </ol>
        </div>
      </nav>

      <div class="bg-main">
        <!-- 1 全貌 -->
        <section id="overview" class="chapter" aria-labelledby="overview-h">
          <h2 id="overview-h"><span class="ch-no">1</span>先看全貌：網站就像一間餐廳</h2>
          <p class="ch-lead">想像你要開一間餐廳。網站從想法到上線，剛好對應這六個動作。</p>
          <GuideFigure :fig="FIGURES.overview" />
          <ol class="flow">
            <li v-for="(f, i) in FLOW" :key="f.name" class="flow-card" data-testid="flow-step">
              <span class="flow-no">{{ i + 1 }}</span>
              <span class="flow-icon"><component :is="ICONS[f.icon]" :size="20" aria-hidden="true" /></span>
              <h3>{{ f.name }}</h3>
              <span class="flow-like">像是：{{ f.like }}</span>
              <p>{{ f.text }}</p>
            </li>
          </ol>
          <div class="card setup">
            <h3>本站的實際配置</h3>
            <dl>
              <template v-for="[k, v] in OUR_SETUP" :key="k">
                <dt>{{ k }}</dt>
                <dd>{{ v }}</dd>
              </template>
            </dl>
            <p class="setup-note">以上是本站的選擇。換成別的 AI 工具或別家主機，整體流程與分工不變。</p>
          </div>
        </section>

        <!-- 2 名詞 -->
        <section id="words" class="chapter" aria-labelledby="words-h">
          <h2 id="words-h"><span class="ch-no">2</span>先認識 8 個名詞</h2>
          <p class="ch-lead">後面會一直出現這幾個詞。每個只要記住「一句白話」就夠了。</p>
          <div class="glossary">
            <article v-for="w in WORDS" :key="w.term" class="gloss" data-testid="glossary-card">
              <h3>{{ w.term }}</h3>
              <p class="gloss-plain">{{ w.plain }}</p>
              <p class="gloss-like">{{ w.like }}</p>
            </article>
          </div>
          <GuideFigure :fig="FIGURES.words" />
        </section>

        <!-- 3 GitHub -->
        <section id="github" class="chapter" aria-labelledby="github-h">
          <h2 id="github-h"><span class="ch-no">3</span>申請 GitHub 帳號</h2>
          <p class="ch-lead">{{ GITHUB.lead }}</p>
          <div class="steps">
            <GuideStep
              v-for="(s, i) in GITHUB.steps"
              :key="s.id"
              :step="s"
              :index="i"
              :done="isDone(s.id)"
              @toggle="toggle"
            />
          </div>
          <p class="callout info"><Info :size="16" aria-hidden="true" /><span><b>本站的做法：</b>{{ GITHUB.ours }}</span></p>
        </section>

        <!-- 4 主機 -->
        <section id="hosting" class="chapter" aria-labelledby="hosting-h">
          <h2 id="hosting-h"><span class="ch-no">4</span>申請網路主機</h2>
          <p class="ch-lead">{{ HOSTING.lead }}</p>

          <h3 class="sub">先選路線</h3>
          <p class="table-hint">表格可以左右滑動，看到全部欄位。</p>
          <div class="table-wrap" data-testid="route-table">
            <table>
              <thead>
                <tr><th v-for="h in HOSTING.routes.head" :key="h" scope="col">{{ h }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in HOSTING.routes.rows" :key="r[0]">
                  <th scope="row">{{ r[0] }}</th>
                  <td v-for="(c, i) in r.slice(1)" :key="i">{{ c }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="callout warn"><TriangleAlert :size="16" aria-hidden="true" /><span><b>{{ HOSTING.lesson.title }}</b><br />{{ HOSTING.lesson.text }}</span></p>

          <h3 class="sub">先看一張圖：別人怎麼走進你的網站</h3>
          <GuideFigure :fig="FIGURES.hosting" />

          <h3 class="sub">照本站的做法申請（騰訊雲 Lighthouse）</h3>
          <div class="steps">
            <GuideStep
              v-for="(s, i) in HOSTING.steps"
              :key="s.id"
              :step="s"
              :index="i"
              :done="isDone(s.id)"
              @toggle="toggle"
            />
          </div>
        </section>

        <!-- 5 分工 -->
        <section id="roles" class="chapter" aria-labelledby="roles-h">
          <h2 id="roles-h"><span class="ch-no">5</span>誰做什麼：人與 AI 的分工</h2>
          <p class="ch-lead">用 AI 開發，最重要的不是會不會寫程式，而是分清楚哪些事一定要你自己來。</p>
          <div class="roles">
            <article class="role human" data-testid="role-human">
              <h3><User :size="17" aria-hidden="true" />{{ ROLES.human.title }}</h3>
              <ul><li v-for="t in ROLES.human.items" :key="t">{{ t }}</li></ul>
            </article>
            <article class="role ai" data-testid="role-ai">
              <h3><Bot :size="17" aria-hidden="true" />{{ ROLES.ai.title }}</h3>
              <ul><li v-for="t in ROLES.ai.items" :key="t">{{ t }}</li></ul>
            </article>
          </div>
          <p class="callout info"><Info :size="16" aria-hidden="true" /><span><b>為什麼帳號與付款要自己來：</b>{{ ROLES.why }}</span></p>
          <h3 class="sub">你的三道關卡</h3>
          <ol class="gates">
            <li v-for="(g, i) in ROLES.gates" :key="g.name" data-testid="gate">
              <span class="gate-no">{{ i + 1 }}</span>
              <div><b>{{ g.name }}</b><p>{{ g.text }}</p></div>
            </li>
          </ol>
        </section>

        <!-- 6 日常一輪 -->
        <section id="cycle" class="chapter" aria-labelledby="cycle-h">
          <h2 id="cycle-h"><span class="ch-no">6</span>日常開發一輪長怎樣</h2>
          <p class="ch-lead">{{ CYCLE.lead }}</p>
          <GuideFigure :fig="FIGURES.cycle" />
          <ol class="timeline">
            <li v-for="(s, i) in CYCLE.steps" :key="s.name" data-testid="cycle-step">
              <span class="tl-no">{{ i + 1 }}</span>
              <div class="tl-body">
                <div class="tl-head"><b>{{ s.name }}</b><span class="who" :class="whoClass(s.who)">{{ s.who }}</span></div>
                <p>{{ s.text }}</p>
              </div>
            </li>
          </ol>
          <h3 class="sub">怎麼跟 AI 說需求</h3>
          <div class="ask">
            <div class="ask-card bad"><span class="ask-tag">不好的說法</span><p>「{{ CYCLE.ask.bad }}」</p></div>
            <div class="ask-card good"><span class="ask-tag">好的說法</span><p>「{{ CYCLE.ask.good }}」</p></div>
          </div>
          <ul class="tips">
            <li v-for="(t, i) in CYCLE.ask.tips" :key="i" v-html="richText(t)"></li>
          </ul>
        </section>

        <!-- 7 上線之後 -->
        <section id="after" class="chapter" aria-labelledby="after-h">
          <h2 id="after-h"><span class="ch-no">7</span>上線之後要顧的事</h2>
          <p class="ch-lead">網站上線只是開始。下面六件事，決定它能不能長久開著。</p>
          <div class="afters">
            <article v-for="a in AFTER" :key="a.title" class="after" data-testid="after-card">
              <h3>{{ a.title }}</h3>
              <p>{{ a.text }}</p>
            </article>
          </div>
        </section>

        <!-- 8 速查 -->
        <section id="faq" class="chapter" aria-labelledby="faq-h">
          <h2 id="faq-h"><span class="ch-no">8</span>速查：檢查清單與常見問題</h2>

          <h3 class="sub">上線前最後檢查</h3>
          <ul class="checklist">
            <li v-for="c in CHECKLIST" :key="c.id" data-testid="checklist-item">
              <label>
                <input type="checkbox" :checked="isDone(c.id)" :data-testid="`check-${c.id}`" @change="toggle(c.id)" />
                <span>{{ c.text }}</span>
              </label>
            </li>
          </ul>

          <h3 class="sub">常見問題</h3>
          <div class="faqs">
            <details v-for="f in FAQ" :key="f.q" class="faq-item" data-testid="faq-item">
              <summary>{{ f.q }}</summary>
              <p>{{ f.a }}</p>
            </details>
          </div>

          <h3 class="sub">延伸閱讀</h3>
          <div class="more">
            <router-link v-for="l in LINKS" :key="l.to" :to="l.to" class="more-card">
              <b>{{ l.title }} →</b>
              <span>{{ l.text }}</span>
            </router-link>
          </div>

          <div class="sources" data-testid="sources">
            <h3>資料來源（查證日期 {{ META.checkedOn }}）</h3>
            <p>申請步驟與價格會隨官網改版而變，實際操作請以官方文件與購買頁為準。</p>
            <ul>
              <li v-for="s in SOURCES" :key="s.url">
                <a :href="s.url" target="_blank" rel="noopener noreferrer">{{ s.title }}<ExternalLink :size="12" aria-hidden="true" /></a>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bot, ChevronDown, ClipboardCheck, ExternalLink, GitBranch, Globe, Info,
  Lightbulb, Printer, Server, TriangleAlert, User,
} from 'lucide-vue-next'
import GuideFigure from '../components/guide/GuideFigure.vue'
import GuideStep from '../components/guide/GuideStep.vue'
import { richText } from '../lib/guideText.js'
import {
  AFTER, CHAPTERS, CHECKLIST, CYCLE, FAQ, FIGURES, FLOW, GITHUB, HOSTING, LINKS, META,
  OUR_SETUP, QUICK, ROLES, SOURCES, WORDS,
} from '../lib/buildGuideContent.js'

const ICONS = { Lightbulb, Bot, GitBranch, ClipboardCheck, Server, Globe }

const route = useRoute()
const router = useRouter()

// ── 完成進度：只存在這台瀏覽器（localStorage 取不到時，頁面照常運作、只是不記得）──
const DONE_KEY = 'finlab.buildGuide.done'
const TRACKED = {
  github: GITHUB.steps.map(s => s.id),
  hosting: HOSTING.steps.map(s => s.id),
  faq: CHECKLIST.map(c => c.id),
}
const KNOWN_IDS = new Set(Object.values(TRACKED).flat())

function loadDone() {
  try {
    const raw = JSON.parse(localStorage.getItem(DONE_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter(id => KNOWN_IDS.has(id)) : []
  } catch {
    return []
  }
}
function saveDone() {
  try { localStorage.setItem(DONE_KEY, JSON.stringify([...doneSet.value])) } catch { /* 無痕或被封鎖時不記就好 */ }
}

const doneSet = ref(new Set(loadDone()))
const isDone = id => doneSet.value.has(id)

function toggle(id) {
  const next = new Set(doneSet.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  doneSet.value = next
  saveDone()
}
function resetProgress() {
  doneSet.value = new Set()
  saveDone()
}

const chapterProgress = computed(() => Object.fromEntries(
  Object.entries(TRACKED).map(([k, ids]) => [k, { done: ids.filter(isDone).length, total: ids.length }]),
))
const overall = computed(() => {
  let done = 0
  let total = 0
  for (const p of Object.values(chapterProgress.value)) { done += p.done; total += p.total }
  return { done, total, pct: total ? Math.round((done / total) * 100) : 0 }
})

// ── 章節導覽 ──────────────────────────────────────────
const activeId = ref(CHAPTERS[0].id)
const tocOpen = ref(false)

// 最近一次捲去的章節：點目錄時我們自己會改網址 #，這時 watch 不必再捲一次
let lastTarget = ''

function goTo(id) {
  const el = document.getElementById(id)
  if (!el) return
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  lastTarget = id
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  activeId.value = id
  tocOpen.value = false
  router.replace({ hash: '#' + id }).catch(() => {})
}

// 網址的 #章節 被改掉（手動改網址、瀏覽器上一頁）而不是點目錄時，也要捲到該章。
// 用立即捲動：它會中斷還在進行的平滑捲動，不會被舊動畫拉回原處。
watch(() => route.hash, (h) => {
  const id = h.replace(/^#/, '')
  if (!id || id === lastTarget || !CHAPTERS.some(c => c.id === id)) return
  lastTarget = id
  document.getElementById(id)?.scrollIntoView({ behavior: 'auto', block: 'start' })
  activeId.value = id
})

let observer = null
function watchChapters() {
  if (!('IntersectionObserver' in window)) return
  observer = new IntersectionObserver((entries) => {
    const hit = entries
      .filter(e => e.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
    if (hit) activeId.value = hit.target.id
  }, { rootMargin: '-10% 0px -70% 0px' })
  document.querySelectorAll('.bg-main > section[id]').forEach(el => observer.observe(el))
}

function whoClass(who) {
  if (who === '你') return 'human'
  if (who === 'AI') return 'ai'
  return 'bot'
}

// ── 列印：展開所有常見問題，列完再還原 ─────────────────────
let openedBeforePrint = []
function expandForPrint() {
  openedBeforePrint = []
  document.querySelectorAll('.faq-item').forEach((d) => {
    if (!d.open) { d.open = true; openedBeforePrint.push(d) }
  })
}
function restoreAfterPrint() {
  openedBeforePrint.forEach((d) => { d.open = false })
  openedBeforePrint = []
}
function printPage() { window.print() }

onMounted(async () => {
  document.title = '建站教學｜FinLab'
  window.addEventListener('beforeprint', expandForPrint)
  window.addEventListener('afterprint', restoreAfterPrint)
  await nextTick()
  watchChapters()
  const hash = route.hash.replace(/^#/, '')
  if (hash && CHAPTERS.some(c => c.id === hash)) goTo(hash)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('beforeprint', expandForPrint)
  window.removeEventListener('afterprint', restoreAfterPrint)
})
</script>

<style scoped>
.bg-view { max-width: 1120px; margin: 0 auto; display: flex; flex-direction: column; gap: 22px; }

/* ── 頂部 ─────────────────────────────── */
.bg-hero h1 { margin: 6px 0 12px; font-size: 2rem; text-wrap: balance; }
.lead { max-width: 66ch; margin: 0; font-size: 1.02rem; line-height: 1.8; color: var(--text-secondary); }
.lead strong { color: var(--text-primary); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 16px 0 0; }
.chips li {
  font-size: 0.78rem; color: var(--text-muted);
  background: var(--bg-well); border: 1px solid var(--border-color);
  border-radius: 999px; padding: 3px 11px;
}
.hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.hero-actions .btn { display: inline-flex; align-items: center; gap: 6px; }

.quick h2 { margin: 0 0 10px; font-size: 1.05rem; }
.quick ul { margin: 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 6px; }
.quick li { line-height: 1.7; color: var(--text-secondary); }
.quick :deep(strong) { color: var(--text-primary); }

/* ── 版型：左章節、右內容 ─────────────────── */
.bg-layout { display: grid; grid-template-columns: 236px minmax(0, 1fr); gap: 32px; align-items: start; }

.bg-toc {
  position: sticky; top: 16px;
  background: var(--bg-card); border: 1px solid var(--border-color);
  border-radius: 14px; padding: 14px;
  max-height: calc(100vh - 32px); overflow-y: auto;
}
.toc-toggle { display: none; }
.toc-progress { display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color); margin-bottom: 8px; }
.toc-progress-text { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.toc-progress-text b { color: var(--text-primary); }
.bar { height: 6px; background: var(--bg-well); border-radius: 999px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent-blue); border-radius: 999px; transition: width 0.25s ease; }
.link-btn { align-self: flex-start; background: none; border: none; padding: 0; font-size: 0.76rem; color: var(--text-muted); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }
.link-btn:hover { color: var(--text-primary); }

.toc-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.toc-list a {
  display: flex; align-items: baseline; gap: 8px;
  padding: 7px 8px; border-radius: 8px;
  color: var(--text-secondary); text-decoration: none; font-size: 0.86rem; line-height: 1.4;
}
.toc-list a:hover { background: var(--bg-hover); color: var(--text-primary); }
.toc-list a.active { background: color-mix(in srgb, var(--blue) 14%, transparent); color: var(--text-primary); font-weight: 600; }
.toc-list a:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 1px; }
.toc-no { flex: none; width: 1.2em; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.toc-title { flex: 1; min-width: 0; }
.toc-prog { flex: none; font-size: 0.72rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }

.bg-main { display: flex; flex-direction: column; gap: 44px; min-width: 0; }

/* ── 章節 ─────────────────────────────── */
.chapter { display: flex; flex-direction: column; gap: 16px; scroll-margin-top: 16px; }
.chapter > h2 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 1.5rem; text-wrap: balance; }
.ch-no {
  flex: none; display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 50%;
  background: color-mix(in srgb, var(--blue) 16%, transparent); color: var(--accent-blue);
  font-size: 0.95rem; font-weight: 800;
}
.ch-lead { margin: 0; max-width: 68ch; font-size: 0.98rem; line-height: 1.8; color: var(--text-secondary); }
.sub { margin: 8px 0 0; font-size: 1.1rem; }

/* 全貌 */
.flow { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
.flow-card {
  position: relative; background: var(--bg-card); border: 1px solid var(--border-color);
  border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 6px;
}
.flow-no { position: absolute; top: 12px; right: 14px; font-size: 0.78rem; font-weight: 700; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.flow-icon {
  width: 38px; height: 38px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--blue) 14%, transparent); color: var(--accent-blue);
}
.flow-card h3 { margin: 6px 0 0; font-size: 1.02rem; }
.flow-like { font-size: 0.78rem; font-weight: 600; color: var(--accent-cyan); }
.flow-card p { margin: 0; font-size: 0.88rem; line-height: 1.65; color: var(--text-secondary); }

.setup h3 { margin: 0 0 10px; }
.setup dl { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 8px 18px; }
.setup dt { font-size: 0.85rem; color: var(--text-muted); }
.setup dd { margin: 0; font-size: 0.9rem; color: var(--text-primary); line-height: 1.6; }
.setup-note { margin: 12px 0 0; font-size: 0.84rem; color: var(--text-muted); }

/* 名詞 */
.glossary { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
.gloss { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 6px; }
.gloss h3 { margin: 0; font-size: 1.02rem; color: var(--accent-blue); }
.gloss-plain { margin: 0; font-weight: 600; color: var(--text-primary); font-size: 0.93rem; line-height: 1.6; }
.gloss-like { margin: 0; font-size: 0.86rem; line-height: 1.65; color: var(--text-muted); }

/* 步驟、提示框 */
.steps { display: flex; flex-direction: column; gap: 14px; }
.callout {
  display: flex; align-items: flex-start; gap: 10px; margin: 0;
  padding: 12px 14px; border-radius: 12px; font-size: 0.9rem; line-height: 1.7; color: var(--text-secondary);
}
.callout svg { flex: none; margin-top: 4px; }
.callout b { color: var(--text-primary); }
.callout.info { background: color-mix(in srgb, var(--blue) 10%, transparent); }
.callout.info svg { color: var(--accent-blue); }
.callout.warn { background: color-mix(in srgb, var(--warn) 12%, transparent); }
.callout.warn svg { color: var(--color-warning); }

/* 路線比較表 */
.table-hint { display: none; margin: -8px 0 0; font-size: 0.8rem; color: var(--text-muted); }
.table-wrap { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 14px; background: var(--bg-card); }
table { width: 100%; border-collapse: collapse; min-width: 720px; }
th, td { text-align: left; vertical-align: top; padding: 12px 14px; font-size: 0.86rem; line-height: 1.6; border-bottom: 1px solid var(--border-color); }
thead th { font-size: 0.76rem; letter-spacing: 0.04em; color: var(--text-muted); background: var(--bg-well); }
tbody th { color: var(--text-primary); font-weight: 600; width: 22%; }
tbody td { color: var(--text-secondary); }
tbody tr:last-child th, tbody tr:last-child td { border-bottom: none; }

/* 分工 */
.roles { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.role { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 18px; }
.role h3 { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; font-size: 1.05rem; }
.role.human h3 { color: var(--color-warning); }
.role.ai h3 { color: var(--accent-blue); }
.role ul { margin: 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 6px; }
.role li { line-height: 1.65; font-size: 0.92rem; color: var(--text-secondary); }
.gates { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.gates li { display: flex; gap: 12px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px; }
.gate-no, .tl-no {
  flex: none; width: 26px; height: 26px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--bg-well); border: 1px solid var(--border-color);
  font-size: 0.8rem; font-weight: 700; color: var(--accent-blue); font-variant-numeric: tabular-nums;
}
.gates b { color: var(--text-primary); }
.gates p { margin: 4px 0 0; font-size: 0.86rem; line-height: 1.6; color: var(--text-secondary); }

/* 日常一輪 */
.timeline { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0; }
.timeline li { display: flex; gap: 14px; position: relative; padding-bottom: 18px; }
.timeline li:not(:last-child)::before {
  content: ''; position: absolute; left: 12.5px; top: 28px; bottom: 2px; width: 1px; background: var(--border-color);
}
.tl-body { flex: 1; min-width: 0; }
.tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tl-head b { color: var(--text-primary); font-size: 0.98rem; }
.tl-body p { margin: 4px 0 0; font-size: 0.9rem; line-height: 1.7; color: var(--text-secondary); }
.who { font-size: 0.72rem; font-weight: 700; padding: 1px 9px; border-radius: 999px; }
.who.human { background: color-mix(in srgb, var(--warn) 16%, transparent); color: var(--color-warning); }
.who.ai { background: color-mix(in srgb, var(--blue) 16%, transparent); color: var(--accent-blue); }
.who.bot { background: color-mix(in srgb, var(--down) 16%, transparent); color: var(--color-down); }

.ask { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.ask-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px; }
.ask-card p { margin: 6px 0 0; font-size: 0.92rem; line-height: 1.75; color: var(--text-secondary); }
.ask-tag { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.04em; }
.ask-card.bad .ask-tag { color: var(--color-warning); }
.ask-card.good .ask-tag { color: var(--color-down); }
.tips { margin: 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 6px; }
.tips li { line-height: 1.7; font-size: 0.92rem; color: var(--text-secondary); }
.tips :deep(strong) { color: var(--text-primary); }

/* 上線之後 */
.afters { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }
.after { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px; }
.after h3 { margin: 0 0 6px; font-size: 1.02rem; }
.after p { margin: 0; font-size: 0.88rem; line-height: 1.7; color: var(--text-secondary); }

/* 速查 */
.checklist { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
.checklist li { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; }
.checklist label { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; cursor: pointer; font-size: 0.9rem; line-height: 1.6; color: var(--text-secondary); }
.checklist input { flex: none; width: 18px; height: 18px; margin-top: 3px; accent-color: var(--accent-blue); cursor: pointer; }
.checklist input:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; }
.checklist input:checked + span { color: var(--text-muted); text-decoration: line-through; }

.faqs { display: flex; flex-direction: column; gap: 8px; }
.faq-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 0 16px; }
.faq-item summary { padding: 13px 0; cursor: pointer; font-weight: 600; color: var(--text-primary); font-size: 0.95rem; }
.faq-item summary:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 2px; border-radius: 6px; }
.faq-item p { margin: 0 0 14px; font-size: 0.9rem; line-height: 1.8; color: var(--text-secondary); }

.more { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.more-card {
  display: flex; flex-direction: column; gap: 4px; text-decoration: none;
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 16px;
}
.more-card:hover { background: var(--bg-hover); }
.more-card b { color: var(--accent-blue); }
.more-card span { font-size: 0.86rem; line-height: 1.6; color: var(--text-secondary); }

.sources { padding-top: 6px; }
.sources h3 { margin: 0 0 6px; font-size: 0.95rem; }
.sources p { margin: 0 0 8px; font-size: 0.84rem; color: var(--text-muted); }
.sources ul { margin: 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 4px; }
.sources li { font-size: 0.84rem; }
.sources a { color: var(--text-muted); text-decoration: underline; text-underline-offset: 2px; display: inline-flex; align-items: center; gap: 4px; }
.sources a:hover { color: var(--accent-blue); }

/* ── 窄螢幕：章節收成一顆按鈕 ───────────────── */
@media (max-width: 900px) {
  .bg-layout { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .bg-toc { position: static; max-height: none; overflow: visible; padding: 0; }
  .toc-toggle {
    display: flex; align-items: center; justify-content: space-between; width: 100%;
    padding: 12px 14px; background: none; border: none; color: var(--text-primary);
    font: inherit; font-weight: 600; cursor: pointer; border-radius: 14px;
  }
  .toc-toggle:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: -2px; }
  .toc-chev { transition: transform 0.15s ease; }
  .bg-toc.open .toc-chev { transform: rotate(180deg); }
  .toc-body { display: none; padding: 0 14px 14px; }
  .bg-toc.open .toc-body { display: block; }
  .bg-hero h1 { font-size: 1.6rem; }
  .chapter > h2 { font-size: 1.3rem; }
  .table-hint { display: block; }
  .setup dl { grid-template-columns: 1fr; gap: 2px; }
  .setup dd { margin-bottom: 8px; }
}

@media (prefers-reduced-motion: reduce) {
  .bar i, .toc-chev { transition: none; }
}

/* ── 列印：改成淺底深字，並隱藏導覽與按鈕 ─────────── */
@media print {
  .bg-view {
    --bg-card: #ffffff; --bg-well: #f3f5f8; --bg-hover: #f3f5f8;
    --text-primary: #111827; --text-secondary: #1f2937; --text-muted: #4b5563;
    --border-color: #cbd5e1; --accent-blue: #1d4ed8; --accent-cyan: #0e7490;
    --color-warning: #b45309; --color-down: #047857;
    color: var(--on-accent); max-width: none;
  }
  .bg-toc, .hero-actions { display: none; }
  .bg-layout { display: block; }
  .bg-main { gap: 24px; }
  .chapter { break-inside: auto; }
  .chapter > h2 { break-after: avoid; }
  .flow-card, .gloss, .role, .after, .faq-item, .timeline li { break-inside: avoid; }
}
</style>

<style>
/* 全站側邊欄與計數器在 scoped 樣式管不到，列印時另外隱藏 */
@media print {
  .app-sidebar, .sidebar-mobile-toggle, .sidebar-backdrop, .global-counter-wrap, .onboard-banner { display: none !important; }
  body { background: #fff !important; }
}
</style>
