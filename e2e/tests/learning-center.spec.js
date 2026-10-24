// @ts-check
const { test, expect } = require('@playwright/test')

// 學習中心（/learn）：教材渲染、測驗批改與補強回饋、本機帳號註冊與進度記錄、
// 程度檢測、AI 助教 UI。AI 助教的 LLM 回應用 route mock（不依賴外部 LLM 額度），
// 其餘都是真打後端；註冊與進度需要 MongoDB（本機 Docker 環境有）。

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

async function registerAndSeed(page, request) {
  const res = await request.post('/api/v1/course/auth/register', {
    data: { email: uniqueEmail(), password: 'e2e-password-123', name: 'E2E 學員' },
  })
  expect(res.ok()).toBeTruthy()
  const data = await res.json()
  await page.addInitScript((d) => {
    localStorage.setItem('admin_token', d.token)
    localStorage.setItem('admin_user', JSON.stringify({ email: d.email, name: d.name, avatar: '', is_admin: false, provider: 'local' }))
  }, data)
  return data
}

test('學習中心首頁列出各階段單元與登入卡片', async ({ page }) => {
  await page.goto('/learn')
  await expect(page.getByRole('heading', { name: /AI Agent 原理到 Claude Code 客製化/ })).toBeVisible()
  await expect(page.getByTestId('unit-card-u1')).toContainText('LLM 與 Prompt 基礎')
  await expect(page.getByTestId('unit-card-l10')).toBeVisible()
  await expect(page.getByTestId('course-auth')).toBeVisible()
})

test('單元頁渲染教材、目錄與 lab；答錯顯示解析與回到段落', async ({ page }) => {
  await page.goto('/learn/u/u2')
  const content = page.getByTestId('unit-content')
  await expect(content.getByRole('heading', { name: '評估順序：deny → ask → allow' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: '本單元目錄' })).toContainText('Permission modes')
  await expect(page.getByTestId('unit-lab')).toContainText('第一個 MCP server')

  // 每題都選第一個選項（題庫刻意讓正解不全是第一項），送出後一定有答錯的題目
  const quiz = page.getByTestId('course-quiz')
  const groups = quiz.getByRole('radiogroup')
  const count = await groups.count()
  for (let i = 0; i < count; i++) await groups.nth(i).getByRole('radio').first().check()
  await quiz.getByRole('button', { name: '送出答案' }).click()
  await expect(page.getByTestId('quiz-result')).toContainText('登入後才會記錄成績')
  const back = quiz.getByRole('button', { name: /^回到「/ }).first()
  await expect(back).toBeVisible()
})

test('lab 起始檔可以下載成 zip', async ({ request }) => {
  const res = await request.get('/api/v1/course/units/u6/lab.zip')
  expect(res.status()).toBe(200)
  expect(res.headers()['content-type']).toContain('application/zip')
  const body = await res.body()
  expect(body.subarray(0, 2).toString()).toBe('PK')
})

test('未登入不能使用進度、助教與管理端點', async ({ request }) => {
  expect((await request.get('/api/v1/course/me')).status()).toBe(401)
  expect((await request.post('/api/v1/course/tutor', { data: { unit_id: 'u1', question: 'hi' } })).status()).toBe(401)
  expect((await request.get('/api/v1/course/admin/projects', { headers: { 'X-Admin-Token': 'bad' } })).status()).toBe(401)
})

test('題目答案不會送到前端', async ({ request }) => {
  const unit = await (await request.get('/api/v1/course/units/u3')).json()
  for (const q of unit.quiz.questions) {
    expect(q).not.toHaveProperty('answer')
    expect(q).not.toHaveProperty('explain')
  }
})

test('註冊登入後，測驗成績寫入進度並顯示在首頁', async ({ page, request }) => {
  await registerAndSeed(page, request)
  await page.goto('/learn/u/l7')
  const quiz = page.getByTestId('course-quiz')
  const groups = quiz.getByRole('radiogroup')
  const count = await groups.count()
  for (let i = 0; i < count; i++) await groups.nth(i).getByRole('radio').nth(1).check()
  await quiz.getByRole('button', { name: '送出答案' }).click()
  await expect(page.getByTestId('quiz-result')).toContainText('已記錄進度')

  await page.goto('/learn')
  await expect(page.getByTestId('course-progress')).toContainText('必修測驗通過')
  await expect(page.getByTestId('unit-card-l7')).toContainText('進行中')
})

test('重複註冊同一個 Email 回 409，錯誤密碼回 401', async ({ request }) => {
  const email = uniqueEmail()
  const payload = { email, password: 'e2e-password-123', name: 'dup' }
  expect((await request.post('/api/v1/course/auth/register', { data: payload })).status()).toBe(200)
  expect((await request.post('/api/v1/course/auth/register', { data: payload })).status()).toBe(409)
  expect((await request.post('/api/v1/course/auth/login', { data: { email, password: 'wrong-password' } })).status()).toBe(401)
  expect((await request.post('/api/v1/course/auth/login', { data: { email, password: 'e2e-password-123' } })).status()).toBe(200)
})

test('程度檢測給出建議起點', async ({ page }) => {
  await page.goto('/learn/placement')
  const quiz = page.getByTestId('course-quiz')
  const groups = quiz.getByRole('radiogroup')
  await expect(groups.first()).toBeVisible()
  const count = await groups.count()
  for (let i = 0; i < count; i++) await groups.nth(i).getByRole('radio').first().check()
  await quiz.getByRole('button', { name: '送出答案' }).click()
  await expect(page.getByTestId('placement-result')).toContainText('建議從')
})

test('AI 助教送出問題並渲染回答（LLM 回應以 mock 取代）', async ({ page, request }) => {
  await registerAndSeed(page, request)
  await page.route('**/api/v1/course/catalog', async (route) => {
    const res = await route.fetch()
    const json = await res.json()
    await route.fulfill({ response: res, json: { ...json, tutor_available: true } })
  })
  await page.route('**/api/v1/course/tutor', route => route.fulfill({
    json: { answer: '**結論**：用 hook 才是強制。\n\n<script>window.__xss = 1</script>' },
  }))
  await page.goto('/learn/u/u6')
  await page.getByTestId('tutor-open').click()
  const tutor = page.getByTestId('course-tutor')
  await tutor.getByRole('textbox').fill('hook 跟 CLAUDE.md 差在哪？')
  await tutor.getByRole('button', { name: '送出' }).click()
  await expect(tutor.locator('strong', { hasText: '結論' })).toBeVisible()
  // markdown 渲染關掉原生 HTML：script 只能以文字出現，不能被執行
  expect(await page.evaluate(() => window.__xss)).toBeUndefined()
})

test('不存在的證書顯示查無資料', async ({ page }) => {
  await page.goto('/learn/cert/doesnotexist')
  await expect(page.getByText('查無此證書')).toBeVisible()
})
