// X9：AI 產生的文字（個股摘要/輿情摘要/複盤/日報導讀）都沒有複製按鈕，
// 使用者想存檔或分享時只能手動選字。抽成共用 composable，跟既有
// AnalysisView 的 copyAiPrompt 是同一種「複製＋顯示已複製提示」模式。
import { ref } from 'vue'

export function useClipboard(resetMs = 2500) {
  const copied = ref(false)

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text)
      copied.value = true
      setTimeout(() => { copied.value = false }, resetMs)
      return true
    } catch {
      return false
    }
  }

  return { copied, copy }
}
