import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/decision',
    name: 'decision',
    component: () => import('./views/DecisionView.vue'),
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
    path: '/stocks/:symbol/seasonal',
    name: 'seasonal',
    component: () => import('./views/SeasonalView.vue'),
  },
  {
    path: '/stocks/:symbol/lead-lag',
    name: 'lead-lag',
    component: () => import('./views/LeadLagView.vue'),
  },
  {
    path: '/stocks/:symbol/major-players',
    name: 'major-players',
    component: () => import('./views/MajorPlayersView.vue'),
  },
  {
    path: '/stocks/:symbol/social-buzz',
    name: 'social-buzz',
    component: () => import('./views/SocialBuzzView.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/SettingsView.vue'),
  },
  {
    path: '/trade-dashboard',
    name: 'TradeDashboard',
    component: () => import('./views/TradeDashboardView.vue'),
  },
  {
    path: '/ai-signals',
    name: 'AISignals',
    component: () => import('./views/AISignalsView.vue'),
  },
  {
    path: '/risk-monitor',
    name: 'RiskMonitor',
    component: () => import('./views/RiskMonitorView.vue'),
  },
  {
    path: '/data-agent',
    name: 'DataAgent',
    component: () => import('./views/DataAgentView.vue'),
  },
  {
    path: '/trade-approval',
    name: 'TradeApproval',
    component: () => import('./views/TradeApprovalView.vue'),
  },
  {
    path: '/signal-rules',
    name: 'SignalRules',
    component: () => import('./views/SignalRulesView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
