// @ts-check
const { test, expect } = require('@playwright/test')

// A3 交易日誌 CSV 匯入：localStorage 是日誌唯一儲存位置，匯出 CSV 因此也是
// 備份手段——但少了匯入就還原不了。匯入吃匯出的同一種格式，重複列自動略過。
const CSV_HEADER = 'symbol,side,entry,stop,target,lots,tag,openDate,status,exit,exitDate,R,pnl'
const CSV_BODY = [
  '2330,long,100,90,130,1,突破,2026-06-01,closed,120,2026-06-10,2.000,20000',
  '2454,short,200,210,,2,"拉回,測試",2026-06-05,closed,180,2026-06-12,2.000,40000',
  '2317,long,50,45,,1,,2026-07-01,open,,,,',
].join('\n')

test('交易日誌 匯入 CSV 還原紀錄，重複匯入自動略過 (A3)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  const csv = '﻿' + CSV_HEADER + '\n' + CSV_BODY
  await page.setInputFiles('input[type="file"]', {
    name: 'trade-journal.csv', mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf-8'),
  })

  await expect(page.locator('.csv-msg')).toContainText('已匯入 3 筆')
  // 已平倉 2 筆進統計、進行中 1 筆
  await expect(page.locator('.stat-cards')).toContainText('2')
  await expect(page.getByRole('heading', { name: /進行中（1）/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: /已平倉（2）/ })).toBeVisible()
  // 帶引號逗號的 tag 有正確解析
  await expect(page.locator('.analytics-grid')).toContainText('拉回,測試')

  // 同一份再匯一次 → 全部視為重複
  await page.setInputFiles('input[type="file"]', {
    name: 'trade-journal.csv', mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf-8'),
  })
  await expect(page.locator('.csv-msg')).toContainText('已匯入 0 筆、略過重複 3 筆')
})

test('交易日誌 匯入缺少必要欄位的 CSV 時報錯不寫入 (A3)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  const bad = 'symbol,entry\n2330,100'
  await page.setInputFiles('input[type="file"]', {
    name: 'bad.csv', mimeType: 'text/csv', buffer: Buffer.from(bad, 'utf-8'),
  })
  await expect(page.locator('.csv-msg')).toContainText('缺少欄位')
  const stored = await page.evaluate(() => localStorage.getItem('finlab_trade_journal'))
  expect(stored).toBeNull()
})

// F5：CSV 匯入沒有檔案大小上限的話，誤選一個大檔會把整個內容讀進記憶體
// 卡住畫面。超過 5MB 直接擋掉，不嘗試讀取。
test('交易日誌 匯入超過大小上限的 CSV 時直接拒絕不讀取 (F5)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.removeItem('finlab_trade_journal'))
  await page.reload()

  const oversized = Buffer.alloc(6 * 1024 * 1024, 'a')
  await page.setInputFiles('input[type="file"]', {
    name: 'huge.csv', mimeType: 'text/csv', buffer: oversized,
  })
  await expect(page.locator('.csv-msg')).toContainText('超過上限')
  const stored = await page.evaluate(() => localStorage.getItem('finlab_trade_journal'))
  expect(stored).toBeNull()
})
