<script setup>
import { ref } from 'vue'
import api from '../api.js'

const domain = ref('')
const file = ref(null)
const url = ref('')
const result = ref(null)
const error = ref('')

function onFileChange(e) {
  file.value = e.target.files[0]
}

async function submitFile() {
  error.value = ''
  result.value = null
  const form = new FormData()
  form.append('file', file.value)
  form.append('domain', domain.value)
  try {
    const { data } = await api.post('/import/file', form)
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || '匯入失敗'
  }
}

async function submitUrl() {
  error.value = ''
  result.value = null
  try {
    const { data } = await api.post('/import/url', { url: url.value, domain: domain.value })
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || '匯入失敗'
  }
}
</script>

<template>
  <h1>資料匯入</h1>
  <label>領域名稱 <input v-model="domain" placeholder="例如 patent" /></label>

  <fieldset>
    <legend>上傳檔案（.docx / .pptx / .pdf / .md / .txt）</legend>
    <input type="file" @change="onFileChange" />
    <button @click="submitFile" :disabled="!file || !domain">上傳並匯入</button>
  </fieldset>

  <fieldset>
    <legend>網址匯入</legend>
    <input v-model="url" placeholder="https://..." style="width: 400px" />
    <button @click="submitUrl" :disabled="!url || !domain">抓取並匯入</button>
  </fieldset>

  <p v-if="error" style="color: red">{{ error }}</p>
  <pre v-if="result">{{ JSON.stringify(result, null, 2) }}</pre>
</template>
