import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import reveal from './directives/reveal.js'
import './assets/main.css'
import { applySavedTheme } from './composables/useTheme.js'

// 開頁時把上次儲存的外觀主題套回 :root（在 mount 前，避免閃爍）
applySavedTheme()

const app = createApp(App)

// Global error net: a component render/handler error used to silently blank
// its subtree (console-only). Surface it as a dismissable toast instead.
// App.vue listens for this event and renders the toast UI.
app.config.errorHandler = (err, _instance, info) => {
  console.error('[finlab] unhandled component error:', err, info)
  try {
    window.dispatchEvent(new CustomEvent('finlab:app-error', {
      detail: String((err && err.message) || err || '未知錯誤'),
    }))
  } catch { /* never let error reporting throw */ }
}

app.use(createPinia())
app.use(router)
app.directive('reveal', reveal)
app.mount('#app')

// E18 PWA：只在正式 build 註冊（dev server 的 HMR 跟 SW 快取會互相打架）。
// S8：偵測到新版本時跳出提示讓使用者自己選擇何時重新整理，而不是背景默默
//接管（分頁開著跨版本部署，動態載入的路由 chunk 可能因為舊 hash 已經不
// 存在而 404，使用者卻不知道發生了什麼事）。
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing
          if (!newWorker) return
          newWorker.addEventListener('statechange', () => {
            // 有現有 controller 才代表這是「更新」（不是使用者第一次造訪、
            // 首次安裝 SW 的情況，那種不需要打擾使用者）。
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              window.dispatchEvent(new CustomEvent('finlab:sw-update-available'))
            }
          })
        })
      })
      .catch((err) => {
        console.warn('[finlab] service worker registration failed:', err)
      })

    // 首次造訪時 SW 安裝完呼叫 clients.claim() 也會觸發 controllerchange
    //（從「無控制者」變成「有控制者」），這種情況不能 reload——否則每個新
    // 訪客第一次載入頁面都會被莫名重新整理一次（e2e 全套跑掛就是這樣抓到
    // 的）。只有「頁面本來就有控制者、被新版 SW 取代」才是真的版本更新。
    let hadController = !!navigator.serviceWorker.controller
    let reloading = false
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController) { hadController = true; return }
      if (reloading) return
      reloading = true
      window.location.reload()
    })
  })
}

// App.vue 的更新提示 banner 呼叫這個函式：通知等待中的新 SW 接管，
// controllerchange 事件會接著觸發上面的自動重新整理。
window.__finlabApplySwUpdate = () => {
  navigator.serviceWorker?.getRegistration().then((registration) => {
    registration?.waiting?.postMessage({ type: 'SKIP_WAITING' })
  })
}
