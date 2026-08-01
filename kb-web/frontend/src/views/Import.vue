<script setup>
import { ref } from 'vue'
import api from '../api.js'

const domain = ref('')
const file = ref(null)
const fileName = ref('')
const url = ref('')
const result = ref(null)
const error = ref('')
const busy = ref(false)

function onFileChange(e) {
  file.value = e.target.files[0]
  fileName.value = file.value ? file.value.name : ''
}

async function submitFile() {
  error.value = ''
  result.value = null
  busy.value = true
  const form = new FormData()
  form.append('file', file.value)
  form.append('domain', domain.value)
  try {
    const { data } = await api.post('/import/file', form)
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || '匯入失敗'
  } finally {
    busy.value = false
  }
}

async function submitUrl() {
  error.value = ''
  result.value = null
  busy.value = true
  try {
    const { data } = await api.post('/import/url', { url: url.value, domain: domain.value })
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || '匯入失敗'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>資料匯入</h1>
      <p>把文件或網頁內容加進指定的知識庫領域。</p>
    </div>

    <div class="card field">
      <label class="label">領域名稱</label>
      <input v-model="domain" placeholder="例如 patent" />
    </div>

    <div class="grid">
      <div class="card">
        <h3>上傳檔案</h3>
        <p class="hint">.docx / .pptx / .pdf / .md / .txt</p>
        <label class="dropzone" :class="{ filled: fileName }">
          <input type="file" @change="onFileChange" />
          <span v-if="fileName">📄 {{ fileName }}</span>
          <span v-else>點擊或拖放檔案</span>
        </label>
        <button style="width: 100%; margin-top: 12px" @click="submitFile" :disabled="!file || !domain || busy">
          {{ busy ? '處理中…' : '上傳並匯入' }}
        </button>
      </div>

      <div class="card">
        <h3>網址匯入</h3>
        <p class="hint">抓取靜態網頁正文</p>
        <div class="field" style="margin-top: 12px">
          <input v-model="url" placeholder="https://..." />
        </div>
        <button style="width: 100%" @click="submitUrl" :disabled="!url || !domain || busy">
          {{ busy ? '處理中…' : '抓取並匯入' }}
        </button>
      </div>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="result" class="card result-card">
      <div class="result-header">
        <span class="badge success">匯入完成</span>
        <span class="hint">共 {{ result.files_total }} 個檔案</span>
      </div>
      <div class="stats">
        <div class="stat"><span class="stat-num">{{ result.imported }}</span><span class="stat-label">已匯入</span></div>
        <div class="stat"><span class="stat-num">{{ result.skipped }}</span><span class="stat-label">已略過</span></div>
        <div class="stat"><span class="stat-num">{{ result.failed }}</span><span class="stat-label">失敗</span></div>
        <div class="stat"><span class="stat-num">{{ result.quality_failed }}</span><span class="stat-label">品質待複查</span></div>
      </div>
      <details>
        <summary>原始回應</summary>
        <pre>{{ JSON.stringify(result, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.hint {
  font-size: 12px;
  margin-bottom: 12px;
}

.dropzone {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 84px;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-dim);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
  position: relative;
}

.dropzone:hover {
  border-color: var(--accent);
  background: var(--accent-dim);
}

.dropzone.filled {
  border-style: solid;
  border-color: var(--accent);
  color: var(--text);
}

.dropzone input[type='file'] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.result-card {
  margin-top: 16px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.stat {
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 10px;
  text-align: center;
}

.stat-num {
  display: block;
  font-size: 20px;
  font-weight: 700;
}

.stat-label {
  display: block;
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}

details {
  font-size: 12px;
}

summary {
  cursor: pointer;
  color: var(--text-dim);
}

pre {
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 12px;
  overflow-x: auto;
  font-family: var(--mono);
  font-size: 12px;
  margin-top: 8px;
}
</style>
