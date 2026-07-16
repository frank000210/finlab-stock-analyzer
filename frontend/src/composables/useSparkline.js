import { computed, unref } from 'vue'

// R7：把一組數值正規化成 SVG <polyline> 的 points 字串，min/max 依資料本身
// 動態決定範圍——這段「找 min/max、依範圍換算 x/y 座標」的邏輯原本在
// AnalysisView（千張大戶走勢）、SocialBuzzView（熱度走勢）、JournalView
// （權益曲線）各自重寫一次，抽成共用 composable。
//
// includeValue：選填，強制把某個值也納入 min/max 範圍（例如權益曲線要讓
// 0 這條零線永遠落在圖表範圍內，不會因為全部都是正值/負值而被擠出畫面）。
// 回傳的 toY 是換算函式，供呼叫端自己畫零線之類的額外參考線。
export function useSparkline(valuesRef, { width = 100, height = 24, includeValue = null } = {}) {
  const layout = computed(() => {
    const values = unref(valuesRef) || []
    if (values.length < 2) {
      return { points: '', toY: () => height / 2 }
    }
    let min = Math.min(...values)
    let max = Math.max(...values)
    if (includeValue != null) {
      min = Math.min(min, includeValue)
      max = Math.max(max, includeValue)
    }
    const range = (max - min) || 1
    const toY = (v) => height - ((v - min) / range) * height
    const points = values
      .map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${toY(v).toFixed(1)}`)
      .join(' ')
    return { points, toY }
  })

  return {
    points: computed(() => layout.value.points),
    toY: computed(() => layout.value.toY),
  }
}
