// X4：把 LLM 回傳的純文字（含 **粗體** 與換行）渲染成 HTML。原本
// AnalysisView 跟 SocialBuzzView 各寫一份幾乎一樣的邏輯，JournalView 的
// AI 複盤區塊甚至完全沒套用（粗體符號直接顯示成 **文字**），三個地方觀感
// 不一致，抽成共用函式。
//
// 必須先轉義 HTML 特殊字元再處理 markdown 標記——直接把 LLM 輸出丟進
// v-html 等於開一個 XSS 破口，因為 LLM 輸出的內容我們不能完全信任其
// 不含 <script> 之類的字串（即使目前的 prompt 沒有誘因產生，防禦要在
// 渲染層做，不能只靠信任上游行為良好）。
export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

export function renderAiMarkdown(raw) {
  return escapeHtml(raw || '')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br />')
}
