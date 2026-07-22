<template>
  <div class="backtest-page">
    <PageFocusBanner text="驗證交易策略的歷史績效與風險，評估是否值得實際採用。" />

    <aside class="config-panel card">
      <h3>📊 回測設定</h3>
      <label class="compare-toggle">
        <input type="checkbox" v-model="compareMode" @change="onCompareModeChange" />
        策略並列比較模式（同股票/同區間，比較多個策略的績效）
      </label>
      <div class="form-group">
        <label>股票代碼</label>
        <input v-model="form.symbol" class="form-input" />
      </div>
      <div class="form-group" v-if="!compareMode">
        <label>策略</label>
        <select v-model="form.strategy_id" class="form-input" @change="onStrategyChange">
          <option v-for="s in strategies" :key="s.strategy_id" :value="s.strategy_id">
            {{ s.name }}
          </option>
        </select>
      </div>
      <div class="form-group" v-else>
        <label>選擇要比較的策略（2~{{ MAX_COMPARE }} 個，各自使用預設參數）</label>
        <div class="compare-strategy-list">
          <label
            v-for="s in strategies" :key="s.strategy_id"
            class="compare-strategy-item"
            :class="{ disabled: !compareSelected.includes(s.strategy_id) && compareSelected.length >= MAX_COMPARE }"
          >
            <input
              type="checkbox"
              :checked="compareSelected.includes(s.strategy_id)"
              :disabled="!compareSelected.includes(s.strategy_id) && compareSelected.length >= MAX_COMPARE"
              @change="toggleCompareStrategy(s.strategy_id)"
            />
            {{ s.name }}
          </label>
        </div>
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

      <div v-if="selectedStrategy && !compareMode" class="params-section">
        <h4>策略參數</h4>
        <label class="sweep-toggle">
          <input type="checkbox" v-model="sweepMode" @change="onSweepModeChange" />
          參數掃描模式（測試多組參數找相對較好的區間）
        </label>
        <div v-for="(schema, key) in selectedStrategy.params_schema.properties" :key="key" class="form-group">
          <label>{{ key }}</label>
          <template v-if="sweepMode">
            <label class="sweep-param-checkbox">
              <input
                type="checkbox"
                :checked="isSweptParam(key)"
                :disabled="!isSweptParam(key) && sweptParamCount >= 2"
                @change="toggleSweptParam(key, schema)"
              />
              掃描這個參數（否則固定用右側數值）
            </label>
            <div v-if="isSweptParam(key)" class="sweep-range-row">
              <input type="number" v-model.number="sweepRanges[key].min" class="form-input sweep-input" placeholder="最小值" />
              <span class="sweep-sep">~</span>
              <input type="number" v-model.number="sweepRanges[key].max" class="form-input sweep-input" placeholder="最大值" />
              <span class="sweep-sep">間距</span>
              <input type="number" v-model.number="sweepRanges[key].step" class="form-input sweep-input" placeholder="間距" min="0.0001" />
            </div>
            <input
              v-else
              :type="schema.type === 'integer' ? 'number' : 'number'"
              :step="schema.type === 'integer' ? 1 : 0.01"
              v-model.number="form.params[key]"
              class="form-input"
            />
          </template>
          <input
            v-else
            :type="schema.type === 'integer' ? 'number' : 'number'"
            :step="schema.type === 'integer' ? 1 : 0.01"
            v-model.number="form.params[key]"
            class="form-input"
          />
        </div>
        <div v-if="sweepMode" class="sweep-meta">
          <p class="muted small">
            將測試 <strong>{{ sweepCombinationCount }}</strong> 組參數組合
            <span v-if="sweepCombinationCount > MAX_SWEEP_COMBOS" class="error-text">（已超過上限 {{ MAX_SWEEP_COMBOS }} 組，請縮小範圍或加大間距）</span>
          </p>
          <div class="form-group">
            <label>排序依據</label>
            <select v-model="sweepMetric" class="form-input">
              <option value="annual_return">年化報酬率</option>
              <option value="sharpe_ratio">夏普比率</option>
              <option value="profit_factor">盈虧比</option>
              <option value="max_drawdown">最大回撤（越接近 0 越好）</option>
            </select>
          </div>
        </div>
      </div>

      <button
        class="btn btn-primary" style="width: 100%; margin-top: 16px;"
        @click="compareMode ? runCompare() : (sweepMode ? runSweep() : runBacktest())"
        :disabled="compareMode
          ? (compareSelected.length < 2 || compareRunning)
          : (sweepMode
            ? (sweepCombinationCount < 2 || sweepCombinationCount > MAX_SWEEP_COMBOS || sweepRunning)
            : running)"
      >
        <span v-if="compareMode ? compareRunning : (sweepMode ? sweepRunning : running)" class="loading-spinner" style="width:14px;height:14px;border-width:2px;vertical-align:-2px;margin-right:6px;" aria-hidden="true"></span>{{ compareMode ? (compareRunning ? '比較回測中...' : `🚀 執行比較回測 (${compareSelected.length})`) : (sweepMode ? (sweepRunning ? '掃描中...' : `🔍 執行參數掃描 (${sweepCombinationCount})`) : (running ? '回測中...' : '🚀 執行回測')) }}
      </button>
    </aside>

    <main class="results">
      <div v-if="running || compareRunning || sweepRunning" class="empty-state card" role="status" aria-live="polite">
        <div class="loading-spinner" style="width:40px;height:40px;border-width:3px;margin:0 auto 12px;"></div>
        <h3>回測運算中…</h3>
        <p>{{ compareMode ? '正在並列執行多個策略的回測，計算各自績效指標' : (sweepMode ? `正在測試 ${sweepCombinationCount} 組參數組合...` : '正在計算年化報酬率、最大回撤、夏普比率等績效指標') }}</p>
      </div>
      <div v-else-if="compareMode && !compareResults.length" class="empty-state card">
        <h3>勾選 2~{{ MAX_COMPARE }} 個策略後點擊「執行比較回測」</h3>
        <p>系統將用相同的股票/區間/資金並列比較各策略績效，找出相對較適合的策略</p>
        <p v-if="compareError" class="error-text">{{ compareError }}</p>
      </div>
      <div v-else-if="sweepMode && !sweepResults.length" class="empty-state card">
        <h3>設定 1~2 個掃描參數的範圍後點擊「執行參數掃描」</h3>
        <p>系統會測試所有參數組合並依你選的指標排序，幫你找出歷史上表現相對較好的參數區間（過去資料，不保證未來）</p>
        <p v-if="sweepError" class="error-text">{{ sweepError }}</p>
      </div>
      <div v-else-if="!compareMode && !sweepMode && !result" class="empty-state card">
        <h3>設定策略參數後點擊「執行回測」</h3>
        <p>系統將計算年化報酬率、最大回撤、夏普比率等績效指標</p>
      </div>

      <template v-if="!compareMode && !sweepMode && result">
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
            <div class="label">夏普比率 <InfoTooltip v-bind="metricGlossary.sharpe" /></div>
          </div>
          <div class="metric-card card">
            <div class="value">{{ (result.performance.win_rate * 100).toFixed(0) }}%</div>
            <div class="label">勝率</div>
          </div>
        </div>

        <div class="grid-4" style="margin-bottom: 16px;">
          <div class="metric-card card">
            <div class="value">{{ result.performance.profit_factor }}</div>
            <div class="label">盈虧比 <InfoTooltip v-bind="metricGlossary.profitFactor" /></div>
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

        <!-- B7 MFE/MAE：出場價只是「結果」，這裡看持有期間的「過程」 -->
        <div v-if="result.mfe_mae && result.mfe_mae.available" class="card mfe-card">
          <h4>📐 MFE / MAE 分析</h4>
          <p class="mfe-intro">MFE＝持有期間內最有利時比進場價高多少；MAE＝最不利時比進場價低多少（負值）。擷取率＝實際報酬佔 MFE 的比例，太低代表出場太早、獲利留在桌上。</p>
          <div class="mfe-grid">
            <div class="mfe-stat"><span>平均 MFE</span><strong class="up">+{{ result.mfe_mae.avg_mfe_pct }}%</strong></div>
            <div class="mfe-stat"><span>平均 MAE</span><strong class="down">{{ result.mfe_mae.avg_mae_pct }}%</strong></div>
            <div class="mfe-stat"><span>最深 MAE（單筆最痛）</span><strong class="down">{{ result.mfe_mae.worst_mae_pct }}%</strong></div>
            <div class="mfe-stat" v-if="result.mfe_mae.avg_capture_pct != null"><span>平均擷取率</span><strong :class="result.mfe_mae.avg_capture_pct >= 50 ? 'up' : 'down'">{{ result.mfe_mae.avg_capture_pct }}%</strong></div>
          </div>
          <p class="mfe-insight" v-if="result.mfe_mae.avg_capture_pct != null && result.mfe_mae.avg_capture_pct < 40">
            💡 平均只擷取了 MFE 的 {{ result.mfe_mae.avg_capture_pct }}%——可能出場太保守，考慮用移動停利讓獲利多留一點（參考分析頁的 ATR 移動停利）。
          </p>
          <p class="mfe-insight" v-else-if="Math.abs(result.mfe_mae.worst_mae_pct) > 2 * Math.abs(result.mfe_mae.avg_mae_pct)">
            💡 最深 MAE（{{ result.mfe_mae.worst_mae_pct }}%）遠比平均 MAE 深很多——代表偶爾會有單筆重壓套很深，檢查停損是否確實執行。
          </p>
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
          <div class="trade-log-head">
            <h4>交易明細 ({{ trades.length }} 筆)</h4>
            <button v-if="trades.length" class="btn xs" type="button" @click="exportTradesCsv">📥 匯出 CSV</button>
          </div>
          <div class="data-table table-wrap">
            <table>
              <thead>
                <tr><th>進場日</th><th>出場日</th><th>進場價</th><th>出場價</th><th>報酬%</th><th>持有天數</th><th>MFE%</th><th>MAE%</th></tr>
              </thead>
              <tbody>
                <tr v-for="(t, i) in trades" :key="i">
                  <td>{{ t.entry_date }}</td>
                  <td>{{ t.exit_date }}</td>
                  <td>{{ t.entry_price }}</td>
                  <td>{{ t.exit_price }}</td>
                  <td :class="t.return >= 0 ? 'up' : 'down'">{{ (t.return * 100).toFixed(2) }}%</td>
                  <td>{{ t.holding_days }}</td>
                  <td class="up">{{ t.mfe_pct != null ? '+' + t.mfe_pct + '%' : '—' }}</td>
                  <td class="down">{{ t.mae_pct != null ? t.mae_pct + '%' : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <template v-if="compareMode && compareResults.length">
        <div class="card" style="margin-bottom: 16px;">
          <div class="trade-log-head">
            <h4>策略績效並列比較</h4>
            <button class="btn xs" type="button" @click="exportCompareCsv">📥 匯出 CSV</button>
          </div>
          <div class="data-table table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="text-align:left;">指標</th>
                  <th v-for="r in compareResults" :key="r.strategy_id">{{ r.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in COMPARE_METRICS" :key="m.key">
                  <td style="text-align:left; color: var(--text-muted);">
                    {{ m.label }}
                    <InfoTooltip v-if="m.key === 'sharpe_ratio'" v-bind="metricGlossary.sharpe" />
                    <InfoTooltip v-else-if="m.key === 'profit_factor'" v-bind="metricGlossary.profitFactor" />
                  </td>
                  <td
                    v-for="r in compareResults" :key="r.strategy_id"
                    :class="{ 'best-cell': m.higherBetter != null && typeof r.performance?.[m.key] === 'number' && r.performance[m.key] === bestValue(m) }"
                  >
                    {{ r.performance?.[m.key] != null ? m.fmt(r.performance[m.key]) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="muted small" style="margin-top: 8px;">比較模式下各策略使用自身預設參數，交易成本設定與單一模式共用。<span class="best-hint">綠底</span>標示該指標表現最佳的策略。</p>
        </div>
        <div class="card">
          <h4>權益曲線比較（相對起始資金的報酬%）</h4>
          <div ref="compareChartHost" class="chart-container" style="height: 320px;"></div>
        </div>
      </template>

      <template v-if="sweepMode && !compareMode && sweepResults.length">
        <div class="card">
          <div class="trade-log-head">
            <h4>參數掃描結果（共 {{ sweepResults.length }} 組，依{{ sweepMetricLabel }}排序）</h4>
            <button class="btn xs" type="button" @click="exportSweepCsv">📥 匯出 CSV</button>
          </div>
          <div class="data-table table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="k in Object.keys(sweepRanges)" :key="k" style="text-align:left;">{{ k }}</th>
                  <th>年化報酬率</th><th>最大回撤</th><th>夏普比率 <InfoTooltip v-bind="metricGlossary.sharpe" /></th><th>勝率</th><th>盈虧比 <InfoTooltip v-bind="metricGlossary.profitFactor" /></th><th>總交易數</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in sweepResults" :key="i" :class="{ 'best-row': i === 0 }">
                  <td v-for="k in Object.keys(sweepRanges)" :key="k" style="text-align:left;">{{ r.params[k] }}</td>
                  <td :class="r.performance.annual_return >= 0 ? 'up' : 'down'">{{ (r.performance.annual_return * 100).toFixed(1) }}%</td>
                  <td class="down">{{ (r.performance.max_drawdown * 100).toFixed(1) }}%</td>
                  <td>{{ r.performance.sharpe_ratio }}</td>
                  <td>{{ (r.performance.win_rate * 100).toFixed(0) }}%</td>
                  <td>{{ r.performance.profit_factor }}</td>
                  <td>{{ r.performance.total_trades }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="muted small" style="margin-top: 8px;">⚠ 排序第一的參數組合是對這段歷史資料最適配的結果，可能過擬合——建議參考附近多組表現都不錯的參數區間，而非只挑單一最高分組合，並搭配上方單一模式的「樣本外驗證」交叉確認。</p>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { createChart } from 'lightweight-charts'
import { useChartTheme } from '../composables/useChartTheme'
import { useStockStore } from '../stores/stock.js'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'

const theme = useChartTheme()
const route = useRoute()
const stockStore = useStockStore()
const strategies = ref([])
const selectedStrategy = ref(null)
const running = ref(false)
const result = ref(null)
const trades = ref([])
const equityChart = ref(null)

// Y7：策略並列比較——同股票/同區間，一次比較多個策略的績效與權益曲線。
const MAX_COMPARE = 4
const compareMode = ref(false)
const compareSelected = ref([])
const compareRunning = ref(false)
const compareResults = ref([]) // [{strategy_id, name, performance, equity_curve}]
const compareError = ref('')
const compareChartHost = ref(null)
let compareChartInstance = null

const COMPARE_METRICS = [
  { key: 'annual_return', label: '年化報酬率', fmt: v => (v * 100).toFixed(1) + '%', higherBetter: true },
  { key: 'max_drawdown', label: '最大回撤', fmt: v => (v * 100).toFixed(1) + '%', higherBetter: true },
  { key: 'sharpe_ratio', label: '夏普比率', fmt: v => String(v), higherBetter: true },
  { key: 'win_rate', label: '勝率', fmt: v => (v * 100).toFixed(0) + '%', higherBetter: true },
  { key: 'profit_factor', label: '盈虧比', fmt: v => String(v), higherBetter: true },
  { key: 'total_trades', label: '總交易數', fmt: v => String(v), higherBetter: null },
  { key: 'avg_holding_days', label: '平均持有(天)', fmt: v => String(v), higherBetter: null },
  { key: 'total_return', label: '總報酬率', fmt: v => (v * 100).toFixed(1) + '%', higherBetter: true },
]

function bestValue(metric) {
  if (metric.higherBetter == null) return null
  const values = compareResults.value.map(r => r.performance?.[metric.key]).filter(v => typeof v === 'number')
  if (!values.length) return null
  return metric.higherBetter ? Math.max(...values) : Math.min(...values)
}

function onCompareModeChange() {
  if (compareMode.value) {
    result.value = null
    trades.value = []
    destroyEquityChart()
    sweepMode.value = false
    sweepResults.value = []
    sweepError.value = ''
    if (!compareSelected.value.length) {
      compareSelected.value = strategies.value.slice(0, 2).map(s => s.strategy_id)
    }
  } else {
    compareResults.value = []
    compareError.value = ''
    destroyCompareChart()
  }
}

function toggleCompareStrategy(id) {
  if (compareSelected.value.includes(id)) {
    compareSelected.value = compareSelected.value.filter(x => x !== id)
  } else if (compareSelected.value.length < MAX_COMPARE) {
    compareSelected.value = [...compareSelected.value, id]
  }
}

async function runCompare() {
  if (compareSelected.value.length < 2) return
  compareRunning.value = true
  compareError.value = ''
  compareResults.value = []
  try {
    const requests = compareSelected.value.map(async (sid) => {
      const strat = strategies.value.find(s => s.strategy_id === sid)
      const defaults = {}
      for (const [key, schema] of Object.entries(strat?.params_schema?.properties || {})) {
        defaults[key] = schema.default
      }
      const resp = await axios.post('/api/v1/backtest/run', {
        symbol: form.value.symbol,
        strategy_id: sid,
        params: defaults,
        date_range: { start: form.value.start, end: form.value.end },
        capital: form.value.capital,
        commission: Math.max(form.value.commissionPct || 0, 0) / 100,
        slippage: Math.max(form.value.slippagePct || 0, 0) / 100,
      })
      const data = resp.data?.data
      if (!data) throw new Error(`${strat?.name || sid} 回測回應格式異常`)
      return { strategy_id: sid, name: strat?.name || sid, performance: data.performance, equity_curve: data.equity_curve || [] }
    })
    compareResults.value = await Promise.all(requests)
    await nextTick()
    renderCompareChart()
  } catch (e) {
    compareError.value = e.response?.data?.detail || e.message || '比較回測失敗'
  }
  compareRunning.value = false
}

function destroyCompareChart() {
  if (compareChartInstance) {
    compareChartInstance.remove()
    compareChartInstance = null
  }
}
onBeforeUnmount(destroyCompareChart)

function renderCompareChart() {
  if (!compareChartHost.value || !compareResults.value.length) return
  destroyCompareChart()
  const chart = createChart(compareChartHost.value, {
    width: compareChartHost.value.clientWidth,
    height: 320,
    layout: { background: { color: 'transparent' }, textColor: theme.muted },
    grid: { vertLines: { color: theme.border }, horzLines: { color: theme.border } },
  })
  const colors = [theme.blue, theme.purple, theme.cyan, theme.warn]
  compareResults.value.forEach((r, i) => {
    if (!r.equity_curve.length) return
    const baseline = r.equity_curve[0].portfolio_value
    const series = chart.addLineSeries({ color: colors[i % colors.length], lineWidth: 2, title: r.name })
    series.setData(r.equity_curve.map(e => ({ time: e.date, value: Number(((e.portfolio_value / baseline - 1) * 100).toFixed(2)) })))
  })
  chart.timeScale().fitContent()
  compareChartInstance = chart
}

function exportCompareCsv() {
  if (!compareResults.value.length) return
  const cols = ['指標', ...compareResults.value.map(r => r.name)]
  const rows = COMPARE_METRICS.map(m => [
    m.label,
    ...compareResults.value.map(r => {
      const v = r.performance?.[m.key]
      return v == null ? '' : m.fmt(v)
    }),
  ])
  downloadCsv(timestampedFilename(`backtest-compare-${form.value.symbol}`), cols, rows)
}

// Y8：參數掃描/最佳化——固定策略，對 1~2 個參數掃描範圍，找出歷史上相對較好的組合。
const MAX_SWEEP_COMBOS = 30
const sweepMode = ref(false)
const sweepRanges = ref({}) // { paramKey: {min, max, step} }
const sweepMetric = ref('annual_return')
const sweepRunning = ref(false)
const sweepResults = ref([]) // [{params, performance}]
const sweepError = ref('')

const SWEEP_METRIC_LABELS = {
  annual_return: '年化報酬率',
  sharpe_ratio: '夏普比率',
  profit_factor: '盈虧比',
  max_drawdown: '最大回撤',
}
const sweepMetricLabel = computed(() => SWEEP_METRIC_LABELS[sweepMetric.value] || sweepMetric.value)

const sweptParamCount = computed(() => Object.keys(sweepRanges.value).length)

function isSweptParam(key) {
  return Object.prototype.hasOwnProperty.call(sweepRanges.value, key)
}

function toggleSweptParam(key, schema) {
  if (isSweptParam(key)) {
    const rest = { ...sweepRanges.value }
    delete rest[key]
    sweepRanges.value = rest
  } else {
    if (sweptParamCount.value >= 2) return
    const base = Number(form.value.params[key] ?? schema.default ?? 0)
    const step = schema.type === 'integer' ? 1 : Math.max(Math.abs(base) * 0.1, 0.01)
    const min = schema.type === 'integer' ? Math.max(base - step * 2, 1) : Math.max(base - step * 2, 0)
    sweepRanges.value = { ...sweepRanges.value, [key]: { min, max: base + step * 2, step } }
  }
}

const sweepCombos = computed(() => {
  const keys = Object.keys(sweepRanges.value)
  if (!keys.length) return []
  const axes = keys.map((k) => {
    const r = sweepRanges.value[k]
    const min = Number(r.min), max = Number(r.max)
    const step = Number(r.step) > 0 ? Number(r.step) : 1
    const values = []
    if (isFinite(min) && isFinite(max) && max >= min) {
      for (let v = min; v <= max + 1e-9; v += step) {
        values.push(Math.round(v * 1e6) / 1e6)
      }
    }
    return { key: k, values }
  })
  if (axes.some(a => !a.values.length)) return []
  let combos = [{}]
  for (const axis of axes) {
    const next = []
    for (const c of combos) {
      for (const v of axis.values) next.push({ ...c, [axis.key]: v })
    }
    combos = next
  }
  return combos
})
const sweepCombinationCount = computed(() => sweepCombos.value.length)

function onSweepModeChange() {
  if (sweepMode.value) {
    compareMode.value = false
    compareResults.value = []
    compareError.value = ''
    destroyCompareChart()
  } else {
    sweepResults.value = []
    sweepError.value = ''
  }
}

function sortSweepResults() {
  sweepResults.value = [...sweepResults.value].sort(
    (a, b) => (b.performance?.[sweepMetric.value] ?? -Infinity) - (a.performance?.[sweepMetric.value] ?? -Infinity)
  )
}
watch(sweepMetric, () => {
  if (sweepResults.value.length) sortSweepResults()
})

async function runSweep() {
  const combos = sweepCombos.value
  if (combos.length < 2 || combos.length > MAX_SWEEP_COMBOS) return
  sweepRunning.value = true
  sweepError.value = ''
  sweepResults.value = []
  try {
    const requests = combos.map(async (combo) => {
      const params = { ...form.value.params, ...combo }
      const resp = await axios.post('/api/v1/backtest/run', {
        symbol: form.value.symbol,
        strategy_id: form.value.strategy_id,
        params,
        date_range: { start: form.value.start, end: form.value.end },
        capital: form.value.capital,
        commission: Math.max(form.value.commissionPct || 0, 0) / 100,
        slippage: Math.max(form.value.slippagePct || 0, 0) / 100,
      })
      const data = resp.data?.data
      if (!data) throw new Error('掃描回應格式異常')
      return { params: combo, performance: data.performance }
    })
    sweepResults.value = await Promise.all(requests)
    sortSweepResults()
  } catch (e) {
    sweepError.value = e.response?.data?.detail || e.message || '參數掃描失敗'
  }
  sweepRunning.value = false
}

function exportSweepCsv() {
  if (!sweepResults.value.length) return
  const paramKeys = Object.keys(sweepRanges.value)
  const cols = [...paramKeys, '年化報酬率%', '最大回撤%', '夏普比率', '勝率%', '盈虧比', '總交易數']
  const rows = sweepResults.value.map(r => [
    ...paramKeys.map(k => r.params[k]),
    (r.performance.annual_return * 100).toFixed(1),
    (r.performance.max_drawdown * 100).toFixed(1),
    r.performance.sharpe_ratio,
    (r.performance.win_rate * 100).toFixed(0),
    r.performance.profit_factor,
    r.performance.total_trades,
  ])
  downloadCsv(timestampedFilename(`backtest-sweep-${form.value.symbol}-${form.value.strategy_id}`), cols, rows)
}

// Y5：交易明細匯出，回測頁原本完全沒有匯出功能
function exportTradesCsv() {
  const cols = ['進場日', '出場日', '進場價', '出場價', '報酬%', '持有天數', 'MFE%', 'MAE%']
  const rows = trades.value.map(t => [
    t.entry_date, t.exit_date, t.entry_price, t.exit_price,
    (t.return * 100).toFixed(2), t.holding_days, t.mfe_pct ?? '', t.mae_pct ?? '',
  ])
  const sym = route.params.symbol || stockStore.symbol || 'backtest'
  downloadCsv(timestampedFilename(`backtest-trades-${sym}`), cols, rows)
}

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
  // 換策略後參數 schema 不同，之前掃描的參數範圍不再適用
  sweepRanges.value = {}
  sweepResults.value = []
  sweepError.value = ''
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
.trade-log-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.trade-log-head h4 { margin: 0; }
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
.compare-toggle {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.82rem; color: var(--text-secondary);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
}
.compare-strategy-list { display: flex; flex-direction: column; gap: 6px; }
.compare-strategy-item {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.85rem; cursor: pointer;
  padding: 6px 8px; border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}
.compare-strategy-item.disabled { opacity: 0.45; cursor: not-allowed; }
.error-text { color: #ef4444; font-size: 0.84rem; margin-top: var(--space-2); }
.best-cell { background: rgba(34, 197, 94, 0.14); color: #22c55e; font-weight: 700; }
.best-hint { display: inline-block; padding: 1px 6px; border-radius: 6px; background: rgba(34, 197, 94, 0.14); color: #22c55e; font-weight: 700; }
.sweep-toggle {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.8rem; color: var(--text-secondary);
  margin-bottom: var(--space-3); cursor: pointer;
}
.sweep-param-checkbox { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 4px; cursor: pointer; }
.sweep-range-row { display: flex; align-items: center; gap: 4px; }
.sweep-input { min-width: 0; flex: 1; }
.sweep-sep { font-size: 0.72rem; color: var(--text-muted); white-space: nowrap; }
.sweep-meta { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border-color); }
.best-row { background: rgba(34, 197, 94, 0.1); }
.best-row td:first-child { font-weight: 700; }
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

.mfe-card { margin-bottom: 16px; }
.mfe-card h4 { margin: 0 0 6px; }
.mfe-intro { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 12px; line-height: 1.6; }
.mfe-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.mfe-stat { border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.mfe-stat span { font-size: 0.74rem; color: var(--text-muted); }
.mfe-stat strong { font-size: 1.1rem; }
.mfe-insight { margin: 12px 0 0; font-size: 0.82rem; color: #f59e0b; background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.3); border-radius: 8px; padding: 8px 12px; }
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
