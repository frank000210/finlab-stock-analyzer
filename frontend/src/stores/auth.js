import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// CC6：先前這裡是全站唯一沒包 try/catch 的 localStorage JSON.parse
// （useTheme.js／watchlist.js／tradeMath.js 等都有包）。store 是在 Pinia
// setup 當下同步執行，壞掉的 admin_user 值（寫到一半、手動改壞）會直接
// throw 到呼叫端，讓任何碰到這個 store 的地方都掛掉。
function loadStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('admin_user') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('admin_token') || null)
  const user = ref(loadStoredUser())

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_admin === true)
  const email = computed(() => user.value?.email || '')
  const name = computed(() => user.value?.name || '')
  const avatar = computed(() => user.value?.avatar || '')

  async function loginWithGoogle(idToken) {
    try {
      const res = await fetch('/api/v1/auth/google/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken }),
      })
      const data = await res.json()
      if (data.valid) {
        token.value = data.token
        user.value = { email: data.email, name: data.name, avatar: data.avatar, is_admin: data.is_admin }
        localStorage.setItem('admin_token', data.token)
        localStorage.setItem('admin_user', JSON.stringify(user.value))
        await fetch('/api/v1/analytics/user-identify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: data.email, name: data.name, avatar: data.avatar }),
        }).catch(() => {})
        return { success: true, is_admin: data.is_admin }
      }
      return { success: false, error: '帳號未獲授權' }
    } catch (e) {
      return { success: false, error: '網路錯誤，請稍後再試' }
    }
  }

  // 學習中心的本機帳號（沒有 Google 帳號的學習者用）。簽出的 token 跟
  // Google 登入同一把 JWT，存在同樣的 localStorage key，全站共用登入狀態。
  async function loginWithPassword(mode, payload) {
    const path = mode === 'register' ? 'register' : 'login'
    try {
      const res = await fetch(`/api/v1/course/auth/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.valid) {
        const detail = Array.isArray(data.detail) ? '輸入格式不正確（密碼至少 8 碼）' : data.detail
        return { success: false, error: detail || '登入失敗，請稍後再試' }
      }
      token.value = data.token
      user.value = { email: data.email, name: data.name, avatar: '', is_admin: false, provider: 'local' }
      localStorage.setItem('admin_token', data.token)
      localStorage.setItem('admin_user', JSON.stringify(user.value))
      return { success: true }
    } catch (e) {
      return { success: false, error: '網路錯誤，請稍後再試' }
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_user')
  }

  function getAuthHeaders() {
    return token.value ? { 'X-Admin-Token': token.value } : {}
  }

  return { token, user, isLoggedIn, isAdmin, email, name, avatar, loginWithGoogle, loginWithPassword, logout, getAuthHeaders }
})