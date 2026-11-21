<template>
  <div class="admin-page">
    <!-- Login Gate -->
    <div v-if="!authStore.isAdmin" class="login-gate">
      <div class="login-card">
        <div class="login-logo">🔐</div>
        <h2>後台管理</h2>
        <p>請輸入管理員密碼</p>
        <div v-if="loginError" class="login-error">{{ loginError }}</div>
        <div class="direct-login-form">
          <input
            v-model="directSecret"
            type="password"
            class="secret-input"
            placeholder="管理員密碼"
            @keydown.enter="directLogin"
          />
          <button class="direct-login-btn" :disabled="directLogging || !directSecret" @click="directLogin">
            {{ directLogging ? '登入中…' : '登入' }}
          </button>
        </div>
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

      <div v-if="loadError" class="login-error">{{ loadError }}</div>

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
        <button
          v-for="t in tabs"
          :key="t.key"
          :data-testid="`admin-tab-${t.key}`"
          :class="['tab-btn', { active: activeTab === t.key }]"
          @click="activeTab = t.key"
        >
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

      <!-- Tab: AI 用量（X2）：站長事先看到消耗速度，避免額度用完才發現 -->
      <div v-if="activeTab === 'llm'" class="tab-panel">
        <h3>AI 用量（近 7 天）</h3>
        <p class="muted small">每日上限 {{ llmUsage.daily_limit ?? '—' }} 次；今日已用 {{ llmUsage.today_count ?? 0 }} 次。額度為全站共用（跨所有 AI 功能），用完當天所有 AI 功能會暫時無法使用。</p>
        <div class="pv-list">
          <div v-for="d in llmUsage.days" :key="d.date" class="pv-row">
            <span class="pv-page">{{ d.date }}</span>
            <div class="pv-bar-wrap">
              <div class="pv-bar" :class="{ 'pv-bar-warn': llmUsage.daily_limit && d.count >= llmUsage.daily_limit }" :style="{ width: llmBarWidth(d.count) }"></div>
            </div>
            <span class="pv-count">{{ d.count }}</span>
          </div>
        </div>
        <div v-if="!llmUsage.days?.length" class="empty">尚無資料</div>
      </div>

      <!-- Tab: 每日資料庫（md_*）白名單與同步管理 + 官方開放資料（od_*）健康概況 -->
      <div v-if="activeTab === 'store'" class="tab-panel store-tab-panel" data-testid="store-panel">
        <div v-if="storeError" class="store-feedback is-err" data-testid="store-load-error">
          {{ storeError }}
        </div>

        <!-- 區塊一：白名單管理 -->
        <section class="store-card" data-testid="store-whitelist-section">
          <div class="panel-header store-card-header">
            <div class="store-title-group">
              <h3>每日資料庫（md_*）白名單管理</h3>
              <span class="store-badge badge-info" data-testid="store-whitelist-count">
                {{ whitelistDraft.length }} / {{ whitelistMax }}
              </span>
              <span class="store-badge badge-muted" data-testid="store-whitelist-source">
                來源：{{ whitelistSourceLabel }}
              </span>
              <span v-if="whitelistDirty" class="store-badge badge-warn" data-testid="store-whitelist-dirty">
                尚未儲存變更
              </span>
            </div>
            <div class="store-actions">
              <button
                type="button"
                class="btn-secondary-outline"
                data-testid="store-whitelist-reset-btn"
                :disabled="!whitelistDirty || whitelistSaving"
                @click="resetWhitelistDraft"
              >
                重設變更
              </button>
              <button
                type="button"
                class="btn-danger-outline"
                data-testid="store-whitelist-clear-btn"
                :disabled="!whitelistDraft.length || whitelistSaving"
                @click="clearWhitelistDraft"
              >
                清空清單
              </button>
              <button
                type="button"
                class="btn-solid-primary"
                data-testid="store-whitelist-save-btn"
                :disabled="whitelistSaving"
                @click="saveWhitelist"
              >
                {{ whitelistSaving ? '儲存中…' : '儲存白名單' }}
              </button>
            </div>
          </div>

          <p class="muted small store-hint">
            每日排程（台灣時間平日 15:00）會針對白名單股票增量抓取日 K、三大法人、融資融券、本益比／淨值比與月營收並寫入 MongoDB（上限 {{ whitelistMax }} 檔，代號為 4～6 碼英數字）。
          </p>

          <!-- 白名單 Chip 列表 -->
          <div v-if="whitelistDraft.length" class="wl-chip-list" data-testid="store-whitelist-tags">
            <span
              v-for="sym in whitelistDraft"
              :key="sym"
              class="wl-chip"
              data-testid="store-whitelist-tag"
              :data-symbol="sym"
            >
              <span class="wl-chip-code">{{ sym }}</span>
              <button
                type="button"
                class="wl-chip-remove"
                data-testid="store-whitelist-remove"
                :aria-label="`移除 ${sym}`"
                :title="`移除 ${sym}`"
                @click="removeWhitelistSymbol(sym)"
              >
                ×
              </button>
            </span>
          </div>
          <div v-else class="store-empty-box" data-testid="store-whitelist-empty">
            目前白名單為空，排程與手動同步將不會抓取任何股票。請在下方輸入股票代號並點擊「儲存白名單」。
          </div>

          <!-- 單筆／批次新增 -->
          <div class="wl-add-box">
            <label for="store-whitelist-textarea" class="wl-add-label">
              單筆或批次新增股票代號（支援逗號、空白或換行分隔，自動轉大寫並去重）
            </label>
            <div class="wl-add-row">
              <textarea
                id="store-whitelist-textarea"
                v-model="whitelistInput"
                class="wl-textarea"
                rows="2"
                data-testid="store-whitelist-input"
                placeholder="例如：2330, 0050, 00940B（或每行一檔）"
                @keydown.ctrl.enter.prevent="addWhitelistSymbols"
              ></textarea>
              <button
                type="button"
                class="btn-secondary-outline wl-add-btn"
                data-testid="store-whitelist-add-btn"
                :disabled="whitelistSaving"
                @click="addWhitelistSymbols"
              >
                + 加入清單
              </button>
            </div>
          </div>

          <div
            v-if="whitelistFeedback"
            :class="['store-feedback', whitelistFeedback.ok ? 'is-ok' : 'is-err']"
            :data-testid="whitelistFeedback.ok ? 'store-whitelist-feedback' : 'store-whitelist-error'"
          >
            {{ whitelistFeedback.msg }}
          </div>
        </section>

        <!-- 區塊二：每日資料庫同步狀態 -->
        <section class="store-card" data-testid="store-status-section">
          <div class="panel-header store-card-header">
            <div class="store-title-group">
              <h3>每日資料庫（md_*）同步狀態</h3>
              <span
                :class="['store-badge', storeStatus.running ? 'badge-warn' : 'badge-ok']"
                data-testid="store-running-badge"
              >
                {{ storeStatus.running ? '同步執行中…' : '閒置' }}
              </span>
            </div>
            <div class="store-actions">
              <button
                type="button"
                class="btn-secondary-outline"
                data-testid="store-refresh-btn"
                :disabled="storeLoading"
                @click="loadStoreTab()"
              >
                {{ storeLoading ? '重新整理中…' : '重新整理狀態' }}
              </button>
              <button
                type="button"
                class="btn-solid-primary"
                data-testid="store-run-btn"
                :disabled="!canTriggerSync"
                :title="syncDisabledReason || '於背景執行一輪增量同步'"
                @click="triggerStoreSync"
              >
                {{ triggeringSync ? '啟動中…' : '立即手動同步' }}
              </button>
            </div>
          </div>

          <p class="muted small store-hint">
            FinMind 免費額度為每小時 600 次（每檔股票每次最多約 5 次請求），手動觸發會於背景執行增量更新，若達額度上限將自動中止並保留斷點。
            <span v-if="syncDisabledReason" class="store-disabled-hint" data-testid="store-run-disabled-reason">
              （{{ syncDisabledReason }}）
            </span>
          </p>

          <div
            v-if="syncFeedback"
            :class="['store-feedback', syncFeedback.ok ? 'is-ok' : 'is-err']"
            data-testid="store-run-feedback"
          >
            {{ syncFeedback.msg }}
          </div>

          <!-- 各資料集已存筆數概況 -->
          <div class="store-datasets-grid" data-testid="store-datasets-grid">
            <div
              v-for="ds in storeDatasetRows"
              :key="ds.key"
              class="store-dataset-card"
              :data-testid="`store-dataset-${ds.key}`"
            >
              <div class="store-dataset-label">{{ ds.label }}</div>
              <div class="store-dataset-count">{{ formatCount(ds.count) }}</div>
              <div class="store-dataset-coll">{{ ds.coll }}</div>
            </div>
          </div>

          <!-- 最近執行紀錄 -->
          <h4 class="store-sub-title">最近執行紀錄</h4>
          <div class="log-table-wrap" data-testid="store-recent-runs">
            <table class="log-table">
              <thead>
                <tr>
                  <th>開始時間</th>
                  <th>觸發方式</th>
                  <th>股票數</th>
                  <th>寫入筆數</th>
                  <th>錯誤數</th>
                  <th>備註／狀態</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(run, idx) in storeStatus.recent_runs" :key="idx">
                  <td>{{ formatTime(run.started_at) }}</td>
                  <td>
                    <span :class="['store-badge', run.trigger === 'manual' ? 'badge-info' : 'badge-muted']">
                      {{ formatTrigger(run.trigger) }}
                    </span>
                  </td>
                  <td class="num-cell">{{ run.symbols ?? 0 }}</td>
                  <td class="num-cell">{{ formatCount(run.rows ?? 0) }}</td>
                  <td class="num-cell">
                    <span :class="run.errors > 0 ? 'text-err' : ''">{{ run.errors ?? 0 }}</span>
                  </td>
                  <td>
                    <span v-if="run.aborted === 'quota'" class="store-badge badge-warn">額度用完提前中止</span>
                    <span v-else-if="run.aborted" class="store-badge badge-err">中止：{{ run.aborted }}</span>
                    <span>{{ run.note || (run.aborted ? '' : '完成') }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!storeStatus.recent_runs?.length" class="empty">尚無同步執行紀錄</div>
          </div>
        </section>

        <!-- 區塊三：官方開放資料倉庫（od_*）健康概況（唯讀輕量卡片） -->
        <section class="store-card store-card-compact" data-testid="open-data-section">
          <div class="panel-header store-card-header">
            <div class="store-title-group">
              <h3>官方開放資料倉庫（od_*）健康概況</h3>
              <span class="store-badge badge-muted">唯讀</span>
              <span
                v-if="openDataStatus"
                :class="['store-badge', openDataOverallClass]"
                data-testid="open-data-overall-badge"
              >
                {{ openDataOverallLabel }}
              </span>
            </div>
          </div>

          <div v-if="openDataUnavailable" class="muted small" data-testid="open-data-fallback">
            目前無法取得官方開放資料倉庫狀態（不影響每日資料庫白名單管理）。
          </div>
          <template v-else-if="openDataStatus">
            <div
              v-if="openDataStatus.cooling_off || openDataStatus.blocked_reason"
              class="store-feedback is-err"
              data-testid="open-data-blocked-banner"
            >
              來源冷卻中：{{ openDataStatus.blocked_reason || '來源暫時封鎖，等待自動冷卻結束' }}
              <span v-if="openDataStatus.blocked_until">（至 {{ formatTime(openDataStatus.blocked_until) }}）</span>
            </div>
            <div class="od-datasets-grid" data-testid="open-data-datasets-grid">
              <div
                v-for="item in openDataRows"
                :key="item.key"
                class="od-dataset-card"
                :data-testid="`open-data-dataset-${item.key}`"
              >
                <div class="od-dataset-top">
                  <span class="od-dataset-label">{{ item.label }}</span>
                  <span :class="['store-badge', odStatusClass(item.status)]">
                    {{ formatOdStatus(item.status) }}
                  </span>
                </div>
                <div class="od-dataset-meta">
                  <span>最新日期：<strong>{{ item.last_data_date || '—' }}</strong></span>
                  <span>筆數：<strong>{{ formatCount(item.count) }}</strong></span>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="muted small">載入中…</div>
        </section>
      </div>

      <!-- Tab: Settings -->
      <div v-if="activeTab === 'settings'" class="tab-panel">
        <div class="panel-header">
          <h3>系統設定</h3>
          <button class="btn-primary" @click="showAddSetting = !showAddSetting">+ 新增</button>
        </div>
        <div v-if="showAddSetting" class="add-setting-form">
          <input v-model="newKey" placeholder="設定鍵值 (Key)" class="input-sm" />
          <input v-model="newValue" placeholder="設定內容 (Value)" class="input-sm" />
          <button class="btn-primary" @click="addSetting" :disabled="addingSetting">{{ addingSetting ? '儲存中...' : '儲存' }}</button>
          <button class="btn-ghost" @click="showAddSetting = false">取消</button>
        </div>
        <div v-if="actionError" class="login-error">{{ actionError }}</div>
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
        <div v-if="actionError" class="login-error">{{ actionError }}</div>
        <div class="admins-list">
          <div v-for="email in adminEmails" :key="email" class="admin-row">
            <span class="admin-email">{{ email }}</span>
            <button class="btn-danger-sm" @click="removeAdmin(email)" :disabled="email === authStore.email">移除</button>
          </div>
        </div>
        <div class="add-admin-form">
          <input v-model="newAdminEmail" placeholder="輸入 Google 帳號 Email" class="input-sm" />
          <button class="btn-primary" @click="addAdmin" :disabled="addingAdmin">{{ addingAdmin ? '新增中...' : '新增' }}</button>
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
// MM7：loadStats/loadLogs/loadPageviews/loadLlmUsage/loadSettings/loadAdmins
// 先前都是空的 catch {}，網路/解析失敗時畫面會跟「本來就沒資料」長得一模
// 一樣（顯示「尚無紀錄」等空狀態），管理員完全看不出東西是不是真的壞了。
const loadError = ref('')
const ADMIN_TAB_KEY = 'finlab_admin_active_tab'
const tabs = [
  { key: 'logs', icon: '📋', label: '訪客紀錄' },
  { key: 'pageviews', icon: '📊', label: '瀏覽統計' },
  { key: 'llm', icon: '🤖', label: 'AI 用量' },
  { key: 'store', icon: '🗄️', label: '每日資料庫' },
  { key: 'settings', icon: '⚙️', label: '系統設定' },
  { key: 'admins', icon: '👤', label: '管理員' },
  { key: 'notify', icon: '🔔', label: '通知設定' },
]
function readSavedTab() {
  try {
    const saved = sessionStorage.getItem(ADMIN_TAB_KEY)
    if (saved && tabs.some((t) => t.key === saved)) return saved
  } catch { /* ignore */ }
  return 'logs'
}
const activeTab = ref(readSavedTab())

const stats = ref({ today_visitors: 0, total_pageviews: 0, unique_visitors: 0 })
const logs = ref([])
const logFilter = ref('')
const pageviewMap = ref({})
const llmUsage = ref({ days: [], daily_limit: null, today_count: 0 })
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
const actionError = ref('')
const addingSetting = ref(false)
const addingAdmin = ref(false)

const maxPV = computed(() => Math.max(...Object.values(pageviewMap.value), 1))
function barWidth(count) { return `${(count / maxPV.value) * 100}%` }

const maxLlmBar = computed(() => Math.max(...(llmUsage.value.days || []).map(d => d.count), llmUsage.value.daily_limit || 0, 1))
function llmBarWidth(count) { return `${(count / maxLlmBar.value) * 100}%` }

function formatTime(ts) {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-TW')
  } catch { return ts }
}

function authHeaders() {
  return { 'X-Admin-Token': authStore.token || '', 'Content-Type': 'application/json' }
}

// II6：以下 6 個初始載入函式原本完全沒檢查 r.ok，admin_token 過期
// （auth.py 簽發的 JWT 12 小時到期）或無效時，後端回傳的 401 錯誤 body
// 會被當成正常資料直接塞進 UI 狀態顯示。401 代表整個 session 已經失效，
// 而不是單一功能失敗，所以統一登出、清空狀態、回登入畫面，而不是各自
// 顯示技術性錯誤訊息。
function handleAdminAuthFailure(status) {
  if (status !== 401) return false
  authStore.logout()
  loginError.value = '登入已過期，請重新登入'
  return true
}

async function loadStats() {
  try {
    const r = await fetch('/api/v1/admin/logs/stats', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    stats.value = d.data || d
  } catch {
    loadError.value = '統計數字載入失敗，請重新整理頁面再試'
  }
}

async function loadLogs() {
  try {
    const q = logFilter.value ? `?type=${logFilter.value}` : ''
    const r = await fetch(`/api/v1/admin/logs${q}`, { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    logs.value = d.data || d || []
  } catch {
    loadError.value = '訪客紀錄載入失敗，請重新整理頁面再試'
  }
}

async function loadPageviews() {
  try {
    const r = await fetch('/api/v1/analytics/pageviews', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    pageviewMap.value = d || {}
  } catch {
    loadError.value = '瀏覽統計載入失敗，請重新整理頁面再試'
  }
}

async function loadLlmUsage() {
  try {
    const r = await fetch('/api/v1/admin/llm-usage', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    if (d.success) llmUsage.value = d.data
  } catch {
    loadError.value = 'AI 用量載入失敗，請重新整理頁面再試'
  }
}

async function loadSettings() {
  try {
    // GG1：改讀 /api/v1/admin/settings——同一份完整設定，但這支才是真的掛
    // require_admin 驗證的（公開的 /api/v1/settings 現在只回傳安全子集，
    // 不再包含 telegram_bot_token 等機密，這裡才拿得到完整內容）。
    const r = await fetch('/api/v1/admin/settings', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    const data = d.data || {}
    Object.keys(settingsMap).forEach(k => delete settingsMap[k])
    Object.assign(settingsMap, data)
    telegramToken.value = data.telegram_bot_token || ''
    telegramChatId.value = data.telegram_chat_id || ''
    lineToken.value = data.line_token || ''
  } catch {
    loadError.value = '系統設定載入失敗，請重新整理頁面再試'
  }
}

async function loadAdmins() {
  try {
    const r = await fetch('/api/v1/admin/allowed-admins', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const d = await r.json()
    adminEmails.value = d.data || d || []
  } catch {
    loadError.value = '管理員清單載入失敗，請重新整理頁面再試'
  }
}

async function addSetting() {
  if (!newKey.value) return
  addingSetting.value = true
  actionError.value = ''
  try {
    const resp = await fetch('/api/v1/admin/settings', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ key: newKey.value, value: newValue.value }),
    })
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || `HTTP ${resp.status}`)
    settingsMap[newKey.value] = newValue.value
    newKey.value = ''; newValue.value = ''
    showAddSetting.value = false
  } catch (e) {
    actionError.value = `新增設定失敗：${e.message || '請稍後再試'}`
  }
  addingSetting.value = false
}

async function updateSetting(key, value) {
  actionError.value = ''
  try {
    const resp = await fetch(`/api/v1/admin/settings/${key}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ value }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  } catch (e) {
    actionError.value = `更新設定「${key}」失敗：${e.message || '請稍後再試'}`
  }
}

async function deleteSetting(key) {
  if (!window.confirm(`確定要刪除設定「${key}」嗎？此動作無法復原。`)) return
  actionError.value = ''
  try {
    const resp = await fetch(`/api/v1/admin/settings/${key}`, { method: 'DELETE', headers: authHeaders() })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    delete settingsMap[key]
  } catch (e) {
    actionError.value = `刪除設定「${key}」失敗：${e.message || '請稍後再試'}`
  }
}

async function addAdmin() {
  if (!newAdminEmail.value) return
  addingAdmin.value = true
  actionError.value = ''
  try {
    const resp = await fetch('/api/v1/admin/allowed-admins', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ email: newAdminEmail.value }),
    })
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(payload?.detail || `HTTP ${resp.status}`)
    adminEmails.value.push(newAdminEmail.value)
    newAdminEmail.value = ''
  } catch (e) {
    actionError.value = `新增管理員失敗：${e.message || '請稍後再試'}`
  }
  addingAdmin.value = false
}

async function removeAdmin(email) {
  if (!window.confirm(`確定要移除管理員「${email}」的權限嗎？`)) return
  actionError.value = ''
  try {
    const resp = await fetch(`/api/v1/admin/allowed-admins/${encodeURIComponent(email)}`, { method: 'DELETE', headers: authHeaders() })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    adminEmails.value = adminEmails.value.filter(e => e !== email)
  } catch (e) {
    actionError.value = `移除管理員「${email}」失敗：${e.message || '請稍後再試'}`
  }
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

const directSecret = ref('')
const directLogging = ref(false)

async function directLogin() {
  if (!directSecret.value || directLogging.value) return
  directLogging.value = true
  loginError.value = ''
  try {
    const API_BASE = import.meta.env.VITE_API_BASE ?? ''
    const r = await fetch(`${API_BASE}/api/v1/auth/direct-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret: directSecret.value }),
    })
    const data = await r.json()
    if (!r.ok) {
      loginError.value = data.detail || '密碼錯誤'
      return
    }
    if (data.valid) {
      authStore.token = data.token
      authStore.user = { email: data.email, name: data.name, avatar: data.avatar, is_admin: data.is_admin }
      localStorage.setItem('admin_token', data.token)
      localStorage.setItem('admin_user', JSON.stringify({ email: data.email, name: data.name, avatar: data.avatar, is_admin: data.is_admin }))
      directSecret.value = ''
      await Promise.all([loadStats(), loadLogs(), loadPageviews(), loadLlmUsage(), loadSettings(), loadAdmins()])
    } else {
      loginError.value = '密碼錯誤'
    }
  } catch {
    loginError.value = '網路錯誤，請稍後再試'
  } finally {
    directLogging.value = false
  }
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

// ───────────────────── 每日資料庫（md_*）與官方開放資料（od_*） ─────────────────────
const SYMBOL_RE = /^[0-9A-Z]{4,6}$/
const STORE_DATASET_ORDER = ['price', 'institutional', 'margin', 'valuation', 'revenue']
const STORE_DATASET_FALLBACK_LABELS = {
  price: '日 K',
  institutional: '三大法人',
  margin: '融資融券',
  valuation: '本益比／淨值比',
  revenue: '月營收',
}
const OD_DATASET_ORDER = ['margin', 'valuation', 'revenue', 'disposal', 'attention', 'tdcc']

const storeLoading = ref(false)
const storeError = ref('')
const whitelistSaved = ref([])
const whitelistDraft = ref([])
const whitelistSource = ref('none')
const whitelistMax = ref(100)
const whitelistInput = ref('')
const whitelistSaving = ref(false)
const whitelistFeedback = ref(null)
const storeStatus = ref({
  running: false,
  datasets: { ...STORE_DATASET_FALLBACK_LABELS },
  stored_counts: {},
  symbols: {},
  recent_runs: [],
  max_symbols: 100,
})
const triggeringSync = ref(false)
const syncFeedback = ref(null)
const openDataStatus = ref(null)
const openDataUnavailable = ref(false)

const whitelistDirty = computed(() => {
  if (whitelistDraft.value.length !== whitelistSaved.value.length) return true
  return whitelistDraft.value.some((s, i) => s !== whitelistSaved.value[i])
})

const whitelistSourceLabel = computed(() => {
  if (whitelistSource.value === 'db') return '資料庫設定'
  if (whitelistSource.value === 'env') return '環境變數'
  return '尚未設定'
})

const storeDatasetRows = computed(() => {
  const dsMap = storeStatus.value.datasets || STORE_DATASET_FALLBACK_LABELS
  const counts = storeStatus.value.stored_counts || {}
  const keys = Object.keys(dsMap).length ? Object.keys(dsMap) : STORE_DATASET_ORDER
  const ordered = [
    ...STORE_DATASET_ORDER.filter(k => keys.includes(k)),
    ...keys.filter(k => !STORE_DATASET_ORDER.includes(k)),
  ]
  return ordered.map(key => ({
    key,
    label: dsMap[key] || STORE_DATASET_FALLBACK_LABELS[key] || key,
    coll: `md_${key}`,
    count: counts[key],
  }))
})

const openDataRows = computed(() => {
  const dsMap = openDataStatus.value?.datasets || {}
  const counts = openDataStatus.value?.stored_counts || {}
  const keys = Object.keys(dsMap)
  const ordered = [
    ...OD_DATASET_ORDER.filter(k => keys.includes(k)),
    ...keys.filter(k => !OD_DATASET_ORDER.includes(k)),
  ]
  return ordered.map(key => ({
    key,
    label: dsMap[key]?.label || key,
    status: dsMap[key]?.status || 'never',
    last_data_date: dsMap[key]?.last_data_date || null,
    count: counts[key],
  }))
})

const openDataOverallLabel = computed(() => {
  if (!openDataStatus.value) return ''
  if (openDataStatus.value.cooling_off) return '來源冷卻中'
  if (openDataStatus.value.running) return '同步中'
  if (openDataStatus.value.ok) return '健康'
  if (openDataStatus.value.stale?.length) return `過期／異常 (${openDataStatus.value.stale.length})`
  if (openDataStatus.value.partial?.length) return `部分失敗 (${openDataStatus.value.partial.length})`
  return '需注意'
})

const openDataOverallClass = computed(() => {
  if (!openDataStatus.value) return 'badge-muted'
  if (openDataStatus.value.cooling_off || openDataStatus.value.stale?.length) return 'badge-err'
  if (openDataStatus.value.partial?.length || openDataStatus.value.running) return 'badge-warn'
  if (openDataStatus.value.ok) return 'badge-ok'
  return 'badge-muted'
})

const canTriggerSync = computed(() => (
  !storeStatus.value.running
  && !triggeringSync.value
  && whitelistSaved.value.length > 0
  && !whitelistDirty.value
))

const syncDisabledReason = computed(() => {
  if (storeStatus.value.running || triggeringSync.value) return '同步任務執行中，請稍候再試'
  if (whitelistDirty.value) return '尚有未儲存的白名單變更，請先儲存白名單後再同步'
  if (whitelistSaved.value.length === 0) return '白名單為空，請先新增並儲存至少 1 檔股票後再同步'
  return ''
})

function formatCount(n) {
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('zh-TW') : '—'
}

function formatTrigger(trigger) {
  if (trigger === 'manual') return '手動'
  if (trigger === 'schedule') return '排程'
  return trigger || '-'
}

function formatOdStatus(st) {
  const map = { ok: '正常', partial: '部分失敗', stale: '過期', error: '異常', never: '尚未同步' }
  return map[st] || st || '—'
}

function odStatusClass(st) {
  if (st === 'ok') return 'badge-ok'
  if (st === 'partial' || st === 'stale') return 'badge-warn'
  if (st === 'error') return 'badge-err'
  return 'badge-muted'
}

function parseSymbolInput(raw) {
  const tokens = String(raw || '')
    .split(/[,\s]+/)
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
  const valid = []
  const invalid = []
  for (const tok of tokens) {
    if (!SYMBOL_RE.test(tok)) {
      if (!invalid.includes(tok)) invalid.push(tok)
    } else if (!valid.includes(tok)) {
      valid.push(tok)
    }
  }
  return { valid, invalid }
}

function addWhitelistSymbols() {
  const raw = whitelistInput.value.trim()
  if (!raw) {
    whitelistFeedback.value = { ok: false, msg: '請先輸入至少一個股票代號' }
    return false
  }
  const { valid, invalid } = parseSymbolInput(raw)
  if (invalid.length > 0) {
    whitelistFeedback.value = {
      ok: false,
      msg: `代號格式不正確：${invalid.join('、')}（需為 4～6 碼英數字）`,
    }
    return false
  }
  const existing = new Set(whitelistDraft.value)
  const added = valid.filter(s => !existing.has(s))
  if (added.length === 0) {
    whitelistInput.value = ''
    whitelistFeedback.value = { ok: true, msg: '輸入的代號皆已在白名單清單中' }
    return true
  }
  if (whitelistDraft.value.length + added.length > whitelistMax.value) {
    whitelistFeedback.value = {
      ok: false,
      msg: `白名單最多 ${whitelistMax.value} 檔，加入後將達 ${whitelistDraft.value.length + added.length} 檔`,
    }
    return false
  }
  whitelistDraft.value = [...whitelistDraft.value, ...added]
  whitelistInput.value = ''
  whitelistFeedback.value = {
    ok: true,
    msg: `已加入 ${added.length} 檔（${added.join('、')}），請點擊「儲存白名單」套用變更`,
  }
  return true
}

function removeWhitelistSymbol(sym) {
  whitelistDraft.value = whitelistDraft.value.filter(s => s !== sym)
  if (whitelistFeedback.value && !whitelistFeedback.value.ok) {
    whitelistFeedback.value = null
  }
}

function resetWhitelistDraft() {
  whitelistDraft.value = [...whitelistSaved.value]
  whitelistInput.value = ''
  whitelistFeedback.value = null
}

function clearWhitelistDraft() {
  whitelistDraft.value = []
  whitelistFeedback.value = { ok: true, msg: '已清空待儲存清單，請點擊「儲存白名單」確認套用' }
}

async function loadStoreWhitelist({ preserveDirty = false } = {}) {
  try {
    const r = await fetch('/api/v1/store/whitelist', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const payload = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(payload?.detail || `HTTP ${r.status}`)
    const data = payload.data || {}
    const syms = Array.isArray(data.symbols) ? data.symbols : []
    const wasDirty = whitelistDirty.value
    whitelistSaved.value = [...syms]
    if (!preserveDirty || !wasDirty) {
      whitelistDraft.value = [...syms]
    }
    whitelistSource.value = data.source || 'none'
    if (typeof data.max_symbols === 'number' && data.max_symbols > 0) {
      whitelistMax.value = data.max_symbols
    }
  } catch (e) {
    storeError.value = `白名單載入失敗：${e.message || '請稍後再試'}`
  }
}

async function loadStoreStatus() {
  try {
    const r = await fetch('/api/v1/store/status', { headers: authHeaders() })
    if (handleAdminAuthFailure(r.status)) return
    const payload = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(payload?.detail || `HTTP ${r.status}`)
    const data = payload.data || {}
    storeStatus.value = {
      running: Boolean(data.running),
      datasets: data.datasets || { ...STORE_DATASET_FALLBACK_LABELS },
      stored_counts: data.stored_counts || {},
      symbols: data.symbols || {},
      recent_runs: Array.isArray(data.recent_runs) ? data.recent_runs : [],
      max_symbols: data.max_symbols || whitelistMax.value,
    }
  } catch (e) {
    storeError.value = `同步狀態載入失敗：${e.message || '請稍後再試'}`
  }
}

async function loadOpenDataStatus() {
  try {
    const r = await fetch('/api/v1/open-data/status', { headers: authHeaders() })
    if (!r.ok) {
      openDataStatus.value = null
      openDataUnavailable.value = true
      return
    }
    const payload = await r.json().catch(() => null)
    if (!payload?.data) {
      openDataStatus.value = null
      openDataUnavailable.value = true
      return
    }
    openDataStatus.value = payload.data
    openDataUnavailable.value = false
  } catch {
    // 唯讀健康卡片靜默降級，不影響白名單與每日資料庫管理
    openDataStatus.value = null
    openDataUnavailable.value = true
  }
}

async function loadStoreTab({ preserveDirty = true } = {}) {
  storeLoading.value = true
  storeError.value = ''
  try {
    await Promise.all([
      loadStoreWhitelist({ preserveDirty }),
      loadStoreStatus(),
      loadOpenDataStatus(),
    ])
  } finally {
    storeLoading.value = false
  }
}

async function saveWhitelist() {
  if (whitelistSaving.value) return
  if (whitelistInput.value.trim()) {
    const ok = addWhitelistSymbols()
    if (!ok) return
  }
  if (whitelistDraft.value.length > whitelistMax.value) {
    whitelistFeedback.value = {
      ok: false,
      msg: `白名單最多 ${whitelistMax.value} 檔，目前 ${whitelistDraft.value.length} 檔`,
    }
    return
  }
  whitelistSaving.value = true
  whitelistFeedback.value = null
  try {
    const r = await fetch('/api/v1/store/whitelist', {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ symbols: whitelistDraft.value }),
    })
    if (handleAdminAuthFailure(r.status)) return
    const payload = await r.json().catch(() => ({}))
    if (!r.ok) {
      whitelistFeedback.value = { ok: false, msg: payload?.detail || `儲存失敗（HTTP ${r.status}）` }
      return
    }
    const saved = Array.isArray(payload?.data?.symbols) ? payload.data.symbols : [...whitelistDraft.value]
    whitelistSaved.value = [...saved]
    whitelistDraft.value = [...saved]
    whitelistSource.value = payload?.data?.source || 'db'
    await loadStoreStatus()
    whitelistFeedback.value = { ok: true, msg: `白名單已儲存（共 ${saved.length} 檔）` }
  } catch (e) {
    whitelistFeedback.value = { ok: false, msg: `儲存白名單失敗：${e.message || '網路錯誤'}` }
  } finally {
    whitelistSaving.value = false
  }
}

async function triggerStoreSync() {
  if (!canTriggerSync.value) return
  triggeringSync.value = true
  syncFeedback.value = null
  try {
    const r = await fetch('/api/v1/store/run', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({}),
    })
    if (handleAdminAuthFailure(r.status)) return
    const payload = await r.json().catch(() => ({}))
    if (!r.ok) {
      syncFeedback.value = { ok: false, msg: payload?.detail || `觸發同步失敗（HTTP ${r.status}）` }
      return
    }
    const data = payload.data || {}
    if (data.started) {
      storeStatus.value = { ...storeStatus.value, running: true }
      syncFeedback.value = {
        ok: true,
        msg: '已啟動背景增量同步，請稍後點擊「重新整理狀態」查看最新執行紀錄。',
      }
    } else if (data.reason === 'already_running') {
      storeStatus.value = { ...storeStatus.value, running: true }
      syncFeedback.value = { ok: false, msg: '目前已有同步任務正在執行中，請稍候再重新整理狀態。' }
    } else {
      syncFeedback.value = { ok: false, msg: '未能啟動同步任務，請稍後再試。' }
    }
  } catch (e) {
    syncFeedback.value = { ok: false, msg: `觸發同步失敗：${e.message || '網路錯誤'}` }
  } finally {
    triggeringSync.value = false
  }
}

watch(activeTab, (tab) => {
  try { sessionStorage.setItem(ADMIN_TAB_KEY, tab) } catch { /* ignore */ }
  if (tab === 'store' && authStore.isAdmin) {
    loadStoreTab({ preserveDirty: true })
  }
})

onMounted(async () => {
  // Handle OAuth redirect callback (#id_token=...) first
  const justLoggedIn = await handleRedirectCallback()
  // 學習中心的 Google 登入也借用 /admin 這個 redirect_uri（Google Console 只登記了這個），
  // 從 /learn 出發的登入要送回原頁，不在後台顯示「未獲授權」。
  const returnTo = sessionStorage.getItem('post_login_redirect')
  if (justLoggedIn && returnTo && returnTo.startsWith('/learn')) {
    sessionStorage.removeItem('post_login_redirect')
    window.location.replace(returnTo)
    return
  }
  if (authStore.isAdmin) {
    const tasks = [loadStats(), loadLogs(), loadPageviews(), loadLlmUsage(), loadSettings(), loadAdmins()]
    if (activeTab.value === 'store') tasks.push(loadStoreTab({ preserveDirty: true }))
    await Promise.all(tasks)
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
  background: var(--bg-secondary, var(--card));
  border: 1px solid var(--border-color, var(--elev));
  border-radius: 16px; padding: 48px 40px; text-align: center;
  max-width: 380px; width: 100%;
}
.login-logo { font-size: 3rem; margin-bottom: 16px; }
.login-card h2 { margin: 0 0 8px; font-size: 1.5rem; }
.login-card p { color: var(--text-secondary, var(--muted)); font-size: 0.9rem; margin-bottom: 24px; }
.direct-login-form { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.secret-input {
  width: 100%; padding: 10px 14px; border-radius: 10px;
  border: 1px solid var(--border-color, color-mix(in srgb, var(--ink) 15%, transparent));
  background: var(--surface-secondary, color-mix(in srgb, var(--ink) 6%, transparent));
  color: var(--text-primary, #fff); font-size: 0.9rem; font-family: inherit;
}
.secret-input:focus { outline: 2px solid var(--accent-blue, var(--blue)); outline-offset: 1px; }
.direct-login-btn {
  width: 100%; padding: 10px; border-radius: 10px; border: none;
  background: var(--accent-blue, var(--blue)); color: var(--on-accent);
  font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: opacity 0.15s;
}
.direct-login-btn:hover:not(:disabled) { opacity: 0.88; }
.direct-login-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.login-error { color: var(--up); background: var(--down-soft); border-radius: 8px; padding: 8px 12px; margin-bottom: 16px; font-size: 0.85rem; }
@media (prefers-reduced-motion: reduce) {
  .direct-login-btn { transition: none; }
}

.admin-content { max-width: 1100px; margin: 0 auto; padding: 24px 16px 80px; }
.admin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
.admin-header-left { display: flex; align-items: center; gap: 12px; }
.admin-header-left h1 { margin: 0; font-size: 1.4rem; }
.admin-badge { background: color-mix(in srgb, var(--purple) 20%, transparent); color: var(--purple); border: 1px solid color-mix(in srgb, var(--purple) 30%, transparent); border-radius: 20px; padding: 2px 10px; font-size: 0.75rem; }
.admin-header-right { display: flex; align-items: center; gap: 12px; }
.admin-avatar { width: 32px; height: 32px; border-radius: 50%; }
.admin-name { font-size: 0.9rem; }
.btn-logout { background: var(--down-soft); color: var(--up); border: 1px solid color-mix(in srgb, var(--up) 30%, transparent); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: var(--bg-secondary, var(--card)); border: 1px solid var(--border-color, var(--elev)); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--accent-blue, var(--purple)); }
.stat-label { font-size: 0.8rem; color: var(--text-secondary, var(--muted)); margin-top: 4px; }

.admin-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tab-btn { background: var(--bg-secondary, var(--card)); border: 1px solid var(--border-color, var(--elev)); color: var(--text-secondary, var(--muted)); border-radius: 8px; padding: 8px 16px; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
.tab-btn.active { background: color-mix(in srgb, var(--purple) 20%, transparent); color: var(--purple); border-color: color-mix(in srgb, var(--purple) 40%, transparent); }

.tab-panel { background: var(--bg-secondary, var(--card)); border: 1px solid var(--border-color, var(--elev)); border-radius: 12px; padding: 24px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-header h3 { margin: 0; }

.log-table-wrap { overflow-x: auto; }
.log-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.log-table th { text-align: left; padding: 8px 12px; background: color-mix(in srgb, var(--ink) 4%, transparent); color: var(--text-muted, var(--muted)); border-bottom: 1px solid var(--border-color, var(--elev)); }
.log-table td { padding: 8px 12px; border-bottom: 1px solid color-mix(in srgb, var(--ink) 4%, transparent); }
.log-type { padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.log-type.pageview { background: color-mix(in srgb, var(--blue) 15%, transparent); color: var(--blue); }
.log-type.login { background: var(--up-soft); color: var(--down); }
.log-ip { font-family: monospace; font-size: 0.78rem; color: var(--text-muted, var(--muted)); }

.pv-list { display: flex; flex-direction: column; gap: 10px; }
.pv-row { display: flex; align-items: center; gap: 12px; }
.pv-page { min-width: 140px; font-size: 0.85rem; color: var(--text-secondary, var(--muted)); }
.pv-bar-wrap { flex: 1; height: 8px; background: color-mix(in srgb, var(--ink) 6%, transparent); border-radius: 4px; overflow: hidden; }
.pv-bar { height: 100%; background: linear-gradient(90deg, var(--purple), var(--accent-purple)); border-radius: 4px; transition: width 0.5s ease; }
.pv-bar-warn { background: linear-gradient(90deg, var(--warn), var(--up)); }
.pv-count { min-width: 40px; text-align: right; font-weight: 600; font-size: 0.85rem; }
.muted { color: var(--text-muted, var(--muted)); }
.small { font-size: 0.8rem; }

.add-setting-form, .add-admin-form { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.settings-list, .admins-list { display: flex; flex-direction: column; gap: 8px; }
.setting-row, .admin-row { display: flex; align-items: center; gap: 8px; }
.setting-key { min-width: 180px; font-family: monospace; font-size: 0.85rem; color: var(--purple); }
.setting-val { flex: 1; }
.admin-email { flex: 1; font-size: 0.9rem; }

.input-sm { background: var(--bg-primary, var(--well)); border: 1px solid var(--border-color, var(--elev)); border-radius: 8px; padding: 6px 10px; color: var(--text-primary, var(--ink)); font-size: 0.85rem; }
.input-full { width: 100%; background: var(--bg-primary, var(--well)); border: 1px solid var(--border-color, var(--elev)); border-radius: 8px; padding: 8px 12px; color: var(--text-primary, var(--ink)); font-size: 0.9rem; margin-bottom: 8px; box-sizing: border-box; }

.btn-primary { background: color-mix(in srgb, var(--purple) 20%, transparent); color: var(--purple); border: 1px solid color-mix(in srgb, var(--purple) 40%, transparent); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; transition: background 0.2s; }
.btn-primary:hover { background: color-mix(in srgb, var(--purple) 35%, transparent); }
.btn-ghost { background: transparent; color: var(--text-secondary, var(--muted)); border: 1px solid var(--border-color, var(--elev)); border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 0.85rem; }
.btn-danger-sm { background: var(--down-soft); color: var(--up); border: 1px solid color-mix(in srgb, var(--up) 20%, transparent); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.8rem; }
.btn-danger-sm:disabled { opacity: 0.4; cursor: not-allowed; }

.notify-section { background: color-mix(in srgb, var(--ink) 3%, transparent); border: 1px solid var(--border-color, var(--elev)); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
.notify-section h4 { margin: 0 0 12px; }
.notify-section label { display: block; font-size: 0.8rem; color: var(--text-secondary, var(--muted)); margin-bottom: 4px; }
.notify-result { padding: 10px 16px; border-radius: 8px; font-size: 0.9rem; margin-top: 12px; }
.notify-result.ok { background: var(--up-soft); color: var(--down); }
.notify-result.err { background: var(--down-soft); color: var(--up); }

.empty { text-align: center; color: var(--text-muted, var(--muted)); padding: 24px; font-size: 0.9rem; }

select { background: var(--bg-primary, var(--well)); border: 1px solid var(--border-color, var(--elev)); border-radius: 8px; padding: 6px 10px; color: var(--text-primary, var(--ink)); font-size: 0.85rem; }

/* 每日資料庫（md_*）與官方開放資料（od_*）管理介面：全數採用 CSS 主題變數，支援 6 組主題與 WCAG AA 對比 */
.store-tab-panel { display: flex; flex-direction: column; gap: 20px; background: transparent; border: none; padding: 0; }
.store-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
}
.store-card-compact { padding: 16px 20px; }
.store-card-header { flex-wrap: wrap; gap: 12px; margin-bottom: 10px; }
.store-title-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.store-title-group h3 { margin: 0; font-size: 1.08rem; color: var(--text-primary); }
.store-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.store-hint { margin: 0 0 14px; line-height: 1.55; }
.store-disabled-hint { color: var(--color-warning); font-weight: 500; }

.store-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.4;
}
.badge-info { background: var(--blue-soft); color: var(--accent-blue); border: 1px solid color-mix(in srgb, var(--accent-blue) 30%, transparent); }
.badge-ok { background: var(--down-soft); color: var(--color-down); border: 1px solid color-mix(in srgb, var(--color-down) 30%, transparent); }
.badge-warn { background: var(--warn-soft); color: var(--color-warning); border: 1px solid color-mix(in srgb, var(--color-warning) 30%, transparent); }
.badge-err { background: var(--up-soft); color: var(--color-up); border: 1px solid color-mix(in srgb, var(--color-up) 30%, transparent); }
.badge-muted { background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border-color); }

.btn-solid-primary {
  background: var(--accent-blue);
  color: var(--on-accent);
  border: 1px solid var(--accent-blue);
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-solid-primary:hover:not(:disabled) { opacity: 0.88; }
.btn-solid-primary:disabled { opacity: 0.45; cursor: not-allowed; }

.btn-secondary-outline {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-secondary-outline:hover:not(:disabled) { background: var(--bg-hover); }
.btn-secondary-outline:disabled { opacity: 0.45; cursor: not-allowed; }

.btn-danger-outline {
  background: var(--up-soft);
  color: var(--color-up);
  border: 1px solid color-mix(in srgb, var(--color-up) 32%, transparent);
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-danger-outline:hover:not(:disabled) { opacity: 0.85; }
.btn-danger-outline:disabled { opacity: 0.45; cursor: not-allowed; }

.wl-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  margin-bottom: 14px;
}
.wl-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px 4px 10px;
  border-radius: 999px;
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
}
.wl-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}
.wl-chip-remove:hover { background: var(--up-soft); color: var(--color-up); }

.store-empty-box {
  padding: 16px;
  border-radius: 10px;
  border: 1px dashed var(--border-color);
  background: var(--bg-well);
  color: var(--text-secondary);
  font-size: 0.88rem;
  text-align: center;
  margin-bottom: 14px;
}

.wl-add-box { display: flex; flex-direction: column; gap: 6px; }
.wl-add-label { font-size: 0.82rem; color: var(--text-secondary); font-weight: 500; }
.wl-add-row { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; }
.wl-textarea {
  flex: 1;
  min-width: 220px;
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 0.86rem;
  line-height: 1.45;
  resize: vertical;
  box-sizing: border-box;
}
.wl-textarea::placeholder { color: var(--text-muted); font-family: var(--font-sans); }
.wl-textarea:focus { outline: 2px solid var(--accent-blue); outline-offset: 1px; }
.wl-add-btn { white-space: nowrap; }

.store-feedback {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.86rem;
  font-weight: 500;
}
.store-feedback.is-ok {
  background: var(--down-soft);
  color: var(--color-down);
  border: 1px solid color-mix(in srgb, var(--color-down) 30%, transparent);
}
.store-feedback.is-err {
  background: var(--up-soft);
  color: var(--color-up);
  border: 1px solid color-mix(in srgb, var(--color-up) 30%, transparent);
}

.store-datasets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.store-dataset-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px 14px;
}
.store-dataset-label { font-size: 0.82rem; color: var(--text-secondary); font-weight: 600; }
.store-dataset-count {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);
  margin: 4px 0 2px;
}
.store-dataset-coll { font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono); }

.store-sub-title { margin: 0 0 10px; font-size: 0.95rem; color: var(--text-primary); }
.num-cell { font-family: var(--font-mono); white-space: nowrap; }
.text-err { color: var(--color-up); font-weight: 700; }

.od-datasets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.od-dataset-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.od-dataset-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.od-dataset-label { font-size: 0.84rem; font-weight: 600; color: var(--text-primary); }
.od-dataset-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
}
.od-dataset-meta strong { color: var(--text-primary); font-family: var(--font-mono); }

@media (prefers-reduced-motion: reduce) {
  .btn-solid-primary, .btn-secondary-outline, .btn-danger-outline { transition: none; }
}
</style>