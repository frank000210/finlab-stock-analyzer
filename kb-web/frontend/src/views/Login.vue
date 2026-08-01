<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'

const password = ref('')
const error = ref('')
const router = useRouter()

async function submit() {
  error.value = ''
  try {
    const { data } = await api.post('/login', { password: password.value })
    localStorage.setItem('kb_token', data.token)
    router.push('/')
  } catch (e) {
    error.value = '密碼錯誤'
  }
}
</script>

<template>
  <form @submit.prevent="submit">
    <h1>知識庫登入</h1>
    <input v-model="password" type="password" placeholder="密碼" autofocus />
    <button type="submit">登入</button>
    <p v-if="error" style="color: red">{{ error }}</p>
  </form>
</template>
