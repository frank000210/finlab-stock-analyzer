<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'
import { isPublicMode } from '../authMode.js'

const notebooks = ref([])
const loading = ref(true)
const error = ref('')
const publicMode = ref(false)
const authModeReady = ref(false)

isPublicMode().then((v) => {
  publicMode.value = v
  authModeReady.value = true
})

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

onMounted(async () => {
  try {
    const [{ data }] = await Promise.all([
      api.get('/notebooks'),
      isPublicMode().then((v) => {
        publicMode.value = v
        authModeReady.value = true
      }),
    ])
    notebooks.value = data
  } catch (e) {
    error.value = '載入失敗'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Notebook 總覽</h1>
      <p v-if="!authModeReady || publicMode">
        依領域分組的知識庫內容，點擊任一領域卡片即可直接向該領域提問。
      </p>
      <p v-else>
        依領域分組的知識庫內容，點擊卡片即可直接提問，或到「資料匯入」新增更多。
      </p>
    </div>

    <p v-if="loading" class="hint">載入中…</p>
    <p v-else-if="error" class="error-text">{{ error }}</p>

    <div v-else-if="notebooks.length" class="grid">
      <router-link
        v-for="nb in notebooks"
        :key="nb.domain"
        :to="{ path: '/ask', query: { domain: nb.domain } }"
        class="card nb-card"
        :aria-label="`前往「${nb.domain}」領域提問（${nb.doc_count} 篇文件）`"
      >
        <div class="nb-top">
          <h2>{{ nb.domain }}</h2>
          <span class="count">{{ nb.doc_count }}</span>
        </div>
        <p class="updated">最後更新 {{ formatDate(nb.last_updated) }}</p>
        <div class="badges">
          <span class="badge" :class="nb.quality_failed ? 'warn' : 'success'">
            品質待複查 {{ nb.quality_failed }}
          </span>
          <span class="badge" :class="nb.needs_review ? 'warn' : 'success'">
            UI 待複查 {{ nb.needs_review }}
          </span>
        </div>
        <div class="nb-cta" aria-hidden="true">
          <span>點擊直接提問</span>
          <span class="nb-cta-arrow">→</span>
        </div>
      </router-link>
    </div>

    <div v-else class="card empty-state">
      <template v-if="publicMode">
        <p>目前尚無公開的知識庫領域內容，歡迎稍後再回來瀏覽，或先前往問答頁查詢。</p>
        <router-link to="/ask" class="empty-ask-link">前往問答頁 →</router-link>
      </template>
      <p v-else>目前沒有任何資料，先到「資料匯入」頁面加入內容。</p>
    </div>
  </div>
</template>

<style scoped>
.hint {
  font-size: 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.nb-card {
  display: flex;
  flex-direction: column;
  padding: 18px;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.nb-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(var(--shadow-rgb), 0.14);
  background: var(--surface-2);
}

.nb-card:hover .nb-cta {
  color: var(--accent);
}

.nb-card:hover .nb-cta-arrow {
  transform: translateX(3px);
}

.nb-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.nb-top h2 {
  font-size: 16px;
  font-family: var(--mono);
  color: var(--text);
  overflow-wrap: anywhere;
}

.count {
  font-size: 26px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
  flex-shrink: 0;
}

.updated {
  font-size: 12px;
  margin-bottom: 14px;
}

.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.nb-cta {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
  transition: color 0.15s ease;
}

.nb-cta-arrow {
  display: inline-block;
  transition: transform 0.15s ease;
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
}

.empty-ask-link {
  display: inline-flex;
  align-items: center;
  margin-top: 14px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--on-accent);
  font-size: 14px;
  font-weight: 500;
}

.empty-ask-link:hover {
  background: var(--accent-hover);
}

@media (prefers-reduced-motion: reduce) {
  .nb-card,
  .nb-cta,
  .nb-cta-arrow {
    transition: none;
  }

  .nb-card:hover {
    transform: none;
  }

  .nb-card:hover .nb-cta-arrow {
    transform: none;
  }
}
</style>
