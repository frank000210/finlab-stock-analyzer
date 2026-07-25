// @ts-check
const { test, expect } = require('@playwright/test')

// GG5：FF1 在 signal_rules/engine.py 加了 AST 靜態驗證，擋掉
// ().__class__.__bases__[0].__subclasses__() 這類逃出 exec() 限制
// builtins 沙箱的手法——但那次修復只用 live container curl 手動驗證過，
// repo 裡完全沒有留下任何自動化測試。沒有測試保護，未來如果有人「順手」
// 精簡 _FORBIDDEN_NAMES 或動到 dunder 屬性檢查，不會有任何測試失敗提醒。
// 這裡直接打真正的後端端點（不 mock），驗證：合法腳本仍可執行、逃逸手法
// 與 import 都會在真的 exec() 之前被擋下。

test('POST /api/v1/signal-rules/test 合法腳本正常執行', async ({ request }) => {
  const resp = await request.post('/api/v1/signal-rules/test', {
    data: {
      symbol: '2330',
      script: 'signal = "BUY" if rsi < 30 else "HOLD"\nconfidence = 0.8\nconditions = []\nreasoning = "rsi check"',
    },
  })
  expect(resp.status()).toBe(200)
  const body = await resp.json()
  expect(body.success).toBe(true)
  expect(['BUY', 'SELL', 'HOLD']).toContain(body.data.signal)
})

test('POST /api/v1/signal-rules/test 沙箱逃逸腳本被 AST 驗證擋下 (400)', async ({ request }) => {
  const resp = await request.post('/api/v1/signal-rules/test', {
    data: {
      symbol: '2330',
      script: 'x = ().__class__.__bases__[0].__subclasses__()\nsignal = "HOLD"',
    },
  })
  expect(resp.status()).toBe(400)
  const body = await resp.json()
  expect(body.detail).toContain('subclasses')
})

test('POST /api/v1/signal-rules/test import 陳述句被擋下 (400)', async ({ request }) => {
  const resp = await request.post('/api/v1/signal-rules/test', {
    data: {
      symbol: '2330',
      script: 'import os\nsignal = "HOLD"',
    },
  })
  expect(resp.status()).toBe(400)
  const body = await resp.json()
  expect(body.detail).toContain('import')
})

test('POST /api/v1/signal-rules/test getattr 繞過嘗試被擋下 (400)', async ({ request }) => {
  const resp = await request.post('/api/v1/signal-rules/test', {
    data: {
      symbol: '2330',
      script: 'signal = "HOLD"\nx = getattr((), "__class__")',
    },
  })
  expect(resp.status()).toBe(400)
  const body = await resp.json()
  expect(body.detail).toContain('getattr')
})
