<template>
  <div class="settings-page">
    <PageFocusBanner text="管理個人化設定與偏好，確保各分析頁面依需求呈現。" />

    <h2>⚙️ 設定</h2>

    <div class="card" style="margin-top: 24px;">
      <h3>API Tokens</h3>
      <div class="form-group">
        <label>FinMind API Token</label>
        <div class="input-row">
          <input type="password" v-model="finmindToken" class="form-input" placeholder="輸入 FinMind Token" />
          <button class="btn btn-primary" @click="validateToken('finmind')">驗證</button>
        </div>
      </div>
      <div class="form-group">
        <label>LINE Notify Token</label>
        <div class="input-row">
          <input type="password" v-model="lineToken" class="form-input" placeholder="輸入 LINE Token" />
          <button class="btn btn-primary" @click="testLine">測試通知</button>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 16px;">
      <h3>預設分析參數</h3>
      <div class="form-group">
        <label>預設時間區間</label>
        <select v-model="defaultPeriod" class="form-input">
          <option value="1M">1個月</option>
          <option value="3M">3個月</option>
          <option value="6M">6個月</option>
          <option value="1Y">1年</option>
          <option value="3Y">3年</option>
        </select>
      </div>
      <div class="form-group">
        <label>預設初始資金</label>
        <input type="number" v-model.number="defaultCapital" class="form-input" />
      </div>
    </div>

    <div class="card" style="margin-top: 16px;">
      <h3>通知偏好</h3>
      <label class="checkbox-label">
        <input type="checkbox" v-model="notifications.price" /> 價格突破通知
      </label>
      <label class="checkbox-label">
        <input type="checkbox" v-model="notifications.signal" /> 技術訊號通知
      </label>
      <label class="checkbox-label">
        <input type="checkbox" v-model="notifications.ai" /> AI 預測通知 (信心 > 70%)
      </label>
    </div>

    <div class="card" style="margin-top: 16px;">
      <h3>🔄 資料更新</h3>
      <p class="theme-hint">關聯圖與類股輪動的資料每天收盤後（15:00）自動更新。需要立即更新時按下方按鈕（大盤資料量大，可能需數十秒）。</p>
      <button class="btn btn-primary" @click="reingestNow" :disabled="reingesting">
        {{ reingesting ? '更新中…' : '立即更新 關聯圖 / 類股輪動 資料' }}
      </button>
      <span v-if="reingestMsg" class="reingest-msg">{{ reingestMsg }}</span>
    </div>

    <div class="card theme-card" style="margin-top: 16px;">
      <h3>🎨 外觀主題</h3>
      <p class="theme-hint">調整頁面、區塊與卡片的底色與邊界，變更會即時套用並自動記住（存在本機瀏覽器）。</p>

      <!-- 常見組合：套用 / 刪除自訂組合 -->
      <div class="preset-section">
        <span class="preset-label">常見組合</span>
        <div class="preset-list">
          <div v-for="p in allPresets" :key="p.id" class="preset-chip">
            <button class="preset-apply" @click="applyPreset(p.values)">{{ p.name }}</button>
            <button v-if="!p.builtin" class="preset-del" title="刪除此組合" @click="deletePreset(p.id)">✕</button>
          </div>
        </div>
      </div>
      <div class="preset-add">
        <input v-model="newPresetName" class="form-input" placeholder="輸入組合名稱，例如「我的暗色」" @keyup.enter="saveAsPreset" />
        <button class="btn btn-primary" @click="saveAsPreset">＋ 儲存目前為新組合</button>
        <button class="btn btn-ghost" @click="resetDefault">重設為預設</button>
      </div>

      <!-- 逐項調整 -->
      <div class="theme-grid">
        <div v-for="f in THEME_FIELDS" :key="f.key" class="theme-field">
          <label>{{ f.label }}</label>
          <div class="theme-control" v-if="f.type === 'color'">
            <input type="color" :value="toHex(state.current[f.key])" @input="setField(f.key, $event.target.value)" />
            <input type="text" class="form-input hex-input" :value="state.current[f.key]" @change="setField(f.key, $event.target.value)" />
          </div>
          <div class="theme-control" v-else>
            <input type="range" min="0" max="6" step="1" :value="toPx(state.current[f.key])" @input="setField(f.key, $event.target.value + 'px')" />
            <span class="width-val">{{ state.current[f.key] }}</span>
          </div>
        </div>
      </div>

      <!-- 即時預覽 -->
      <div class="theme-preview">
        <div class="tp-block">
          <span class="tp-tag">區塊預覽</span>
          <div class="tp-inner-card">
            <span>區塊裏的卡片</span>
            <span class="tp-up">▲ 漲 1.50%</span>
            <span class="tp-down">▼ 跌 0.80%</span>
          </div>
        </div>
      </div>
    </div>

    <button class="btn btn-primary" style="margin-top: 24px;" @click="save">💾 儲存設定</button>
    <span v-if="saved" style="margin-left: 12px; color: var(--color-up);">✓ 已儲存</span>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { computed, ref } from 'vue'
import axios from 'axios'
import { useTheme } from '../composables/useTheme.js'

const { state, THEME_FIELDS, BUILT_IN_PRESETS, setField, applyPreset, resetDefault, addPreset, deletePreset } = useTheme()
const newPresetName = ref('')
const allPresets = computed(() => [...BUILT_IN_PRESETS, ...state.presets])

function saveAsPreset() {
  if (addPreset(newPresetName.value)) {
    newPresetName.value = ''
  } else {
    alert('請先輸入組合名稱')
  }
}

// <input type="color"> 只吃 #rrggbb；把值正規化，非 hex 時給合理預設
function toHex(value) {
  const v = String(value || '').trim()
  if (/^#[0-9a-fA-F]{6}$/.test(v)) return v
  if (/^#[0-9a-fA-F]{3}$/.test(v)) return '#' + v.slice(1).split('').map((c) => c + c).join('')
  return '#131b30'
}
function toPx(value) {
  const n = parseInt(String(value), 10)
  return Number.isFinite(n) ? n : 1
}

const reingesting = ref(false)
const reingestMsg = ref('')
async function reingestNow() {
  reingesting.value = true
  reingestMsg.value = ''
  try {
    const resp = await axios.post('/api/v1/cache/reingest')
    reingestMsg.value = resp.data?.success
      ? '✓ 已更新，回到關聯圖／類股輪動頁重新整理即可看到最新資料'
      : '✗ 更新失敗'
  } catch {
    reingestMsg.value = '✗ 更新失敗，請稍後再試'
  } finally {
    reingesting.value = false
  }
}

const finmindToken = ref('')
const lineToken = ref('')
const defaultPeriod = ref('1Y')
const defaultCapital = ref(1000000)
const notifications = ref({ price: true, signal: true, ai: true })
const saved = ref(false)

async function validateToken(type) {
  try {
    const resp = await axios.post('/api/v1/settings/validate-token', { token_type: type, token: finmindToken.value })
    alert(resp.data.data.valid ? '✅ Token 有效' : '❌ Token 無效')
  } catch {
    alert('❌ 驗證失敗')
  }
}

async function testLine() {
  try {
    await axios.post('/api/v1/notifications/line/test', { token: lineToken.value })
    alert('✅ 通知已發送')
  } catch {
    alert('❌ 發送失敗，請檢查 Token')
  }
}

async function save() {
  saved.value = true
  setTimeout(() => { saved.value = false }, 3000)
}
</script>

<style scoped>
.settings-page { max-width: 700px; }
.form-group { margin-top: 12px; }
.form-group label { display: block; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 4px; }
.form-input { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary); }
.input-row { display: flex; gap: 8px; }
.input-row .form-input { flex: 1; }
.checkbox-label { display: block; padding: 8px 0; cursor: pointer; }
.checkbox-label input { margin-right: 8px; }

.reingest-msg { margin-left: 12px; font-size: 0.85rem; color: var(--text-secondary); }

/* ===== 外觀主題自訂 ===== */
.theme-hint { font-size: 0.82rem; color: var(--text-muted); margin: 4px 0 16px; }

.preset-section { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.preset-label { font-size: 0.82rem; color: var(--text-secondary); padding-top: 7px; white-space: nowrap; }
.preset-list { display: flex; flex-wrap: wrap; gap: 8px; }
.preset-chip { display: inline-flex; align-items: stretch; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color); }
.preset-apply {
  padding: 6px 12px; border: none; cursor: pointer;
  background: var(--bg-elevated); color: var(--text-primary); font-size: 0.82rem;
}
.preset-apply:hover { background: var(--bg-hover); color: var(--accent-blue); }
.preset-del {
  padding: 0 8px; border: none; border-left: 1px solid var(--border-color); cursor: pointer;
  background: var(--bg-elevated); color: var(--text-muted); font-size: 0.72rem;
}
.preset-del:hover { color: var(--color-down); }

.preset-add { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.preset-add .form-input { flex: 1; min-width: 180px; }
.btn { padding: 8px 14px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-elevated); color: var(--text-primary); cursor: pointer; font-size: 0.85rem; }
.btn-primary { background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; }
.btn-ghost { background: transparent; }

.theme-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 20px; }
.theme-field { display: grid; gap: 6px; }
.theme-field label { font-size: 0.82rem; color: var(--text-secondary); }
.theme-control { display: flex; align-items: center; gap: 10px; }
.theme-control input[type="color"] {
  width: 42px; height: 32px; padding: 0; border: 1px solid var(--border-color);
  border-radius: 6px; background: transparent; cursor: pointer; flex-shrink: 0;
}
.theme-control input[type="range"] { flex: 1; }
.hex-input { flex: 1; font-family: var(--font-mono); font-size: 0.8rem; text-transform: uppercase; }
.width-val { font-family: var(--font-mono); font-size: 0.82rem; color: var(--text-secondary); min-width: 34px; }

.theme-preview { margin-top: 20px; }
.tp-block {
  position: relative;
  background: var(--bg-card);
  border: var(--block-border-width) solid var(--block-border-color);
  border-radius: var(--radius-lg); padding: 20px;
}
.tp-tag { font-size: 0.72rem; color: var(--text-muted); }
.tp-inner-card {
  margin-top: 10px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  background: var(--card-inner-bg);
  border: var(--card-inner-border-width) solid var(--card-inner-border-color);
  border-radius: var(--radius); padding: 16px; color: var(--text-secondary); font-size: 0.9rem;
}
.tp-up { color: var(--color-up); font-family: var(--font-mono); font-weight: 700; }
.tp-down { color: var(--color-down); font-family: var(--font-mono); font-weight: 700; }

@media (max-width: 420px) {
  .settings-page { max-width: 100%; padding: 0; }
  .input-row { flex-direction: column; }
  .theme-grid { grid-template-columns: 1fr; }
}
</style>
