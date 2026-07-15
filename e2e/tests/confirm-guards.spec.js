// @ts-check
const { test, expect } = require('@playwright/test')

// P1：破壞性操作（刪除/清空）加上 confirm() 二次確認，避免誤按就無法復原
// （交易日誌/投組風險頁都是把 localStorage 當唯一儲存位置，清掉救不回來）。

test('交易日誌 刪除單筆交易需確認，取消不刪除、確認才刪除 (P1)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    { id: 'p1-1', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'open', exit: null, exitDate: null },
  ])))
  await page.reload()

  const row = page.locator('.j-table tbody tr', { hasText: '2330' })
  await expect(row).toBeVisible()

  page.once('dialog', (d) => d.dismiss())
  await row.locator('.del').click()
  await expect(row).toBeVisible() // 取消後仍在

  page.once('dialog', (d) => d.accept())
  await row.locator('.del').click()
  await expect(page.locator('.j-table tbody tr', { hasText: '2330' })).toHaveCount(0)
})

test('交易日誌 清空全部需確認，取消不清空、確認才清空 (P1)', async ({ page }) => {
  await page.goto('/journal')
  await page.evaluate(() => localStorage.setItem('finlab_trade_journal', JSON.stringify([
    { id: 'p1-2', symbol: '2330', name: '台積電', side: 'long', entry: 100, stop: 90, target: null, lots: 1, tag: '', openDate: '2026-07-01', status: 'closed', exit: 110, exitDate: '2026-07-05' },
  ])))
  await page.reload()

  await expect(page.getByRole('button', { name: '清空全部' })).toBeVisible()

  page.once('dialog', (d) => d.dismiss())
  await page.getByRole('button', { name: '清空全部' }).click()
  let journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal.length).toBe(1)

  page.once('dialog', (d) => d.accept())
  await page.getByRole('button', { name: '清空全部' }).click()
  journal = await page.evaluate(() => JSON.parse(localStorage.getItem('finlab_trade_journal') || '[]'))
  expect(journal.length).toBe(0)
})

test('投組風險 刪除部位與清空都需確認 (P1)', async ({ page }) => {
  await page.goto('/portfolio-heat')
  await page.evaluate(() => localStorage.clear())
  await page.reload()

  await page.getByPlaceholder('代碼 2330').fill('2330')
  await page.getByPlaceholder('進場價').fill('2440')
  await page.getByPlaceholder('停損價').fill('2310')
  await page.getByPlaceholder('張數').fill('1')
  await page.getByRole('button', { name: '加入' }).click()
  await expect(page.locator('.pos-table tbody tr')).toHaveCount(1)

  page.once('dialog', (d) => d.dismiss())
  await page.locator('.pos-table .del').click()
  await expect(page.locator('.pos-table tbody tr')).toHaveCount(1) // 取消後仍在

  page.once('dialog', (d) => d.dismiss())
  await page.getByRole('button', { name: '清空' }).click()
  await expect(page.locator('.pos-table tbody tr')).toHaveCount(1) // 取消後仍在

  page.once('dialog', (d) => d.accept())
  await page.locator('.pos-table .del').click()
  await expect(page.locator('.pos-table tbody tr')).toHaveCount(0)
})
