// Y5：CSV 匯出共用工具。原本只有交易日誌（JournalView）有匯出功能，抽出
// 通用版本讓分析頁/回測頁/類股輪動頁/投組風險頁也能匯出各自的表格資料。
export function csvCell(v) {
  const s = String(v ?? '')
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
}

// columns: string[]；rows: 二維陣列（每列的值依 columns 順序排好，未跳脫）
export function downloadCsv(filename, columns, rows) {
  if (!rows.length) return
  const lines = rows.map(row => row.map(csvCell).join(','))
  // 開頭 BOM 讓 Excel 開啟 UTF-8 中文不會變亂碼，跟既有 JournalView 匯出慣例一致
  const csv = '﻿' + [columns.join(','), ...lines].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function timestampedFilename(prefix) {
  return `${prefix}-${new Date().toISOString().slice(0, 10)}.csv`
}
