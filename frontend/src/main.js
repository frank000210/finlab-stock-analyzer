import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import reveal from './directives/reveal.js'
import './assets/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.directive('reveal', reveal)
app.mount('#app')
