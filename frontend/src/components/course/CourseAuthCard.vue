<template>
  <section class="card auth-card" data-testid="course-auth">
    <h2>登入學習中心</h2>
    <p class="muted">登入後會記錄你的測驗成績、lab 進度，並可以使用 AI 助教與送出期末專題。</p>

    <div class="tabs" role="tablist">
      <button role="tab" :aria-selected="mode === 'login'" :class="{ active: mode === 'login' }" @click="mode = 'login'">登入</button>
      <button role="tab" :aria-selected="mode === 'register'" :class="{ active: mode === 'register' }" @click="mode = 'register'">註冊</button>
    </div>

    <form class="auth-form" @submit.prevent="submit">
      <label v-if="mode === 'register'" class="field">
        <span>顯示名稱</span>
        <input v-model.trim="form.name" class="inp" maxlength="40" placeholder="證書上會顯示這個名字" autocomplete="nickname" />
      </label>
      <label class="field">
        <span>Email</span>
        <input v-model.trim="form.email" class="inp" type="email" required autocomplete="email" />
      </label>
      <label class="field">
        <span>密碼{{ mode === 'register' ? '（至少 8 碼）' : '' }}</span>
        <input v-model="form.password" class="inp" type="password" required :minlength="mode === 'register' ? 8 : 1"
               :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" />
      </label>
      <button class="btn btn-primary" type="submit" :disabled="busy">
        {{ busy ? '處理中…' : (mode === 'register' ? '建立帳號' : '登入') }}
      </button>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    </form>

    <div class="divider"><span>或</span></div>
    <button class="btn btn-secondary google-btn" type="button" @click="googleLogin">使用 Google 帳號登入</button>
    <p v-if="googleError" class="error-text">{{ googleError }}</p>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useAuthStore } from '../../stores/auth.js'

const emit = defineEmits(['logged-in'])
const auth = useAuthStore()
const mode = ref('login')
const busy = ref(false)
const error = ref('')
const googleError = ref('')
const form = reactive({ name: '', email: '', password: '' })

async function submit() {
  busy.value = true
  error.value = ''
  const payload = mode.value === 'register'
    ? { email: form.email, password: form.password, name: form.name }
    : { email: form.email, password: form.password }
  const result = await auth.loginWithPassword(mode.value, payload)
  busy.value = false
  if (!result.success) {
    error.value = result.error
    return
  }
  form.password = ''
  emit('logged-in')
}

function googleLogin() {
  const clientId = window.__GOOGLE_CLIENT_ID__ || ''
  if (!clientId) {
    googleError.value = '此站尚未設定 Google 登入，請改用 Email 註冊。'
    return
  }
  // redirect_uri 只登記了 /admin；AdminView 處理完回呼後會依這個值送回來
  sessionStorage.setItem('post_login_redirect', window.location.pathname)
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36)
  sessionStorage.setItem('gsi_nonce', nonce)
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: window.location.origin + '/admin',
    response_type: 'id_token',
    scope: 'openid email profile',
    nonce,
    prompt: 'select_account',
  })
  window.location.href = 'https://accounts.google.com/o/oauth2/v2/auth?' + params.toString()
}
</script>

<style scoped>
.auth-card { max-width: 440px; }
.auth-card h2 { margin: 0 0 6px; font-size: 1.1rem; }
.muted { color: var(--text-muted); font-size: 0.85rem; margin: 0 0 14px; }
.tabs { display: flex; gap: 4px; margin-bottom: 12px; background: var(--bg-well); padding: 4px; border-radius: 10px; }
.tabs button {
  flex: 1; padding: 8px; border: 0; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--text-secondary); font: inherit;
}
.tabs button.active { background: var(--bg-elevated); color: var(--text-primary); font-weight: 600; }
.auth-form { display: flex; flex-direction: column; gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem; color: var(--text-secondary); }
.error-text { color: var(--color-warning); font-size: 0.85rem; margin: 4px 0 0; }
.divider { display: flex; align-items: center; gap: 10px; margin: 14px 0; color: var(--text-muted); font-size: 0.8rem; }
.divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: var(--border-color); }
.google-btn { width: 100%; }
</style>
