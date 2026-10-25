<template>
  <div class="learn-page">
    <router-link to="/learn" class="back">← 回學習中心</router-link>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <div v-else-if="!cert" class="empty-state">驗證中…</div>
    <article v-else class="certificate" data-testid="certificate">
      <p class="eyebrow">結業證書 · Certificate of Completion</p>
      <h1>{{ cert.name }}</h1>
      <p class="body">已完成課程</p>
      <h2>{{ cert.course }}</h2>
      <p class="body">並通過期末專題審核</p>
      <dl>
        <div><dt>證書編號</dt><dd>{{ cert.cert_id }}</dd></div>
        <div><dt>核發日期</dt><dd>{{ issued }}</dd></div>
        <div v-if="cert.repo_url"><dt>專題</dt><dd><a :href="cert.repo_url" target="_blank" rel="noopener noreferrer">{{ cert.repo_url }}</a></dd></div>
      </dl>
      <p class="verify">任何人都可以用這個網址驗證這份證書。</p>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { courseFetch } from '../lib/courseApi.js'

const route = useRoute()
const cert = ref(null)
const error = ref('')
const issued = computed(() => (cert.value?.issued_at ? new Date(cert.value.issued_at).toLocaleDateString('zh-TW') : '—'))

onMounted(async () => {
  try {
    cert.value = await courseFetch(`/certificate/${encodeURIComponent(route.params.certId)}`)
  } catch (e) {
    error.value = e.status === 404 ? '查無此證書，請確認編號是否正確。' : e.message
  }
})
</script>

<style scoped>
.learn-page { padding: 24px; max-width: 760px; margin: 0 auto; }
.back { color: var(--text-muted); text-decoration: none; font-size: 0.85rem; }
.error-text { color: var(--color-warning); margin-top: 20px; }
.certificate {
  margin-top: 18px; padding: 48px 32px; text-align: center; border-radius: 18px;
  background: var(--bg-card); border: 2px solid var(--accent-cyan);
  box-shadow: 0 0 0 6px var(--bg-primary) inset, 0 0 0 7px var(--border-color) inset;
}
.eyebrow { letter-spacing: 0.12em; font-size: 0.78rem; color: var(--accent-cyan); margin: 0 0 18px; }
.certificate h1 { font-size: 2rem; margin: 0 0 12px; }
.certificate h2 { font-size: 1.2rem; margin: 6px 0; color: var(--text-primary); }
.body { color: var(--text-secondary); margin: 6px 0; }
dl { display: grid; gap: 8px; margin: 28px auto 0; max-width: 420px; text-align: left; }
dl div { display: flex; gap: 12px; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; }
dt { color: var(--text-muted); font-size: 0.85rem; }
dd { margin: 0; font-family: ui-monospace, monospace; font-size: 0.85rem; overflow-wrap: anywhere; text-align: right; }
dd a { color: var(--accent-cyan); }
.verify { color: var(--text-muted); font-size: 0.8rem; margin-top: 24px; }
@media (max-width: 640px) { .learn-page { padding: 16px; } .certificate { padding: 32px 18px; } }
</style>
