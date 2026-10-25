<template>
  <div class="learn-page">
    <header class="page-header">
      <div>
        <h1>🎓 {{ catalog?.title || '學習中心' }}</h1>
        <p class="subtitle">從 AI Agent 的原理出發，對照 Claude Code 的實作，最後打造你自己的 plugin。每個單元都是「學 → 做 → 測 → 補強」。</p>
      </div>
      <div v-if="auth.isLoggedIn" class="who">
        <span>👋 {{ auth.name || auth.email }}</span>
        <router-link v-if="auth.isAdmin" to="/learn/admin" class="btn btn-secondary sm">學員管理</router-link>
        <button class="btn btn-secondary sm" type="button" @click="auth.logout()">登出</button>
      </div>
    </header>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <div v-if="loading" class="empty-state">載入中…</div>

    <template v-else-if="catalog">
      <div class="top-grid">
        <CourseAuthCard v-if="!auth.isLoggedIn" @logged-in="loadMe" />

        <section v-else class="card progress-card" data-testid="course-progress">
          <h2>我的進度</h2>
          <div class="meter" role="progressbar" :aria-valuenow="passedCount" aria-valuemin="0" :aria-valuemax="requiredTotal">
            <div class="meter-fill" :style="{ width: requiredTotal ? `${(passedCount / requiredTotal) * 100}%` : '0%' }"></div>
          </div>
          <p>必修測驗通過 <strong>{{ passedCount }}</strong> / {{ requiredTotal }}</p>
          <p v-if="me?.progress?.placement" class="muted">
            程度檢測建議起點：<router-link :to="`/learn/u/${me.progress.placement.recommended_start}`">{{ unitTitle(me.progress.placement.recommended_start) }}</router-link>
          </p>
          <div class="progress-actions">
            <router-link v-if="nextUnit" :to="`/learn/u/${nextUnit.id}`" class="btn btn-primary">繼續：{{ nextUnit.code }} {{ nextUnit.title }}</router-link>
            <router-link v-if="certId" :to="`/learn/cert/${certId}`" class="btn btn-secondary">🏅 查看結業證書</router-link>
          </div>
        </section>

        <section class="card placement-card">
          <h2>還不確定從哪裡開始？</h2>
          <p class="muted">12 題程度檢測，約 5 分鐘。系統會依你答對的主題，推薦第一個該學的單元。</p>
          <router-link to="/learn/placement" class="btn btn-secondary">開始程度檢測</router-link>
        </section>
      </div>

      <section v-for="stage in catalog.stages" :key="stage.id" class="stage">
        <h2 class="stage-title">{{ stage.title }}<span class="muted"> · {{ stage.summary }}</span></h2>
        <div class="unit-grid">
          <router-link v-for="unit in unitsOf(stage.id)" :key="unit.id" :to="`/learn/u/${unit.id}`"
                       class="unit-card" :class="statusClass(unit)" :data-testid="`unit-card-${unit.id}`">
            <div class="unit-top">
              <span class="code">{{ unit.code }}</span>
              <span class="status">{{ statusLabel(unit) }}</span>
            </div>
            <h3>{{ unit.title }}</h3>
            <p class="summary">{{ unit.summary }}</p>
            <div class="unit-foot">
              <span v-if="unit.concept" class="tag">原理：{{ unit.concept }}</span>
              <span class="muted">約 {{ unit.minutes }} 分鐘{{ unit.required ? ' · 必修' : '' }}</span>
            </div>
          </router-link>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CourseAuthCard from '../components/course/CourseAuthCard.vue'
import { courseFetch } from '../lib/courseApi.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const catalog = ref(null)
const me = ref(null)
const loading = ref(true)
const error = ref('')

const unitsProgress = computed(() => me.value?.progress?.units || {})
const requiredTotal = computed(() => me.value?.progress?.required?.length || 0)
const passedCount = computed(() => me.value?.progress?.passed_required?.length || 0)
const certId = computed(() => (me.value?.project?.status === 'approved' ? me.value.project.cert_id : ''))
const recommended = computed(() => me.value?.progress?.placement?.recommended_start || '')

const nextUnit = computed(() => {
  if (!catalog.value) return null
  const units = catalog.value.units
  const start = units.findIndex(u => u.id === recommended.value)
  const pool = start > 0 ? units.slice(start) : units
  return pool.find(u => u.quiz && !unitsProgress.value[u.id]?.passed) || null
})

function unitsOf(stageId) {
  return catalog.value.units.filter(u => u.stage === stageId)
}
function unitTitle(id) {
  const u = catalog.value?.units.find(x => x.id === id)
  return u ? `${u.code} ${u.title}` : id
}
function statusClass(unit) {
  const p = unitsProgress.value[unit.id]
  if (p?.passed) return 'is-passed'
  if (unit.id === recommended.value) return 'is-recommended'
  if (p?.attempts) return 'is-started'
  return ''
}
function statusLabel(unit) {
  const p = unitsProgress.value[unit.id]
  if (p?.passed) return p.lab_done || !unit.lab ? '✅ 完成' : '✅ 測驗通過'
  if (unit.id === recommended.value) return '⭐ 建議起點'
  if (p?.attempts) return `進行中（最佳 ${Math.round((p.best || 0) * 100)}%）`
  if (p?.lab_done) return 'lab 已完成'
  return ''
}

async function loadCatalog() {
  catalog.value = await courseFetch('/catalog')
}
async function loadMe() {
  if (!auth.isLoggedIn) { me.value = null; return }
  try {
    me.value = await courseFetch('/me')
  } catch (e) {
    if (e.status !== 401) error.value = e.message
  }
}

watch(() => auth.isLoggedIn, (v) => { if (!v) me.value = null })

onMounted(async () => {
  try {
    await Promise.all([loadCatalog(), loadMe()])
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.learn-page { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 20px; }
.page-header h1 { margin: 0 0 6px; font-size: 1.5rem; }
.subtitle { margin: 0; color: var(--text-secondary); max-width: 720px; line-height: 1.6; }
.who { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: var(--text-secondary); }
.sm { padding: 6px 12px; font-size: 0.85rem; }
.muted { color: var(--text-muted); font-size: 0.85rem; }
.error-text { color: var(--color-warning); }
.top-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 28px; align-items: start; }
.progress-card h2, .placement-card h2 { margin: 0 0 10px; font-size: 1.05rem; }
.meter { height: 10px; background: var(--bg-well); border-radius: 999px; overflow: hidden; margin-bottom: 8px; }
.meter-fill { height: 100%; background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); }
.progress-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.stage { margin-bottom: 28px; }
.stage-title { font-size: 1.1rem; margin: 0 0 12px; }
.stage-title .muted { font-weight: 400; }
.unit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.unit-card {
  display: flex; flex-direction: column; gap: 6px; padding: 16px; border-radius: 14px; text-decoration: none;
  background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary);
  transition: border-color 0.15s ease, transform 0.15s ease;
}
.unit-card:hover { border-color: var(--accent-blue); transform: translateY(-1px); }
.unit-card.is-passed { border-color: rgba(16, 185, 129, 0.5); }
.unit-card.is-recommended { border-color: var(--color-warning); box-shadow: 0 0 0 1px var(--color-warning) inset; }
.unit-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.code { font-size: 0.75rem; font-weight: 700; color: var(--accent-cyan); letter-spacing: 0.04em; }
.status { font-size: 0.75rem; color: var(--text-secondary); }
.unit-card h3 { margin: 0; font-size: 1rem; }
.summary { margin: 0; color: var(--text-secondary); font-size: 0.86rem; line-height: 1.55; flex: 1; }
.unit-foot { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; align-items: center; }
.tag { font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; background: var(--bg-elevated); color: var(--text-secondary); }
@media (max-width: 640px) { .learn-page { padding: 16px; } }
@media (prefers-reduced-motion: reduce) { .unit-card { transition: none; } .unit-card:hover { transform: none; } }
</style>
