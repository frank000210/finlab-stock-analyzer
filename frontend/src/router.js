import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('./views/OverviewView.vue'),
  },
  {
    path: '/decision',
    name: 'decision',
    component: () => import('./views/DecisionView.vue'),
  },
  {
    path: '/graph',
    name: 'graph',
    component: () => import('./views/GraphView.vue'),
  },
  {
    path: '/graph01',
    name: 'graph01',
    component: () => import('./views/Graph01View.vue'),
  },
  {
    path: '/rotation',
    name: 'rotation',
    component: () => import('./views/RotationView.vue'),
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
    path: '/stocks/:symbol/chip',
    name: 'chip',
    component: () => import('./views/ChipAnalysisView.vue'),
  },
  {
    path: '/stocks/:symbol/social-buzz',
    name: 'social-buzz',
    component: () => import('./views/SocialBuzzView.vue'),
  },
  {
    path: '/stocks/:symbol/public-data',
    name: 'public-data',
    component: () => import('./views/PublicDataView.vue'),
  },
  {
    path: '/risk-sizing',
    name: 'risk-sizing',
    component: () => import('./views/RiskSizingView.vue'),
  },
  {
    path: '/portfolio-heat',
    name: 'portfolio-heat',
    component: () => import('./views/PortfolioHeatView.vue'),
  },
  {
    path: '/journal',
    name: 'journal',
    component: () => import('./views/JournalView.vue'),
  },
  {
    path: '/monte-carlo',
    name: 'monte-carlo',
    component: () => import('./views/MonteCarloView.vue'),
  },
  {
    path: '/signals',
    name: 'signals',
    component: () => import('./views/SignalsView.vue'),
  },
  {
    path: '/command',
    name: 'command',
    component: () => import('./views/CommandView.vue'),
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
  {
    path: '/admin',
    name: 'admin',
    component: () => import('./views/AdminView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
