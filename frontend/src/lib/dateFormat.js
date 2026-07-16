// R8：把 TDCC 集保股權分散表這類「YYYYMMDD」格式的日期字串轉成 YYYY/MM/DD
// 顯示用——AnalysisView.vue 跟 ChipAnalysisView.vue 原本各自重寫一份一模
// 一樣的邏輯，抽成共用工具。
export function formatYyyymmdd(d) {
  const s = String(d || '')
  return s.length === 8 ? `${s.slice(0, 4)}/${s.slice(4, 6)}/${s.slice(6, 8)}` : s
}
