// 學習中心 API 包裝：統一帶上登入 token、把錯誤訊息整理成一句中文。
import { useAuthStore } from '../stores/auth.js'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export class CourseApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function courseFetch(path, { method = 'GET', body } = {}) {
  const auth = useAuthStore()
  const headers = { ...auth.getAuthHeaders() }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let resp
  try {
    resp = await fetch(`${API_BASE}/api/v1/course${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new CourseApiError('網路連線失敗，請稍後再試', 0)
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    // token 過期：清掉登入狀態，讓畫面回到登入卡片
    if (resp.status === 401 && auth.isLoggedIn) auth.logout()
    const detail = Array.isArray(data.detail) ? '輸入格式不正確' : data.detail
    throw new CourseApiError(detail || `請求失敗（${resp.status}）`, resp.status)
  }
  return data
}
