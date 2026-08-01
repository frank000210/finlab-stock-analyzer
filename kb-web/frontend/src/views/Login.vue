<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'

const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await api.post('/login', { password: password.value })
    localStorage.setItem('kb_token', data.token)
    router.push('/')
  } catch (e) {
    error.value = '密碼錯誤'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-screen">
    <form class="card login-card" @submit.prevent="submit">
      <div class="brand">
        <span class="brand-dot"></span>
        知識庫
      </div>
      <p class="subtitle">輸入密碼以繼續</p>
      <div class="field">
        <input v-model="password" type="password" placeholder="密碼" autofocus />
      </div>
      <button type="submit" :disabled="!password || loading" style="width: 100%">
        {{ loading ? '登入中…' : '登入' }}
      </button>
      <p v-if="error" class="error-text">{{ error }}</p>
    </form>
  </div>
</template>

<style scoped>
.login-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 340px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 18px;
  margin-bottom: 6px;
}

.brand-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}

.subtitle {
  font-size: 13px;
  margin-bottom: 20px;
}
</style>
