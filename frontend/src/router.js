import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/stocks/:symbol',
    name: 'analysis',
    component: () => import('./views/AnalysisView.vue'),
  },
  {
    path: '/stocks/:symbol/backtest',
    name: 'backtest',
    component: () => import('./views/BacktestView.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/SettingsView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
