// W3：財報矛盾偵測——純規則、不呼叫 LLM，頁面載入時自動顯示（免成本、免等待）。
// 靈感來自國巨(2327)案例：營收 YoY +36%、毛利率連五季創高，但 EPS 從
// 11~13元崩到 3~4元——這種「營收/毛利率在漲、EPS 在跌」的組合本身就值得
// 特別標出來，不需要 AI 才能發現，純算術就能抓。
//
// 只負責「指出矛盾＋列出待查證方向」，不猜測原因、不給投資建議——原因可能
// 是業外認損、一次性費用、股本膨脹等，網站的既有數據無法判斷，留給使用者
// 自己查財報附註。

function avg(nums) {
  const valid = nums.filter(n => n != null && Number.isFinite(n))
  return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null
}

/**
 * @param {Array<{quarter:string, eps:number}>} epsRows 升冪排序
 * @param {Array<{month:string, yoy:number}>} revenueRows 升冪排序
 * @param {Array<{quarter:string, gross_margin:number, operating_margin:number}>} marginRows 升冪排序
 * @returns {Array<{id:string, tone:'warn'|'info', text:string}>}
 */
export function detectFundamentalFlags(epsRows, revenueRows, marginRows) {
  const flags = []
  const eps = (epsRows || []).filter(r => r.eps != null)
  const margins = (marginRows || []).filter(r => r.gross_margin != null)
  const recentYoy = (revenueRows || []).filter(r => r.yoy != null).slice(-3).map(r => r.yoy)
  const revenueYoyAvg = avg(recentYoy)

  // 1. 營收成長但 EPS 年減——用「同季度去年同期」比較，避開淡旺季雜訊
  if (eps.length >= 5 && revenueYoyAvg != null && revenueYoyAvg > 5) {
    const last = eps[eps.length - 1]
    const yearAgoIdx = eps.findIndex(r => r.quarter === `${Number(last.quarter.slice(0, 4)) - 1}${last.quarter.slice(4)}`)
    if (yearAgoIdx >= 0) {
      const yearAgo = eps[yearAgoIdx]
      if (yearAgo.eps > 0 && last.eps < yearAgo.eps * 0.7) {
        const dropPct = Math.round((1 - last.eps / yearAgo.eps) * 100)
        flags.push({
          id: 'revenue_eps_divergence',
          tone: 'warn',
          text: `營收近三月均年增 ${revenueYoyAvg.toFixed(1)}%，但 EPS（${last.quarter}）較去年同期衰退 ${dropPct}%——營收與獲利明顯脫鉤，建議查證財報附註（業外損益／一次性費用／股本變化）。`,
        })
      }
    }
  }

  // 2. 毛利率連續上升但 EPS 沒跟上（用最近 4 季線性趨勢粗判）
  if (margins.length >= 4 && eps.length >= 4) {
    const recentMargins = margins.slice(-4)
    const marginRising = recentMargins.every((r, i) => i === 0 || r.gross_margin >= recentMargins[i - 1].gross_margin - 0.3)
    const marginUpTotal = recentMargins[recentMargins.length - 1].gross_margin - recentMargins[0].gross_margin
    const recentEps = eps.slice(-4)
    const epsFlat = recentEps[recentEps.length - 1].eps <= recentEps[0].eps * 1.1
    if (marginRising && marginUpTotal > 1.5 && epsFlat) {
      flags.push({
        id: 'margin_up_eps_flat',
        tone: 'warn',
        text: `毛利率近四季由 ${recentMargins[0].gross_margin.toFixed(1)}% 升至 ${recentMargins[recentMargins.length - 1].gross_margin.toFixed(1)}%，本業獲利能力增強，但 EPS 未見同步成長——可能有費用認列時間差或業外干擾，建議追蹤下一季能否反映。`,
      })
    }
  }

  // 3. 營收成長但毛利率走低（可能削價競爭/成本上升）
  if (margins.length >= 4 && revenueYoyAvg != null && revenueYoyAvg > 10) {
    const recentMargins = margins.slice(-4)
    const marginDownTotal = recentMargins[0].gross_margin - recentMargins[recentMargins.length - 1].gross_margin
    if (marginDownTotal > 2) {
      flags.push({
        id: 'margin_compression',
        tone: 'info',
        text: `營收近三月均年增 ${revenueYoyAvg.toFixed(1)}%，但毛利率近四季由 ${recentMargins[0].gross_margin.toFixed(1)}% 降至 ${recentMargins[recentMargins.length - 1].gross_margin.toFixed(1)}%——營收成長可能伴隨降價或成本上升，非單純利多。`,
      })
    }
  }

  // 4. 由盈轉虧或虧轉盈（近兩季變號）
  if (eps.length >= 2) {
    const [prev, last] = eps.slice(-2)
    if (prev.eps > 0 && last.eps < 0) {
      flags.push({ id: 'turned_loss', tone: 'warn', text: `${last.quarter} 由盈轉虧（EPS ${last.eps}），為近兩季內結構性轉變，建議優先查證原因。` })
    } else if (prev.eps < 0 && last.eps > 0) {
      flags.push({ id: 'turned_profit', tone: 'info', text: `${last.quarter} 由虧轉盈（EPS ${last.eps}），留意是否為業外一次性收益墊高。` })
    }
  }

  return flags
}
