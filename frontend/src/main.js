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
app.use(createPinia())
app.use(router)
app.directive('reveal', reveal)
app.mount('#app')
