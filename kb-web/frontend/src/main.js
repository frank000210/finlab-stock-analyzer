import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import './themes.css'
import './style.css'
import './skin.css'
import { applySavedColorTheme } from './lib/colorThemes.js'

applySavedColorTheme()

createApp(App).use(createPinia()).use(router).mount('#app')
