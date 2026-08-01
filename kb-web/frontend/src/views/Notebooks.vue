<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const notebooks = ref([])
const loading = ref(true)

onMounted(async () => {
  const { data } = await api.get('/notebooks')
  notebooks.value = data
  loading.value = false
})
</script>

<template>
  <h1>Notebook 總覽</h1>
  <p v-if="loading">載入中…</p>
  <table v-else>
    <thead>
      <tr><th>領域</th><th>篇數</th><th>最後更新</th><th>品質待複查</th><th>UI待複查</th></tr>
    </thead>
    <tbody>
      <tr v-for="nb in notebooks" :key="nb.domain">
        <td>{{ nb.domain }}</td>
        <td>{{ nb.doc_count }}</td>
        <td>{{ nb.last_updated }}</td>
        <td>{{ nb.quality_failed }}</td>
        <td>{{ nb.needs_review }}</td>
      </tr>
    </tbody>
  </table>
  <p v-if="!loading && notebooks.length === 0">目前沒有任何資料，先到「資料匯入」頁面加入內容。</p>
</template>
