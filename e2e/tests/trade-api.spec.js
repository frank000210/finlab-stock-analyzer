// @ts-check
const { test, expect } = require('@playwright/test')
const { getAdminToken } = require('../helpers/admin-token')

// HH10：trade.py 的 GET /pending、POST /approve 是真實端點，會動到
// TradeApprovalService 記憶體狀態。RR1-RR3 hardened them to require admin auth.
//
// TradeApprovalService 沒有「手動建立一筆假交易」的端點——PENDING 交易
// 完全由 sync_from_signals() 依當下即時訊號（信心度 > 0.7 的 BUY/SELL）
// 自動產生，是否存在取決於當下真實市場資料，測試端無法保證一定有。這裡
// 對「一定為真」的部分（回應格式、對不存在 task_id 核准會 404）斷言，
// 剛好遇到有真實 PENDING 交易時才額外驗證核准流程本身會生效。

test('GET /api/v1/trade/pending 對真實後端回傳正確格式', async ({ request }) => {
  const token = await getAdminToken(request)
  const resp = await request.get('/api/v1/trade/pending?status=ALL', {
    headers: { 'X-Admin-Token': token },
  })
  expect(resp.status()).toBe(200)
  const body = await resp.json()
  expect(body.success).toBe(true)
  expect(Array.isArray(body.data.items)).toBe(true)
})

test('POST /api/v1/trade/approve 對不存在的 task_id 回傳 404', async ({ request }) => {
  const token = await getAdminToken(request)
  const resp = await request.post('/api/v1/trade/approve', {
    headers: { 'X-Admin-Token': token },
    data: { task_id: 'nonexistent-task-id-e2e-test', action: 'APPROVE' },
  })
  expect(resp.status()).toBe(404)
})

test('POST /api/v1/trade/approve 對真實存在的 PENDING 交易生效（若當下有資料）', async ({ request }) => {
  const token = await getAdminToken(request)
  const listResp = await request.get('/api/v1/trade/pending?status=PENDING', {
    headers: { 'X-Admin-Token': token },
  })
  const items = (await listResp.json()).data.items
  test.skip(items.length === 0, '目前沒有真實 PENDING 交易可測（取決於即時訊號），跳過')

  const target = items[0]
  const approveResp = await request.post('/api/v1/trade/approve', {
    headers: { 'X-Admin-Token': token },
    data: { task_id: target.task_id, action: 'REJECT' },
  })
  expect(approveResp.status()).toBe(200)
  const approveBody = await approveResp.json()
  expect(approveBody.success).toBe(true)
  expect(approveBody.data.status).toBe('REJECTED')
})
