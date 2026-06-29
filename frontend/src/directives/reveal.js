// v-reveal — 進場動效指令：元素捲入視窗時淡入上移。
// 安全設計：
//  1. 尊重 prefers-reduced-motion（直接顯示，不加動畫）。
//  2. 內容預設可見；僅在 JS 確認可動畫時才暫時隱藏，並以 failsafe 計時器保證
//     即使 IntersectionObserver 未觸發（隱藏分頁／headless）也一定會顯示，絕不留白。
//  3. 可傳入 { delay } 做 stagger 交錯。

const prefersReduced =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

const supportsIO = typeof window !== 'undefined' && 'IntersectionObserver' in window

function show(el) {
  el.classList.add('reveal-in')
  if (el._revealTimer) {
    clearTimeout(el._revealTimer)
    el._revealTimer = null
  }
  if (el._revealIO) {
    el._revealIO.disconnect()
    el._revealIO = null
  }
}

export default {
  mounted(el, binding) {
    if (prefersReduced || !supportsIO) return // 內容維持預設可見

    const delay = Number(binding.value?.delay ?? 0)
    el.style.setProperty('--reveal-delay', `${delay}ms`)
    el.classList.add('reveal-init')

    // Failsafe：1.4s 後一律顯示，避免任何情況下留白
    el._revealTimer = setTimeout(() => show(el), 1400 + delay)

    el._revealIO = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) show(el)
        })
      },
      { threshold: 0.08, rootMargin: '0px 0px -8% 0px' }
    )
    el._revealIO.observe(el)
  },
  unmounted(el) {
    if (el._revealTimer) clearTimeout(el._revealTimer)
    if (el._revealIO) el._revealIO.disconnect()
  },
}
