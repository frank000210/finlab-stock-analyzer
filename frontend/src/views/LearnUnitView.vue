<template>
  <div class="unit-page">
    <div class="crumbs">
      <router-link to="/learn">學習中心</router-link>
      <span v-if="meta"> / {{ meta.code }} {{ meta.title }}</span>
    </div>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <div v-if="loading" class="empty-state">載入中…</div>

    <div v-else-if="meta" class="layout">
      <nav class="toc" aria-label="本單元目錄">
        <p class="toc-title">本單元</p>
        <a v-for="item in toc" :key="item.id" :href="`#${item.id}`" :class="`lv${item.level}`"
           @click.prevent="gotoId(item.id)">{{ item.text }}</a>
        <a v-if="labReadme" href="#lab" @click.prevent="gotoId('lab')" class="lv2">🛠 動手實作</a>
        <a v-if="quiz" href="#quiz" @click.prevent="gotoId('quiz')" class="lv2">📝 單元測驗</a>
        <a v-if="isCapstone" href="#project" @click.prevent="gotoId('project')" class="lv2">🏁 送出專題</a>
      </nav>

      <main class="content">
        <section class="card objectives">
          <div class="obj-head">
            <span class="code">{{ meta.code }}</span>
            <span class="muted">約 {{ meta.minutes }} 分鐘{{ meta.required ? ' · 必修' : '' }}</span>
            <span v-if="progress?.passed" class="pill ok">✅ 測驗已通過</span>
          </div>
          <p class="obj-label">學完這個單元，你能夠：</p>
          <ul><li v-for="o in meta.objectives" :key="o">{{ o }}</li></ul>
          <div v-if="meta.features?.length" class="features">
            <span v-for="f in meta.features" :key="f" class="tag">{{ f }}</span>
          </div>
        </section>

        <article class="md" v-html="html" data-testid="unit-content"></article>

        <section v-if="labReadme" id="lab" class="card lab-card" data-testid="unit-lab">
          <div class="lab-head">
            <h2>🛠 動手實作</h2>
            <a class="btn btn-secondary sm" :href="`/api/v1/course/units/${meta.id}/lab.zip`" download>下載 lab 起始檔</a>
          </div>
          <div class="md" v-html="labHtml"></div>
          <label v-if="auth.isLoggedIn" class="lab-done">
            <input type="checkbox" :checked="!!progress?.lab_done" :disabled="labBusy" @change="toggleLab($event.target.checked)" />
            我已完成這個 lab（執行 <code>check.py</code> 全部通過）
          </label>
          <p v-else class="muted">登入後可以記錄 lab 完成狀態。</p>
        </section>

        <div v-if="quiz" id="quiz">
          <CourseQuiz :quiz="quiz" :submit-path="`/units/${meta.id}/quiz`" :tutor-enabled="tutorUsable"
                      :show-login-hint="!auth.isLoggedIn"
                      @graded="onGraded" @goto-section="gotoSection" @ask-tutor="openTutor" />
        </div>

        <section v-if="isCapstone" id="project" class="card project-card" data-testid="project-form">
          <h2>🏁 送出期末專題</h2>
          <template v-if="!auth.isLoggedIn">
            <p class="muted">請先在學習中心首頁登入。</p>
          </template>
          <template v-else-if="project?.status === 'approved'">
            <p>🎉 專題已通過審核！</p>
            <router-link :to="`/learn/cert/${project.cert_id}`" class="btn btn-primary">查看結業證書</router-link>
          </template>
          <template v-else>
            <div v-if="project" class="project-status" :class="project.status">
              目前狀態：<strong>{{ projectStatusLabel }}</strong>
              <p v-if="project.review_comment" class="muted">審核意見：{{ project.review_comment }}</p>
            </div>
            <p v-if="!allRequiredPassed" class="muted">
              必修單元尚未全部通過（{{ passedRequired.length }} / {{ requiredIds.length }}），通過後才能送出。
            </p>
            <label class="field"><span>repo 網址（https://）</span>
              <input v-model.trim="projectForm.repo_url" class="inp" placeholder="https://github.com/you/my-claude-toolkit" /></label>
            <label class="field"><span>專題說明（至少 50 字）</span>
              <textarea v-model="projectForm.summary" class="inp" rows="8" maxlength="6000"
                        placeholder="做了哪些元件、各解決什麼痛點、為什麼選這個機制、遇到什麼困難"></textarea></label>
            <button class="btn btn-primary" type="button" :disabled="projectBusy || !allRequiredPassed || projectForm.summary.trim().length < 50"
                    @click="submitProject">{{ projectBusy ? '送出中…（AI 初評約需 30 秒）' : '送出專題' }}</button>
            <p v-if="projectError" class="error-text" role="alert">{{ projectError }}</p>
            <div v-if="project?.ai_feedback" class="ai-feedback">
              <p class="obj-label">🤖 AI 初審回饋</p>
              <div class="md" v-html="renderChatMarkdown(project.ai_feedback)"></div>
            </div>
          </template>
        </section>

        <nav class="pager">
          <router-link v-if="prevId" :to="`/learn/u/${prevId}`" class="btn btn-secondary">← 上一單元</router-link>
          <span></span>
          <router-link v-if="nextId" :to="`/learn/u/${nextId}`" class="btn btn-primary">下一單元 →</router-link>
        </nav>
      </main>
    </div>

    <button v-if="meta && !tutorOpen" class="tutor-fab" type="button" @click="openTutor('')" data-testid="tutor-open">🤖 問 AI 助教</button>
    <CourseTutor v-if="meta" :open="tutorOpen" :unit-id="meta.id" :unit-title="`${meta.code} ${meta.title}`"
                 :available="tutorUsable" :prefill="tutorPrefill" @close="tutorOpen = false" />
    <div v-if="tutorOpen && !auth.isLoggedIn" class="tutor-login-hint" role="status">AI 助教需要先登入。</div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CourseQuiz from '../components/course/CourseQuiz.vue'
import CourseTutor from '../components/course/CourseTutor.vue'
import { courseFetch } from '../lib/courseApi.js'
import { renderChatMarkdown, renderCourseMarkdown, sectionId } from '../lib/courseMarkdown.js'
import { useAuthStore } from '../stores/auth.js'

const route = useRoute()
const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const meta = ref(null)
const html = ref('')
const toc = ref([])
const labReadme = ref('')
const labHtml = ref('')
const quiz = ref(null)
const prevId = ref(null)
const nextId = ref(null)
const me = ref(null)
const tutorAvailable = ref(false)
const tutorOpen = ref(false)
const tutorPrefill = ref('')
const labBusy = ref(false)
const project = ref(null)
const projectForm = reactive({ repo_url: '', summary: '' })
const projectBusy = ref(false)
const projectError = ref('')

const isCapstone = computed(() => meta.value?.id === 'l10')
const progress = computed(() => me.value?.progress?.units?.[meta.value?.id] || null)
const requiredIds = computed(() => me.value?.progress?.required || [])
const passedRequired = computed(() => me.value?.progress?.passed_required || [])
const allRequiredPassed = computed(() => !!me.value?.progress?.all_required_passed)
const tutorUsable = computed(() => tutorAvailable.value && auth.isLoggedIn)
const projectStatusLabel = computed(() => ({ pending: '審核中', rejected: '需要補強後重新送出', approved: '已通過' }[project.value?.status] || ''))

function gotoId(id) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function gotoSection(section) { gotoId(sectionId(section)) }
function openTutor(prefill) {
  tutorPrefill.value = ''
  nextTick(() => { tutorPrefill.value = prefill || '' })
  tutorOpen.value = true
}

async function loadMe() {
  if (!auth.isLoggedIn) { me.value = null; return }
  try {
    me.value = await courseFetch('/me')
    project.value = me.value.project
    if (project.value) {
      projectForm.repo_url = project.value.repo_url || ''
      projectForm.summary = project.value.summary || ''
    }
  } catch { /* 進度載入失敗不影響閱讀 */ }
}

async function load(unitId) {
  loading.value = true
  error.value = ''
  try {
    const [unit, catalog] = await Promise.all([courseFetch(`/units/${unitId}`), courseFetch('/catalog')])
    meta.value = unit.meta
    const rendered = renderCourseMarkdown(unit.markdown)
    html.value = rendered.html
    toc.value = rendered.toc.filter(t => t.level === 2)
    labReadme.value = unit.lab_readme || ''
    labHtml.value = labReadme.value ? renderCourseMarkdown(labReadme.value).html : ''
    quiz.value = unit.quiz
    prevId.value = unit.prev
    nextId.value = unit.next
    tutorAvailable.value = !!catalog.tutor_available
    document.title = `${unit.meta.code} ${unit.meta.title}｜學習中心`
    await loadMe()
  } catch (e) {
    meta.value = null
    error.value = e.status === 404 ? '找不到這個單元。' : e.message
  } finally {
    loading.value = false
    window.scrollTo({ top: 0 })
  }
}

async function onGraded() { await loadMe() }

async function toggleLab(done) {
  labBusy.value = true
  try {
    await courseFetch(`/units/${meta.value.id}/lab`, { method: 'POST', body: { done } })
    await loadMe()
  } catch (e) {
    error.value = e.message
  } finally {
    labBusy.value = false
  }
}

async function submitProject() {
  projectBusy.value = true
  projectError.value = ''
  try {
    await courseFetch('/project', { method: 'POST', body: { ...projectForm } })
    await loadMe()
  } catch (e) {
    projectError.value = e.message
  } finally {
    projectBusy.value = false
  }
}

watch(() => route.params.unitId, (id) => { if (id) { tutorOpen.value = false; load(id) } }, { immediate: true })
watch(() => auth.isLoggedIn, () => loadMe())
</script>

<style scoped>
.unit-page { padding: 24px; max-width: 1240px; margin: 0 auto; }
.crumbs { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 14px; }
.crumbs a { color: var(--accent-cyan); text-decoration: none; }
.error-text { color: var(--color-warning); }
.layout { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 28px; align-items: start; }
.toc { position: sticky; top: 16px; display: flex; flex-direction: column; gap: 2px; max-height: calc(100vh - 32px); overflow-y: auto; }
.toc-title { font-size: 0.75rem; letter-spacing: 0.08em; color: var(--text-muted); margin: 0 0 6px; }
.toc a { color: var(--text-secondary); text-decoration: none; font-size: 0.84rem; padding: 5px 8px; border-radius: 6px; line-height: 1.4; }
.toc a:hover { background: var(--bg-hover); color: var(--text-primary); }
.content { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.objectives .obj-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.code { font-weight: 700; color: var(--accent-cyan); }
.muted { color: var(--text-muted); font-size: 0.85rem; }
.pill.ok { font-size: 0.78rem; padding: 2px 8px; border-radius: 999px; background: var(--down-soft); }
.obj-label { font-weight: 600; margin: 0 0 6px; }
.objectives ul { margin: 0; padding-left: 20px; color: var(--text-secondary); line-height: 1.7; }
.features { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.tag { font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; background: var(--bg-elevated); color: var(--text-secondary); }
.sm { padding: 6px 12px; font-size: 0.85rem; }

.md { color: var(--text-secondary); line-height: 1.8; font-size: 0.95rem; overflow-wrap: anywhere; }
.md :deep(h1) { font-size: 1.6rem; color: var(--text-primary); margin: 0 0 12px; }
.md :deep(h2) { font-size: 1.25rem; color: var(--text-primary); margin: 32px 0 10px; padding-top: 8px; scroll-margin-top: 16px; border-top: 1px solid var(--border-color); }
.md :deep(h3) { font-size: 1.05rem; color: var(--text-primary); margin: 22px 0 8px; scroll-margin-top: 16px; }
.md :deep(blockquote) { margin: 0 0 16px; padding: 10px 14px; border-left: 3px solid var(--accent-cyan); background: var(--bg-well); border-radius: 0 8px 8px 0; }
.md :deep(blockquote p) { margin: 2px 0; }
.md :deep(code) { font-family: ui-monospace, 'Cascadia Code', monospace; font-size: 0.86em; background: var(--bg-elevated); padding: 1px 5px; border-radius: 4px; color: var(--text-primary); }
.md :deep(pre) { background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 14px; overflow-x: auto; line-height: 1.55; }
.md :deep(pre code) { background: none; padding: 0; font-size: 0.84rem; }
.md :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.88rem; display: block; overflow-x: auto; }
.md :deep(th), .md :deep(td) { border: 1px solid var(--border-color); padding: 7px 10px; text-align: left; vertical-align: top; }
.md :deep(th) { background: var(--bg-elevated); color: var(--text-primary); }
.md :deep(a) { color: var(--accent-cyan); }
.md :deep(strong) { color: var(--text-primary); }

.lab-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.lab-head h2 { margin: 0; font-size: 1.1rem; }
.lab-card .md :deep(h1) { font-size: 1.15rem; margin-top: 12px; }
.lab-done { display: flex; gap: 8px; align-items: center; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-color); color: var(--text-primary); }
.project-card h2 { margin: 0 0 12px; font-size: 1.1rem; }
.project-card .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; font-size: 0.85rem; color: var(--text-secondary); }
.project-status { padding: 10px 12px; border-radius: 10px; background: var(--bg-well); margin-bottom: 12px; }
.project-status.rejected { background: var(--warn-soft); }
.ai-feedback { margin-top: 16px; padding: 12px 14px; border-radius: 10px; background: var(--bg-well); }
.pager { display: flex; justify-content: space-between; gap: 12px; }

.tutor-fab {
  position: fixed; right: 20px; bottom: 20px; z-index: 350; padding: 12px 18px; border-radius: 999px; border: 0;
  background: var(--accent-blue); color: #fff; font: inherit; font-weight: 600; cursor: pointer;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
}
.tutor-login-hint {
  position: fixed; right: 16px; bottom: 96px; z-index: 450; padding: 8px 12px; border-radius: 8px;
  background: var(--bg-elevated); color: var(--text-primary); font-size: 0.85rem;
}

@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .toc { display: none; }
}
@media (max-width: 640px) { .unit-page { padding: 16px; } }
</style>
