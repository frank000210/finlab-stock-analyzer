// 事件研究台的「我的決策紀錄」。跟交易日誌一樣只存在使用者自己的瀏覽器
// （localStorage），伺服器不保存任何個人的部位或決策。
//
// 用途不是記帳，而是「事前把話說死」：動作之前先寫下理由、最多願意賠多少、
// 什麼情況算自己看錯、哪一天回頭檢討。事後才有東西可以對照，不會硬凹。

const KEY = 'finlab_event_decisions_v1'

export const DECISION_ACTIONS = [
  { value: 'none', label: '不動作' },
  { value: 'watch', label: '觀察，等訊號出現再說' },
  { value: 'reduce', label: '減碼' },
  { value: 'add', label: '加碼' },
  { value: 'hedge', label: '避險' },
]

export function actionLabel(value) {
  return DECISION_ACTIONS.find(a => a.value === value)?.label || value || ''
}

// 用本機時區的今天（不是 UTC），台灣早上 8 點前才不會算成前一天
export function todayIso(now = new Date()) {
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${m}-${d}`
}

export function loadDecisions() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(raw) ? raw.filter(r => r && typeof r === 'object' && r.id) : []
  } catch {
    return []
  }
}

function persist(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
    return true
  } catch {
    // 無痕模式或容量滿：存不進去就回報失敗，讓畫面提示使用者
    return false
  }
}

export function decisionsFor(briefId) {
  return loadDecisions()
    .filter(r => r.brief_id === briefId)
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
}

export function addDecision(rec) {
  const list = loadDecisions()
  const item = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    created_at: new Date().toISOString(),
    brief_id: String(rec.brief_id || ''),
    brief_title: String(rec.brief_title || ''),
    action: String(rec.action || 'none'),
    thesis: String(rec.thesis || '').trim(),
    max_loss_pct: rec.max_loss_pct === '' || rec.max_loss_pct == null ? null : Number(rec.max_loss_pct),
    invalidation: String(rec.invalidation || '').trim(),
    review_date: String(rec.review_date || ''),
    reviewed: false,
    review_note: '',
    reviewed_at: null,
  }
  list.push(item)
  return persist(list) ? item : null
}

export function reviewDecision(id, note) {
  const list = loadDecisions()
  const item = list.find(r => r.id === id)
  if (!item) return false
  item.reviewed = true
  item.review_note = String(note || '').trim()
  item.reviewed_at = new Date().toISOString()
  return persist(list)
}

export function removeDecision(id) {
  return persist(loadDecisions().filter(r => r.id !== id))
}

// 到了檢討日、還沒檢討的紀錄
export function dueDecisions(today = todayIso()) {
  return loadDecisions().filter(r => !r.reviewed && r.review_date && r.review_date <= today)
}
