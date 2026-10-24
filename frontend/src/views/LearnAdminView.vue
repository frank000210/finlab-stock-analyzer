<template>
  <div class="learn-page">
    <router-link to="/learn" class="back">← 回學習中心</router-link>
    <header class="page-header"><h1>🧑‍🏫 學員管理</h1></header>

    <p v-if="!auth.isAdmin" class="empty-state">需要管理員權限。請從側邊欄用管理員帳號登入。</p>
    <template v-else>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>

      <section class="card">
        <h2>期末專題（{{ projects.length }}）</h2>
        <div v-if="!projects.length" class="empty-state">還沒有人送出專題。</div>
        <article v-for="p in projects" :key="p.uid" class="project" :class="p.status">
          <div class="p-head">
            <strong>{{ p.name }}</strong><span class="muted">{{ p.email }}</span>
            <span class="pill">{{ statusLabel(p.status) }}</span>
            <span class="muted">{{ fmt(p.submitted_at) }}</span>
          </div>
          <p v-if="p.repo_url"><a :href="p.repo_url" target="_blank" rel="noopener noreferrer">{{ p.repo_url }}</a></p>
          <details><summary>專題說明</summary><p class="pre">{{ p.summary }}</p></details>
          <details v-if="p.ai_feedback"><summary>AI 初審回饋</summary><p class="pre">{{ p.ai_feedback }}</p></details>
          <div v-if="p.status !== 'approved'" class="review">
            <textarea v-model="comments[p.uid]" class="inp" rows="2" placeholder="審核意見（選填）"></textarea>
            <div class="review-actions">
              <button class="btn btn-primary" type="button" :disabled="busy" @click="review(p, true)">核准並發證書</button>
              <button class="btn btn-secondary" type="button" :disabled="busy" @click="review(p, false)">退回補強</button>
            </div>
          </div>
          <p v-else class="muted">證書：<router-link :to="`/learn/cert/${p.cert_id}`">{{ p.cert_id }}</router-link></p>
        </article>
      </section>

      <section class="card">
        <h2>學員進度（{{ learners.length }}）</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>學員</th><th>Email</th><th>必修通過</th><th>檢測起點</th><th>最後活動</th></tr></thead>
            <tbody>
              <tr v-for="l in learners" :key="l.uid">
                <td>{{ l.name }}</td><td>{{ l.email }}</td>
                <td>{{ l.passed_required }} / {{ l.required_total }}</td>
                <td>{{ l.placement_start || '—' }}</td>
                <td>{{ fmt(l.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { courseFetch } from '../lib/courseApi.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const projects = ref([])
const learners = ref([])
const comments = reactive({})
const busy = ref(false)
const error = ref('')

const statusLabel = s => ({ pending: '待審核', approved: '已核准', rejected: '已退回' }[s] || s)
const fmt = d => (d ? new Date(d).toLocaleString('zh-TW', { hour12: false }) : '—')

async function load() {
  try {
    const [p, l] = await Promise.all([courseFetch('/admin/projects'), courseFetch('/admin/learners')])
    projects.value = p.projects
    learners.value = l.learners
  } catch (e) {
    error.value = e.message
  }
}

async function review(p, approved) {
  busy.value = true
  error.value = ''
  try {
    await courseFetch('/admin/projects/review', { method: 'POST', body: { uid: p.uid, approved, comment: comments[p.uid] || '' } })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(() => { if (auth.isAdmin) load() })
</script>

<style scoped>
.learn-page { padding: 24px; max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }
.back { color: var(--text-muted); text-decoration: none; font-size: 0.85rem; }
.page-header h1 { margin: 0; font-size: 1.4rem; }
h2 { font-size: 1.05rem; margin: 0 0 12px; }
.muted { color: var(--text-muted); font-size: 0.85rem; }
.error-text { color: var(--color-warning); }
.project { padding: 12px 14px; border-radius: 10px; background: var(--bg-well); margin-bottom: 10px; border: 1px solid var(--border-color); }
.project.approved { border-color: rgba(16, 185, 129, 0.5); }
.p-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.pill { font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; background: var(--bg-elevated); }
.project a { color: var(--accent-cyan); overflow-wrap: anywhere; }
.pre { white-space: pre-wrap; color: var(--text-secondary); font-size: 0.88rem; }
details { margin: 6px 0; }
summary { cursor: pointer; color: var(--text-secondary); }
.review { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.review-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.86rem; }
th, td { border-bottom: 1px solid var(--border-color); padding: 7px 10px; text-align: left; white-space: nowrap; }
th { color: var(--text-muted); font-weight: 500; }
@media (max-width: 640px) { .learn-page { padding: 16px; } }
</style>
