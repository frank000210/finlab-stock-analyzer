<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const notebooks = ref([])
const loading = ref(true)
const error = ref('')

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

onMounted(async () => {
  try {
    const { data } = await api.get('/notebooks')
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
      <p>依領域分組的知識庫內容，點「資料匯入」新增更多。</p>
    </div>

    <p v-if="loading" class="hint">載入中…</p>
    <p v-else-if="error" class="error-text">{{ error }}</p>

    <div v-else-if="notebooks.length" class="grid">
      <div v-for="nb in notebooks" :key="nb.domain" class="card nb-card">
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
      </div>
    </div>

    <div v-else class="card empty-state">
      <p>目前沒有任何資料，先到「資料匯入」頁面加入內容。</p>
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
  padding: 18px;
}

.nb-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 6px;
}

.nb-top h2 {
  font-size: 16px;
  font-family: var(--mono);
  color: var(--text);
}

.count {
  font-size: 26px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
}

.updated {
  font-size: 12px;
  margin-bottom: 14px;
}

.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
}
</style>
