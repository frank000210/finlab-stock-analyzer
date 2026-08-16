<template>
  <div class="risk-page">
    <PageFocusBanner text="監控帳戶與部位風險指標，及早發現超出容忍範圍的風險。" />

    <div class="page-header">
      <div>
        <h1>風控監控</h1>
        <p>追蹤最大回撤、熔斷機制與權益曲線</p>
      </div>
      <button class="btn btn-primary" @click="loadRiskData" :disabled="loading">
        {{ loading ? '載入中...' : '重新整理' }}
      </button>
    </div>

    <section class="top-grid">
      <article class="card gauge-card">
        <div class="section-header">
          <div>
            <h2>MDD 風險儀表 <InfoTooltip v-bind="metricGlossary.mdd" /></h2>
            <p>綠色 &lt; {{ mddWarnPct }}%，黃色 {{ mddWarnPct }}-{{ mddPausePct }}%，紅色 ≥ {{ mddPausePct }}%</p>
          </div>
        </div>
        <div class="gauge-wrap">
          <div class="gauge" :style="gaugeStyle">
            <div class="gauge-inner">
              <strong>{{ formatPercent(mddValue) }}</strong>
              <span>MDD</span>
            </div>
          </div>
        </div>
        <MetricScale
          v-if="hasJournalData"
          class="mdd-scale"
          :min="0" :max="mddScaleMax" :value="mddPercent"
          :zones="mddZones" :thresholds="mddThresholds"
          left-label="0%" :decimals="1"
        />
        <p class="mdd-narrative" v-if="hasJournalData">{{ mddNarrative }}</p>
      </article>

      <article class="card state-card">
        <div class="section-header">
          <div>
            <h2>熔斷機制狀態</h2>
            <p>依交易日誌實際回撤與當日交易數判定</p>
          </div>
        </div>
        <div class="state-body">
          <span class="status-pill" :class="statusClass(circuitStatus)">{{ circuitBreakerLabel }}</span>
          <p>{{ statusDescription }}</p>
          <div class="threshold-cfg">
            <label>警戒 MDD<input v-model.number="mddWarnPct" type="number" min="0.5" step="0.5" class="cfg-inp" @change="saveThresholds" />%</label>
            <label>熔斷 MDD<input v-model.number="mddPausePct" type="number" min="1" step="0.5" class="cfg-inp" @change="saveThresholds" />%</label>
            <label>當日上限<input v-model.number="dailyTradeLimit" type="number" min="1" step="1" class="cfg-inp" @change="saveThresholds" />筆</label>
          </div>
        </div>
      </article>

      <article class="card trades-card">
        <div class="section-header">
          <div>
            <h2>當日交易次數</h2>
            <p>達 {{ warnTrades }} 筆警戒、{{ dailyTradeLimit }} 筆熔斷</p>
          </div>
        </div>
        <div class="trade-counter">
          <strong>{{ dailyTrades }}</strong>
          <span>/ {{ dailyTradeLimit }}</span>
        </div>
        <div class="progress-track counter-track">
          <div class="progress-fill counter-fill" :style="{ width: `${tradePercent}%` }"></div>
        </div>
      </article>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益曲線</h2>
          <p>依「交易日誌」已平倉紀錄按日彙總，起始為投組風險頁設定的帳戶資金</p>
        </div>
        <span v-if="unrealizedInfo" class="badge-estimated badge-unrealized">含 {{ unrealizedInfo.priced }} 筆未實現損益</span>
        <span v-if="hasJournalData" class="badge-estimated">資料來源：交易日誌</span>
      </div>
      <div v-if="equitySeries.length" class="chart-wrapper">
        <span class="y-axis-label">新台幣(元)</span>
        <div ref="chartEl" class="chart-area"></div>
      </div>
      <div v-if="!equitySeries.length" class="empty-state">尚無已平倉交易紀錄，請先在「交易日誌」記錄並平倉交易後再回來查看權益曲線。</div>
      <div class="x-axis-label" v-if="equitySeries.length">日期</div>
      <!-- TT8: R 曲線最大回撤 -->
      <div v-if="rCurveMdd" class="r-curve-stats">
        <div class="rc-stat">
          <span class="rc-label">R 曲線最大回撤 <InfoTooltip label="R 曲線最大回撤" text="累計 R 序列從峰值到最低點的最大回落（單位：R，不受帳戶大小影響）。代表你的系統在最差連虧序列時，從高點累計虧了幾倍風險單位。< 2R 屬健康水準。" /></span>
          <strong :class="rCurveMdd.mddR > 5 ? 'down' : rCurveMdd.mddR > 2 ? 'warn' : 'up'">{{ rCurveMdd.mddR.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">累計 R 峰值</span>
          <strong class="up">+{{ rCurveMdd.peakR.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">報酬回撤比 (R) <InfoTooltip label="報酬回撤比（R 版）" text="峰值累計 R ÷ R 曲線最大回撤，類似 Calmar Ratio 但以 R 衡量。越高代表每承受一單位連虧深度能賺到更多 R。" /></span>
          <strong>{{ rCurveMdd.ratio ?? '—' }}</strong>
        </div>
      </div>
      <!-- VV9: 距高水位回撤 -->
      <div v-if="hwmDistance" class="r-curve-stats">
        <div class="rc-stat">
          <span class="rc-label">R 曲線高水位 <InfoTooltip label="權益高水位（HWM）" text="歷史上累計 R 達到的最高點。目前距高水位的回撤 = HWM − 當前累計 R。與 R 曲線最大回撤不同：MDD 是歷史最大值，HWM 距離是「現在」的即時距離，讓你知道是否正在回撤中。" /></span>
          <strong class="up">+{{ hwmDistance.hwm.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">目前距高水位</span>
          <strong :class="hwmDistance.atHwm ? 'up' : hwmDistance.drawdown > 2 ? 'down' : 'warn'">
            {{ hwmDistance.atHwm ? '在高水位' : '-' + hwmDistance.drawdown.toFixed(1) + 'R' }}
          </strong>
        </div>
      </div>
      <!-- UU6: 近20日波動率相對歷史警示 -->
      <div v-if="volatilityRegime" class="r-curve-stats vol-regime-row">
        <div class="rc-stat">
          <span class="rc-label">近20日波動率 vs 歷史均值 <InfoTooltip label="系統波動率比值" text="近20個交易日的日損益標準差，相對於全部歷史均值的倍數。≥ 1.5× 代表系統近期處於高波動狀態——Van Tharp 建議此時縮減倉位至標準的 50%，降低高波動期被連續大虧洗出的機率。" /></span>
          <strong :class="volatilityRegime.elevated ? 'warn' : 'up'">{{ volatilityRegime.ratio.toFixed(1) }}×</strong>
        </div>
        <div class="rc-stat" v-if="volatilityRegime.elevated">
          <span class="rc-label vol-warn-msg">⚠ 高波動期 — 建議縮減倉位至標準的 50%</span>
        </div>
      </div>
      <!-- WW9: 月報酬統計（機構月 P&L 剖面） -->
      <div v-if="monthlyReturnStats" class="r-curve-stats">
        <div class="rc-stat">
          <span class="rc-label">月報酬中位數 <InfoTooltip label="月報酬中位數 R" text="機構 P&L 評核：月為標準績效週期。中位數比平均更能代表典型月份，不被異常月拉偏。" /></span>
          <strong :class="monthlyReturnStats.median >= 0 ? 'up' : 'down'">{{ monthlyReturnStats.median >= 0 ? '+' : '' }}{{ monthlyReturnStats.median.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">月報酬標準差</span>
          <strong>{{ monthlyReturnStats.std.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">正報酬月比率</span>
          <strong :class="monthlyReturnStats.posMonthPct >= 60 ? 'up' : monthlyReturnStats.posMonthPct >= 40 ? 'warn' : 'down'">
            {{ monthlyReturnStats.posMonthPct.toFixed(0) }}%（{{ monthlyReturnStats.posMonths }}/{{ monthlyReturnStats.totalMonths }} 月）
          </strong>
        </div>
      </div>
      <!-- XX7: 回撤週期追蹤器（Richard Dennis/Turtle） -->
      <div v-if="drawdownEpisodes" class="r-curve-stats dd-episode-block">
        <div class="rc-stat rc-stat--full">
          <span class="rc-label">回撤週期追蹤（Dennis/Turtle：系統強健的指標是能快速恢復）</span>
        </div>
        <div class="rc-stat">
          <span class="rc-label">歷史回撤次數</span>
          <strong>{{ drawdownEpisodes.total }} 次</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">平均恢復筆數</span>
          <strong :class="drawdownEpisodes.avgRecovery > 10 ? 'warn' : 'up'">{{ drawdownEpisodes.avgRecovery.toFixed(1) }} 筆</strong>
        </div>
        <div class="dd-episode-table-wrap">
          <table class="j-table xx-dd-table">
            <thead><tr><th>回撤深度</th><th>恢復筆數</th></tr></thead>
            <tbody>
              <tr v-for="(ep, i) in drawdownEpisodes.episodes" :key="i">
                <td :class="ep.depth > 3 ? 'down' : 'warn'">-{{ ep.depth.toFixed(1) }}R</td>
                <td>{{ ep.recoveryTrades }} 筆</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- YY8: 期望值三階段分析（Bruce Kovner） -->
    <section class="card chart-card" v-if="expectancyPhases">
      <div class="section-header">
        <div>
          <h2>期望值成長軌跡</h2>
          <p class="chart-sub">Kovner：持續追蹤早期→中期→近期期望值，確認系統是否在改善中。</p>
        </div>
        <span class="rc-label" :class="expectancyPhases.improving ? 'up' : 'down'">
          {{ expectancyPhases.improving ? '↑ 進步中' : '↓ 退步中' }}（{{ expectancyPhases.trend >= 0 ? '+' : '' }}{{ expectancyPhases.trend.toFixed(2) }}R）
        </span>
      </div>
      <div class="yy-phase-row">
        <div v-for="ph in expectancyPhases.phases" :key="ph.label" class="yy-phase-col">
          <span class="rc-label">{{ ph.label }}</span>
          <strong :class="ph.mean >= 0 ? 'up' : 'down'">{{ ph.mean >= 0 ? '+' : '' }}{{ ph.mean.toFixed(2) }}R</strong>
          <span class="muted" style="font-size:0.75rem">{{ ph.count }} 筆</span>
        </div>
      </div>
    </section>

    <!-- YY9: 權益曲線平滑度 R²（Ed Seykota） -->
    <section class="card chart-card" v-if="equityCurveR2">
      <div class="section-header">
        <div>
          <h2>權益曲線平滑度（R²）</h2>
          <p class="chart-sub">Seykota：穩定系統的累積 R 曲線應接近直線向上；R² 越高越平滑穩定。</p>
        </div>
      </div>
      <div class="r-curve-stats">
        <div class="rc-stat">
          <span class="rc-label">R²</span>
          <strong :class="equityCurveR2.cls">{{ equityCurveR2.r2.toFixed(3) }}</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">平滑度評級</span>
          <strong :class="equityCurveR2.cls">{{ equityCurveR2.label }}</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">趨勢斜率</span>
          <strong :class="equityCurveR2.slope >= 0 ? 'up' : 'down'">{{ equityCurveR2.slope >= 0 ? '+' : '' }}{{ equityCurveR2.slope.toFixed(3) }}R/筆</strong>
        </div>
      </div>
      <p class="chart-sub" style="margin-top:0.5rem; padding: 0 1rem 0.75rem">R² ≥ 0.9 平滑，0.7-0.9 中等，&lt; 0.7 不穩定（高雜訊/高波動）。</p>
    </section>

    <!-- ZZ7: Ed Seykota — Tag × Month Performance Heatmap -->
    <section class="card chart-card zz-tag-month" v-if="tagMonthHeatmap">
      <div class="section-header">
        <div>
          <h2>策略×月份績效熱圖</h2>
          <p class="chart-sub">Seykota：了解系統在不同季節與策略標籤下的交互作用，強化在最佳制度的曝露。</p>
        </div>
      </div>
      <div style="overflow-x:auto; padding: 0 1rem 1rem">
        <table class="zz-heatmap-table">
          <thead>
            <tr>
              <th class="muted" style="text-align:left; font-size:0.7rem; padding-right:8px">標籤\月</th>
              <th v-for="m in tagMonthHeatmap.months" :key="m" class="muted" style="font-size:0.68rem">{{ m }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tagMonthHeatmap.rows" :key="row.tag">
              <td class="muted" style="font-size:0.75rem; white-space:nowrap; padding-right:8px; text-align:left">{{ row.tag }}</td>
              <td v-for="(cell, idx) in row.cells" :key="idx" class="zz-heatmap-cell"
                  :class="cell ? (cell.avg > 0.5 ? 'zz-heat-hot' : cell.avg > 0 ? 'zz-heat-warm' : 'zz-heat-cold') : 'zz-heat-empty'">
                <span v-if="cell" style="font-size:0.68rem">{{ cell.avg > 0 ? '+' : '' }}{{ cell.avg.toFixed(1) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ZZ8: Richard Dennis — Forward Loss Scenario Planning -->
    <section class="card chart-card zz-forward-loss" v-if="forwardLossScenario">
      <div class="section-header">
        <div>
          <h2>連虧情境推演</h2>
          <p class="chart-sub">Dennis/Turtle：永遠先思考最壞情況再進場，預演連虧衝擊有助保持心理準備。</p>
        </div>
      </div>
      <div class="r-curve-stats" style="padding: 0 1rem 0.5rem; flex-wrap: wrap; gap: 1rem">
        <div v-for="s in forwardLossScenario.scenarios" :key="s.n" class="rc-stat">
          <span class="rc-label">連虧 {{ s.n }} 筆</span>
          <strong class="down">-{{ s.drawdown.toFixed(1) }}R</strong>
        </div>
        <div class="rc-stat">
          <span class="rc-label">歷史最長連虧</span>
          <strong>{{ forwardLossScenario.maxStreak }} 筆</strong>
        </div>
      </div>
      <p class="chart-sub" style="padding: 0 1rem 0.75rem">平均部位 {{ forwardLossScenario.avgLots }} 張，以每筆 -1R×張數估算連虧損失。</p>
    </section>

    <!-- ZZ10: Jack Schwager — Composite Wizard Score -->
    <section class="card chart-card zz-wizard-score" v-if="wizardScore">
      <div class="section-header">
        <div>
          <h2>綜合向導分數（Schwager）</h2>
          <p class="chart-sub">市場向導共同特質：SQN 品質 + 曲線平滑 + 恢復力 + 右尾特性 + 月度一致性</p>
        </div>
        <div class="rc-stat" style="text-align:right; align-items:flex-end">
          <span class="rc-label">{{ wizardScore.label }}</span>
          <strong :class="wizardScore.total >= 60 ? 'up' : 'warn'" style="font-size:1.5rem">{{ wizardScore.total }}</strong>
        </div>
      </div>
      <div class="zz-wizard-bars">
        <div v-for="c in wizardScore.components" :key="c.name" class="zz-wizard-row">
          <span class="rc-label" style="min-width:72px; font-size:0.72rem">{{ c.name }}</span>
          <div class="zz-wizard-bar-bg">
            <div class="zz-wizard-bar-fill" :style="{ width: (c.score / c.max * 100) + '%' }"></div>
          </div>
          <span class="muted" style="font-size:0.72rem; min-width:36px; text-align:right">{{ c.score }}/{{ c.max }}</span>
        </div>
      </div>
    </section>

    <!-- AAA9: Monroe Trout — Monthly Return Volatility -->
    <section class="card chart-card aaa-monthly-vol" v-if="monthlyReturnVol">
      <div class="section-header">
        <div>
          <h2>月收益波動性（Trout）</h2>
          <p class="chart-sub">每月累計 R 的標準差——一致性是專業交易員的基礎特質</p>
        </div>
        <div style="display:flex;gap:1rem;align-items:center">
          <div class="rc-stat" style="text-align:right">
            <span class="rc-label">月 R 標準差</span>
            <strong :class="monthlyReturnVol.std <= 1 ? 'up' : monthlyReturnVol.std <= 2 ? 'warn' : 'down'" style="font-size:1.4rem">
              {{ monthlyReturnVol.std.toFixed(2) }}R
            </strong>
          </div>
          <div class="rc-stat" style="text-align:right">
            <span class="rc-label">月均 R</span>
            <strong :class="monthlyReturnVol.mean >= 0 ? 'up' : 'down'">{{ monthlyReturnVol.mean >= 0 ? '+' : '' }}{{ monthlyReturnVol.mean.toFixed(2) }}R</strong>
          </div>
        </div>
      </div>
      <div style="display:flex;gap:0.75rem;flex-wrap:wrap;padding:0 1rem 1rem">
        <div v-for="m in monthlyReturnVol.months" :key="m.key" class="yy-phase-col" style="min-width:72px">
          <span class="muted" style="font-size:0.65rem">{{ m.key }}</span>
          <strong :class="m.total >= 0 ? 'up' : 'down'" style="font-size:0.85rem">{{ m.total >= 0 ? '+' : '' }}{{ m.total.toFixed(1) }}R</strong>
        </div>
      </div>
    </section>

    <!-- AAA10: Curtis Faith 海龜 — System Compliance Rate -->
    <section class="card chart-card aaa-compliance" v-if="turtleCompliance">
      <div class="section-header">
        <div>
          <h2>系統遵守度（Curtis Faith 海龜）</h2>
          <p class="chart-sub">每筆交易是否按系統設定停損與目標——紀律是可量化的</p>
        </div>
        <div class="rc-stat" style="text-align:right">
          <span class="rc-label">{{ turtleCompliance.stopRate >= 0.9 ? '✓ 高度紀律' : turtleCompliance.stopRate >= 0.7 ? '△ 部分遵守' : '⚠ 紀律不足' }}</span>
          <strong :class="turtleCompliance.stopRate >= 0.9 ? 'up' : turtleCompliance.stopRate >= 0.7 ? 'warn' : 'down'" style="font-size:1.5rem">
            {{ (turtleCompliance.stopRate * 100).toFixed(0) }}%
          </strong>
        </div>
      </div>
      <div class="yy-phase-row">
        <div class="yy-phase-col">
          <strong :class="turtleCompliance.stopRate >= 0.9 ? 'up' : 'warn'" style="font-size:1.1rem">{{ (turtleCompliance.stopRate * 100).toFixed(0) }}%</strong>
          <span class="muted" style="font-size:0.72rem">有設停損率</span>
          <span class="muted" style="font-size:0.65rem">{{ turtleCompliance.nStop }}/{{ turtleCompliance.total }}</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="turtleCompliance.targetRate >= 0.9 ? 'up' : 'warn'" style="font-size:1.1rem">{{ (turtleCompliance.targetRate * 100).toFixed(0) }}%</strong>
          <span class="muted" style="font-size:0.72rem">有設目標率</span>
          <span class="muted" style="font-size:0.65rem">{{ turtleCompliance.nTarget }}/{{ turtleCompliance.total }}</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="turtleCompliance.bothRate >= 0.9 ? 'up' : 'warn'" style="font-size:1.1rem">{{ (turtleCompliance.bothRate * 100).toFixed(0) }}%</strong>
          <span class="muted" style="font-size:0.72rem">兩者齊備率</span>
        </div>
      </div>
    </section>

    <!-- BBB2: Jim Simons — Statistical Edge Decay Detection -->
    <section class="card chart-card bbb-edge-decay" v-if="edgeDecay">
      <div class="section-header">
        <div>
          <h2>統計優勢衰退偵測（Simons）</h2>
          <p class="chart-sub">最近10筆均值R vs 歷史均值R——系統優勢是否正在衰退？</p>
        </div>
        <div style="display:flex;gap:1rem">
          <div class="rc-stat" style="text-align:right">
            <span class="rc-label">歷史均值 R</span>
            <strong :class="edgeDecay.overall >= 0 ? 'up' : 'down'">{{ edgeDecay.overall >= 0 ? '+' : '' }}{{ edgeDecay.overall.toFixed(3) }}</strong>
          </div>
          <div class="rc-stat" style="text-align:right">
            <span class="rc-label">近10筆均值 R</span>
            <strong :class="edgeDecay.recentAvg >= 0 ? 'up' : 'down'" style="font-size:1.3rem">{{ edgeDecay.recentAvg >= 0 ? '+' : '' }}{{ edgeDecay.recentAvg.toFixed(3) }}</strong>
          </div>
        </div>
      </div>
      <div class="yy-phase-row">
        <div class="yy-phase-col">
          <strong :class="edgeDecay.trend >= 0 ? 'up' : 'down'" style="font-size:1.1rem">{{ edgeDecay.trend >= 0 ? '+' : '' }}{{ edgeDecay.trend.toFixed(3) }}</strong>
          <span class="muted" style="font-size:0.72rem">趨勢差值 (近-歷史)</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="edgeDecay.decaying ? 'down' : 'up'" style="font-size:1.1rem">{{ edgeDecay.decaying ? '⚠ 衰退' : '✓ 穩定' }}</strong>
          <span class="muted" style="font-size:0.72rem">優勢狀態</span>
        </div>
      </div>
    </section>

    <!-- BBB5: Dennis Gartman — Max Single Loss Control -->
    <section class="card chart-card bbb-max-loss-control" v-if="maxLossControl">
      <div class="section-header">
        <div>
          <h2>最大單筆損失控制（Gartman）</h2>
          <p class="chart-sub">你的最大單筆損失是平均贏單的幾倍？——Gartman：永遠不讓任何一筆損失失控</p>
        </div>
        <div class="rc-stat" style="text-align:right">
          <span class="rc-label">{{ maxLossControl.controlled ? '✓ 尾部受控' : '⚠ 損失失控' }}</span>
          <strong :class="maxLossControl.controlled ? 'up' : 'down'" style="font-size:1.5rem">{{ maxLossControl.ratio.toFixed(2) }}×</strong>
        </div>
      </div>
      <div class="yy-phase-row">
        <div class="yy-phase-col">
          <strong class="down">{{ maxLossControl.maxLoss.toFixed(2) }}R</strong>
          <span class="muted" style="font-size:0.72rem">最大單筆損失</span>
        </div>
        <div class="yy-phase-col">
          <strong class="up">+{{ maxLossControl.avgWin.toFixed(2) }}R</strong>
          <span class="muted" style="font-size:0.72rem">平均贏單 R</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="maxLossControl.controlled ? 'up' : 'down'">{{ maxLossControl.ratio.toFixed(2) }}×</strong>
          <span class="muted" style="font-size:0.72rem">損失/贏單比</span>
          <span class="muted" style="font-size:0.65rem">（≤2× 為受控）</span>
        </div>
      </div>
    </section>

    <!-- BBB8: Joel Greenblatt — Losing Streak Recovery Speed -->
    <section class="card chart-card bbb-recovery-speed" v-if="recoverySpeed">
      <div class="section-header">
        <div>
          <h2>最長虧損期回復速度（Greenblatt）</h2>
          <p class="chart-sub">系統從最長連虧期恢復需要幾筆交易？——韌性是可以量化的</p>
        </div>
        <div class="rc-stat" style="text-align:right">
          <span class="rc-label">最長連虧</span>
          <strong class="down" style="font-size:1.5rem">{{ recoverySpeed.maxStreak }}連虧</strong>
        </div>
      </div>
      <div class="yy-phase-row">
        <div class="yy-phase-col">
          <strong class="down">{{ recoverySpeed.streakLoss.toFixed(1) }}R</strong>
          <span class="muted" style="font-size:0.72rem">連虧期損失</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="recoverySpeed.recovered ? 'up' : 'warn'" style="font-size:1.1rem">
            {{ recoverySpeed.recovered ? recoverySpeed.recoveryTrades + '筆' : '未回復' }}
          </strong>
          <span class="muted" style="font-size:0.72rem">回復所需筆數</span>
        </div>
        <div class="yy-phase-col">
          <strong :class="recoverySpeed.recovered && recoverySpeed.recoveryTrades <= recoverySpeed.maxStreak ? 'up' : 'warn'">
            {{ recoverySpeed.recovered ? (recoverySpeed.recoveryTrades <= recoverySpeed.maxStreak ? '✓ 快速回彈' : '△ 慢速回彈') : '⚠ 仍在回復中' }}
          </strong>
          <span class="muted" style="font-size:0.72rem">韌性評級</span>
        </div>
      </div>
    </section>

    <!-- BBB9: Larry Hite — Open Position Worst-Case Loss -->
    <section class="card chart-card bbb-open-worstcase" v-if="openWorstCase">
      <div class="section-header">
        <div>
          <h2>開倉最大損失情境（Hite）</h2>
          <p class="chart-sub">若所有開倉都停損，最大損失是多少？——Hite：永遠知道你的最大可能損失</p>
        </div>
        <div class="rc-stat" style="text-align:right">
          <span class="rc-label">現有開倉（{{ openWorstCase.positions }}筆）</span>
          <strong class="down" style="font-size:1.4rem">-{{ openWorstCase.worstCase.toFixed(0) }}</strong>
        </div>
      </div>
      <div class="yy-phase-row" v-if="openWorstCase.avgHistoricalLossR !== null">
        <div class="yy-phase-col">
          <strong class="down">{{ openWorstCase.avgHistoricalLossR.toFixed(2) }}R</strong>
          <span class="muted" style="font-size:0.72rem">歷史平均虧損 R</span>
        </div>
        <div class="yy-phase-col">
          <strong class="muted">{{ openWorstCase.positions }}個部位</strong>
          <span class="muted" style="font-size:0.72rem">已設停損</span>
        </div>
      </div>
    </section>

    <!-- CCC4: Stan Weinstein — Rolling Win Rate Trajectory -->
    <section class="card chart-card ccc-rollwinrate" v-if="rollingWinTrend">
      <div class="section-header">
        <div>
          <h2>勝率趨勢軌跡（Weinstein 階段分析）</h2>
          <p>首10筆 vs 最近10筆滾動勝率——你的系統是否持續進化？</p>
        </div>
      </div>
      <div style="display:flex;gap:2rem;flex-wrap:wrap;padding:0.5rem 0;align-items:center">
        <div style="text-align:center">
          <strong style="font-size:1.5rem">{{ (rollingWinTrend.first10WinPct * 100).toFixed(0) }}%</strong>
          <div class="muted" style="font-size:0.72rem">首10筆勝率</div>
        </div>
        <div style="font-size:1.5rem;opacity:0.4">→</div>
        <div style="text-align:center">
          <strong :class="rollingWinTrend.improving ? 'up' : 'down'" style="font-size:1.5rem">{{ (rollingWinTrend.last10WinPct * 100).toFixed(0) }}%</strong>
          <div class="muted" style="font-size:0.72rem">最近10筆勝率</div>
        </div>
        <div :class="rollingWinTrend.improving ? 'up' : 'down'" style="font-size:0.8rem">
          {{ rollingWinTrend.improving ? '▲ 勝率上升，系統持續進化' : '▼ 勝率下降，需檢視入場條件是否退化' }}
        </div>
      </div>
    </section>

    <!-- CCC5: Ed Seykota — Consecutive Loss Streak Frequency -->
    <section class="card chart-card ccc-streakfreq" v-if="streakFrequency">
      <div class="section-header">
        <div>
          <h2>連虧頻率分布（Seykota 損失控制）</h2>
          <p>不同長度連虧序列出現次數——過多長串連虧是風控警號</p>
        </div>
      </div>
      <div style="display:flex;gap:1rem;flex-wrap:wrap;padding:0.5rem 0;align-items:flex-end">
        <div v-for="b in streakFrequency.buckets" :key="b.label" style="text-align:center;min-width:60px">
          <strong :class="(b.label === '5+連虧' && b.count > 1) || (b.label === '4連虧' && b.count > 2) ? 'down' : ''" style="font-size:1.2rem">{{ b.count }}</strong>
          <div class="muted" style="font-size:0.72rem">{{ b.label }}</div>
        </div>
      </div>
      <div class="muted" style="font-size:0.72rem;margin-top:0.25rem">
        {{ streakFrequency.totalStreaks }}次連虧事件；最長 {{ streakFrequency.maxStreak }} 連虧
        <span v-if="streakFrequency.buckets[4].count > 1" class="down">　⚠ 5+連虧出現超過1次，入場條件可能在特定市況下失效</span>
      </div>
    </section>

    <!-- CCC8: Van Tharp — System Quality Number -->
    <section class="card chart-card ccc-sqn" v-if="sqn">
      <div class="section-header">
        <div>
          <h2>系統品質指數 SQN（Van Tharp）</h2>
          <p>SQN = √n × 均值R / 標準差R；> 2.0 優秀，> 1.6 良好，> 1.0 可交易，&lt; 1.0 不穩定</p>
        </div>
      </div>
      <div style="display:flex;gap:2rem;flex-wrap:wrap;padding:0.5rem 0;align-items:center">
        <div style="text-align:center">
          <strong :class="sqn.rating === '優秀' || sqn.rating === '良好' ? 'up' : sqn.rating === '可交易' ? '' : 'down'" style="font-size:2rem">{{ sqn.value.toFixed(2) }}</strong>
          <div class="muted" style="font-size:0.72rem">SQN</div>
        </div>
        <div style="text-align:center">
          <strong :class="sqn.rating === '優秀' || sqn.rating === '良好' ? 'up' : sqn.rating === '可交易' ? '' : 'down'" style="font-size:1.2rem">{{ sqn.rating }}</strong>
          <div class="muted" style="font-size:0.72rem">品質評級</div>
        </div>
        <div style="text-align:center">
          <strong style="font-size:1rem">{{ sqn.meanR >= 0 ? '+' : '' }}{{ sqn.meanR.toFixed(2) }}R</strong>
          <div class="muted" style="font-size:0.72rem">均值R</div>
        </div>
        <div style="text-align:center">
          <strong style="font-size:1rem">{{ sqn.stdR.toFixed(2) }}R</strong>
          <div class="muted" style="font-size:0.72rem">標準差R</div>
        </div>
        <div class="muted" style="font-size:0.72rem">n={{ sqn.n }}</div>
      </div>
    </section>

    <section class="card chart-card">
      <div class="section-header">
        <div>
          <h2>權益日變動分布</h2>
          <p>直方圖 + 核密度估計，觀察報酬是否過度偏態或有厚尾風險</p>
        </div>
        <span v-if="hasJournalData" class="badge-estimated">資料來源：交易日誌</span>
      </div>
      <div ref="histEl" class="chart-host"></div>
      <p class="chart-caption">
        參考：D3 gallery - Histogram / Kernel density estimation；資料取自權益曲線期間日變動率（需至少 8 個平倉交易日才會繪製）。
      </p>
    </section>
  </div>
</template>

<script setup>
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import MetricScale from '../components/MetricScale.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createChart } from 'lightweight-charts'
import * as d3 from 'd3'
import { useChartTheme } from '../composables/useChartTheme'
import { useJournalRisk } from '../composables/useJournalRisk'
import { tradePnl, realizedR } from '../lib/tradeMath'
import { fetchLivePrices } from '../lib/livePriceCache'

const theme = useChartTheme()
const loading = ref(false)
const chartEl = ref(null)
const histEl = ref(null)
let chart = null

const {
  hasJournalData, equitySeries, mddPercent, dailyTrades, dailyTradeLimit,
  mddWarnPct, mddPausePct, warnTrades, circuitBreaker, circuitBreakerLabel, reload, saveRiskConfig,
  openTrades, unrealizedPnl, closedTrades,
} = useJournalRisk()

// C2 未實現回撤：抓進行中部位的現價（與交易日誌同一個 sizing API），把
// 浮動損益灌回權益曲線，讓 MDD/熔斷即時反映凹單中的風險。best-effort：
// 抓不到價的部位就跳過，全都抓不到則維持只看已實現。
const unrealizedInfo = ref(null) // { priced, total } 供 UI 標示
async function refreshUnrealized() {
  const open = openTrades.value
  if (!open.length) { unrealizedInfo.value = null; return }
  const symbols = [...new Set(open.map(t => t.symbol))]
  const results = await fetchLivePrices(symbols)
  const priced = open.filter(t => results[t.symbol]?.price > 0)
  if (!priced.length) { unrealizedInfo.value = null; unrealizedPnl.value = null; return }
  const total = priced.reduce((a, t) => a + tradePnl(t, results[t.symbol].price), 0)
  unrealizedPnl.value = total
  unrealizedInfo.value = { priced: priced.length, total }
}

const returnSeries = computed(() => computeReturns(equitySeries.value))

// VV9: 距權益高水位（HWM）回撤（機構基金標準監控指標）
// 顯示目前累計 R 離歷史高點差幾 R，讓使用者即時感知是否正在回撤中
const hwmDistance = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  let cum = 0, hwm = 0
  for (const t of sorted) {
    const r = realizedR(t)
    cum += r
    if (cum > hwm) hwm = cum
  }
  if (hwm <= 0) return null
  const drawdown = hwm - cum
  return { hwm, current: cum, drawdown, atHwm: drawdown < 0.01 }
})

// UU6: 近20日波動率 vs 全歷史比值
// Van Tharp: 當系統進入高波動狀態，縮減至半標準倉位可保護資金曲線
const volatilityRegime = computed(() => {
  const rets = returnSeries.value
  if (rets.length < 25) return null
  const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length
  const std = (arr) => { const m = mean(arr); return Math.sqrt(arr.reduce((a, r) => a + (r - m) ** 2, 0) / arr.length) }
  const allStd = std(rets)
  if (!allStd) return null
  const recent = rets.slice(-20)
  const recentStd = std(recent)
  const ratio = recentStd / allStd
  return { ratio, recentStd: recentStd.toFixed(2), allStd: allStd.toFixed(2), elevated: ratio >= 1.5 }
})

// WW9: 月報酬統計（機構 P&L 剖面：中位數、標準差、正月比率）
// 機構以月為標準績效評估週期；正月比率 ≥ 60% = 穩定系統，< 40% = 高波動警告
const monthlyReturnStats = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 6) return null
  const byMonth = {}
  for (const t of cl) {
    const mo = String(t.exitDate).slice(0, 7) // YYYY-MM
    if (!byMonth[mo]) byMonth[mo] = 0
    byMonth[mo] += realizedR(t)
  }
  const months = Object.values(byMonth)
  if (months.length < 3) return null
  const sorted = [...months].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  const mean = months.reduce((a, b) => a + b, 0) / months.length
  const std = Math.sqrt(months.reduce((a, v) => a + (v - mean) ** 2, 0) / months.length)
  const posMonths = months.filter(r => r > 0).length
  return { median, std, posMonthPct: posMonths / months.length * 100, posMonths, totalMonths: months.length }
})

// XX7: 回撤週期追蹤器（Richard Dennis/Turtle Trading: 系統要能快速從回撤中恢復）
// 識別每段回撤的深度（R）、進入時的累計筆數、恢復所需筆數
const drawdownEpisodes = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 8) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const episodes = []
  let cum = 0, peak = 0, inDD = false, ddStart = 0, ddDepth = 0, ddStartIdx = 0
  for (let i = 0; i < sorted.length; i++) {
    cum += realizedR(sorted[i])
    if (cum > peak) {
      if (inDD) {
        episodes.push({ depth: ddDepth, entryIdx: ddStartIdx, recoveryTrades: i - ddStartIdx, peakR: peak })
        inDD = false
      }
      peak = cum
    } else if (peak > 0 && !inDD) {
      inDD = true
      ddStart = cum
      ddStartIdx = i
      ddDepth = peak - cum
    } else if (inDD) {
      ddDepth = Math.max(ddDepth, peak - cum)
    }
  }
  if (inDD && ddDepth > 0) episodes.push({ depth: ddDepth, entryIdx: ddStartIdx, recoveryTrades: sorted.length - ddStartIdx, peakR: peak })
  if (!episodes.length) return null
  const top5 = [...episodes].sort((a, b) => b.depth - a.depth).slice(0, 5)
  const avgRecovery = episodes.reduce((a, e) => a + e.recoveryTrades, 0) / episodes.length
  return { episodes: top5, avgRecovery, total: episodes.length }
})

// YY8: 期望值三階段分析（Bruce Kovner：持續追蹤系統是否在改善，以早中近三段期望值為指標）
const expectancyPhases = computed(() => {
  const cl = [...closedTrades.value]
    .filter(t => t.exitDate)
    .sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  if (cl.length < 9) return null
  const n = Math.floor(cl.length / 3)
  const phases = [cl.slice(0, n), cl.slice(n, 2 * n), cl.slice(2 * n)].map((ts, i) => {
    const Rs = ts.map(realizedR)
    return { label: ['早期', '中期', '近期'][i], mean: Rs.reduce((a, b) => a + b, 0) / Rs.length, count: Rs.length }
  })
  const trend = phases[2].mean - phases[0].mean
  return { phases, improving: trend > 0, trend }
})

// YY9: 權益曲線平滑度 R²（Seykota：好系統的 equity curve 接近直線向上；R² 越近 1 越平滑）
const equityCurveR2 = computed(() => {
  const cl = [...closedTrades.value]
    .filter(t => t.exitDate)
    .sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  if (cl.length < 10) return null
  const pts = [0]
  let cum = 0
  for (const t of cl) { cum += realizedR(t); pts.push(cum) }
  const n = pts.length
  const meanX = (n - 1) / 2
  const meanY = pts.reduce((a, b) => a + b, 0) / n
  let ssXY = 0, ssXX = 0, ssTot = 0
  for (let i = 0; i < n; i++) {
    ssXY += (i - meanX) * (pts[i] - meanY)
    ssXX += (i - meanX) ** 2
    ssTot += (pts[i] - meanY) ** 2
  }
  if (ssXX === 0 || ssTot === 0) return null
  const slope = ssXY / ssXX
  const intercept = meanY - slope * meanX
  let ssRes = 0
  for (let i = 0; i < n; i++) ssRes += (pts[i] - (slope * i + intercept)) ** 2
  const r2 = Math.max(0, 1 - ssRes / ssTot)
  const cls = r2 >= 0.9 ? 'up' : r2 >= 0.7 ? 'warn' : 'down'
  const label = r2 >= 0.9 ? '平滑' : r2 >= 0.7 ? '中等' : '不穩定'
  return { r2, slope, cls, label }
})

// ZZ7: 策略×月份績效熱圖（Ed Seykota：識別哪些策略標籤在哪些月份有優勢，在最佳組合加大曝露）
const tagMonthHeatmap = computed(() => {
  const trades = closedTrades.value.filter(t => t.exitDate && t.tag)
  if (trades.length < 10) return null
  const tags = [...new Set(trades.map(t => t.tag))].sort()
  if (tags.length < 2) return null
  const monthNums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
  const grid = {}
  tags.forEach(tag => { grid[tag] = {}; monthNums.forEach(m => { grid[tag][m] = [] }) })
  trades.forEach(t => {
    const m = new Date(t.exitDate).getMonth() + 1
    if (grid[t.tag]) grid[t.tag][m].push(realizedR(t))
  })
  const activeMonths = monthNums.filter(m => tags.some(tag => grid[tag][m].length > 0))
  if (activeMonths.length < 2) return null
  const rows = tags.map(tag => ({
    tag,
    cells: activeMonths.map(m => {
      const arr = grid[tag][m]
      return arr.length ? { avg: arr.reduce((a, b) => a + b, 0) / arr.length, n: arr.length } : null
    }),
  }))
  return { rows, months: activeMonths.map(String) }
})

// ZZ8: 連虧情境推演（Richard Dennis：永遠先計算最壞情況，讓自己在面對連虧時保持冷靜而非驚慌）
const forwardLossScenario = computed(() => {
  const trades = closedTrades.value
  if (trades.length < 5) return null
  const avgLots = trades.reduce((a, t) => a + (t.lots || 1), 0) / trades.length
  const scenarios = [3, 5, 10].map(n => ({ n, drawdown: n * avgLots }))
  const sorted = [...trades].filter(t => t.exitDate)
    .sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  let maxStreak = 0, streak = 0
  sorted.forEach(t => {
    if (realizedR(t) < 0) { streak++; maxStreak = Math.max(maxStreak, streak) }
    else streak = 0
  })
  return { scenarios, maxStreak, avgLots: Math.round(avgLots * 10) / 10 }
})

// ZZ10: 綜合向導分數（Jack Schwager：市場向導的共通特質可量化為複合指標，追蹤整體系統成熟度）
const wizardScore = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 20) return null
  const Rs = cl.map(realizedR)
  const N = Math.min(Rs.length, 100)
  const mean = Rs.reduce((a, b) => a + b, 0) / Rs.length
  const variance = Rs.reduce((a, b) => a + (b - mean) ** 2, 0) / Rs.length
  const sqn = variance > 0 ? mean / Math.sqrt(variance) * Math.sqrt(N) : 0
  const sqnScore = Math.min(30, Math.max(0, sqn * 10))

  const sorted2 = [...cl].filter(t => t.exitDate)
    .sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  let cumR2 = 0
  const cumRs2 = sorted2.map(t => { cumR2 += realizedR(t); return cumR2 })
  const n2 = cumRs2.length
  const xMean2 = (n2 - 1) / 2
  const yMean2 = cumRs2.reduce((a, b) => a + b, 0) / n2
  let ssXY2 = 0, ssXX2 = 0, ssTot2 = 0
  cumRs2.forEach((y, x) => { ssXY2 += (x - xMean2) * (y - yMean2); ssXX2 += (x - xMean2) ** 2; ssTot2 += (y - yMean2) ** 2 })
  const slope2 = ssXX2 ? ssXY2 / ssXX2 : 0
  const intercept2 = yMean2 - slope2 * xMean2
  const ssRes2 = cumRs2.reduce((s, y, x) => s + (y - (slope2 * x + intercept2)) ** 2, 0)
  const r2val = ssTot2 > 0 ? Math.max(0, 1 - ssRes2 / ssTot2) : 0
  const r2Score = Math.min(20, Math.max(0, r2val * 20))

  let peak2 = 0, maxDD2 = 0
  cumRs2.forEach(r => { if (r > peak2) peak2 = r; maxDD2 = Math.max(maxDD2, peak2 - r) })
  const rf = maxDD2 > 0 ? cumR2 / maxDD2 : (cumR2 > 0 ? 5 : 0)
  const rfScore = Math.min(20, Math.max(0, rf * 4))

  const wins2 = Rs.filter(r => r > 0).sort((a, b) => b - a)
  let outlierScore = 0
  if (wins2.length >= 3) {
    const topN2 = Math.max(1, Math.ceil(wins2.length * 0.1))
    const topSum2 = wins2.slice(0, topN2).reduce((a, b) => a + b, 0)
    const totalGross2 = wins2.reduce((a, b) => a + b, 0)
    const pct2 = totalGross2 > 0 ? topSum2 / totalGross2 : 0
    outlierScore = Math.min(15, Math.max(0, pct2 * 37.5))
  }

  const byMonth2 = {}
  cl.filter(t => t.exitDate).forEach(t => {
    const key = t.exitDate.slice(0, 7)
    if (!byMonth2[key]) byMonth2[key] = []
    byMonth2[key].push(realizedR(t))
  })
  const monthArr2 = Object.values(byMonth2)
  const posMonths2 = monthArr2.filter(arr => arr.reduce((a, b) => a + b, 0) > 0).length
  const monthWinRate2 = monthArr2.length ? posMonths2 / monthArr2.length : 0
  const monthScore = Math.min(15, Math.max(0, monthWinRate2 * 21.4))

  const total = sqnScore + r2Score + rfScore + outlierScore + monthScore
  const label = total >= 80 ? 'Exceptional' : total >= 60 ? 'Proficient' : total >= 40 ? 'Competent' : 'Developing'
  return {
    total: Math.round(total), label,
    components: [
      { name: 'SQN 品質', score: Math.round(sqnScore), max: 30 },
      { name: 'R² 平滑度', score: Math.round(r2Score), max: 20 },
      { name: '恢復係數', score: Math.round(rfScore), max: 20 },
      { name: '離群貢獻', score: Math.round(outlierScore), max: 15 },
      { name: '正報月率', score: Math.round(monthScore), max: 15 },
    ],
  }
})

// AAA9: 月收益波動性（Monroe Trout：穩定的月度收益是頂尖 CTA 的核心特徵，std 越低代表系統越一致）
const monthlyReturnVol = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 8) return null
  const byMonth = {}
  cl.forEach(t => {
    const key = t.exitDate.slice(0, 7)
    if (!byMonth[key]) byMonth[key] = 0
    byMonth[key] += realizedR(t)
  })
  const months = Object.entries(byMonth).sort(([a], [b]) => a.localeCompare(b)).map(([key, total]) => ({ key, total }))
  if (months.length < 3) return null
  const totals = months.map(m => m.total)
  const mean = totals.reduce((a, b) => a + b, 0) / totals.length
  const std = Math.sqrt(totals.reduce((a, b) => a + (b - mean) ** 2, 0) / totals.length)
  return { months, mean, std }
})

// AAA10: 系統遵守度（Curtis Faith 海龜：Dennis 要求海龜完整記錄每筆交易的停損與目標，紀律是可量化的，不是感覺）
const turtleCompliance = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const hasStop = t => t.stop !== null && t.stop !== undefined && Number(t.stop) !== 0 && Number(t.stop) !== Number(t.entry)
  const hasTarget = t => t.target !== null && t.target !== undefined && Number(t.target) !== 0 && Number(t.target) !== Number(t.entry)
  const nStop = cl.filter(hasStop).length
  const nTarget = cl.filter(hasTarget).length
  const nBoth = cl.filter(t => hasStop(t) && hasTarget(t)).length
  return { nStop, nTarget, nBoth, total: cl.length, stopRate: nStop / cl.length, targetRate: nTarget / cl.length, bothRate: nBoth / cl.length }
})

// BBB2: 統計優勢衰退偵測（Jim Simons：Renaissance 的核心是持續監控統計優勢是否仍然有效——優勢會隨市場適應而消退）
const edgeDecay = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 20) return null
  const sorted = [...cl].filter(t => t.exitDate).sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  const Rs = sorted.map(realizedR)
  const overall = Rs.reduce((a, b) => a + b, 0) / Rs.length
  const recent10 = Rs.slice(-10)
  const recentAvg = recent10.reduce((a, b) => a + b, 0) / recent10.length
  const trend = recentAvg - overall
  return { overall, recentAvg, trend, decaying: trend < -0.1 && recentAvg < overall * 0.7 }
})

// BBB5: 最大單筆損失控制（Dennis Gartman：永遠不讓任何一筆損失失控——若最大損失超過平均贏單2倍，代表停損紀律有問題）
const maxLossControl = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const Rs = cl.map(realizedR)
  const wins = Rs.filter(r => r > 0)
  const losses = Rs.filter(r => r < 0)
  if (!wins.length || !losses.length) return null
  const maxLoss = Math.min(...losses)
  const avgWin = wins.reduce((a, b) => a + b, 0) / wins.length
  const ratio = avgWin > 0 ? Math.abs(maxLoss) / avgWin : Infinity
  return { maxLoss, avgWin, ratio, controlled: ratio <= 2 }
})

// BBB8: 最長虧損期回復速度（Joel Greenblatt：魔法公式的考驗在連虧期——能快速回彈的系統才值得信賴和長期執行）
const recoverySpeed = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 10) return null
  const sorted = [...cl].filter(t => t.exitDate).sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  const Rs = sorted.map(realizedR)
  let maxStreak = 0, currentStreak = 0, maxStreakEnd = -1
  Rs.forEach((r, i) => {
    if (r < 0) { currentStreak++; if (currentStreak > maxStreak) { maxStreak = currentStreak; maxStreakEnd = i } }
    else currentStreak = 0
  })
  if (maxStreak < 2 || maxStreakEnd < 0) return null
  const streakStart = maxStreakEnd - maxStreak + 1
  const streakLoss = Rs.slice(streakStart, maxStreakEnd + 1).reduce((a, b) => a + b, 0)
  let cumR = 0, recoveryTrades = 0, recovered = false
  for (let i = maxStreakEnd + 1; i < Rs.length; i++) {
    cumR += Rs[i]
    recoveryTrades++
    if (cumR >= Math.abs(streakLoss)) { recovered = true; break }
  }
  return { maxStreak, streakLoss, recoveryTrades: recovered ? recoveryTrades : null, recovered }
})

// BBB9: 開倉最大損失情境（Larry Hite：Mint Investment 的核心風控——始終知道你的最大可能損失，不要讓意外損失成為帳戶終結者）
const openWorstCase = computed(() => {
  const open = openTrades.value.filter(t => t.stop && Number(t.stop) !== 0 && Number(t.stop) !== Number(t.entry))
  if (!open.length) return null
  const worstCase = open.reduce((total, t) => {
    const entry = Number(t.entry), stop = Number(t.stop), lots = Number(t.lots) || 1
    return total + Math.abs(entry - stop) * lots
  }, 0)
  const cl = closedTrades.value
  const lossRs = cl.map(realizedR).filter(r => r < 0)
  const avgHistoricalLossR = lossRs.length >= 3 ? lossRs.reduce((a, b) => a + b, 0) / lossRs.length : null
  return { worstCase, positions: open.length, avgHistoricalLossR: avgHistoricalLossR ? Math.abs(avgHistoricalLossR) : null }
})

// CCC4: 勝率趨勢軌跡（Stan Weinstein：持續改進的系統應有上升的滾動勝率）
const rollingWinTrend = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 20) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const isWin = t => realizedR(t) > 0
  const first10WinPct = sorted.slice(0, 10).filter(isWin).length / 10
  const last10WinPct = sorted.slice(-10).filter(isWin).length / 10
  return { first10WinPct, last10WinPct, improving: last10WinPct > first10WinPct }
})

// CCC5: 連虧頻率分布（Ed Seykota：截斷虧損——頻繁長串連虧是入場時機或執行的系統性問題）
const streakFrequency = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 10) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const Rs = sorted.map(realizedR)
  const buckets = [{ label: '1連虧', count: 0 }, { label: '2連虧', count: 0 }, { label: '3連虧', count: 0 }, { label: '4連虧', count: 0 }, { label: '5+連虧', count: 0 }]
  let streak = 0, maxStreak = 0, totalStreaks = 0
  const flushStreak = () => {
    if (streak > 0) {
      totalStreaks++
      buckets[Math.min(streak, 5) - 1].count++
      streak = 0
    }
  }
  Rs.forEach(r => { if (r < 0) { streak++; if (streak > maxStreak) maxStreak = streak } else flushStreak() })
  flushStreak()
  if (totalStreaks === 0) return null
  return { buckets, totalStreaks, maxStreak }
})

// CCC8: 系統品質指數（Van Tharp SQN = √n × μ/σ；>2.0優秀 >1.6良好 >1.0可交易 <1.0不穩定）
const sqn = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 10) return null
  const Rs = cl.map(realizedR)
  const n = Rs.length
  const mean = Rs.reduce((a, b) => a + b, 0) / n
  const variance = Rs.reduce((a, b) => a + (b - mean) ** 2, 0) / n
  const std = Math.sqrt(variance)
  if (std === 0) return null
  const value = Math.sqrt(n) * mean / std
  const rating = value >= 2.0 ? '優秀' : value >= 1.6 ? '良好' : value >= 1.0 ? '可交易' : '不穩定'
  return { value, meanR: mean, stdR: std, rating, n }
})

// TT8: R 曲線最大回撤（單位：R，跨帳戶大小可比較）
const rCurveMdd = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  let peak = 0, cum = 0, maxDD = 0
  for (const t of sorted) {
    cum += realizedR(t)
    if (cum > peak) peak = cum
    if (peak > 0) maxDD = Math.max(maxDD, peak - cum)
  }
  if (peak <= 0) return null
  const ratio = maxDD > 0 ? (peak / maxDD).toFixed(1) : null
  return { mddR: maxDD, peakR: peak, ratio }
})

const mddValue = computed(() => mddPercent.value / 100)
const circuitStatus = circuitBreaker

// 尺標滿刻度跟圓環刻度用同一個「熔斷門檻 × 1.2」邏輯，兩個視覺化才會對得起來。
const mddScaleMax = computed(() => Math.max(1, mddPausePct.value * 1.2))
const mddZones = computed(() => [
  { to: mddWarnPct.value, tone: 'good' },
  { to: mddPausePct.value, tone: 'warn' },
  { to: mddScaleMax.value, tone: 'bad' },
])
const mddThresholds = computed(() => [
  { value: mddWarnPct.value, label: `${mddWarnPct.value}% 警戒` },
  { value: mddPausePct.value, label: `${mddPausePct.value}% 熔斷` },
])
const mddNarrative = computed(() => {
  const v = mddPercent.value
  if (v >= mddPausePct.value) return `目前回撤 ${formatPercent(mddValue.value)}，已超過熔斷門檻 ${mddPausePct.value}%，系統會暫停新倉，建議先複盤交易日誌。`
  if (v >= mddWarnPct.value) return `目前回撤 ${formatPercent(mddValue.value)}，已達警戒線 ${mddWarnPct.value}%，建議暫緩加碼並檢視部位。`
  return `目前回撤 ${formatPercent(mddValue.value)}，低於警戒線 ${mddWarnPct.value}%，風險在可控範圍。`
})
const tradePercent = computed(() => Math.min(100, Math.round((dailyTrades.value / Math.max(1, dailyTradeLimit.value)) * 100)))

function saveThresholds() {
  saveRiskConfig()
}
const statusDescription = computed(() => {
  if (!hasJournalData.value) return '尚無已平倉交易紀錄，請先在「交易日誌」記錄並平倉交易。'
  if (circuitStatus.value === 'ACTIVE') return '回撤與當日交易次數都在安全範圍內。'
  if (circuitStatus.value === 'WARNING') return '回撤或當日交易次數接近風控上限，建議降低部位或暫緩加碼。'
  if (circuitStatus.value === 'PAUSED') return '回撤或當日交易次數已超過風控上限，建議停止新倉並先複盤交易日誌。'
  return '尚未取得狀態說明。'
})
const gaugeColor = computed(() => {
  if (mddPercent.value >= mddPausePct.value) return theme.down
  if (mddPercent.value >= mddWarnPct.value) return theme.warn
  return theme.up
})
const gaugeStyle = computed(() => {
  // 滿刻度取熔斷門檻的 1.2 倍，讓達門檻時圓環明顯接近全滿。
  const fullScale = Math.max(1, mddPausePct.value * 1.2)
  const percent = Math.min(100, Math.round((mddPercent.value / fullScale) * 100))
  return { background: `conic-gradient(${gaugeColor.value} ${percent}%, ${theme.border} ${percent}% 100%)` }
})

onMounted(async () => {
  window.addEventListener('resize', renderChart)
  window.addEventListener('resize', renderHistogram)
  await loadRiskData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', renderChart)
  window.removeEventListener('resize', renderHistogram)
  if (chart) chart.remove()
})

async function loadRiskData() {
  loading.value = true
  reload()
  await refreshUnrealized()
  await nextTick()
  renderChart()
  renderHistogram()
  loading.value = false
}

// B2 跨分頁同步觸發 reload 後（unrealizedPnl 會被清空），重抓現價。
watch(openTrades, (now, prev) => {
  const key = (arr) => arr.map(t => t.id).join(',')
  if (key(now) !== key(prev || [])) refreshUnrealized()
})

function computeReturns(series) {
  const rets = []
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].value
    const cur = series[i].value
    if (prev > 0) rets.push(((cur - prev) / prev) * 100)
  }
  return rets
}

function renderHistogram() {
  const host = histEl.value
  if (!host) return
  host.innerHTML = ''
  const rets = returnSeries.value
  if (rets.length < 8) {
    host.innerHTML = '<p class="chart-empty">資料點不足，無法繪製分布圖。</p>'
    return
  }

  const width = host.clientWidth || 720
  const height = 300
  const margin = { top: 16, right: 16, bottom: 30, left: 40 }
  const innerW = Math.max(10, width - margin.left - margin.right)
  const innerH = height - margin.top - margin.bottom

  const x = d3.scaleLinear().domain(d3.extent(rets)).nice().range([0, innerW])
  const bins = d3.bin().domain(x.domain()).thresholds(20)(rets)
  const y = d3.scaleLinear().domain([0, d3.max(bins, (b) => b.length) || 1]).nice().range([innerH, 0])

  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height)
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  g.append('g').attr('transform', `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6).tickFormat((v) => `${v}%`)).attr('class', 'axis')
  g.append('g').call(d3.axisLeft(y).ticks(5)).attr('class', 'axis')

  g.selectAll('rect.bin')
    .data(bins)
    .join('rect')
    .attr('class', 'bin')
    .attr('x', (d) => x(d.x0) + 1)
    .attr('width', (d) => Math.max(0, x(d.x1) - x(d.x0) - 1))
    .attr('y', (d) => y(d.length))
    .attr('height', (d) => innerH - y(d.length))
    .attr('fill', 'var(--accent-blue)')
    .attr('fill-opacity', 0.55)

  // KDE overlay, scaled to the same bin-count y-axis for visual comparison.
  const bandwidth = 1.06 * d3.deviation(rets) * Math.pow(rets.length, -0.2) || 0.5
  const kernel = (u) => Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI)
  const xs = d3.range(x.domain()[0], x.domain()[1], (x.domain()[1] - x.domain()[0]) / 100)
  const binWidth = bins[0] ? bins[0].x1 - bins[0].x0 : 1
  const density = xs.map((xv) => {
    const sum = rets.reduce((acc, v) => acc + kernel((xv - v) / bandwidth), 0)
    return { x: xv, y: (sum / (rets.length * bandwidth)) * rets.length * binWidth }
  })
  const kdeLine = d3.line().x((d) => x(d.x)).y((d) => y(d.y)).curve(d3.curveBasis)
  g.append('path')
    .datum(density)
    .attr('fill', 'none')
    .attr('stroke', 'var(--accent-red)')
    .attr('stroke-width', 2)
    .attr('d', kdeLine)

  g.append('line')
    .attr('x1', x(0)).attr('x2', x(0))
    .attr('y1', 0).attr('y2', innerH)
    .attr('stroke', 'var(--border-color)')
    .attr('stroke-dasharray', '3,3')
}

watch(returnSeries, () => nextTick(renderHistogram))
// B2 跨分頁同步：storage 事件觸發 reload 後，權益曲線圖跟著重畫。
watch(equitySeries, () => nextTick(renderChart))

function renderChart() {
  if (!chartEl.value || !equitySeries.value.length) return
  if (chart) chart.remove()
  chart = createChart(chartEl.value, {
    width: chartEl.value.clientWidth || 720,
    height: 320,
    layout: { background: { color: '#0d1117' }, textColor: theme.muted },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
  })
  const lineSeries = chart.addLineSeries({ color: theme.up, lineWidth: 2 })
  lineSeries.setData(equitySeries.value)
  chart.timeScale().fitContent()
}

function formatPercent(unitValue) {
  return `${(unitValue * 100).toFixed(2)}%`
}

function statusClass(status) {
  if (status === 'ACTIVE') return 'is-active'
  if (status === 'WARNING') return 'is-warning'
  if (status === 'PAUSED') return 'is-paused'
  return 'is-neutral'
}
</script>

<style scoped>
.risk-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header,
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-header p,
.section-header p,
.state-body p,
.empty-state {
  color: var(--text-secondary);
}

.top-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.gauge-wrap,
.state-body,
.trade-counter {
  margin-top: 16px;
}

.gauge-wrap {
  display: flex;
  justify-content: center;
}

.mdd-scale { margin-top: 16px; }
.mdd-narrative { font-size: 0.78rem; color: var(--text-secondary); margin: 8px 0 0; line-height: 1.5; }

.gauge {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  padding: 14px;
}

.gauge-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #0d1117;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.gauge-inner strong,
.trade-counter strong {
  font-size: 2rem;
}

.state-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}

.status-pill {
  padding: 6px 12px;
  border-radius: 999px;
  font-weight: 700;
}

.threshold-cfg {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.threshold-cfg label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.cfg-inp {
  width: 58px;
  background: var(--bg-well);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 0.82rem;
}

.is-active {
  background: var(--up-soft);
  color: var(--color-up);
}

.is-warning {
  background: var(--warn-soft);
  color: var(--color-warning);
}

.is-paused {
  background: var(--down-soft);
  color: var(--color-down);
}

.is-neutral {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

.trade-counter {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.counter-track,
.chart-area {
  margin-top: 16px;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.counter-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #2563eb);
}

.chart-area {
  width: 100%;
  min-height: 320px;
  border-radius: 12px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.chart-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
  margin-top: 16px;
}

.chart-wrapper .chart-area {
  flex: 1;
  margin-top: 0;
}

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

/* TT8: R 曲線最大回撤 */
.r-curve-stats { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 14px; padding: 12px 16px; background: var(--bg-well, rgba(15,23,42,0.4)); border: 1px solid var(--border-color); border-radius: 12px; }
.rc-stat { display: flex; flex-direction: column; gap: 4px; }
.rc-label { font-size: 0.74rem; color: var(--text-muted); display: flex; align-items: center; gap: 4px; }
.rc-stat strong { font-size: 1.25rem; }
.vol-warn-msg { color: var(--warn, #f59e0b); font-size: 0.8rem; font-weight: 600; }
.vol-regime-row { border-color: var(--warn, #f59e0b); }

/* YY8/YY9 */
.yy-phase-row { display: flex; gap: 1rem; margin-top: 0.75rem; padding: 0 1rem 0.75rem; }
.yy-phase-col { display: flex; flex-direction: column; flex: 1; align-items: center; gap: 4px; padding: 0.5rem; background: var(--color-surface); border-radius: 6px; text-align: center; }

/* AAA9 AAA10 */
.aaa-monthly-vol, .aaa-compliance { margin-bottom: 0; }
/* BBB2 BBB5 BBB8 BBB9 */
.bbb-edge-decay, .bbb-max-loss-control, .bbb-recovery-speed, .bbb-open-worstcase { margin-bottom: 0; }
/* CCC4 CCC5 CCC8 */
.ccc-rollwinrate, .ccc-streakfreq, .ccc-sqn { margin-bottom: 0; }
/* ZZ7 ZZ8 ZZ10 */
.zz-heatmap-table { border-collapse: collapse; font-size: 0.78rem; }
.zz-heatmap-table th, .zz-heatmap-table td { padding: 4px 6px; text-align: center; border: 1px solid var(--color-surface); }
.zz-heatmap-cell { min-width: 32px; }
.zz-heat-hot { background: rgba(34,197,94,0.4); }
.zz-heat-warm { background: rgba(34,197,94,0.15); }
.zz-heat-cold { background: rgba(239,68,68,0.22); }
.zz-heat-empty { background: transparent; }
.zz-wizard-bars { display: flex; flex-direction: column; gap: 7px; padding: 0 1rem 1rem; }
.zz-wizard-row { display: flex; align-items: center; gap: 8px; }
.zz-wizard-bar-bg { flex: 1; height: 10px; background: var(--color-surface); border-radius: 5px; overflow: hidden; }
.zz-wizard-bar-fill { height: 100%; background: var(--color-up, #22c55e); border-radius: 5px; }

/* XX7 drawdown episode table */
.dd-episode-block { flex-direction: column; }
.rc-stat--full { width: 100%; }
.dd-episode-table-wrap { overflow-x: auto; width: 100%; }
.j-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.j-table th, .j-table td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.j-table th:first-child, .j-table td:first-child { text-align: left; }
.j-table th { color: var(--text-muted); font-weight: 500; font-size: 0.74rem; }
.xx-dd-table td, .xx-dd-table th { font-size: 0.82rem; }

.chart-host { width: 100%; min-height: 300px; margin-top: 16px; }
.chart-host :deep(.axis text) { fill: var(--text-muted); font-size: 0.7rem; }
.chart-host :deep(.axis path),
.chart-host :deep(.axis line) { stroke: var(--border-color); }
.chart-caption { font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; }
.chart-empty { color: var(--text-muted); font-style: italic; font-size: 0.85rem; }

@media (max-width: 1100px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 420px) {
  .risk-page {
    gap: var(--space-3);
  }
  .rule-card,
  .card {
    padding: var(--space-3);
  }
}
</style>
