<template>
  <div class="admin-page">
    <!-- Login Gate -->
    <div v-if="!authStore.isAdmin" class="login-gate">
      <div class="login-card">
        <div class="login-logo">🔐</div>
        <h2>後台管理</h2>
        <p>請使用授權的 Google 帳號登入</p>
        <div v-if="loginError" class="login-error">{{ loginError }}</div>
        <button class="google-login-btn" @click="startGoogleLogin">
          <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
          使用 Google 登入
        </button>
        <p class="login-hint">僅限授權帳號 (frank210@gmail.com) 進入</p>
      </div>
    </div>

    <!-- Admin Dashboard -->
    <div v-else class="admin-content">
      <PageFocusBanner text="監控系統使用狀況與後台管理功能，掌握平台運作健康度。" />

      <header class="admin-header">
        <div class="admin-header-left">
          <h1>⚙️ 後台管理</h1>
          <span class="admin-badge">管理員</span>
        </div>
        <div class="admin-header-right">
          <img v-if="authStore.avatar" :src="authStore.avatar" class="admin-avatar" />
          <span class="admin-name">{{ authStore.name }}</span>
          <button class="btn-logout" @click="authStore.logout()">登出</button>
        </div>
      </header>

      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.todays_visitors }}</div>
          <div class="stat-label">今日訪客</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_pageviews }}</div>
          <div class="stat-label">總瀏覽數</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.unique_visitors }}</div>
          <div class="stat-label">不重複訪客</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ Object.keys(pageviewMap).length }}</div>
          <div class="stat-label">頁面數</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="admin-tabs">
        <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: activeTab === t.key }]" @click="activeTab = t.key">
          {{ t.icon }} {{ t.label }}
        </button>
      </div>

      <!-- Tab: Logs -->
      <div v-if="activeTab === 'logs'" class="tab-panel">
        <div class="panel-header">
          <h3>訪客紀錄</h3>
          <select v-model="logFilter" @change="loadLogs">
            <option value="">全部</option>
            <option value="pageview">瀏覽</option>
            <option value="login">登入</option>
          </select>
        </div>
        <div class="log-table-wrap">
          <table class="log-table">
            <thead>
              <tr>
                <th>時間</th><th>類型</th><th>頁面</th><th>帳號</th><th>IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(log, i) in logs" :key="i">
                <td>{{ formatTime(log.timestamp) }}</td>
                <td><span :class="['log-type', log.type]">{{ log.type }}</span></td>
                <td>{{ log.page || log.email || '-' }}</td>
                <td>{{ log.email || '-' }}</td>
                <td class="log-ip">{{ log.ip || '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!logs.length" class="empty">尚無紀錄</div>
        </div>
      </div>

      <!-- Tab: Pageviews -->
      <div v-if="activeTab === 'pageviews'" class="tab-panel">
        <h3>頁面瀏覽統計</h3>
        <div class="pv-list">
          <div v-for="(count, page) in pageviewMap" :key="page" class="pv-row">
            <span class="pv-page">{{ page }}</span>
            <div class="pv-bar-wrap">
              <div class="pv-bar" :style="{ width: barWidth(count) }"></div>
            </div>
            <span class="pv-count">{{ count }}</span>
          </div>
        </div>
      </div>

      <!-- Tab: Settings -->
      <div v-if="activeTab === 'settings'" class="tab-panel">
        <div class="panel-header">
          <h3>系統設定</h3>
          <button class="btn-primary" @click="showAddSetting = !showAddSetting">+ 新增</button>
        </div>
        <div v-if="showAddSetting" class="add-setting-form">
          <input v-model="newKey" placeholder="Key" class="input-sm" />
          <input v-model="newValue" placeholder="Value" class="input-sm" />
          <button class="btn-primary" @click="addSetting">儲存</button>
          <button class="btn-ghost" @click="showAddSetting = false">取消</button>
        </div>
        <div class="settings-list">
          <div v-for="(val, key) in settingsMap" :key="key" class="setting-row">
            <span class="setting-key">{{ key }}</span>
            <input v-model="settingsMap[key]" class="setting-val input-sm" @blur="updateSetting(key, settingsMap[key])" />
            <button class="btn-danger-sm" @click="deleteSetting(key)">刪</button>
          </div>
          <div v-if="!Object.keys(settingsMap).length" class="empty">尚無設定項目</div>
        </div>
      </div>

      <!-- Tab: Admin Users -->
      <div v-if="activeTab === 'admins'" class="tab-panel">
        <div class="panel-header">
          <h3>管理員帳號</h3>
        </div>
        <div class="admins-list">
          <div v-for="email in adminEmails" :key="email" class="admin-row">
            <span class="admin-email">{{ email }}</span>
            <button class="btn-danger-sm" @click="removeAdmin(email)" :disabled="email === authStore.email">移除</button>
          </div>
        </div>
        <div class="add-admin-form">
          <input v-model="newAdminEmail" placeholder="輸入 Google 帳號 Email" class="input-sm" />
          <button class="btn-primary" @click="addAdmin">新增</button>
        </div>
      </div>

      <!-- Tab: Notify -->
      <div v-if="activeTab === 'notify'" class="tab-panel">
        <h3>通知設定</h3>
        <div class="notify-section">
          <h4>Telegram</h4>
          <label>Bot Token</label>
          <input v-model="telegramToken" class="input-full" placeholder="bot token from @BotFather" @blur="saveTelegramToken" />
          <label>Chat ID</label>
          <input v-model="telegramChatId" class="input-full" placeholder="your chat_id" @blur="saveTelegramChatId" />
          <button class="btn-primary" @click="testNotify('telegram')">傳送測試訊息</button>
        </div>
        <div class="notify-section">
          <h4>LINE Notify</h4>
          <label>Token</label>
          <input v-model="lineToken" class="input-full" placeholder="LINE Notify token" @blur="saveLineToken" />
          <button class="btn-primary" @click="testNotify('line')">傳送測試訊息</button>
        </div>
        <div v-if="notifyResult" :class="['notify-result', notifyResult.ok ? 'ok' : 'err']">
          {{ notifyResult.msg }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '../stores/auth.js'

const authStore = useAuthStore()
const loginError = ref('')
const activeTab = ref('logs')
const tabs = [
  { key: 'logs', icon: '📋', label: '訪客紀錄' },
  { key: 'pageviews', icon: '📊', label: '瀏覽統計' },
  { key: 'settings', icon: '⚙️', label: '系統設定' },
  { key: 'admins', icon: '👤', label: '管理員' },
  { key: 'notify', icon: '🔔', label: '通知設定' },
]

const stats = ref({ today_visitors: 0, total_pageviews: 0, unique_visitors: 0 })
const logs = ref([])
const logFilter = ref('')
const pageviewMap = ref({})
const settingsMap = reactive({})
const adminEmails = ref([])
const showAddSetting = ref(false)
const newKey = ref('')
const newValue = ref('')
const newAdminEmail = ref('')
const telegramToken = ref('')
const telegramChatId = ref('')
const lineToken = ref('')
const notifyResult = ref(null)

const maxPV = computed(() => Math.max(...Object.values(pageviewMap.value), 1))
function barWidth(count) { return `${(count / maxPV.value) * 100}%` }

function formatTime(ts) {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-TW')
  } catch { return ts }
}

function authHeaders() {
  return { 'X-Admin-Token': authStore.token || '', 'Content-Type': 'application/json' }
}

async function loadStats() {
  try {
    const r = await fetch('/api/v1/admin/logs/stats', { headers: authHeaders() })
    const d = await r.json()
    stats.value = d.data || d
  } catch {}
}

async function loadLogs() {
  try {
    const q = logFilter.value ? `?type=${logFilter.value}` : ''
    const r = await fetch(`/api/v1/admin/logs${q}`, { headers: authHeaders() })
    const d = await r.json()
    logs.value = d.data || d || []
  } catch {}
}

async function loadPageviews() {
  try {
    const r = await fetch('/api/v1/analytics/pageviews', { headers: authHeaders() })
    const d = await r.json()
    pageviewMap.value = d || {}
  } catch {}
}

async function loadSettings() {
  try {
    const r = await fetch('/api/v1/settings', { headers: authHeaders() })
    const d = await r.json()
    const data = d.data || {}
    Object.keys(settingsMap).forEach(k => delete settingsMap[k])
    Object.assign(settingsMap, data)
    telegramToken.value = data.telegram_bot_token || ''
    telegramChatId.value = data.telegram_chat_id || ''
    lineToken.value = data.line_token || ''
  } catch {}
}

async function loadAdmins() {
  try {
    const r = await fetch('/api/v1/admin/allowed-admins', { headers: authHeaders() })
    const d = await r.json()
    adminEmails.value = d.data || d || []
  } catch {}
}

async function addSetting() {
  if (!newKey.value) return
  try {
    await fetch('/api/v1/admin/settings', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ key: newKey.value, value: newValue.value }),
    })
    settingsMap[newKey.value] = newValue.value
    newKey.value = ''; newValue.value = ''
    showAddSetting.value = false
  } catch {}
}

async function updateSetting(key, value) {
  try {
    await fetch(`/api/v1/admin/settings/${key}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ value }),
    })
  } catch {}
}

async function deleteSetting(key) {
  try {
    await fetch(`/api/v1/admin/settings/${key}`, { method: 'DELETE', headers: authHeaders() })
    delete settingsMap[key]
  } catch {}
}

async function addAdmin() {
  if (!newAdminEmail.value) return
  try {
    await fetch('/api/v1/admin/allowed-admins', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ email: newAdminEmail.value }),
    })
    adminEmails.value.push(newAdminEmail.value)
    newAdminEmail.value = ''
  } catch {}
}

async function removeAdmin(email) {
  try {
    await fetch(`/api/v1/admin/allowed-admins/${encodeURIComponent(email)}`, { method: 'DELETE', headers: authHeaders() })
    adminEmails.value = adminEmails.value.filter(e => e !== email)
  } catch {}
}

async function saveTelegramToken() { await updateSetting('telegram_bot_token', telegramToken.value) }
async function saveTelegramChatId() { await updateSetting('telegram_chat_id', telegramChatId.value) }
async function saveLineToken() { await updateSetting('line_token', lineToken.value) }

async function testNotify(channel) {
  notifyResult.value = null
  try {
    const r = await fetch('/api/v1/admin/notify/test', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ channel }),
    })
    const d = await r.json()
    notifyResult.value = { ok: d.ok || r.ok, msg: d.message || (r.ok ? '發送成功' : '發送失敗') }
  } catch {
    notifyResult.value = { ok: false, msg: '網路錯誤' }
  }
}

function startGoogleLogin() {
  const clientId = window.__GOOGLE_CLIENT_ID__ || ''
  if (!clientId) {
    loginError.value = '尚未設定 Google Client ID，請聯繫管理員'
    return
  }
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

async function handleRedirectCallback() {
  const hash = window.location.hash || ''
  if (!hash.includes('id_token=')) return false
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  const idToken = params.get('id_token')
  // Clean the hash from the URL regardless of outcome
  history.replaceState(null, '', window.location.pathname)
  if (!idToken) return false
  const result = await authStore.loginWithGoogle(idToken)
  if (!result.success) {
    loginError.value = result.error || '登入失敗'
    return false
  }
  loginError.value = ''
  return true
}

onMounted(async () => {
  // Handle OAuth redirect callback (#id_token=...) first
  await handleRedirectCallback()
  if (authStore.isAdmin) {
    await Promise.all([loadStats(), loadLogs(), loadPageviews(), loadSettings(), loadAdmins()])
  } else if (authStore.isLoggedIn) {
    // Logged in but not an authorized admin
    loginError.value = '此帳號未獲授權進入後台'
  }
})
</script>

<style scoped>
.admin-page { min-height: 100vh; padding: 0; }

.login-gate {
  display: flex; align-items: center; justify-content: center;
  min-height: 80vh;
}
.login-card {
  background: var(--bg-secondary, #1a1a2e);
  border: 1px solid var(--border-color, #2a2a4a);
  border-radius: 16px; padding: 48px 40px; text-align: center;
  max-width: 380px; width: 100%;
}
.login-logo { font-size: 3rem; margin-bottom: 16px; }
.login-card h2 { margin: 0 0 8px; font-size: 1.5rem; }
.login-card p { color: var(--text-secondary, #aaa); font-size: 0.9rem; margin-bottom: 24px; }
.login-hint { font-size: 0.75rem; color: var(--text-muted, #666); margin-top: 16px; }
.login-error { color: #f87171; background: var(--down-soft); border-radius: 8px; padding: 8px 12px; margin-bottom: 16px; font-size: 0.85rem; }
.google-login-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  width: 100%; box-sizing: border-box;
  background: #fff; color: #1f1f1f;
  border: none; border-radius: 10px;
  padding: 12px 20px; font-size: 0.95rem; font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  transition: box-shadow 0.2s ease, transform 0.06s ease;
}
.google-login-btn:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.45); }
.google-login-btn:active { transform: scale(0.985); }
@media (prefers-reduced-motion: reduce) {
  .google-login-btn { transition: none; }
  .google-login-btn:active { transform: none; }
}

.admin-content { max-width: 1100px; margin: 0 auto; padding: 24px 16px 80px; }
.admin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
.admin-header-left { display: flex; align-items: center; gap: 12px; }
.admin-header-left h1 { margin: 0; font-size: 1.4rem; }
.admin-badge { background: rgba(99,102,241,0.2); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); border-radius: 20px; padding: 2px 10px; font-size: 0.75rem; }
.admin-header-right { display: flex; align-items: center; gap: 12px; }
.admin-avatar { width: 32px; height: 32px; border-radius: 50%; }
.admin-name { font-size: 0.9rem; }
.btn-logout { background: var(--down-soft); color: #f87171; border: 1px solid rgba(239,68,68,0.3); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: var(--bg-secondary, #1a1a2e); border: 1px solid var(--border-color, #2a2a4a); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--accent-blue, #6366f1); }
.stat-label { font-size: 0.8rem; color: var(--text-secondary, #aaa); margin-top: 4px; }

.admin-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tab-btn { background: var(--bg-secondary, #1a1a2e); border: 1px solid var(--border-color, #2a2a4a); color: var(--text-secondary, #aaa); border-radius: 8px; padding: 8px 16px; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
.tab-btn.active { background: rgba(99,102,241,0.2); color: #a5b4fc; border-color: rgba(99,102,241,0.4); }

.tab-panel { background: var(--bg-secondary, #1a1a2e); border: 1px solid var(--border-color, #2a2a4a); border-radius: 12px; padding: 24px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-header h3 { margin: 0; }

.log-table-wrap { overflow-x: auto; }
.log-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.log-table th { text-align: left; padding: 8px 12px; background: rgba(255,255,255,0.04); color: var(--text-muted, #666); border-bottom: 1px solid var(--border-color, #2a2a4a); }
.log-table td { padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.log-type { padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.log-type.pageview { background: rgba(59,130,246,0.15); color: #93c5fd; }
.log-type.login { background: var(--up-soft); color: #6ee7b7; }
.log-ip { font-family: monospace; font-size: 0.78rem; color: var(--text-muted, #666); }

.pv-list { display: flex; flex-direction: column; gap: 10px; }
.pv-row { display: flex; align-items: center; gap: 12px; }
.pv-page { min-width: 140px; font-size: 0.85rem; color: var(--text-secondary, #aaa); }
.pv-bar-wrap { flex: 1; height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden; }
.pv-bar { height: 100%; background: linear-gradient(90deg, #6366f1, var(--accent-purple)); border-radius: 4px; transition: width 0.5s ease; }
.pv-count { min-width: 40px; text-align: right; font-weight: 600; font-size: 0.85rem; }

.add-setting-form, .add-admin-form { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.settings-list, .admins-list { display: flex; flex-direction: column; gap: 8px; }
.setting-row, .admin-row { display: flex; align-items: center; gap: 8px; }
.setting-key { min-width: 180px; font-family: monospace; font-size: 0.85rem; color: #a5b4fc; }
.setting-val { flex: 1; }
.admin-email { flex: 1; font-size: 0.9rem; }

.input-sm { background: var(--bg-primary, #0d0d1a); border: 1px solid var(--border-color, #2a2a4a); border-radius: 8px; padding: 6px 10px; color: var(--text-primary, #e2e8f0); font-size: 0.85rem; }
.input-full { width: 100%; background: var(--bg-primary, #0d0d1a); border: 1px solid var(--border-color, #2a2a4a); border-radius: 8px; padding: 8px 12px; color: var(--text-primary, #e2e8f0); font-size: 0.9rem; margin-bottom: 8px; box-sizing: border-box; }

.btn-primary { background: rgba(99,102,241,0.2); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.4); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; transition: background 0.2s; }
.btn-primary:hover { background: rgba(99,102,241,0.35); }
.btn-ghost { background: transparent; color: var(--text-secondary, #aaa); border: 1px solid var(--border-color, #2a2a4a); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; }
.btn-danger-sm { background: var(--down-soft); color: #f87171; border: 1px solid rgba(239,68,68,0.2); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.8rem; }
.btn-danger-sm:disabled { opacity: 0.4; cursor: not-allowed; }

.notify-section { background: rgba(255,255,255,0.03); border: 1px solid var(--border-color, #2a2a4a); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
.notify-section h4 { margin: 0 0 12px; }
.notify-section label { display: block; font-size: 0.8rem; color: var(--text-secondary, #aaa); margin-bottom: 4px; }
.notify-result { padding: 10px 16px; border-radius: 8px; font-size: 0.9rem; margin-top: 12px; }
.notify-result.ok { background: var(--up-soft); color: #6ee7b7; }
.notify-result.err { background: var(--down-soft); color: #f87171; }

.empty { text-align: center; color: var(--text-muted, #666); padding: 24px; font-size: 0.9rem; }

select { background: var(--bg-primary, #0d0d1a); border: 1px solid var(--border-color, #2a2a4a); border-radius: 8px; padding: 6px 10px; color: var(--text-primary, #e2e8f0); font-size: 0.85rem; }
</style>