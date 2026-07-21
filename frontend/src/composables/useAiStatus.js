// X3：checkAiConfigured() 原本在 AnalysisView/SocialBuzzView/JournalView/
// ScreenerView/NewsCheckerView 各寫一份一模一樣的 fetch，抽成共用 composable。
import { ref } from 'vue'
import { fetchWithRetry } from '../lib/apiFetch'

export function useAiStatus() {
  const aiConfigured = ref(false)

  async function checkAiConfigured() {
    try {
      const res = await fetchWithRetry('/api/v1/stocks/ai/status')
      const json = await res.json()
      aiConfigured.value = Boolean(json?.data?.configured)
    } catch {
      aiConfigured.value = false
    }
  }

  return { aiConfigured, checkAiConfigured }
}
