// @ts-check
const { test, expect } = require('@playwright/test')

// BB：回測頁「自訂條件模式」——買賣條件用簡化版運算式語言描述（類似簡化版
// Pine Script），可以自己寫也可以用 AI 把白話描述翻譯成運算式。AI 生成的
// 端點這裡用 mock（不打真的 LLM），跟本站其他 AI 功能測試的慣例一致；
// 語法驗證/執行回測則走真正的後端 parser/evaluator + 真實股價資料。

test('自訂條件模式：預設運算式可直接執行回測並顯示績效', async ({ page }) => {
  await page.goto('/stocks/2330/backtest')
  await page.getByText('自訂條件模式').click()

  const buyExpr = page.locator('textarea.mono').first()
  const sellExpr = page.locator('textarea.mono').nth(1)
  await expect(buyExpr).toHaveValue('RSI(14) < 30')
  await expect(sellExpr).toHaveValue('RSI(14) > 70')

  const runBtn = page.getByRole('button', { name: /執行回測/ })
  await expect(runBtn).toBeEnabled()
  await runBtn.click()

  await expect(page.locator('.metric-card .value').first()).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.chart-container')).toBeVisible()
})

test('自訂條件模式：語法錯誤的運算式離開欄位時顯示錯誤訊息', async ({ page }) => {
  await page.goto('/stocks/2330/backtest')
  await page.getByText('自訂條件模式').click()

  const buyExpr = page.locator('textarea.mono').first()
  await buyExpr.fill('RSI(14) AND MA(5)') // 兩邊都是裸指標，沒有比較符號——語法上不合法
  await buyExpr.blur()

  await expect(page.locator('.error-text')).toContainText('比較式')
})

test('自訂條件模式：AI 生成條件會先驗證過才填入欄位', async ({ page }) => {
  await page.route('**/api/v1/backtest/generate-expression', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          buy_expr: 'MA(5) CROSSES_ABOVE MA(20)',
          sell_expr: 'MA(5) CROSSES_BELOW MA(20)',
          description: '5日均線黃金交叉買進，死亡交叉賣出',
        },
      }),
    })
  })

  await page.goto('/stocks/2330/backtest')
  await page.getByText('自訂條件模式').click()

  const aiInput = page.getByPlaceholder(/RSI 低於 30/)
  await aiInput.fill('5日均線黃金交叉買，死亡交叉賣')
  await page.getByRole('button', { name: /AI 生成條件/ }).click()

  const buyExpr = page.locator('textarea.mono').first()
  const sellExpr = page.locator('textarea.mono').nth(1)
  await expect(buyExpr).toHaveValue('MA(5) CROSSES_ABOVE MA(20)', { timeout: 10_000 })
  await expect(sellExpr).toHaveValue('MA(5) CROSSES_BELOW MA(20)')
  await expect(page.getByText('AI 理解：5日均線黃金交叉買進，死亡交叉賣出')).toBeVisible()
})

test('自訂條件模式：AI 生成失敗時顯示明確錯誤，不會把破損內容填入欄位', async ({ page }) => {
  await page.route('**/api/v1/backtest/generate-expression', async (route) => {
    await route.fulfill({
      status: 422, contentType: 'application/json',
      body: JSON.stringify({ detail: 'AI 沒有生成有效的買賣條件，請換個描述方式再試一次。' }),
    })
  })

  await page.goto('/stocks/2330/backtest')
  await page.getByText('自訂條件模式').click()

  const buyExprBefore = await page.locator('textarea.mono').first().inputValue()
  const aiInput = page.getByPlaceholder(/RSI 低於 30/)
  await aiInput.fill('一個很奇怪、很難翻譯的描述')
  await page.getByRole('button', { name: /AI 生成條件/ }).click()

  await expect(page.getByText('AI 沒有生成有效的買賣條件')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('textarea.mono').first()).toHaveValue(buyExprBefore) // 欄位維持原樣，沒被破損內容覆蓋
})

test('自訂條件模式：跟策略比較/參數掃描模式互斥', async ({ page }) => {
  await page.goto('/stocks/2330/backtest')
  const customToggle = page.getByText('自訂條件模式')
  const compareToggle = page.getByText('策略並列比較模式')

  await compareToggle.click()
  await expect(page.locator('.compare-strategy-list')).toBeVisible()

  await customToggle.click()
  await expect(page.locator('.compare-strategy-list')).toHaveCount(0)
  await expect(page.locator('textarea.mono')).toHaveCount(2)
})
