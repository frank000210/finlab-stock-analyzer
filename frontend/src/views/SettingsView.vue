<template>
  <div class="settings-page">
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

    <button class="btn btn-primary" style="margin-top: 24px;" @click="save">💾 儲存設定</button>
    <span v-if="saved" style="margin-left: 12px; color: var(--color-up);">✓ 已儲存</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const finmindToken = ref('')
const lineToken = ref('')
const defaultPeriod = ref('1Y')
const defaultCapital = ref(1000000)
const notifications = ref({ price: true, signal: true, ai: true })
const saved = ref(false)

async function validateToken(type) {
  try {
    const resp = await axios.post(`/api/v1/settings/validate-token?token_type=${type}&token=${finmindToken.value}`)
    alert(resp.data.data.valid ? '✅ Token 有效' : '❌ Token 無效')
  } catch {
    alert('❌ 驗證失敗')
  }
}

async function testLine() {
  try {
    await axios.post(`/api/v1/notifications/line/test?token=${lineToken.value}`)
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

@media (max-width: 420px) {
  .settings-page { max-width: 100%; padding: 0; }
  .input-row { flex-direction: column; }
}
</style>
