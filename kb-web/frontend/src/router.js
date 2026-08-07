import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Notebooks from './views/Notebooks.vue'
import Import from './views/Import.vue'
import Ask from './views/Ask.vue'
import PatentReport from './views/PatentReport.vue'
import PatentPlan from './views/PatentPlan.vue'
import PatentReview from './views/PatentReview.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Notebooks },
    { path: '/import', component: Import },
    { path: '/ask', component: Ask },
    { path: '/patent-plan', component: PatentPlan },
    { path: '/patent-report', component: PatentReport },
    { path: '/patent-review', component: PatentReview },
  ],
})

router.beforeEach((to) => {
  const hasToken = !!localStorage.getItem('kb_token')
  if (to.path !== '/login' && !hasToken) {
    return '/login'
  }
})

export default router
