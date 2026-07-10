<template>
  <div class="backtest-page">
    <PageFocusBanner text="驗證交易策略的歷史績效與風險，評估是否值得實際採用。" />

    <aside class="config-panel card">
      <h3>📊 回測設定</h3>
      <div class="form-group">
        <label>股票代碼</label>
        <input v-model="form.symbol" class="form-input" />
      </div>
      <div class="form-group">
        <label>策略</label>
        <select v-model="form.strategy_id" class="form-input" @change="onStrategyChange">
          <option v-for="s in strategies" :key="s.strategy_id" :value="s.strategy_id">
            {{ s.name }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label>起始日期</label>
        <input type="date" v-model="form.start" class="form-input" />
      </div>
      <div class="form-group">
        <label>結束日期</label>
        <input type="date" v-model="form.end" class="form-input" />
      </div>
      <div class="form-group">
        <label>初始資金 (TWD)</label>
        <input type="number" v-model.number="form.capital" class="form-input" />
      </div>
      <div class="form-group">
        <label>手續費率 %／邊（券商折扣後）</label>
        <input type="number" v-model.number="form.commissionPct" step="0.001" min="0" class="form-input" />
      </div>
      <div class="form-group">
        <label>滑價 %／邊（賣出證交稅 0.3% 另計）</label>
        <input type="number" v-model.number="form.slippagePct" step="0.01" min="0" class="form-input" />
      </div>

      <div v-if="selectedStrategy" class="params-section">
        <h4>策略參數</h4>
        <div v-for="(schema, key) in selectedStrategy.params_schema.properties" :key="key" class="form-group">
          <label>{{ key }}</label>
          <input
            :type="schema.type === 'integer' ? 'number' : 'number'"
            :step="schema.type === 'integer' ? 1 : 0.01"
            v-model.number="form.params[key]"
            class="form-input"
          />
        </div>
      </div>

      <button class="btn btn-primary" style="width: 100%; margin-top: 16px;" @click="runBacktest" :disabled="running">
        <span v-if="running" class="loading-spinner" style="width:14px;height:14px;border-width:2px;vertical-align:-2px;margin-right:6px;" aria-hidden="true"></span>{{ running ? '回測中...' : '🚀 執行回測' }}
      </button>
    </aside>

    <main class="results">
      <div v-if="running" class="empty-state card" role="status" aria-live="polite">
        <div class="loading-spinner" style="width:40px;height:40px;border-width:3px;margin:0 auto 12px;"></div>
        <h3>回測運算中…</h3>
        <p>正在計算年化報酬率、最大回撤、夏普比率等績效指標</p>
      </div>
      <div v-else-if="!result" class="empty-state card">
        <h3>設定策略參數後點擊「執行回測」</h3>
        <p>系統將計算年化報酬率、最大回撤、夏普比率等績效指標</p>
      </div>

      <template v-if="result">
        <!-- Performance Metrics -->
        <div class="grid-4" style="margin-bottom: 16px;">
          <div class="metric-card card">
            <div class="value" :class="result.performance.annual_return >= 0 ? 'up' : 'down'">
              {{ (result.performance.annual_return * 100).toFixed(1) }}%
            </div>
            <div class="label">年化報酬率</div>
          </div>
          <div class="metric-card card">
            <div class="value down">{{ (result.performance.max_drawdown * 100).toFixed(1) }}%</div>
            <div class="label">最大回撤</div>
          </div>
          <div class="metric-card card">
            <div class="value">{{ result.performance.sharpe_ratio }}</div>
            <div class="label">夏普比率</div>
          </div>
          <div class="metric-card card">
            <div class="value">{{ (result.performance.win_rate * 100).toFixed(0) }}%</div>
            <div class="label">勝率</div>
          </div>
        </div>

        <div class="grid-4" style="margin-bottom: 16px;">
          <div class="metric-card card">
            <div class="value">{{ result.performance.profit_factor }}</div>
            <div class="label">盈虧比</div>
          </div>
          <div class="metric-card card">
            <div class="value">{{ result.performance.total_trades }}</div>
            <div class="label">總交易數</div>
          </div>
          <div class="metric-card card">
            <div class="value">{{ result.performance.avg_holding_days }}天</div>
            <div class="label">平均持有</div>
          </div>
          <div class="metric-card card">
            <div class="value" :class="result.performance.total_return >= 0 ? 'up' : 'down'">
              {{ (result.performance.total_return * 100).toFixed(1) }}%
            </div>
            <div class="label">總報酬率</div>
          </div>
        </div>

        <!-- 交易成本（績效已淨值化） -->
        <div v-if="result.costs" class="cost-strip">
          💸 交易成本已計入：本次回測共支出 <strong>{{ Math.round(result.costs.total_costs || 0).toLocaleString('en-US') }}</strong> 元
          （手續費 {{ ((result.costs.commission || 0) * 100).toFixed(4) }}%/邊、證交稅 0.3%、滑價 {{ ((result.costs.slippage || 0) * 100).toFixed(2) }}%/邊，
          約佔初始資金 {{ ((result.costs.cost_pct_of_capital || 0) * 100).toFixed(1) }}%）— 上列績效皆為<strong>稅後費後淨值</strong>。
        </div>

        <!-- A3 過擬合防護：樣本內／樣本外 70/30 走勢驗證 -->
        <div v-if="result.overfit_check" class="card overfit-card">
          <h4>🛡️ 樣本外驗證（防止過擬合）</h4>
          <p v-if="result.overfit_check.low_trade_count" class="of-warn">
            ⚠ {{ result.overfit_check.low_trade_note }}
          </p>
          <template v-if="result.overfit_check.available">
            <div class="of-verdict" :class="'of-' + result.overfit_check.verdict">
              {{ result.overfit_check.verdict_label }}
            </div>
            <div class="of-split">切分日：{{ result.overfit_check.split_date }}（前 70% 為樣本內、後 30% 為樣本外，同一策略同一組參數）</div>
            <div class="of-grid">
              <div class="of-col">
                <div class="of-col-title">樣本內 In-Sample</div>
                <div class="of-range">{{ result.overfit_check.in_sample.start }} ~ {{ result.overfit_check.in_sample.end }}</div>
                <div class="of-metric"><span>年化報酬</span><strong :class="result.overfit_check.in_sample.annual_return >= 0 ? 'up' : 'down'">{{ (result.overfit_check.in_sample.annual_return * 100).toFixed(1) }}%</strong></div>
                <div class="of-metric"><span>勝率</span><strong>{{ (result.overfit_check.in_sample.win_rate * 100).toFixed(0) }}%</strong></div>
                <div class="of-metric"><span>獲利因子</span><strong>{{ result.overfit_check.in_sample.profit_factor }}</strong></div>
                <div class="of-metric"><span>交易數</span><strong>{{ result.overfit_check.in_sample.total_trades }}</strong></div>
              </div>
              <div class="of-col">
                <div class="of-col-title">樣本外 Out-of-Sample</div>
                <div class="of-range">{{ result.overfit_check.out_sample.start }} ~ {{ result.overfit_check.out_sample.end }}</div>
                <div class="of-metric"><span>年化報酬</span><strong :class="result.overfit_check.out_sample.annual_return >= 0 ? 'up' : 'down'">{{ (result.overfit_check.out_sample.annual_return * 100).toFixed(1) }}%</strong></div>
                <div class="of-metric"><span>勝率</span><strong>{{ (result.overfit_check.out_sample.win_rate * 100).toFixed(0) }}%</strong></div>
                <div class="of-metric"><span>獲利因子</span><strong>{{ result.overfit_check.out_sample.profit_factor }}</strong></div>
                <div class="of-metric"><span>交易數</span><strong>{{ result.overfit_check.out_sample.total_trades }}</strong></div>
              </div>
            </div>
          </template>
          <p v-else-if="!result.overfit_check.low_trade_count || result.overfit_check.note" class="of-note">{{ result.overfit_check.note }}</p>
        </div>

        <!-- Equity Curve Chart -->
        <div class="card" style="margin-bottom: 16px;">
          <h4>權益曲線</h4>
          <div class="chart-wrapper">
            <span class="y-axis-label">新台幣(元)</span>
            <div ref="equityChart" class="chart-container"></div>
          </div>
          <div class="x-axis-label">日期</div>
        </div>

        <!-- Trade History -->
        <div class="card">
          <h4>交易明細 ({{ trades.length }} 筆)</h4>
          <div class="data-table">
            <table>
              <thead>
                <tr><th>進場日</th><th>出場日</th><th>進場價</th><th>出場價</th><th>報酬%</th><th>持有天數</th></tr>
              </thead>
              <tbody>
                <tr v-for="(t, i) in trades" :key="i">
                  <td>{{ t.entry_date }}</td>
                  <td>{{ t.exit_date }}</td>
                  <td>{{ t.entry_price }}</td>
                  <td>{{ t.exit_price }}</td>
                  <td :class="t.return >= 0 ? 'up' : 'down'">{{ (t.return * 100).toFixed(2) }}%</td>
                  <td>{{ t.holding_days }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { createChart } from 'lightweight-charts'
import { useChartTheme } from '../composables/useChartTheme'
import { useStockStore } from '../stores/stock.js'

const theme = useChartTheme()
const route = useRoute()
const stockStore = useStockStore()
const strategies = ref([])
const selectedStrategy = ref(null)
const running = ref(false)
const result = ref(null)
const trades = ref([])
const equityChart = ref(null)

const form = ref({
  symbol: route.params.symbol || stockStore.symbol || '2330',
  strategy_id: 'ma_crossover',
  start: '2021-01-01',
  end: new Date().toISOString().split('T')[0],
  capital: 1000000,
  commissionPct: 0.1425, // 手續費率%／邊（可依券商折扣調低）
  slippagePct: 0.1,      // 滑價%／邊
  params: { fast_ma: 5, slow_ma: 20, stop_loss: 0.08, take_profit: 0.20 },
})

onMounted(async () => {
  try {
    const resp = await axios.get('/api/v1/backtest/strategies')
    strategies.value = resp.data?.data?.strategies || []
    onStrategyChange()
  } catch { /* ignore */ }
})

// 側欄搜尋在這頁（/stocks/:symbol/backtest）換股：換代號欄位，讓下一次
// 「執行回測」用新的股票（結果本身仍是使用者按按鈕才觸發，不自動重跑）。
watch(() => route.params.symbol, (sym) => {
  if (sym) form.value.symbol = sym
})

function onStrategyChange() {
  selectedStrategy.value = strategies.value.find(s => s.strategy_id === form.value.strategy_id)
  if (selectedStrategy.value) {
    const defaults = {}
    for (const [key, schema] of Object.entries(selectedStrategy.value.params_schema.properties || {})) {
      defaults[key] = form.value.params[key] ?? schema.default
    }
    form.value.params = defaults
  }
}

async function runBacktest() {
  running.value = true
  result.value = null
  trades.value = []

  try {
    const resp = await axios.post('/api/v1/backtest/run', {
      symbol: form.value.symbol,
      strategy_id: form.value.strategy_id,
      params: form.value.params,
      date_range: { start: form.value.start, end: form.value.end },
      capital: form.value.capital,
      commission: Math.max(form.value.commissionPct || 0, 0) / 100,
      slippage: Math.max(form.value.slippagePct || 0, 0) / 100,
    })
    if (!resp.data?.data || typeof resp.data.data !== 'object') {
      throw new Error('回測回應格式異常')
    }
    result.value = resp.data.data

    // Load trades
    if (result.value.backtest_id) {
      const tResp = await axios.get(`/api/v1/backtest/${result.value.backtest_id}/trades`)
      trades.value = tResp.data?.data?.items || []
    }

    await nextTick()
    renderEquityCurve()
  } catch (e) {
    alert('回測失敗: ' + (e.response?.data?.detail || e.message))
  }
  running.value = false
}

let equityChartInstance = null

function destroyEquityChart() {
  if (equityChartInstance) {
    equityChartInstance.remove()
    equityChartInstance = null
  }
}

onBeforeUnmount(destroyEquityChart)

function renderEquityCurve() {
  if (!equityChart.value || !result.value?.equity_curve) return

  destroyEquityChart()

  const chart = createChart(equityChart.value, {
    width: equityChart.value.clientWidth,
    height: 300,
    layout: { background: { color: '#1e293b' }, textColor: theme.muted },
    grid: { vertLines: { color: theme.border }, horzLines: { color: theme.border } },
  })

  const series = chart.addLineSeries({ color: theme.blue, lineWidth: 2 })
  series.setData(result.value.equity_curve.map(e => ({
    time: e.date,
    value: e.portfolio_value,
  })))
  chart.timeScale().fitContent()
  equityChartInstance = chart
}
</script>

<style scoped>
.backtest-page {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--space-6);
}
/* 觀測重點 banner 要橫跨兩欄；先前它佔走第一格，把設定面板擠到右邊、
   結果區掉到左邊窄欄，造成整頁左右錯置。 */
.backtest-page > :deep(.page-focus-banner) {
  grid-column: 1 / -1;
}
.config-panel { position: sticky; top: 80px; align-self: start; }
.form-group { margin-top: var(--space-3); }
.form-group label { display: block; font-size: 0.8rem; color: var(--text-secondary); margin-bottom: var(--space-1); font-weight: 500; }
.form-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.85rem;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.form-input:focus {
  outline: none;
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.params-section { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--border-color); }
.empty-state { text-align: center; padding: var(--space-12); }
.empty-state p { color: var(--text-secondary); margin-top: var(--space-2); }
.chart-container { width: 100%; margin-top: var(--space-3); border-radius: var(--radius); overflow: hidden; }
.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
}
.chart-wrapper .chart-container { flex: 1; }
.y-axis-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  padding: 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.x-axis-label {
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}
.data-table { overflow-x: auto; margin-top: var(--space-3); }
.data-table table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.data-table th, .data-table td { padding: 8px 12px; text-align: right; border-bottom: 1px solid var(--border-color); }
.data-table th { color: var(--text-muted); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }

@media (max-width: 768px) {
  .backtest-page {
    grid-template-columns: 1fr;
  }
  .config-panel {
    position: static;
  }
}

@media (max-width: 420px) {
  .backtest-page {
    gap: var(--space-3);
  }
  .config-panel,
  .results-panel .card {
    padding: var(--space-3);
  }
}

.cost-strip {
  margin-bottom: 16px;
  padding: 8px 14px;
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.08);
  color: var(--text-muted);
  font-size: 0.82rem;
  line-height: 1.6;
}
.cost-strip strong { color: #f59e0b; }

.overfit-card { margin-bottom: 16px; }
.overfit-card h4 { margin: 0 0 10px; }
.of-warn { color: #f59e0b; font-size: 0.82rem; margin: 0 0 10px; }
.of-note { color: var(--text-muted); font-size: 0.84rem; }
.of-verdict {
  font-weight: 700;
  font-size: 0.9rem;
  padding: 8px 12px;
  border-radius: 8px;
  margin-bottom: 8px;
}
.of-verdict.of-low { background: rgba(34,197,94,0.14); color: #22c55e; }
.of-verdict.of-medium { background: rgba(245,158,11,0.14); color: #f59e0b; }
.of-verdict.of-high { background: rgba(239,68,68,0.14); color: #ef4444; }
.of-split { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px; }
.of-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.of-col { border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 12px; }
.of-col-title { font-weight: 700; font-size: 0.84rem; margin-bottom: 2px; }
.of-range { font-size: 0.72rem; color: var(--text-muted); margin-bottom: 8px; }
.of-metric { display: flex; justify-content: space-between; font-size: 0.82rem; padding: 3px 0; }
.of-metric span { color: var(--text-muted); }
@media (max-width: 640px) {
  .of-grid { grid-template-columns: 1fr; }
}
</style>
