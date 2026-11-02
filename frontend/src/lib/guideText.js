// 建站教學頁（/build-guide）內文的極簡標記：**粗體**、`程式碼`、[文字](https://…)。
// 先跳脫 HTML 再轉標記；內容全是程式碼裡寫死的字串，不吃任何使用者輸入，所以 v-html 安全。
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }

export function richText(s) {
  return String(s ?? '')
    .replace(/[&<>"]/g, c => ESC[c])
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
}
