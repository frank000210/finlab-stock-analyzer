// 技術指標（純函式）。急跌與反彈的走勢圖用：後端只給看盤價日線，指標由前端用同一份資料即時算，
// 這樣勾選均線、縮放範圍都不用再打 API。
// 輸入是等長的數字陣列，輸出也等長；暖機期不足的位置是 null（不是 0，圖上才不會畫出假的線）。

/** 簡單移動平均：第 n 根起才有值。 */
export function sma(values, n) {
  const out = new Array(values.length).fill(null)
  if (!(n >= 1)) return out
  let sum = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    if (i >= n) sum -= values[i - n]
    if (i >= n - 1) out[i] = sum / n
  }
  return out
}

/**
 * KD（預設 9,3,3，台股慣例）與看盤軟體常見的 J：
 *   RSV = (收盤 − 近 n 日最低) ÷ (近 n 日最高 − 近 n 日最低) × 100（區間為 0 時當 50）
 *   K = ⅔ × 前一日 K + ⅓ × RSV；D = ⅔ × 前一日 D + ⅓ × K；起始 K = D = 50
 *   j9   = 3D − 2K（Yahoo 股市的「J9」）
 *   k3d2 = 3K − 2D（Yahoo 股市的「K3D2」，一般書上說的 J）
 * 兩個式子用 Yahoo 截圖的數字反推過：K 55.42、D 53.31 → J9 49.09、K3D2 59.64，對得上 49.08、59.65。
 */
export function kdj(high, low, close, n = 9) {
  const len = close.length
  const mk = () => new Array(len).fill(null)
  const out = { rsv: mk(), k: mk(), d: mk(), j9: mk(), k3d2: mk() }
  let k = 50
  let d = 50
  for (let i = n - 1; i < len; i++) {
    let hh = -Infinity
    let ll = Infinity
    for (let j = i - n + 1; j <= i; j++) {
      if (high[j] > hh) hh = high[j]
      if (low[j] < ll) ll = low[j]
    }
    const rsv = hh > ll ? ((close[i] - ll) / (hh - ll)) * 100 : 50
    k = (2 / 3) * k + (1 / 3) * rsv
    d = (2 / 3) * d + (1 / 3) * k
    out.rsv[i] = rsv
    out.k[i] = k
    out.d[i] = d
    out.j9[i] = 3 * d - 2 * k
    out.k3d2[i] = 3 * k - 2 * d
  }
  return out
}
