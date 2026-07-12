// @ts-check
const { test, expect } = require('@playwright/test')

// F1: 交易日誌的日期戳過去用 new Date().toISOString().slice(0,10)（UTC 日曆
// 日），台灣時間（UTC+8）凌晨到早上 8 點之間記錄/平倉的交易會被蓋成「昨
// 天」——這個 app 也支援美股，半夜盯盤後平倉正好踩到，導致單日虧損熔斷、
// 過度交易偵測、當日交易數全部算錯天。固定時鐘到「UTC 還是前一天、但台北
// 已經是隔天」的時刻，驗證日期戳採用台北本地日曆日，不是 UTC。
test.use({ timezoneId: 'Asia/Taipei' })

// UTC 2026-07-11T20:00:00Z = 台北 2026-07-12T04:00:00+08:00
const CROSS_MIDNIGHT_UTC = '2026-07-11T20:00:00Z'
const EXPECTED_LOCAL_DATE = '2026-07-12'

test('交易日誌 新增交易的開倉日期使用台北本地日曆日，不是 UTC (F1)', async ({ page }) => {
  await page.clock.install({ time: new Date(CROSS_MIDNIGHT_UTC) })
  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('100')
  await page.getByPlaceholder('停損價').fill('90')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByRole('button', { name: '加入' }).click()

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal).toHaveLength(1)
  expect(journal[0].openDate).toBe(EXPECTED_LOCAL_DATE)
})

test('交易日誌 平倉日期使用台北本地日曆日，不是 UTC (F1)', async ({ page }) => {
  await page.clock.install({ time: new Date(CROSS_MIDNIGHT_UTC) })
  await page.goto('/journal')
  await page.evaluate(() => {
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 't1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 1, tag: '', openDate: '2026-07-11', status: 'open', exit: null, exitDate: null,
    }]))
  })
  await page.reload()

  await page.locator('.j-table input[type="number"]').first().fill('110')
  await page.getByRole('button', { name: '平倉', exact: true }).click()

  const journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal[0].exitDate).toBe(EXPECTED_LOCAL_DATE)
})

test('風控監控 當日交易數以台北本地日曆日判定，不是 UTC (F1)', async ({ page }) => {
  await page.clock.install({ time: new Date(CROSS_MIDNIGHT_UTC) })
  await page.goto('/risk-monitor')
  await page.evaluate((expectedLocalDate) => {
    // openDate 已經是「今天」的台北日期（04:00 台北時間新記的單），但 UTC
    // 當下還是前一天——舊的 UTC 版當日交易數會漏算這筆。
    localStorage.setItem('finlab_trade_journal', JSON.stringify([{
      id: 't1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null,
      lots: 1, tag: '', openDate: expectedLocalDate, status: 'open', exit: null, exitDate: null,
    }]))
  }, EXPECTED_LOCAL_DATE)
  await page.reload()

  await expect(page.locator('.trade-counter strong')).toHaveText('1')
})
