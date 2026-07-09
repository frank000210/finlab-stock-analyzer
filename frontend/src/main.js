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
