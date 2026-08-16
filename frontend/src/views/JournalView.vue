<template>
  <div class="journal-view">
    <div class="focus-banner" v-reveal>
      <span class="focus-tag">📓 觀測重點</span>
      系統會從你的實戰學習：記錄每筆進出場，算出<strong>你自己的</strong>勝率、期望值與 R 分布。這才是把工具變成系統的地基。
    </div>

    <!-- 統計總覽 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <div>
          <h2>交易日誌（Trade Journal）</h2>
          <p class="muted">以 R 倍數（每筆風險＝1R）衡量績效，勝率與期望值可回灌部位試算。</p>
        </div>
      </div>
      <div class="stat-cards">
        <div class="scard"><span class="slabel">已平倉筆數</span><strong class="sval">{{ stats.count }}</strong><span class="shint">進行中 {{ openTrades.length }}</span></div>
        <div class="scard"><span class="slabel">勝率</span><strong class="sval">{{ stats.count ? (stats.winRate * 100).toFixed(0) + '%' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">期望值 / 筆</span><strong class="sval" :class="stats.expectancyR >= 0 ? 'up' : 'down'">{{ stats.count ? stats.expectancyR.toFixed(2) + ' R' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">獲利因子 <InfoTooltip v-bind="metricGlossary.profitFactor" /></span><strong class="sval" :class="stats.profitFactor >= 1 ? 'up' : 'down'">{{ stats.count ? fmt(stats.profitFactor) : '—' }}</strong></div>
        <div class="scard"><span class="slabel">累計 R</span><strong class="sval" :class="stats.totalR >= 0 ? 'up' : 'down'">{{ stats.count ? (stats.totalR >= 0 ? '+' : '') + stats.totalR.toFixed(2) + ' R' : '—' }}</strong></div>
        <div class="scard"><span class="slabel">累計損益</span><strong class="sval" :class="stats.totalPnl >= 0 ? 'up' : 'down'">{{ stats.count ? fmtInt(stats.totalPnl) : '—' }}</strong></div>
        <div class="scard"><span class="slabel">最大連虧</span><strong class="sval">{{ stats.count ? stats.maxConsecLoss : '—' }}</strong></div>
        <div class="scard"><span class="slabel">平均獲利 / 虧損</span><strong class="sval">{{ stats.count ? stats.avgWinR.toFixed(2) + ' / ' + stats.avgLossR.toFixed(2) + ' R' : '—' }}</strong></div>
        <!-- UU1: Sortino Ratio -->
        <div class="scard" v-if="sortinoRatio !== null">
          <span class="slabel">Sortino Ratio <InfoTooltip label="Sortino Ratio（下行風險調整報酬）" text="平均 R ÷ 負R標準差。只懲罰下行波動，比 Sharpe 更貼近交易實情。≥ 1.0 代表每承受一單位下行風險能賺到超過 1R 的期望值，屬優秀水準。" /></span>
          <strong class="sval" :class="sortinoRatio === Infinity ? 'up' : sortinoRatio >= 1 ? 'up' : sortinoRatio >= 0 ? 'warn' : 'down'">{{ sortinoRatio === Infinity ? '∞' : sortinoRatio.toFixed(2) }}</strong>
        </div>
        <!-- UU10: 系統健康總分 -->
        <div class="scard health-card" v-if="systemHealth">
          <span class="slabel">系統健康分 <InfoTooltip label="系統績效健康總分" text="五項關鍵指標各 20 分（勝率、期望值、獲利因子、最大連虧、盈虧比），總分反映系統目前的整體健康狀態。80-100 健康，60-79 需留意，< 60 建議停手複盤。" /></span>
          <strong class="sval health-score" :class="systemHealth.score >= 80 ? 'up' : systemHealth.score >= 60 ? 'warn' : 'down'">{{ systemHealth.score }}<span class="health-total">/100</span></strong>
          <div class="health-breakdown">
            <span v-for="item in systemHealth.items" :key="item.label" class="health-dot" :class="item.ok ? 'dot-ok' : 'dot-no'" :title="item.label + '：' + item.detail">●</span>
          </div>
        </div>
        <!-- VV1: 當前連勝/連敗 -->
        <div class="scard" v-if="currentStreak">
          <span class="slabel">當前{{ currentStreak.type === 'win' ? '連勝' : '連敗' }} <InfoTooltip label="當前連勝/連敗條數" text="最後幾筆交易連續同方向的筆數。連敗 ≥ 3 時需警惕「復仇交易」衝動（Mark Douglas：交易是機率遊戲，任何單筆結果都不代表系統能力）。" /></span>
          <strong class="sval" :class="currentStreak.type === 'win' ? 'up' : currentStreak.count >= 3 ? 'down' : 'warn'">{{ currentStreak.count }} 筆</strong>
          <span v-if="currentStreak.type === 'loss' && currentStreak.count >= 3" class="shint down">⚠ 連敗 ≥ 3，避免復仇交易</span>
        </div>
        <!-- VV2: Recovery Factor -->
        <div class="scard" v-if="recoveryFactor">
          <span class="slabel">Recovery Factor <InfoTooltip label="回報回撤比（RF）" text="累計 R ÷ R 曲線最大回撤。CTA 業界標準：> 3 優秀、1-3 尚可、< 1 代表虧損還沒從最大回撤中回復。反映系統彌補虧損的效率。" /></span>
          <strong class="sval" :class="recoveryFactor.rf >= 3 ? 'up' : recoveryFactor.rf >= 1 ? 'warn' : 'down'">{{ recoveryFactor.rf.toFixed(2) }}</strong>
        </div>
        <!-- VV4: 交易頻率 -->
        <div class="scard" v-if="tradeFreqPerWeek">
          <span class="slabel">交易頻率 <InfoTooltip label="平均每週交易筆數" text="已平倉交易總筆數 ÷ 跨越週數。Van Tharp: > 3 筆/週通常是過度交易的信號，降低每筆交易的 R:R 要求並增加噪音進場。" /></span>
          <strong class="sval" :class="tradeFreqPerWeek.elevated ? 'warn' : 'up'">{{ tradeFreqPerWeek.freq.toFixed(1) }} 筆/週</strong>
          <span v-if="tradeFreqPerWeek.elevated" class="shint warn">⚠ 可能過度交易</span>
        </div>
        <!-- VV8: 進行中部位總熱度 -->
        <div class="scard" v-if="openHeatPct">
          <span class="slabel">總風險熱度 <InfoTooltip label="進行中部位合計風險佔帳戶比" text="所有進行中部位的停損風險加總 ÷ 帳戶總資金（從「部位風控」頁設定）。Van Tharp Total Heat：建議 ≤ 6%，超過代表整體曝險過高，市場同步下跌時容易一次燒掉太多本金。" /></span>
          <strong class="sval" :class="openHeatPct.pct > 10 ? 'down' : openHeatPct.pct > 6 ? 'warn' : 'up'">{{ openHeatPct.pct.toFixed(1) }}%</strong>
          <span v-if="openHeatPct.pct > 6" class="shint warn">⚠ 超過建議 6% 上限</span>
        </div>
        <!-- WW1: 贏/輸單平均持倉天數（Livermore 時間框架） -->
        <div class="scard" v-if="holdTimeAnalysis">
          <span class="slabel">持倉天數：贏 vs 輸 <InfoTooltip label="贏/輸單平均持倉天數" text="Livermore：知道你的時間框架。輸單持倉比贏單長 = 凹單傾向（害怕認賠），應截虧更快。贏單應讓利潤充分奔跑。" /></span>
          <strong class="sval" :class="holdTimeAnalysis.holdsLonger ? 'warn' : 'up'">
            贏{{ holdTimeAnalysis.avgWin.toFixed(1) }}天 / 輸{{ holdTimeAnalysis.avgLoss.toFixed(1) }}天
          </strong>
          <span v-if="holdTimeAnalysis.holdsLonger" class="shint warn">⚠ 輸單持倉比贏單更久</span>
        </div>
        <!-- WW2: 滾動10筆勝率趨勢（Druckenmiller 熱/冷系統偵測） -->
        <div class="scard" v-if="rollingWinRatePoints.length >= 2">
          <span class="slabel">勝率趨勢（滾動10筆） <InfoTooltip label="滾動10筆勝率" text="Druckenmiller：系統轉好還是轉壞，要早發現。滾動窗口勝率下滑代表系統正在走冷，應縮減新部位或暫停。" /></span>
          <svg :viewBox="`0 0 ${rollingWrW} ${rollingWrH}`" class="sparkline-svg">
            <polyline :points="rollingWrPolyline" fill="none" stroke="currentColor" stroke-width="2" />
          </svg>
          <span class="shint muted">最新 {{ (rollingWinRatePoints[rollingWinRatePoints.length - 1] * 100).toFixed(0) }}%</span>
        </div>
        <!-- WW3: 張數一致性 CV（Tom Basso 系統化部位） -->
        <div class="scard" v-if="lotConsistency">
          <span class="slabel">張數一致性（CV） <InfoTooltip label="張數變異係數" text="Tom Basso：系統化不只是進場訊號，部位大小也要一致。CV（標準差/平均）越低越一致。&lt; 20% 屬良好，&gt; 40% 代表可能因情緒調整部位。" /></span>
          <strong class="sval" :class="lotConsistency.consistent ? 'up' : 'warn'">{{ lotConsistency.cv.toFixed(0) }}%</strong>
          <span v-if="!lotConsistency.consistent" class="shint warn">⚠ 張數波動偏大</span>
        </div>
        <!-- WW4: 近零報酬滲漏（Larry Williams 無效交易） -->
        <div class="scard" v-if="nearZeroLeak">
          <span class="slabel">近零R滲漏（|R|&lt;0.3） <InfoTooltip label="近零報酬交易比率" text="Larry Williams：小贏和小輸都是資本浪費，消耗手續費與注意力。&gt; 20% 代表系統可能進場過早或缺乏耐心，應提高入場標準。" /></span>
          <strong class="sval" :class="nearZeroLeak.pct > 20 ? 'warn' : 'up'">{{ nearZeroLeak.pct.toFixed(0) }}%</strong>
          <span class="shint muted">{{ nearZeroLeak.count }}/{{ nearZeroLeak.total }} 筆</span>
        </div>
        <!-- WW5: R/天 資本效率（Druckenmiller 效率） -->
        <div class="scard" v-if="rPerDay">
          <span class="slabel">R/天（資本效率） <InfoTooltip label="每日曆天平均 R" text="Druckenmiller：同樣獲利，佔用資金天數越少越有效率。Total R ÷ 跨度日曆天數。越高代表系統翻倉效率越佳。" /></span>
          <strong class="sval" :class="rPerDay.rPerDay > 0 ? 'up' : 'down'">{{ rPerDay.rPerDay >= 0 ? '+' : '' }}{{ rPerDay.rPerDay.toFixed(3) }}R/天</strong>
          <span class="shint muted">{{ rPerDay.spanDays }} 天跨度，總 {{ rPerDay.totalR >= 0 ? '+' : '' }}{{ rPerDay.totalR.toFixed(1) }}R</span>
        </div>
      </div>

      <div v-if="equityPoints.length > 1" class="equity">
        <span class="slabel">權益曲線（累計 R）</span>
        <svg class="equity-svg" :viewBox="`0 0 ${eqW} ${eqH}`" preserveAspectRatio="none">
          <line :x1="0" :y1="eqZeroY" :x2="eqW" :y2="eqZeroY" class="eq-zero" />
          <polyline :points="equityPolyline" class="eq-line" :class="{ down: stats.totalR < 0 }" />
        </svg>
      </div>
    </section>

    <!-- 新增交易 -->
    <section class="section-block" v-reveal>
      <h3>記錄一筆交易</h3>
      <div class="add-form">
        <input v-model="form.symbol" class="inp w110" placeholder="代碼 2330" aria-label="股票代碼" />
        <select v-model="form.side" class="inp" aria-label="交易方向"><option value="long">做多</option><option value="short">做空</option></select>
        <input v-model.number="form.entry" type="number" class="inp w110" placeholder="進場價" step="0.05" aria-label="進場價" />
        <input v-model.number="form.stop" type="number" class="inp w110" placeholder="停損價" step="0.05" aria-label="停損價" />
        <input v-model.number="form.target" type="number" class="inp w110" placeholder="目標價(選填)" step="0.05" aria-label="目標價（選填）" />
        <input v-model.number="form.lots" type="number" class="inp w90" placeholder="張數" min="1" step="1" aria-label="張數" />
        <input v-model="form.tag" class="inp w110" placeholder="型態(選填)" aria-label="交易型態（選填）" />
        <input v-model="form.catalyst" class="inp w160" placeholder="進場理由/催化劑(選填)" aria-label="進場理由/催化劑（選填）" />
        <!-- W7：AI 檢查進場理由夠不夠具體，選填、手動觸發，不影響加入交易的主流程 -->
        <button
          v-if="aiConfigured"
          class="btn xs"
          type="button"
          :disabled="!form.catalyst.trim() || catalystChecking"
          @click="checkCatalystQuality"
        >
          <span v-if="catalystChecking" class="loading-spinner btn-spinner" aria-hidden="true"></span>
          🤖 檢查理由品質
        </button>
        <button class="btn btn-primary" @click="addTrade">加入</button>
        <button class="btn" @click="importOpenPositions">從投組帶入</button>
      </div>
      <p v-if="formError" class="error-text">{{ formError }}</p>
      <p v-if="importMsg" class="muted small">{{ importMsg }}</p>
      <p v-if="catalystAssessment" class="muted small">🤖 {{ catalystAssessment }}</p>
      <p v-if="catalystError" class="error-text">{{ catalystError }}</p>
    </section>

    <!-- 進行中 -->
    <section class="section-block" v-reveal v-if="openTrades.length">
      <div class="head-row">
        <h3>進行中（{{ openTrades.length }}）<span class="muted small paper-tag">🧾 紙上交易 — 沒有真的下單，練習盯盤與停損紀律</span></h3>
        <button class="btn" :disabled="pricesLoading" @click="fetchLivePricesForOpenTrades">
          <span v-if="pricesLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>🔄 更新現價
        </button>
      </div>
      <div class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>目標</th><th>張</th><th>風險(1R)</th><th>現價</th><th>未實現R</th><th>未實現損益</th><th>平倉價</th><th>動作</th></tr></thead>
          <tbody>
            <tr v-for="t in openTrades" :key="t.id" :class="{ 'row-breach': stopBreached(t) }">
              <td class="sym">
                {{ t.symbol }}<small>{{ t.name && t.name !== t.symbol ? ' ' + t.name : '' }}</small>
                <span v-if="t.catalyst" class="catalyst-tag" :title="`進場理由：${t.catalyst}`">📝</span>
                <span
                  v-if="nextEvent(t)"
                  class="event-tag"
                  :title="`${nextEvent(t).date} ${nextEvent(t).label}${nextEvent(t).estimated ? '（預估）' : ''} — 留倉過夜前留意這個地雷日`"
                >📅 {{ nextEvent(t).date.slice(5) }}</span>
              </td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ t.target ? fmt(t.target) : '—' }}</td>
              <td>{{ t.lots }}</td>
              <td>{{ fmtInt(riskAmount(t)) }}</td>
              <td>
                {{ livePrice(t) != null ? fmt(livePrice(t)) : '—' }}
                <span v-if="stopBreached(t)" class="breach-tag" title="現價已觸及停損">⚠已觸停損</span>
                <span
                  v-else-if="emaBroken(t)"
                  class="ema-tag"
                  :title="emaBrokenTitle(t)"
                >📉 跌破8EMA</span>
              </td>
              <td v-if="unrealizedR(t) != null"><strong :class="unrealizedR(t) >= 0 ? 'up' : 'down'">{{ unrealizedR(t) >= 0 ? '+' : '' }}{{ unrealizedR(t).toFixed(2) }}R</strong></td>
              <td v-else>—</td>
              <td :class="unrealizedPnl(t) != null ? (unrealizedPnl(t) >= 0 ? 'up' : 'down') : ''">
                {{ unrealizedPnl(t) != null ? fmtInt(unrealizedPnl(t)) : '—' }}
                <span
                  v-if="profitGivebackPct(t) != null && profitGivebackPct(t) >= PROFIT_GIVEBACK_WARN_PCT"
                  class="giveback-tag"
                  :title="`這筆單未實現獲利曾經最高到 ${fmtInt(t.peakUnrealizedPnl)}，目前已回吐 ${profitGivebackPct(t).toFixed(0)}%，考慮分批停利或移動停損`"
                >📉 回吐{{ profitGivebackPct(t).toFixed(0) }}%</span>
              </td>
              <td><input v-model.number="t._exitInput" type="number" class="inp w90" step="0.05" placeholder="價格" :aria-label="`${t.symbol} 出場價格`" /></td>
              <td class="actions">
                <button class="btn xs" :disabled="livePrice(t) == null" title="用目前市價直接平倉" @click="closeAtMarket(t)">現價平倉</button>
                <button class="btn xs" @click="closeTrade(t)">平倉</button>
                <button class="del" @click="removeTrade(t.id)" title="刪除" aria-label="刪除交易紀錄">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="disclaimer">※ 紙上交易：未實現損益以最新市價估算，僅供練習與紀律訓練，非實際成交結果。</p>
    </section>

    <!-- 已平倉 -->
    <section class="section-block" v-reveal>
      <div class="head-row">
        <h3>已平倉（{{ closedTrades.length }}）</h3>
        <div class="head-actions">
          <button class="btn" @click="triggerImport">匯入 CSV</button>
          <input ref="csvFileInput" type="file" accept=".csv,text/csv" class="hidden-file" @change="importCsv" />
          <button v-if="trades.length" class="btn" @click="exportCsv">匯出 CSV</button>
          <button v-if="trades.length" class="btn" @click="clearAll">清空全部</button>
        </div>
      </div>
      <p v-if="csvMsg" class="muted small csv-msg">{{ csvMsg }}</p>
      <div v-if="closedTrades.length" class="table-wrap">
        <table class="j-table">
          <thead><tr><th>代碼</th><th>方向</th><th>進場</th><th>停損</th><th>出場</th><th>張</th><th>R 倍數</th><th>損益</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in closedTradesSorted" :key="t.id">
              <td class="sym">
                {{ t.symbol }}<small>{{ t.name && t.name !== t.symbol ? ' ' + t.name : '' }}</small>
                <span v-if="t.catalyst" class="catalyst-tag" :title="`進場理由：${t.catalyst}`">📝</span>
              </td>
              <td :class="t.side === 'long' ? 'up' : 'down'">{{ t.side === 'long' ? '多' : '空' }}</td>
              <td>{{ fmt(t.entry) }}</td>
              <td>{{ fmt(t.stop) }}</td>
              <td>{{ fmt(t.exit) }}</td>
              <td>{{ t.lots }}</td>
              <td><strong :class="realizedR(t) >= 0 ? 'up' : 'down'">{{ realizedR(t) >= 0 ? '+' : '' }}{{ realizedR(t).toFixed(2) }}R</strong></td>
              <td :class="pnl(t) >= 0 ? 'up' : 'down'">{{ fmtInt(pnl(t)) }}</td>
              <td><button class="del" @click="removeTrade(t.id)" title="刪除" aria-label="刪除交易紀錄">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted empty">還沒有已平倉紀錄。記錄幾筆交易並平倉，系統就會算出你的實戰勝率與期望值。</p>
      <p class="disclaimer">※ R＝(出場−進場)/|進場−停損|（做空反向）。本工具僅為交易紀錄與統計，非投資建議。</p>
    </section>

    <!-- 複盤分析 -->
    <section class="section-block" v-reveal v-if="closedTrades.length">
      <h3>複盤分析</h3>
      <div class="analytics-grid">
        <div class="an-block" v-if="rHist">
          <span class="slabel">R 分布（{{ closedTrades.length }} 筆）——留意有沒有「凹單放大虧損」或「賺一點就跑」</span>
          <svg class="rhist-svg" :viewBox="`0 0 ${eqW} ${eqH}`" preserveAspectRatio="none">
            <line :x1="rHist.zeroX" y1="0" :x2="rHist.zeroX" :y2="eqH" class="rh-zero" />
            <rect v-for="(b, i) in rHist.bars" :key="i" :x="b.x" :y="eqH - b.h" :width="b.w" :height="b.h" :class="b.mid >= 0 ? 'bar-up' : 'bar-down'" />
          </svg>
          <div class="rhist-axis">
            <span>{{ rHist.lowOutliers ? `←${rHist.lowOutliers}筆 ` : '' }}{{ rHist.min.toFixed(0) }}R</span>
            <span>0</span>
            <span>+{{ rHist.max.toFixed(0) }}R{{ rHist.highOutliers ? ` ${rHist.highOutliers}筆→` : '' }}</span>
          </div>
        </div>
        <div class="an-block">
          <span class="slabel">依型態統計（哪種設定最會賺，就多做那種）</span>
          <div class="table-wrap">
            <table class="j-table">
              <thead><tr><th>型態</th><th>筆數</th><th>勝率</th><th>期望值</th><th>累計 R</th><th>近5筆期望值 <InfoTooltip label="型態近5筆期望值" text="該型態最近 5 筆已平倉交易的期望值（需至少 3 筆才顯示）。若比全體期望值明顯下滑，代表這個 setup 近期可能在衰退，建議暫緩使用或縮小倉位。" /></th></tr></thead>
              <tbody>
                <!-- UU8: 使用 byTagWithRecent 增加近5筆期望值欄 -->
                <tr v-for="g in byTagWithRecent" :key="g.tag">
                  <td class="sym">{{ g.tag }}</td>
                  <!-- SS4: 樣本 < 3 筆時統計不顯著，加⚠提示 -->
                  <td :class="{ 'muted': g.count < 3 }" :title="g.count < 3 ? '樣本不足 3 筆，勝率/期望值不可靠' : ''">{{ g.count }}<span v-if="g.count < 3" class="sample-warn"> ⚠</span></td>
                  <td :class="g.count < 3 ? 'muted' : ''">{{ (g.winRate * 100).toFixed(0) }}%</td>
                  <td :class="g.expectancyR >= 0 ? 'up' : 'down'">{{ g.expectancyR >= 0 ? '+' : '' }}{{ g.expectancyR.toFixed(2) }}R</td>
                  <td><strong :class="g.totalR >= 0 ? 'up' : 'down'">{{ g.totalR >= 0 ? '+' : '' }}{{ g.totalR.toFixed(2) }}R</strong></td>
                  <td v-if="g.recent5Exp !== null" :class="g.recent5Exp >= 0 ? 'up' : 'down'">
                    {{ g.recent5Exp >= 0 ? '+' : '' }}{{ g.recent5Exp.toFixed(2) }}R
                    <span v-if="g.expectancyR > 0.1 && g.recent5Exp < 0" class="sample-warn" title="近期轉負，原本正期望值的策略衰退信號"> ↓</span>
                  </td>
                  <td v-else class="muted">—</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- TT2: 損益貢獻結構 -->
        <div class="an-block" v-if="grossRDecomp">
          <span class="slabel">損益貢獻結構——贏單累計 R vs 輸單累計 R（差距越大越好）</span>
          <div class="contrib-bars">
            <div class="contrib-row">
              <span class="contrib-label">贏單合計</span>
              <div class="contrib-track">
                <div class="contrib-fill contrib-win" style="width:100%"></div>
              </div>
              <strong class="up">+{{ grossRDecomp.grossWinR.toFixed(1) }}R</strong>
            </div>
            <div class="contrib-row">
              <span class="contrib-label">輸單合計</span>
              <div class="contrib-track">
                <div class="contrib-fill contrib-loss" :style="{ width: Math.min(100, (Math.abs(grossRDecomp.grossLossR) / grossRDecomp.grossWinR) * 100).toFixed(1) + '%' }"></div>
              </div>
              <strong class="down">{{ grossRDecomp.grossLossR.toFixed(1) }}R</strong>
            </div>
          </div>
          <p class="shint muted">獲利因子 {{ grossRDecomp.grossLossR < 0 ? (grossRDecomp.grossWinR / Math.abs(grossRDecomp.grossLossR)).toFixed(2) : '∞' }}（贏單合計 R 是輸單合計 R 的幾倍；> 1.5 算健康）</p>
        </div>

        <!-- TT3: 計畫 R:R vs 實際 R -->
        <div class="an-block" v-if="planVsActual">
          <span class="slabel">計畫 R:R vs 實際 R（設有目標的 {{ planVsActual.count }} 筆，中位數）</span>
          <div class="pva-row">
            <div class="pva-card">
              <span class="slabel">計畫 R:R</span>
              <strong>+{{ planVsActual.medianPlannedR.toFixed(2) }}R</strong>
              <span class="shint">你設定的目標大小</span>
            </div>
            <span class="pva-arrow">→</span>
            <div class="pva-card" :class="planVsActual.medianActualR >= planVsActual.medianPlannedR * 0.7 ? 'pva-ok' : 'pva-warn'">
              <span class="slabel">實際 R（中位數）</span>
              <strong :class="planVsActual.medianActualR >= 0 ? 'up' : 'down'">{{ planVsActual.medianActualR >= 0 ? '+' : '' }}{{ planVsActual.medianActualR.toFixed(2) }}R</strong>
              <span class="shint">達成率 {{ planVsActual.medianPlannedR > 0 ? (planVsActual.medianActualR / planVsActual.medianPlannedR * 100).toFixed(0) : '—' }}%</span>
            </div>
          </div>
        </div>

        <!-- TT9: 勝率 × 盈虧比象限圖 -->
        <div class="an-block" v-if="quadrantChart">
          <span class="slabel">勝率 × 盈虧比象限圖（虛線上方 = 正期望值）</span>
          <svg class="quad-svg" :viewBox="`0 0 ${quadrantChart.svgW} ${quadrantChart.svgH}`" xmlns="http://www.w3.org/2000/svg">
            <path :d="quadrantChart.curvePath + ` L${quadrantChart.ax2},${quadrantChart.ay1} L${quadrantChart.ax1},${quadrantChart.ay1} Z`" class="quad-positive" />
            <path :d="quadrantChart.curvePath" class="quad-curve" />
            <line :x1="quadrantChart.ax1" :y1="quadrantChart.ay2" :x2="quadrantChart.ax2" :y2="quadrantChart.ay2" class="quad-axis" />
            <line :x1="quadrantChart.ax1" :y1="quadrantChart.ay1" :x2="quadrantChart.ax1" :y2="quadrantChart.ay2" class="quad-axis" />
            <g v-for="t in quadrantChart.xTicks" :key="'x'+t.label">
              <line :x1="t.x" :y1="quadrantChart.ay2" :x2="t.x" :y2="+quadrantChart.ay2 + 4" class="quad-tick" />
              <text :x="t.x" :y="+quadrantChart.ay2 + 14" class="quad-label" text-anchor="middle">{{ t.label }}</text>
            </g>
            <g v-for="t in quadrantChart.yTicks" :key="'y'+t.label">
              <line :x1="+quadrantChart.ax1 - 4" :y1="t.y" :x2="quadrantChart.ax1" :y2="t.y" class="quad-tick" />
              <text :x="+quadrantChart.ax1 - 6" :y="+t.y + 4" class="quad-label" text-anchor="end">{{ t.label }}</text>
            </g>
            <circle :cx="quadrantChart.dotX" :cy="quadrantChart.dotY" r="6" :class="quadrantChart.above ? 'dot-up' : 'dot-down'" />
          </svg>
          <p class="shint muted">盈虧比 {{ quadrantChart.px }}、勝率 {{ quadrantChart.py }}% — {{ quadrantChart.above ? '✓ 正期望值（虛線上方）' : '✗ 負期望值（虛線下方），需要改善勝率或盈虧比' }}</p>
        </div>

        <!-- UU2: 多空分開統計 -->
        <div class="an-block" v-if="bySide.length >= 2">
          <span class="slabel">多空分開績效（Minervini：集中資本在你有真正優勢的方向）</span>
          <div class="table-wrap">
            <table class="j-table">
              <thead><tr><th>方向</th><th>筆數</th><th>勝率</th><th>期望值</th><th>累計 R</th></tr></thead>
              <tbody>
                <tr v-for="g in bySide" :key="g.side">
                  <td :class="g.side === 'long' ? 'up' : 'down'">{{ g.side === 'long' ? '做多' : '做空' }}</td>
                  <td>{{ g.count }}</td>
                  <td>{{ (g.winRate * 100).toFixed(0) }}%</td>
                  <td :class="g.expectancyR >= 0 ? 'up' : 'down'">{{ g.expectancyR >= 0 ? '+' : '' }}{{ g.expectancyR.toFixed(2) }}R</td>
                  <td><strong :class="g.totalR >= 0 ? 'up' : 'down'">{{ g.totalR >= 0 ? '+' : '' }}{{ g.totalR.toFixed(2) }}R</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- UU4: R 分布偏態係數 -->
        <div class="an-block" v-if="rSkewness !== null">
          <span class="slabel">R 分布偏態係數（正值 = 右偏 ✓ 讓利潤奔跑，負值 = 左偏 ✗ 凹單或跑太快）</span>
          <div class="skew-row">
            <div class="skew-val" :class="rSkewness >= 0.3 ? 'up' : rSkewness >= -0.3 ? '' : 'down'">
              <strong>{{ rSkewness >= 0 ? '+' : '' }}{{ rSkewness.toFixed(2) }}</strong>
            </div>
            <p class="skew-text muted">
              <template v-if="rSkewness > 0.5">右偏明顯 ✓ — 偶有大贏、多為小輸，符合「截斷虧損、讓利潤奔跑」的正確模式。</template>
              <template v-else-if="rSkewness >= -0.3">分布接近對稱 — 正常範圍，持續觀察是否有讓利潤跑更遠的空間。</template>
              <template v-else>左偏 ✗ — 偶有大輸、多為小贏，可能存在凹單（讓虧損擴大）或提早獲利了結的習慣，建議對照停損執行紀律與目標達成率。</template>
            </p>
          </div>
        </div>

        <!-- UU7: 依星期幾績效統計 -->
        <div class="an-block" v-if="dayOfWeekHasData">
          <span class="slabel">依星期幾累計 R（識別個人弱勢交易日，系統性規避）</span>
          <div class="dow-grid">
            <div v-for="d in byDayOfWeek" :key="d.label" class="dow-cell"
              :class="d.count ? (d.totalR > 0.2 ? 'dow-up' : d.totalR < -0.2 ? 'dow-down' : '') : 'dow-empty'">
              <span class="dow-label">{{ d.label }}</span>
              <strong class="dow-r" v-if="d.count">{{ d.totalR >= 0 ? '+' : '' }}{{ d.totalR.toFixed(1) }}R</strong>
              <span class="dow-count muted" v-if="d.count">{{ d.count }} 筆</span>
              <span class="dow-count muted" v-else>無資料</span>
            </div>
          </div>
        </div>

        <!-- VV3: 催化劑/進場理由分析 -->
        <div class="an-block" v-if="byCatalyst.length">
          <span class="slabel">依進場理由統計（O'Neil CAN SLIM：知道「為什麼」進場，勝率才能穩定）</span>
          <div class="table-wrap">
            <table class="j-table">
              <thead><tr><th>進場理由</th><th>筆數</th><th>勝率</th><th>期望值</th><th>累計 R</th></tr></thead>
              <tbody>
                <tr v-for="g in byCatalyst" :key="g.catalyst">
                  <td class="catalyst-label">{{ g.catalyst }}</td>
                  <td>{{ g.count }}</td>
                  <td>{{ (g.winRate * 100).toFixed(0) }}%</td>
                  <td :class="g.expectancyR >= 0 ? 'up' : 'down'">{{ g.expectancyR >= 0 ? '+' : '' }}{{ g.expectancyR.toFixed(2) }}R</td>
                  <td><strong :class="g.totalR >= 0 ? 'up' : 'down'">{{ g.totalR >= 0 ? '+' : '' }}{{ g.totalR.toFixed(2) }}R</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- VV7: 標的集中度警告 -->
        <div class="an-block" v-if="bySymbolConc">
          <span class="slabel">標的集中度（Templeton：分散是防止無知的保護，單一標的 > 30% 屬集中風險）</span>
          <div class="conc-row">
            <div v-for="g in bySymbolConc.top" :key="g.sym" class="conc-bar-wrap">
              <div class="conc-label-row">
                <span class="conc-sym">{{ g.sym }}</span>
                <span class="conc-pct" :class="g.pct > 30 ? 'down' : ''">{{ g.pct.toFixed(0) }}%</span>
              </div>
              <div class="conc-bar-track">
                <div class="conc-bar-fill" :class="g.pct > 30 ? 'conc-warn' : ''" :style="{ width: `${Math.min(g.pct, 100)}%` }"></div>
              </div>
            </div>
            <p v-if="bySymbolConc.concentrated" class="skew-text muted down">⚠ {{ bySymbolConc.topSym }} 佔總絕對 R 的 {{ bySymbolConc.topPct.toFixed(0) }}%——集中度偏高，建議分散或降低單一標的的部位比重。</p>
          </div>
        </div>

        <!-- VV10: 異常大贏依賴度（Taleb 脆弱性） -->
        <div class="an-block" v-if="outlierFrailty">
          <span class="slabel">異常大贏依賴度（Taleb：若獲利集中在少數幾筆，系統本質上依賴運氣）</span>
          <div class="skew-row">
            <div class="skew-val" :class="outlierFrailty.fragile ? 'down' : 'up'">
              <strong>{{ outlierFrailty.pct.toFixed(0) }}%</strong>
            </div>
            <p class="skew-text muted">
              <template v-if="outlierFrailty.fragile">⚠ 前三大贏佔總獲利 R 的 {{ outlierFrailty.pct.toFixed(0) }}%——系統脆弱，移除這幾筆後績效將大幅縮水，建議檢視這幾筆是否可重複。</template>
              <template v-else>✓ 前三大贏佔總獲利 R 的 {{ outlierFrailty.pct.toFixed(0) }}%——獲利分布相對均勻，系統穩健性較佳。</template>
            </p>
          </div>
        </div>

        <!-- WW7: 近8週週績效（機構週評節奏） -->
        <div class="an-block an-block--full" v-if="weeklyPerf">
          <span class="slabel">近8週週績效（機構節奏：週為最小評估單位）</span>
          <div class="table-wrap">
            <table class="j-table ww-weekly-table">
              <thead><tr><th>週（週一）</th><th>筆數</th><th>週R</th><th>累計R</th></tr></thead>
              <tbody>
                <tr v-for="w in weeklyPerf" :key="w.week">
                  <td>{{ w.week }}</td>
                  <td>{{ w.trades }}</td>
                  <td :class="w.weekR > 0 ? 'up' : w.weekR < 0 ? 'down' : ''">{{ w.weekR >= 0 ? '+' : '' }}{{ w.weekR.toFixed(2) }}R</td>
                  <td :class="w.cumR > 0 ? 'up' : w.cumR < 0 ? 'down' : ''">{{ w.cumR >= 0 ? '+' : '' }}{{ w.cumR.toFixed(2) }}R</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- WW8: 目標達成率＋平均獲利捕捉率（PTJ：只做你知道會成功的交易） -->
        <div class="an-block" v-if="targetAchievement">
          <span class="slabel">目標達成率（PTJ：只做你知道會成功的交易，事後驗證預測力）</span>
          <div class="skew-row">
            <div class="skew-val" :class="targetAchievement.hitRate >= 0.5 ? 'up' : 'warn'">
              <strong>{{ (targetAchievement.hitRate * 100).toFixed(0) }}%</strong>
              <small class="muted">達標率</small>
            </div>
            <div class="skew-val" :class="targetAchievement.avgCapture >= 0.7 ? 'up' : 'warn'">
              <strong>{{ (targetAchievement.avgCapture * 100).toFixed(0) }}%</strong>
              <small class="muted">平均捕捉率</small>
            </div>
            <p class="skew-text muted">{{ targetAchievement.hits }}/{{ targetAchievement.count }} 筆達到目標；平均實際獲利為計畫目標的 {{ (targetAchievement.avgCapture * 100).toFixed(0) }}%。捕捉率 &lt; 70% 代表習慣提早出場，建議複查持倉紀律。</p>
          </div>
        </div>

        <!-- XX1: Kelly Fraction 倉位建議（Ed Thorp） -->
        <div class="scard" v-if="kellyFraction">
          <span class="slabel">Kelly 倉位建議（Thorp：最優賭注比例，超賭必輸）</span>
          <div class="sc-row">
            <div class="sc-val">
              <strong>{{ kellyFraction.quarter.toFixed(1) }}%</strong>
              <small class="muted">¼-Kelly（建議上限）</small>
            </div>
            <div class="sc-val" :class="kellyFraction.full > 0 ? 'up' : 'down'">
              <strong>{{ kellyFraction.full.toFixed(1) }}%</strong>
              <small class="muted">Full Kelly</small>
            </div>
          </div>
          <p class="scard-hint muted">勝率 {{ (kellyFraction.p * 100).toFixed(0) }}%、平均賠比 {{ kellyFraction.b.toFixed(2) }}×。每筆風險不超過帳戶 {{ kellyFraction.quarter.toFixed(1) }}%（¼-Kelly 安全邊際）。</p>
        </div>

        <!-- XX2: 權益曲線動能信號（Nick Radge） -->
        <div class="scard" v-if="ecMomentum">
          <span class="slabel">權益曲線動能（Radge：低於均線就縮手）</span>
          <div class="sc-row">
            <div class="sc-val" :class="ecMomentum.trade ? 'up' : 'warn'">
              <strong>{{ ecMomentum.trade ? '✓ TRADE' : '⚠ PAUSE' }}</strong>
              <small class="muted">操作信號</small>
            </div>
            <div class="sc-val">
              <strong>{{ fmt(ecMomentum.current) }} R</strong>
              <small class="muted">當前累積</small>
            </div>
            <div class="sc-val">
              <strong>{{ fmt(ecMomentum.sma) }} R</strong>
              <small class="muted">10筆SMA</small>
            </div>
          </div>
          <p class="scard-hint muted">{{ ecMomentum.trade ? '權益曲線高於10筆均線，系統運作正常，可正常下單。' : '權益曲線跌破10筆均線，建議縮減倉位或暫停直到曲線回穩。' }}</p>
        </div>

        <!-- XX5: R 四分位分布（Michael Covel） -->
        <div class="scard" v-if="rQuartile">
          <span class="slabel">R 四分位分布（Covel：趨勢跟蹤靠右尾肥）</span>
          <div class="sc-row">
            <div class="sc-val">
              <strong>{{ fmt(rQuartile.p25) }}</strong>
              <small class="muted">P25</small>
            </div>
            <div class="sc-val">
              <strong>{{ fmt(rQuartile.p50) }}</strong>
              <small class="muted">P50</small>
            </div>
            <div class="sc-val" :class="rQuartile.thinRightTail ? 'warn' : 'up'">
              <strong>{{ fmt(rQuartile.p75) }}</strong>
              <small class="muted">P75</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="rQuartile.thinRightTail">⚠ P75 &lt; 1.5R：利潤右尾偏薄，可能提早出場或沒讓贏家充分奔跑。</p>
          <p class="scard-hint muted" v-else>P75 ≥ 1.5R：右尾健康，有讓部分贏單充分奔跑 ✓</p>
        </div>

        <!-- XX6: 月獲利因子趨勢（CTA 標準） -->
        <div class="scard" v-if="monthlyPFPoints.length >= 2">
          <span class="slabel">月獲利因子趨勢（CTA 標準：PF &lt; 1 = 負期望值月份）</span>
          <svg class="sparkline-svg" :width="pfW" :height="pfH" :viewBox="`0 0 ${pfW} ${pfH}`" preserveAspectRatio="none">
            <line :x1="0" :y1="pfH/2" :x2="pfW" :y2="pfH/2" stroke="var(--color-border)" stroke-width="1" stroke-dasharray="3,3"/>
            <polyline :points="pfPolyline" fill="none" stroke="var(--color-accent)" stroke-width="2" stroke-linejoin="round"/>
          </svg>
          <p class="scard-hint muted">近 6 個月獲利因子趨勢（1.0 = 損益平衡，越高越佳）</p>
        </div>

        <!-- XX8: 停損觸發恢復成本（Martin Schwartz） -->
        <div class="an-block" v-if="stopRecoveryCost">
          <span class="slabel">停損觸發恢復成本（Schwartz：輸一筆需要幾筆贏單才能回本）</span>
          <table class="j-table xx-recovery-table">
            <thead><tr><th>代號</th><th>張數</th><th>若觸停 (-1R)</th><th>需贏單數</th></tr></thead>
            <tbody>
              <tr v-for="r in stopRecoveryCost" :key="r.symbol">
                <td>{{ r.symbol }}</td>
                <td>{{ r.lots }}</td>
                <td class="down">-{{ r.lots }}R</td>
                <td :class="r.recoveryTrades * r.lots > 3 ? 'warn' : ''">{{ (r.recoveryTrades * r.lots).toFixed(1) }} 筆</td>
              </tr>
            </tbody>
          </table>
          <p class="scard-hint muted">以均值贏單 {{ stopRecoveryCost[0] ? fmt(stopRecoveryCost[0].avgWin) : '—' }}R 計算，超過 3 筆為高恢復成本警示。</p>
        </div>

        <!-- XX9: 當前連勝/連敗機率（George Soros） -->
        <div class="scard" v-if="streakProb">
          <span class="slabel">當前連{{ streakProb.type === 'win' ? '勝' : '敗' }}機率（Soros：隨機性中的極端是正常的）</span>
          <div class="sc-row">
            <div class="sc-val">
              <strong>{{ streakProb.n }} 連{{ streakProb.type === 'win' ? '勝' : '敗' }}</strong>
              <small class="muted">當前連線</small>
            </div>
            <div class="sc-val" :class="streakProb.rare ? 'up' : ''">
              <strong>{{ (streakProb.pAtLeast * 100).toFixed(1) }}%</strong>
              <small class="muted">此連線機率</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="streakProb.rare && streakProb.type === 'win'">✓ 統計罕見的連勝（{{ (streakProb.pAtLeast * 100).toFixed(1) }}%），小心過度自信，勿貿然擴大倉位。</p>
          <p class="scard-hint muted" v-else-if="streakProb.rare && streakProb.type === 'loss'">⚠ 統計罕見的連敗（{{ (streakProb.pAtLeast * 100).toFixed(1) }}%），可能是系統失效而非隨機雜訊，應檢視設定。</p>
          <p class="scard-hint muted" v-else>此長度的連線在目前勝率下屬正常範圍（{{ (streakProb.pAtLeast * 100).toFixed(1) }}%）。</p>
        </div>

        <!-- XX10: 交易評分分布（William O'Neil） -->
        <div class="an-block" v-if="tradeGrades">
          <span class="slabel">交易評分分布（O'Neil/IBD：只做 A 級設定）</span>
          <div class="xx-grade-row">
            <div v-for="g in ['A','B','C','D']" :key="g" class="xx-grade-cell" :class="`grade-${g.toLowerCase()}`">
              <strong>{{ tradeGrades.counts[g] }}</strong>
              <span class="muted"> ({{ tradeGrades.pct[g].toFixed(0) }}%)</span>
              <small>{{ g }}</small>
            </div>
          </div>
          <p class="scard-hint muted">A=達目標且≥均值贏 ｜ B=其中一項 ｜ C=正報酬但無達成 ｜ D=虧損。A+B 佔比越高越好。</p>
        </div>

        <!-- YY1: 系統品質分數 SQN（Van Tharp） -->
        <div class="scard" v-if="sqn">
          <span class="slabel">系統品質分數（SQN）（Tharp：≥ 2.5 可穩定交易，≥ 3.0 優秀）</span>
          <div class="sc-row">
            <div class="sc-val" :class="sqn.cls">
              <strong>{{ sqn.value.toFixed(2) }}</strong>
              <small class="muted">SQN</small>
            </div>
            <div class="sc-val" :class="sqn.cls">
              <strong>{{ sqn.label }}</strong>
              <small class="muted">品質等級</small>
            </div>
            <div class="sc-val">
              <strong>{{ sqn.N }}</strong>
              <small class="muted">計算筆數</small>
            </div>
          </div>
          <p class="scard-hint muted">mean(R)/σ(R)×√N。&lt; 1.6 差，1.6-2.0 普通，2.0-3.0 良好，≥ 3.0 優秀。</p>
        </div>

        <!-- YY2: 催化劑績效分層（Paul Tudor Jones） -->
        <div class="an-block" v-if="catalystPerf">
          <span class="slabel">催化劑績效分層（Tudor Jones：只做最強的設定類型）</span>
          <div class="table-wrap">
            <table class="j-table yy-catalyst-table">
              <thead><tr><th style="text-align:left">催化劑</th><th>筆數</th><th>勝率</th><th>均值R</th><th>PF</th></tr></thead>
              <tbody>
                <tr v-for="row in catalystPerf" :key="row.cat">
                  <td style="text-align:left">{{ row.cat }}</td>
                  <td>{{ row.count }}</td>
                  <td :class="row.winRate >= 50 ? 'up' : 'down'">{{ row.winRate.toFixed(0) }}%</td>
                  <td :class="row.avgR >= 0 ? 'up' : 'down'">{{ row.avgR >= 0 ? '+' : '' }}{{ row.avgR.toFixed(2) }}</td>
                  <td :class="row.pf >= 1 ? 'up' : 'down'">{{ row.pf.toFixed(2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="scard-hint muted">提高高均值R設定的交易頻率，縮減或淘汰負期望值設定。</p>
        </div>

        <!-- YY3: 月份勝率模式（Ed Seykota） -->
        <div class="scard" v-if="monthlyWinRate">
          <span class="slabel">月份勝率模式（Seykota：了解哪些月份適合或不適合交易）</span>
          <div class="yy-month-bars">
            <div v-for="m in monthlyWinRate.months" :key="m.month" class="yy-month-bar-col">
              <div class="yy-month-bar-bg">
                <div v-if="m.wr !== null" class="yy-month-bar-fill"
                  :style="{ height: (m.wr * 100) + '%' }"
                  :class="m.wr >= 0.6 ? 'yy-bar-good' : m.wr >= 0.4 ? 'yy-bar-warn' : 'yy-bar-bad'"></div>
              </div>
              <span class="yy-month-label muted">{{ m.month + 1 }}</span>
            </div>
          </div>
          <p class="scard-hint muted">
            最佳：{{ ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'][monthlyWinRate.best.month] }}（{{ (monthlyWinRate.best.wr * 100).toFixed(0) }}%）
            ｜ 最差：{{ ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'][monthlyWinRate.worst.month] }}（{{ (monthlyWinRate.worst.wr * 100).toFixed(0) }}%）
          </p>
        </div>

        <!-- YY4: 倉位大小績效相關（Tom Basso） -->
        <div class="scard" v-if="lotSizeEffect">
          <span class="slabel">倉位大小績效相關（Basso：情緒化者大倉勝率更低，系統化者兩者接近）</span>
          <div class="sc-row">
            <div class="sc-val" :class="lotSizeEffect.emotional ? 'down' : 'up'">
              <strong>{{ lotSizeEffect.bigWR.toFixed(0) }}%</strong>
              <small class="muted">大單勝率（>{{ lotSizeEffect.median }}張）</small>
            </div>
            <div class="sc-val">
              <strong>{{ lotSizeEffect.smallWR.toFixed(0) }}%</strong>
              <small class="muted">小單勝率（≤{{ lotSizeEffect.median }}張）</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="lotSizeEffect.emotional">⚠ 大單勝率顯著低於小單（> 5%），可能是情緒驅動下放大部位，建議系統化定額交易。</p>
          <p class="scard-hint muted" v-else>大小單勝率接近，倉位大小由系統決定，符合 Basso 的機械化交易原則。</p>
        </div>

        <!-- YY5: 離群贏單貢獻度（Ed Seykota / Michael Covel） -->
        <div class="scard" v-if="outlierContribution">
          <span class="slabel">離群贏單貢獻度（Seykota：大行情才是主要收入來源，不要截斷贏單）</span>
          <div class="sc-row">
            <div class="sc-val" :class="outlierContribution.healthy ? 'up' : 'warn'">
              <strong>{{ outlierContribution.pct.toFixed(0) }}%</strong>
              <small class="muted">前 {{ outlierContribution.topN }} 筆佔獲利</small>
            </div>
            <div class="sc-val" :class="outlierContribution.withoutOutliers >= 0 ? 'up' : 'down'">
              <strong>{{ outlierContribution.withoutOutliers >= 0 ? '+' : '' }}{{ outlierContribution.withoutOutliers.toFixed(1) }}R</strong>
              <small class="muted">去除後累積R</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="outlierContribution.healthy">前 10% 贏單貢獻 > 40% 總獲利，具備健康的右尾特性，應繼續讓贏單奔跑。</p>
          <p class="scard-hint muted" v-else>贏單分布偏均勻，前 10% 貢獻 &lt; 40%，可能習慣提早獲利了結，減少了大行情的捕捉。</p>
        </div>

        <!-- ZZ1: Jesse Livermore — Never Average a Loss -->
        <div class="scard zz-avgdown-card" v-if="avgDownDetector">
          <span class="slabel">連虧重入率（Livermore：永遠不要攤平虧損，虧損後同標的立即重入是危險信號）</span>
          <div class="sc-row">
            <div class="sc-val" :class="avgDownDetector.risky ? 'down' : 'up'">
              <strong>{{ (avgDownDetector.rate * 100).toFixed(0) }}%</strong>
              <small class="muted">虧後14天內同標重入率</small>
            </div>
            <div class="sc-val">
              <strong>{{ avgDownDetector.incidents }}/{{ avgDownDetector.total }}</strong>
              <small class="muted">重入次/虧損後機會</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="avgDownDetector.risky">⚠ 虧損後頻繁重入同標的，疑似情緒驅動的攤平行為，請確認每次均為全新設定而非加碼。</p>
          <p class="scard-hint muted" v-else>連虧後重入比率低，展現 Livermore 紀律：讓虧損的倉位自然出局，不用新倉補救舊倉。</p>
        </div>

        <!-- ZZ2: Nassim Taleb — Volatility Regime Performance -->
        <div class="scard zz-volreg-card" v-if="volatilityRegime">
          <span class="slabel">波動制度績效（Taleb：真正反脆弱的系統在各種波動環境下均具正期望值）</span>
          <div class="sc-row">
            <div v-for="tier in volatilityRegime.tiers" :key="tier.label" class="sc-val">
              <strong :class="tier.avgR > 0 ? 'up' : 'down'">{{ tier.avgR > 0 ? '+' : '' }}{{ tier.avgR.toFixed(2) }}R</strong>
              <small class="muted">{{ tier.label }}</small>
              <small class="muted">{{ tier.n }} 筆</small>
            </div>
          </div>
          <p class="scard-hint muted">依停損距離%分層（緊&lt;2%，中2-4%，寬&gt;4%），各制度均為正均值代表系統具廣譜穩健性。</p>
        </div>

        <!-- ZZ4: Stan Druckenmiller — High-Conviction Sizing Check -->
        <div class="scard zz-conviction-card" v-if="convictionAvgR">
          <span class="slabel">高信念倉位驗證（Druckenmiller：真正的信念應反映在部位大小，且大倉績效要更優）</span>
          <div class="sc-row">
            <div class="sc-val" :class="convictionAvgR.bigAvg > 0 ? 'up' : 'down'">
              <strong>{{ convictionAvgR.bigAvg > 0 ? '+' : '' }}{{ convictionAvgR.bigAvg.toFixed(2) }}R</strong>
              <small class="muted">大倉平均 R</small>
            </div>
            <div class="sc-val" :class="convictionAvgR.smallAvg > 0 ? 'up' : 'down'">
              <strong>{{ convictionAvgR.smallAvg > 0 ? '+' : '' }}{{ convictionAvgR.smallAvg.toFixed(2) }}R</strong>
              <small class="muted">小倉平均 R</small>
            </div>
            <div class="sc-val" :class="convictionAvgR.healthy ? 'up' : 'down'">
              <strong>{{ convictionAvgR.gap > 0 ? '+' : '' }}{{ convictionAvgR.gap.toFixed(2) }}R</strong>
              <small class="muted">大倉超額 R</small>
            </div>
          </div>
          <p class="scard-hint muted" v-if="convictionAvgR.healthy">大倉平均R優於小倉，倉位大小與進場信念正相關，Druckenmiller 式加碼紀律良好。</p>
          <p class="scard-hint muted" v-else>⚠ 大倉表現遜於小倉，可能在情緒或直覺驅動下放大倉位，而非依據更強的系統信號。</p>
        </div>

        <!-- ZZ5: Larry Williams — Hold Duration Sweet Spot -->
        <div class="scard zz-duration-card" v-if="holdDurationSweetSpot">
          <span class="slabel">持倉天數甜蜜點（Williams：了解策略的最佳持倉時間，在對的時間出場）</span>
          <div class="zz-dur-bars">
            <div v-for="b in holdDurationSweetSpot" :key="b.label" class="zz-dur-col">
              <div class="zz-dur-bar-bg">
                <div v-if="b.n > 0" class="zz-dur-bar-fill"
                     :class="(b.avgR || 0) > 0 ? 'zz-bar-up' : 'zz-bar-down'"
                     :style="{ height: Math.min(100, Math.abs(b.avgR || 0) * 20 + 5) + '%' }"></div>
              </div>
              <span class="muted" style="font-size:0.65rem">{{ b.label }}</span>
              <span style="font-size:0.72rem" :class="b.avgR > 0 ? 'up' : b.n > 0 ? 'down' : ''">
                {{ b.n > 0 ? ((b.avgR > 0 ? '+' : '') + b.avgR.toFixed(2) + 'R') : '–' }}
              </span>
            </div>
          </div>
        </div>

        <!-- ZZ6: Peter Lynch — Symbol Net P&L Ranking -->
        <div class="scard zz-symbol-pnl" v-if="symbolNetPnl">
          <span class="slabel">標的淨貢獻排名（Lynch：了解你持有的每個標的，確認哪些真正在幫你賺錢）</span>
          <div class="zz-symbol-row">
            <div class="zz-symbol-group">
              <span class="muted" style="font-size:0.7rem">▲ 貢獻最大</span>
              <div v-for="s in symbolNetPnl.top" :key="s.symbol" class="zz-symbol-item">
                <span class="zz-sym-code mono">{{ s.symbol }}</span>
                <span :class="s.netR >= 0 ? 'up' : 'down'" style="font-size:0.85rem">{{ s.netR >= 0 ? '+' : '' }}{{ s.netR.toFixed(1) }}R</span>
                <span class="muted" style="font-size:0.65rem">{{ s.n }}筆</span>
              </div>
            </div>
            <div class="zz-symbol-group" v-if="symbolNetPnl.bottom.length">
              <span class="muted" style="font-size:0.7rem">▼ 拖累最大</span>
              <div v-for="s in symbolNetPnl.bottom" :key="s.symbol" class="zz-symbol-item">
                <span class="zz-sym-code mono">{{ s.symbol }}</span>
                <span class="down" style="font-size:0.85rem">{{ s.netR >= 0 ? '+' : '' }}{{ s.netR.toFixed(1) }}R</span>
                <span class="muted" style="font-size:0.65rem">{{ s.n }}筆</span>
              </div>
            </div>
          </div>
        </div>

        <!-- AAA1: Warren Buffett — Top-Symbol Concentration Efficiency -->
        <div class="scard aaa-concentration-card" v-if="concentrationEfficiency">
          <span class="slabel">最佳標的集中度效益（Buffett：確認你的最佳構想是否真正表現最好）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <strong class="mono" :class="concentrationEfficiency.topAvgR > concentrationEfficiency.restAvgR ? 'up' : 'warn'">
                {{ concentrationEfficiency.topSymbol }}
              </strong>
              <span class="muted" style="font-size:0.75rem">（最佳標的，{{ concentrationEfficiency.topN }}筆）</span>
              <br>
              <span style="font-size:1.1rem" :class="concentrationEfficiency.topAvgR >= 0 ? 'up' : 'down'">
                {{ concentrationEfficiency.topAvgR >= 0 ? '+' : '' }}{{ concentrationEfficiency.topAvgR.toFixed(2) }}R
              </span>
              <span class="muted" style="font-size:0.72rem"> avg</span>
            </div>
            <div style="font-size:1.5rem;color:var(--color-muted)">vs</div>
            <div>
              <span class="muted" style="font-size:0.75rem">其他 {{ concentrationEfficiency.restCount }} 個標的均值</span>
              <br>
              <span style="font-size:1.1rem" :class="concentrationEfficiency.restAvgR >= 0 ? 'up' : 'down'">
                {{ concentrationEfficiency.restAvgR >= 0 ? '+' : '' }}{{ concentrationEfficiency.restAvgR.toFixed(2) }}R
              </span>
            </div>
            <div :class="concentrationEfficiency.topAvgR > concentrationEfficiency.restAvgR ? 'up' : 'down'" style="font-size:0.8rem">
              {{ concentrationEfficiency.topAvgR > concentrationEfficiency.restAvgR ? '✓ 集中有效' : '⚠ 集中無效' }}
            </div>
          </div>
        </div>

        <!-- AAA4: George Soros — Reflexivity Re-entry Tracker -->
        <div class="scard aaa-reflexivity" v-if="reflexivityReentry">
          <span class="slabel">同標的再進場反身性（Soros：盈利後加倉是因為市場自我強化，還是你在情緒追高？）</span>
          <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:0.5rem">
            <div v-for="sym in reflexivityReentry.symbols" :key="sym.symbol">
              <span class="mono muted" style="font-size:0.75rem">{{ sym.symbol }}</span>
              <div style="display:flex;gap:0.75rem;margin-top:2px">
                <div>
                  <span class="muted" style="font-size:0.65rem">首次</span>
                  <br>
                  <strong :class="sym.firstAvgR >= 0 ? 'up' : 'down'" style="font-size:0.9rem">{{ sym.firstAvgR >= 0 ? '+' : '' }}{{ sym.firstAvgR.toFixed(2) }}R</strong>
                </div>
                <div>
                  <span class="muted" style="font-size:0.65rem">再進 ({{ sym.reN }}筆)</span>
                  <br>
                  <strong :class="sym.reAvgR >= 0 ? 'up' : 'down'" style="font-size:0.9rem">{{ sym.reAvgR >= 0 ? '+' : '' }}{{ sym.reAvgR.toFixed(2) }}R</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- AAA5: David Ricardo — Win/Loss Hold Duration Asymmetry -->
        <div class="scard aaa-duration-ratio" v-if="durationAsymmetry">
          <span class="slabel">勝損持倉時長不對稱（Ricardo：讓贏家奔跑、快速認錯——比率 > 1.5 才是正確紀律）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">贏單平均持倉</span><br>
              <strong class="up">{{ durationAsymmetry.avgWinDays.toFixed(1) }}天</strong>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">虧單平均持倉</span><br>
              <strong class="down">{{ durationAsymmetry.avgLossDays.toFixed(1) }}天</strong>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">不對稱比率</span><br>
              <strong :class="durationAsymmetry.ratio >= 1.5 ? 'up' : durationAsymmetry.ratio >= 1.0 ? 'warn' : 'down'" style="font-size:1.2rem">
                {{ durationAsymmetry.ratio.toFixed(2) }}×
              </strong>
              <span class="muted" style="font-size:0.7rem"> {{ durationAsymmetry.ratio >= 1.5 ? '✓ 紀律良好' : '⚠ 過早出場/拖延虧損' }}</span>
            </div>
          </div>
        </div>

        <!-- AAA7: Victor Niederhoffer — Trade Sequence Autocorrelation -->
        <div class="scard aaa-autocorr" v-if="serialCorrelation">
          <span class="slabel">交易序列自相關（Niederhoffer：勝負是否會叢聚？—— P(勝｜前勝) vs P(勝｜前敗)）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">P(勝｜前一勝)</span><br>
              <strong :class="serialCorrelation.pWinGivenWin >= 0.5 ? 'up' : 'down'" style="font-size:1.1rem">
                {{ (serialCorrelation.pWinGivenWin * 100).toFixed(0) }}%
              </strong>
              <span class="muted" style="font-size:0.65rem"> ({{ serialCorrelation.nWW }}筆)</span>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">P(勝｜前一敗)</span><br>
              <strong :class="serialCorrelation.pWinGivenLoss >= 0.5 ? 'up' : 'down'" style="font-size:1.1rem">
                {{ (serialCorrelation.pWinGivenLoss * 100).toFixed(0) }}%
              </strong>
              <span class="muted" style="font-size:0.65rem"> ({{ serialCorrelation.nLW }}筆)</span>
            </div>
            <div class="muted" style="font-size:0.75rem">
              {{ serialCorrelation.clustered ? '⚠ 叢聚性強，連勝連敗明顯' : '✓ 序列近似隨機，心理影響小' }}
            </div>
          </div>
        </div>

        <!-- AAA8: Marty Schwartz — Day-of-Week Performance -->
        <div class="scard aaa-weekday" v-if="weekdayPerf">
          <span class="slabel">星期幾績效（Schwartz：了解自己在哪天狀態最好，避開弱勢日交易）</span>
          <div class="aaa-weekday-bars">
            <div v-for="d in weekdayPerf" :key="d.label" class="aaa-wd-col">
              <div class="aaa-wd-bar-bg">
                <div class="aaa-wd-bar-fill" :class="d.avgR >= 0 ? 'zz-bar-up' : 'zz-bar-down'"
                  :style="{ height: d.n > 0 ? Math.min(100, Math.abs(d.avgR) * 40 + 10) + '%' : '4px' }"></div>
              </div>
              <span class="muted" style="font-size:0.65rem">{{ d.label }}</span>
              <span v-if="d.n" :class="d.avgR >= 0 ? 'up' : 'down'" style="font-size:0.7rem">{{ d.avgR >= 0 ? '+' : '' }}{{ d.avgR.toFixed(2) }}R</span>
              <span v-else class="muted" style="font-size:0.65rem">–</span>
            </div>
          </div>
        </div>

        <!-- BBB1: Ralph Vince — Optimal f Position Sizing -->
        <div class="scard bbb-optimal-f" v-if="optimalF">
          <span class="slabel">最優倉位尺寸 Optimal f（Vince：Kelly 準則的實務形式——最大化幾何成長率的最佳下注比例）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">最優 f（理論值）</span><br>
              <strong :class="optimalF.healthy ? 'up' : 'down'" style="font-size:1.3rem">
                {{ (optimalF.f * 100).toFixed(1) }}%
              </strong>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">系統期望值</span><br>
              <strong :class="optimalF.edge >= 0 ? 'up' : 'down'">{{ optimalF.edge >= 0 ? '+' : '' }}{{ optimalF.edge.toFixed(3) }}R/筆</strong>
            </div>
            <div class="muted" style="font-size:0.75rem;max-width:200px">
              {{ optimalF.healthy ? 'Vince：系統具備正期望，存在最優倉位比例，過度或不足下注都會降低幾何成長率。' : '⚠ 期望值為負，任何倉位下注都無法獲利，應先改善系統邊際再考慮倉位優化。' }}
            </div>
          </div>
        </div>

        <!-- BBB3: Bernard Baruch — Exit Quality Score -->
        <div class="scard bbb-exit-quality" v-if="exitQuality">
          <span class="slabel">贏單出場品質（Baruch：適時獲利了結和適時進場一樣重要——你的贏單平均捕捉了多少計劃利潤？）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">平均捕捉率</span><br>
              <strong :class="exitQuality.avgRatio >= 0.7 ? 'up' : exitQuality.avgRatio >= 0.4 ? 'warn' : 'down'" style="font-size:1.3rem">
                {{ (exitQuality.avgRatio * 100).toFixed(0) }}%
              </strong>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">接近目標（≥90%）</span><br>
              <strong :class="exitQuality.nearTargetPct >= 0.4 ? 'up' : 'warn'">
                {{ (exitQuality.nearTargetPct * 100).toFixed(0) }}%
              </strong>
              <span class="muted" style="font-size:0.65rem"> ({{ exitQuality.n }}筆贏單)</span>
            </div>
            <div class="muted" style="font-size:0.75rem">
              {{ exitQuality.avgRatio >= 0.7 ? '✓ 出場品質良好' : '⚠ 過早獲利了結，未能讓贏家奔跑' }}
            </div>
          </div>
        </div>

        <!-- BBB6: Gerald Loeb — Lot Concentration Gini Coefficient -->
        <div class="scard bbb-lot-gini" v-if="lotGini">
          <span class="slabel">倉位集中度 Gini 係數（Loeb：在最有信念的機會集中押注，而非均分資金）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">Gini 係數</span><br>
              <strong :class="lotGini.concentrated ? 'up' : 'muted'" style="font-size:1.3rem">{{ lotGini.gini.toFixed(3) }}</strong>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">張數範圍</span><br>
              <span class="mono">{{ lotGini.min }} – {{ lotGini.max }}張</span>
              <span class="muted" style="font-size:0.65rem"> 均值 {{ lotGini.mean.toFixed(1) }}</span>
            </div>
            <div class="muted" style="font-size:0.75rem">
              {{ lotGini.concentrated ? '✓ 具差異化的倉位配置（信念分級）' : '△ 倉位趨於均等，缺乏信念差異化' }}
            </div>
          </div>
        </div>

        <!-- BBB7: Michael Steinhardt — Monthly Frequency vs Performance Correlation -->
        <div class="scard bbb-freq-corr" v-if="frequencyCorrelation">
          <span class="slabel">月頻率 × 績效相關（Steinhardt：對比觀點需要高度選擇性——過度交易常是信念不足的表現）</span>
          <div style="display:flex;gap:1.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap">
            <div>
              <span class="muted" style="font-size:0.72rem">相關係數 r</span><br>
              <strong :class="frequencyCorrelation.r < -0.3 ? 'up' : frequencyCorrelation.r > 0.3 ? 'warn' : 'muted'" style="font-size:1.3rem">
                r={{ frequencyCorrelation.r >= 0 ? '+' : '' }}{{ frequencyCorrelation.r.toFixed(2) }}
              </strong>
            </div>
            <div class="muted" style="font-size:0.75rem;max-width:220px">
              {{ frequencyCorrelation.r < -0.3 ? '✓ 負相關：交易越少、績效越好（高選擇性有效）' : frequencyCorrelation.r > 0.3 ? '△ 正相關：活躍月份績效更好，可能有動能規律' : '→ 相關性不顯著，頻率與績效關聯不明確' }}
            </div>
          </div>
        </div>

        <!-- BBB10: Philip Fisher — Holding Duration Percentiles -->
        <div class="scard bbb-holding-pct" v-if="holdingPercentiles">
          <span class="slabel">持倉天數分位數（Fisher：耐心持有偉大公司的正確執行——贏單中位數持倉應長於虧單）</span>
          <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.5rem">
            <div>
              <span class="muted" style="font-size:0.72rem">贏單持倉天</span>
              <div style="display:flex;gap:0.5rem;margin-top:2px">
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P25</span><br>
                  <strong class="up" style="font-size:0.85rem">{{ holdingPercentiles.win.p25 }}天</strong>
                </div>
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P50</span><br>
                  <strong class="up" style="font-size:0.85rem">{{ holdingPercentiles.win.p50 }}天</strong>
                </div>
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P75</span><br>
                  <strong class="up" style="font-size:0.85rem">{{ holdingPercentiles.win.p75 }}天</strong>
                </div>
              </div>
            </div>
            <div>
              <span class="muted" style="font-size:0.72rem">虧單持倉天</span>
              <div style="display:flex;gap:0.5rem;margin-top:2px">
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P25</span><br>
                  <strong class="down" style="font-size:0.85rem">{{ holdingPercentiles.loss.p25 }}天</strong>
                </div>
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P50</span><br>
                  <strong class="down" style="font-size:0.85rem">{{ holdingPercentiles.loss.p50 }}天</strong>
                </div>
                <div style="text-align:center">
                  <span class="muted" style="font-size:0.62rem">P75</span><br>
                  <strong class="down" style="font-size:0.85rem">{{ holdingPercentiles.loss.p75 }}天</strong>
                </div>
              </div>
            </div>
            <div :class="holdingPercentiles.wellManaged ? 'up' : 'down'" style="font-size:0.75rem;align-self:center">
              {{ holdingPercentiles.wellManaged ? '✓ 贏單持倉更長（讓利潤奔跑）' : '⚠ 虧單持倉更長（快速認錯紀律不足）' }}
            </div>
          </div>
        </div>

        <!-- CCC1: Jesse Livermore — Planned R/R Bucket Distribution -->
        <div class="scard ccc-rrplan" v-if="plannedRRDist">
          <span class="slabel">計劃風報比分布（Livermore：只進入期望值為正、風報比有利的機會——計劃R/R分布揭示入場紀律）</span>
          <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.5rem">
            <div v-for="b in plannedRRDist.buckets" :key="b.label" style="text-align:center;min-width:80px">
              <strong :class="b.label === '≥2R' ? 'up' : b.label === '<1R' ? 'down' : ''" style="font-size:1.1rem">{{ b.pct.toFixed(0) }}%</strong>
              <div class="muted" style="font-size:0.72rem">計劃 {{ b.label }}</div>
              <div class="muted" style="font-size:0.65rem">{{ b.count }}筆</div>
            </div>
          </div>
          <div style="font-size:0.72rem;margin-top:0.5rem" :class="plannedRRDist.qualityPct >= 60 ? 'up' : plannedRRDist.qualityPct >= 40 ? '' : 'down'">
            {{ plannedRRDist.qualityPct.toFixed(0) }}% 的交易計劃風報比 ≥ 2R {{ plannedRRDist.qualityPct >= 60 ? '✓ 入場紀律良好' : plannedRRDist.qualityPct >= 40 ? '尚可' : '⚠ 低品質入場過多' }}
          </div>
        </div>

        <!-- CCC2: Nicolas Darvas — Symbol Selectivity Index -->
        <div class="scard ccc-selectivity" v-if="symbolSelectivity">
          <span class="slabel">標的選擇性指數（Darvas：深入研究後才行動——重複操作同一標的代表選擇性下降？）</span>
          <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.5rem;align-items:center">
            <div style="text-align:center">
              <strong style="font-size:1.4rem">{{ symbolSelectivity.uniqueSymbols }}</strong>
              <div class="muted" style="font-size:0.72rem">不同標的數</div>
            </div>
            <div style="text-align:center">
              <strong style="font-size:1.4rem">{{ symbolSelectivity.avgTradesPerSymbol.toFixed(1) }}筆</strong>
              <div class="muted" style="font-size:0.72rem">每標的均操作次</div>
            </div>
            <div style="text-align:center">
              <strong :class="symbolSelectivity.onceOnlyPct >= 60 ? 'up' : ''" style="font-size:1.4rem">{{ symbolSelectivity.onceOnlyPct.toFixed(0) }}%</strong>
              <div class="muted" style="font-size:0.72rem">只交易一次的標的</div>
            </div>
          </div>
          <div style="font-size:0.72rem;margin-top:0.5rem;color:var(--muted)">最頻繁：<strong>{{ symbolSelectivity.topSymbol }}</strong>（{{ symbolSelectivity.topCount }}次）{{ symbolSelectivity.avgTradesPerSymbol > 3 ? '⚠ 過度集中單一標的，可能缺乏新機會探索' : '✓ 操作標的多元，符合選擇性原則' }}</div>
        </div>

        <!-- CCC3: William O'Neil — CAN SLIM Catalyst Win Rate -->
        <div class="scard ccc-catalyst" v-if="catalystWinRate">
          <span class="slabel">催化劑勝率分析（O'Neil CAN SLIM：N = 新催化劑，好的催化劑類型應有顯著更高勝率）</span>
          <div class="ccc-catalyst-grid" style="margin-top:0.5rem">
            <div v-for="c in catalystWinRate.catalysts" :key="c.label" class="ccc-catalyst-row">
              <span style="font-size:0.75rem;min-width:70px;word-break:break-all">{{ c.label }}</span>
              <div class="ccc-catalyst-bar-bg">
                <div class="ccc-catalyst-bar-fill" :style="`width:${c.winRate}%;background:${c.winRate >= 60 ? 'var(--good)' : c.winRate >= 40 ? 'var(--warn-soft)' : 'var(--critical)'}`"></div>
              </div>
              <span :class="c.winRate >= 60 ? 'up' : c.winRate < 40 ? 'down' : ''" style="font-size:0.75rem;min-width:42px;text-align:right">{{ c.winRate.toFixed(0) }}%</span>
              <span class="muted" style="font-size:0.65rem">{{ c.total }}筆</span>
            </div>
          </div>
        </div>

        <!-- CCC6: Mark Minervini — VCP Tightness vs Outcome Correlation -->
        <div class="scard ccc-vcp" v-if="vcpCorrelation">
          <span class="slabel">入場緊度 vs 結果相關（Minervini VCP：收縮型態下的緊停損應帶來更高R——Pearson r 量化緊度效益）</span>
          <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.5rem;align-items:center">
            <div style="text-align:center">
              <strong :class="vcpCorrelation.r < -0.2 ? 'up' : vcpCorrelation.r > 0.2 ? 'down' : ''" style="font-size:1.4rem">r={{ vcpCorrelation.r >= 0 ? '+' : '' }}{{ vcpCorrelation.r.toFixed(2) }}</strong>
              <div class="muted" style="font-size:0.72rem">停損距離 vs 實現R</div>
            </div>
            <div style="font-size:0.72rem;color:var(--muted);max-width:220px">
              {{ vcpCorrelation.r < -0.2 ? '✓ 停損越緊、實現R越高（VCP紀律有效）' : vcpCorrelation.r > 0.2 ? '⚠ 停損越寬、實現R反而越高（可能停損設太緊被洗出）' : '無顯著相關（停損設定對結果影響不明顯）' }}
            </div>
          </div>
        </div>

        <!-- CCC7: Paul Tudor Jones — R Multiple Distribution Bins -->
        <div class="scard ccc-rbins" v-if="rBinDist">
          <span class="slabel">R倍數分布（PTJ：尋求 5:1 機會——你的系統有多少大獲全勝？）</span>
          <div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:0.5rem">
            <div v-for="b in rBinDist.bins" :key="b.label" style="text-align:center;min-width:64px">
              <strong :class="b.label === '<0R' ? 'down' : b.label === '≥3R' ? 'up' : ''" style="font-size:1.05rem">{{ b.pct.toFixed(0) }}%</strong>
              <div class="muted" style="font-size:0.7rem">{{ b.label }}</div>
              <div class="muted" style="font-size:0.63rem">{{ b.count }}筆</div>
            </div>
          </div>
          <div style="font-size:0.72rem;margin-top:0.5rem" :class="rBinDist.bigWinPct >= 20 ? 'up' : rBinDist.bigWinPct >= 10 ? '' : 'down'">
            大獲全勝（≥3R）佔比 {{ rBinDist.bigWinPct.toFixed(0) }}% {{ rBinDist.bigWinPct >= 20 ? '✓ 系統能捕捉趨勢行情' : rBinDist.bigWinPct >= 10 ? '尚可' : '⚠ 缺乏大贏單，系統偏均值回歸型' }}
          </div>
        </div>

        <!-- CCC10: Richard Donchian — Win Holding Duration Trend -->
        <div class="scard ccc-duration-trend" v-if="winDurationTrend">
          <span class="slabel">贏單持倉天數趨勢（Donchian 趨勢跟蹤：是否越來越善於持有贏單直到趨勢結束？）</span>
          <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.5rem;align-items:center">
            <div style="text-align:center">
              <strong style="font-size:1.1rem">{{ winDurationTrend.earlyP50 }}天</strong>
              <div class="muted" style="font-size:0.72rem">前半段贏單中位</div>
            </div>
            <div style="font-size:1.2rem;color:var(--muted)">→</div>
            <div style="text-align:center">
              <strong :class="winDurationTrend.improving ? 'up' : 'down'" style="font-size:1.1rem">{{ winDurationTrend.recentP50 }}天</strong>
              <div class="muted" style="font-size:0.72rem">後半段贏單中位</div>
            </div>
            <div :class="winDurationTrend.improving ? 'up' : 'down'" style="font-size:0.75rem">
              {{ winDurationTrend.improving ? '✓ 持倉天數增加，越來越善於持有趨勢' : '⚠ 持倉天數縮短，過早了結獲利的傾向加重' }}
            </div>
          </div>
        </div>

        <!-- TT4: 月份績效柱狀圖 (full width) -->
        <div class="an-block an-block--full" v-if="monthlyPerfBars">
          <span class="slabel">月份績效（月別累計 R）——觀察是否有季節性弱點</span>
          <div class="month-wrap">
            <svg class="month-svg" :viewBox="`0 0 ${monthlyPerfBars.W} ${monthlyPerfBars.svgH}`" :width="monthlyPerfBars.W" :height="monthlyPerfBars.svgH">
              <line x1="0" :y1="monthlyPerfBars.zeroY" :x2="monthlyPerfBars.W" :y2="monthlyPerfBars.zeroY" class="rh-zero" />
              <g v-for="b in monthlyPerfBars.bars" :key="b.x">
                <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :class="b.positive ? 'bar-up' : 'bar-down'" rx="2" />
                <text :x="b.lx" :y="monthlyPerfBars.H + 14" class="month-label" text-anchor="middle">{{ b.label }}</text>
                <title>{{ b.label }}: {{ b.totalR >= 0 ? '+' : '' }}{{ b.totalR.toFixed(2) }}R</title>
              </g>
            </svg>
          </div>
        </div>
      </div>
    </section>

    <!-- E15 複盤教練：從既有統計自動生成的紀律建議 -->
    <section class="section-block" v-reveal v-if="closedTrades.length">
      <div class="coach-head">
        <h3>🎓 複盤教練</h3>
        <!-- W6：AI 複盤找規則式教練沒設計到的細緻行為模式，跟下方規則式建議並存 -->
        <button
          v-if="aiConfigured && closedTrades.length >= 10"
          class="btn xs btn-primary"
          type="button"
          :disabled="aiCoachLoading"
          @click="loadAiCoach"
        >
          <span v-if="aiCoachLoading" class="loading-spinner btn-spinner" aria-hidden="true"></span>
          {{ aiCoachLoading ? '分析中…' : (aiCoachInsight ? '重新分析' : '🤖 AI 複盤（找細緻模式）') }}
        </button>
      </div>
      <ul class="coach-list">
        <li v-for="(insight, i) in coachInsights" :key="i" class="coach-item" :class="'coach-' + insight.tone">
          <span class="coach-icon">{{ insight.icon }}</span>
          <span class="coach-text">{{ insight.text }}</span>
        </li>
      </ul>
      <p class="disclaimer">※ 教練建議由你自己的交易紀錄統計規則產生，僅供覆盤參考，非投資建議。</p>

      <p v-if="aiCoachError" class="error-text">{{ aiCoachError }}</p>
      <div v-if="aiCoachInsight" class="ai-coach-box">
        <strong>🤖 AI 複盤（細緻模式，非統計規則） <InfoTooltip v-bind="metricGlossary.aiJournalCoach" /></strong>
        <p v-html="aiCoachInsightHtml"></p>
        <button class="btn xs" type="button" @click="copyAiCoach(aiCoachInsight)">
          {{ aiCoachCopied ? '已複製！' : '📋 複製' }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useStockStore } from '../stores/stock.js'
import { riskPerShare, profitPerShare, realizedR, tradePnl as pnl, riskAmount, loadJournal, saveJournal, localDateStr } from '../lib/tradeMath'
import { fetchLivePrices } from '../lib/livePriceCache'
import { useSparkline } from '../composables/useSparkline'
import { resolveStockName } from '../lib/stockSearch'
import InfoTooltip from '../components/InfoTooltip.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { useAiStatus } from '../composables/useAiStatus'
import { renderAiMarkdown } from '../composables/useAiMarkdown'
import { useClipboard } from '../composables/useClipboard'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'

const stockStore = useStockStore()

const trades = ref([])
const form = reactive({ symbol: stockStore.symbol || '', side: 'long', entry: null, stop: null, target: null, lots: 1, tag: '', catalyst: '' })

// W6+W7：AI 複盤與進場理由品質檢查，皆為選填、手動觸發，未設定 AI 服務時
// 相關按鈕整個不顯示（不影響交易日誌本身的核心功能）
const { aiConfigured, checkAiConfigured } = useAiStatus()
const aiCoachLoading = ref(false)
const aiCoachInsight = ref('')
const aiCoachError = ref('')
const aiCoachInsightHtml = computed(() => renderAiMarkdown(aiCoachInsight.value))
const { copied: aiCoachCopied, copy: copyAiCoach } = useClipboard()
const catalystChecking = ref(false)
const catalystAssessment = ref('')
const catalystError = ref('') // EE3：跟 aiCoachError 一樣獨立出來，成功/失敗訊息不能共用同一個欄位、同一種樣式

async function loadAiCoach() {
  aiCoachLoading.value = true
  aiCoachError.value = ''
  try {
    const payload = {
      trades: closedTrades.value.map(t => ({
        symbol: t.symbol, side: t.side, entry: t.entry, exit: t.exit,
        r_multiple: Number(realizedR(t).toFixed(2)), tag: t.tag || '', catalyst: t.catalyst || '',
      })),
      stats: stats.value,
    }
    const res = await fetch('/api/v1/journal/ai-coach', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    })
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || 'AI 複盤失敗')
    aiCoachInsight.value = json.data.insight
  } catch (e) {
    aiCoachError.value = e?.message || 'AI 複盤失敗'
  } finally {
    aiCoachLoading.value = false
  }
}

async function checkCatalystQuality() {
  const catalyst = form.catalyst.trim()
  if (!catalyst) return
  catalystChecking.value = true
  catalystAssessment.value = ''
  catalystError.value = ''
  try {
    const res = await fetch('/api/v1/journal/catalyst-quality', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: form.symbol, side: form.side, catalyst }),
    })
    const json = await res.json()
    if (!res.ok || !json.success) throw new Error(json.detail || '檢查失敗')
    catalystAssessment.value = json.data.assessment
  } catch (e) {
    catalystError.value = e?.message || '檢查失敗'
  } finally {
    catalystChecking.value = false
  }
}

// 側欄搜尋切換全站目前個股時，新增交易表單的代號欄位跟著換
// （只在使用者還沒動過欄位、或欄位仍是上一個全站個股時才更新，避免蓋掉
// 使用者正在手動輸入的其他代號）。
watch(() => stockStore.symbol, (sym, prevGlobalSym) => {
  if (sym && (!form.symbol || form.symbol === prevGlobalSym)) form.symbol = sym
})
const formError = ref('')
const importMsg = ref('')

const openTrades = computed(() => trades.value.filter(t => t.status === 'open'))
const openSymbols = computed(() => [...new Set(openTrades.value.map(t => t.symbol))].sort().join(','))

// E16 紙上交易：進行中的部位是「紙上」的（沒有真的下單），但用即時市價算
// 未實現損益，讓使用者練習盯盤/停損紀律，而不用真的冒風險。
const livePrices = ref({}) // symbol -> { price, as_of, loading, error }
const pricesLoading = ref(false)

// AA4: debounce the three openSymbols watchers so a CSV import that adds
// N positions in a loop doesn't fire N×3 parallel API bursts.
// Each watcher gets its own timer so they don't cancel each other out.
let _priceDebounce = null, _eventsDebounce = null, _emaDebounce = null

// 進行中交易的代號組合一變（新增/帶入/刪除），就重新查一次現價。
watch(openSymbols, () => { clearTimeout(_priceDebounce); _priceDebounce = setTimeout(fetchLivePricesForOpenTrades, 300) })

// N1：波段留倉最怕撞上財報/除息等「地雷日」——當沖不用管這個，因為當天就平倉了。
// 進行中部位的代號一變就查一次行事曆，7 天內有事件就在該筆旁標警示。
const EVENT_WARN_DAYS = 7
const upcomingEvents = ref({}) // symbol -> [{date, type, label, estimated}]
watch(openSymbols, () => { clearTimeout(_eventsDebounce); _eventsDebounce = setTimeout(fetchUpcomingEventsForOpenTrades, 300) })

async function fetchUpcomingEventsForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  const today = new Date()
  const cutoff = new Date(today.getTime() + EVENT_WARN_DAYS * 86400000)
  await Promise.all(symbols.map(async (sym) => {
    try {
      const res = await fetch(`/api/v1/analysis/${sym}/calendar`)
      const json = await res.json()
      const events = json?.data?.events || []
      upcomingEvents.value[sym] = events.filter((e) => {
        const d = new Date(e.date + 'T00:00:00')
        return d >= today && d <= cutoff
      })
    } catch {
      upcomingEvents.value[sym] = []
    }
  }))
}

function nextEvent(t) {
  const events = upcomingEvents.value[t.symbol]
  return events && events.length ? events[0] : null
}

// N4：波段持倉的去留不看「抱了幾分鐘」，看「股價是否仍沿著 8 日均線走」——
// 日K實體收盤跌破 8EMA（多單）或站上 8EMA（空單）就是趨勢轉弱的訊號。
const EMA_PERIOD = 8
const emaTrend = ref({}) // symbol -> { ema8, lastClose, broken }
watch(openSymbols, () => { clearTimeout(_emaDebounce); _emaDebounce = setTimeout(fetchEmaTrendForOpenTrades, 300) })

function computeEma(closes, period) {
  if (closes.length < period) return null
  const k = 2 / (period + 1)
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period
  for (let i = period; i < closes.length; i++) ema = closes[i] * k + ema * (1 - k)
  return ema
}

async function fetchEmaTrendForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  await Promise.all(symbols.map(async (sym) => {
    try {
      const res = await fetch(`/api/v1/stocks/${sym}/price`)
      const json = await res.json()
      const items = json?.data?.items || []
      const closes = items.map(i => Number(i.close)).filter(Number.isFinite)
      const ema8 = computeEma(closes, EMA_PERIOD)
      const lastClose = closes.length ? closes[closes.length - 1] : null
      emaTrend.value[sym] = (ema8 == null || lastClose == null) ? null : { ema8, lastClose }
    } catch {
      emaTrend.value[sym] = null
    }
  }))
}

function emaBroken(t) {
  const info = emaTrend.value[t.symbol]
  if (!info) return false
  return t.side === 'long' ? info.lastClose < info.ema8 : info.lastClose > info.ema8
}

function emaBrokenTitle(t) {
  const info = emaTrend.value[t.symbol]
  if (!info) return ''
  return `日K收盤 ${fmt(info.lastClose)} 已${t.side === 'long' ? '跌破' : '站上'} 8 日均線 ${fmt(info.ema8)}，波段趨勢轉弱訊號`
}

async function fetchLivePricesForOpenTrades() {
  const symbols = [...new Set(openTrades.value.map(t => t.symbol))]
  if (!symbols.length) return
  pricesLoading.value = true
  for (const sym of symbols) livePrices.value[sym] = { ...(livePrices.value[sym] || {}), loading: true, error: '' }
  const results = await fetchLivePrices(symbols)
  for (const sym of symbols) {
    const r = results[sym]
    livePrices.value[sym] = { price: r.price, as_of: r.as_of, loading: false, error: r.error }
  }
  pricesLoading.value = false
  updatePeakUnrealized()
}

// N2：波段停利看的是「這筆單曾經賺最多到多少，現在回吐了多少」，不是當沖的
// 「當日總損益回吐 30%」——用高水位（峰值未實現損益）當基準才抓得到。
function updatePeakUnrealized() {
  let changed = false
  for (const t of openTrades.value) {
    const pnl = unrealizedPnl(t)
    if (pnl == null) continue
    if (t.peakUnrealizedPnl == null || pnl > t.peakUnrealizedPnl) {
      t.peakUnrealizedPnl = pnl
      changed = true
    }
  }
  if (changed) save()
}

const PROFIT_GIVEBACK_WARN_PCT = 30

function profitGivebackPct(t) {
  const peak = t.peakUnrealizedPnl
  const pnl = unrealizedPnl(t)
  if (peak == null || pnl == null || peak <= 0) return null
  return Math.max(0, (peak - pnl) / peak * 100)
}

function livePrice(t) { return livePrices.value[t.symbol]?.price ?? null }
function unrealizedProfitPerShare(t) {
  const price = livePrice(t)
  return price == null ? null : profitPerShare(t, price)
}
function unrealizedR(t) {
  const pps = unrealizedProfitPerShare(t)
  if (pps == null) return null
  const risk = riskPerShare(t)
  return risk > 0 ? pps / risk : null
}
function unrealizedPnl(t) {
  const pps = unrealizedProfitPerShare(t)
  return pps == null ? null : (Number(t.lots) || 0) * 1000 * pps
}
function stopBreached(t) {
  const price = livePrice(t)
  if (price == null) return false
  return t.side === 'short' ? price >= Number(t.stop) : price <= Number(t.stop)
}
function closeAtMarket(t) {
  const price = livePrice(t)
  if (price == null) return
  // SS7: 現價平倉是不可逆操作，需確認避免誤觸
  if (!window.confirm(`確定用現價 ${fmt(price)} 對 ${t.symbol} 平倉嗎？平倉後無法還原。`)) return
  t._exitInput = price
  closeTrade(t)
}
const closedTrades = computed(() => trades.value.filter(t => t.status === 'closed'))
// SS10: 顯示用的排序版本（出場日降序），不影響所有依賴 closedTrades 的統計
// computed（stats/byTag/equityPoints 等都各自再排序，不依賴這裡的順序）
const closedTradesSorted = computed(() =>
  [...closedTrades.value].sort((a, b) => new Date(b.exitDate || 0) - new Date(a.exitDate || 0))
)

const stats = computed(() => {
  const cl = closedTrades.value
  const n = cl.length
  if (!n) return { count: 0, winRate: 0, expectancyR: 0, profitFactor: 0, totalR: 0, totalPnl: 0, maxConsecLoss: 0, maxConsecWin: 0, avgWinR: 0, avgLossR: 0 }
  const Rs = cl.map(t => realizedR(t))
  const pnls = cl.map(t => pnl(t))
  const wins = Rs.filter(r => r > 0)
  const losses = Rs.filter(r => r <= 0)
  const grossWin = pnls.filter(p => p > 0).reduce((a, b) => a + b, 0)
  const grossLoss = Math.abs(pnls.filter(p => p < 0).reduce((a, b) => a + b, 0))
  // DD2：closedTrades 沒有固定的時間順序（新交易 unshift 到最前面、CSV 匯入
  // 用 push 加到最後面），連續虧損筆數是「照平倉時間順序數」才有意義——這裡
  // 跟既有的 expectancyTrend 用同一招，另外排一份按 exitDate 排序的複本，
  // 不去動 closedTrades 本身（避免影響其他依賴它目前順序的地方）。
  const chronoRs = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0)).map(realizedR)
  let maxConsec = 0, cur = 0
  // SS8: 同時追蹤連勝，供「連勝後過度自信」的複盤教練規則使用
  let maxConsecW = 0, curW = 0
  for (const r of chronoRs) {
    if (r <= 0) { cur += 1; maxConsec = Math.max(maxConsec, cur); curW = 0 }
    else { curW += 1; maxConsecW = Math.max(maxConsecW, curW); cur = 0 }
  }
  return {
    count: n,
    winRate: wins.length / n,
    expectancyR: Rs.reduce((a, b) => a + b, 0) / n,
    profitFactor: grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? Infinity : 0),
    totalR: Rs.reduce((a, b) => a + b, 0),
    totalPnl: pnls.reduce((a, b) => a + b, 0),
    maxConsecLoss: maxConsec,
    maxConsecWin: maxConsecW,
    avgWinR: wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0,
    avgLossR: losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0,
  }
})

// cumulative-R equity curve — DD2：跟 stats.maxConsecLoss 同一個理由，要照
// 平倉時間順序累加才是真正的權益曲線，不能照陣列的插入順序。
const equityPoints = computed(() => {
  const chrono = [...closedTrades.value].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  let cum = 0
  const pts = [0]
  for (const t of chrono) { cum += realizedR(t); pts.push(cum) }
  return pts
})
const eqW = 600, eqH = 120
// R7：共用 sparkline composable，includeValue: 0 讓零線永遠落在圖表範圍內
// （權益曲線要看得到零線，不能因為全部都是正值/負值而被擠出畫面）。
const { points: equityPolyline, toY: eqToY } = useSparkline(equityPoints, { width: eqW, height: eqH, includeValue: 0 })
const eqZeroY = computed(() => eqToY.value(0))

// R-multiple distribution histogram
// SS3: 固定顯示範圍 [-4R, +8R] 避免單筆極端 R 把整個直方圖壓扁，超出範圍的
// 交易計為 outlier 顯示在軸標籤，不影響 bin 分布的可讀性。
const HIST_R_MIN = -4, HIST_R_MAX = 8
const rHist = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (!Rs.length) return null
  const min = HIST_R_MIN, max = HIST_R_MAX
  const lowOutliers = Rs.filter(r => r < min).length
  const highOutliers = Rs.filter(r => r > max).length
  const bins = 16
  const range = max - min
  const counts = new Array(bins).fill(0)
  for (const r of Rs) {
    const clipped = Math.max(min, Math.min(max, r))
    let idx = Math.floor(((clipped - min) / range) * bins)
    if (idx >= bins) idx = bins - 1
    if (idx < 0) idx = 0
    counts[idx] += 1
  }
  const maxC = Math.max(...counts, 1)
  const bw = eqW / bins
  return {
    min, max, lowOutliers, highOutliers,
    zeroX: ((0 - min) / range) * eqW,
    bars: counts.map((c, i) => ({ x: i * bw, w: Math.max(bw - 1, 1), h: (c / maxC) * eqH, mid: min + (i + 0.5) * (range / bins) })),
  }
})

// group closed trades by 型態 tag
const byTag = computed(() => {
  const groups = {}
  for (const t of closedTrades.value) {
    const key = (t.tag && String(t.tag).trim()) || '未分類'
    if (!groups[key]) groups[key] = []
    groups[key].push(t)
  }
  return Object.entries(groups).map(([tag, arr]) => {
    const Rs = arr.map(realizedR)
    const totalR = Rs.reduce((a, b) => a + b, 0)
    return { tag, count: arr.length, winRate: Rs.filter(r => r > 0).length / arr.length, expectancyR: totalR / arr.length, totalR }
  }).sort((a, b) => b.totalR - a.totalR)
})

// F2 部位大小一致性：抓「哪幾筆押注明顯比平常大」（風險金額 ≥ 該交易者
// 自己歷史中位數的 1.5 倍），再看這些押得比較重的交易表現是不是反而比較
// 差——常是報復性下單/情緒化加碼的訊號，而非真的更有信心的紀律決策。
const sizeConsistency = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 8) return null
  const amounts = cl.map(riskAmount).filter(a => a > 0).sort((a, b) => a - b)
  if (amounts.length < 8) return null
  const mid = Math.floor(amounts.length / 2)
  const median = amounts.length % 2 ? amounts[mid] : (amounts[mid - 1] + amounts[mid]) / 2
  if (median <= 0) return null
  const oversized = cl.filter(t => riskAmount(t) >= median * 1.5)
  const normal = cl.filter(t => riskAmount(t) < median * 1.5)
  if (oversized.length < 3 || normal.length < 3) return null
  const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length
  return { count: oversized.length, oversizedR: avg(oversized.map(realizedR)), normalR: avg(normal.map(realizedR)) }
})

// F3 期望值趨勢（邊際衰退偵測）：把已平倉交易按出場日排序，比較「最近 N
// 筆」跟「更早之前」的期望值。以前有正期望值、最近卻明顯轉差，代表策略
// 邊際可能在衰退、市場體制變了，或是執行紀律開始鬆動——不是單純的運氣
// 波動，值得先降部位、重新檢視最近的交易，而不是照常加大力度想拗回來。
const RECENT_TREND_N = 10
const expectancyTrend = computed(() => {
  const cl = closedTrades.value
  const n = cl.length
  if (n < 20) return null
  const chrono = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const recent = chrono.slice(-RECENT_TREND_N)
  const earlier = chrono.slice(0, n - RECENT_TREND_N)
  if (!earlier.length) return null
  const avg = (arr) => arr.reduce((a, t) => a + realizedR(t), 0) / arr.length
  return { recentR: avg(recent), earlierR: avg(earlier), recentN: recent.length, earlierN: earlier.length }
})

// F4 過度交易偵測：把所有交易（不分已平倉/進行中）按進場日分組，算出「有
// 交易的那些天」典型一天做幾筆，再看有沒有哪天筆數暴增。不管那天賺賠，
// 單日筆數突然暴增本身就是衝動/報復性下單的訊號，跟結果無關。
const overtradingDay = computed(() => {
  const byDay = {}
  for (const t of trades.value) {
    if (!t.openDate) continue
    byDay[t.openDate] = (byDay[t.openDate] || 0) + 1
  }
  const counts = Object.values(byDay)
  if (counts.length < 5) return null
  const sorted = [...counts].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  if (median <= 0) return null
  let maxDay = null, maxCount = 0
  for (const [day, c] of Object.entries(byDay)) {
    if (c > maxCount) { maxCount = c; maxDay = day }
  }
  if (maxCount >= Math.max(4, median * 3)) {
    return { day: maxDay, count: maxCount, median }
  }
  return null
})

// F5 停損執行紀律：虧損交易的實際出場價，有沒有真的在停損價附近出場，還是
// 凹單讓虧損超過原本設定的停損（尤其做多不設停損就跑，虧更深）。這是「執行
// 有沒有照計畫」的問題，跟賺賠不對稱、部位大小、頻率都是不同角度。
const stopAdherence = computed(() => {
  const losers = closedTrades.value.filter(t => realizedR(t) < 0)
  if (losers.length < 5) return null
  const blownThrough = losers.filter((t) => {
    const risk = riskPerShare(t)
    if (risk <= 0) return false
    const diff = t.side === 'short' ? (Number(t.exit) || 0) - (Number(t.stop) || 0) : (Number(t.stop) || 0) - (Number(t.exit) || 0)
    return diff > risk * 0.1
  })
  if (blownThrough.length < 3) return null
  const ratio = blownThrough.length / losers.length
  if (ratio < 0.4) return null
  const avgBlownR = blownThrough.reduce((a, t) => a + realizedR(t), 0) / blownThrough.length
  return { count: blownThrough.length, total: losers.length, ratio, avgBlownR }
})

// F8 持有期處置效應：贏單抱太短、輸單抱太長（disposition effect）。純看持有
// 天數（exitDate - openDate），跟停損執行（F5）、賺賠不對稱、部位、頻率都是
// 不同角度——問的是「該放的沒放、該砍的沒砍」。
const holdingDisposition = computed(() => {
  const cl = closedTrades.value
  const holdDays = (t) => {
    if (!t.openDate || !t.exitDate) return null  // AA3: guard missing dates
    const o = new Date(t.openDate).getTime(), e = new Date(t.exitDate).getTime()
    if (isNaN(o) || isNaN(e)) return null
    return Math.max(0, Math.round((e - o) / 86400000))
  }
  const winHolds = cl.filter(t => realizedR(t) > 0).map(holdDays).filter(d => d != null)
  const lossHolds = cl.filter(t => realizedR(t) < 0).map(holdDays).filter(d => d != null)
  if (winHolds.length < 3 || lossHolds.length < 3) return null
  const winHold = winHolds.reduce((a, b) => a + b, 0) / winHolds.length
  const lossHold = lossHolds.reduce((a, b) => a + b, 0) / lossHolds.length
  if (winHold <= 0) return null
  const ratio = lossHold / winHold
  if (ratio < 1.5) return null
  return { winHold, lossHold, ratio, winN: winHolds.length, lossN: lossHolds.length }
})

// SS6: 贏單實際 R vs 目標 R — 偵測是否習慣提前出場而沒到達設定目標
const targetShortfall = computed(() => {
  const winsWithTarget = closedTrades.value.filter(t =>
    realizedR(t) > 0 && t.target != null && Number(t.target) > 0
  )
  const paired = winsWithTarget.map(t => {
    const risk = riskPerShare(t)
    if (risk <= 0) return null
    const tR = Math.abs((Number(t.target) - Number(t.entry)) / risk)
    if (tR <= 0.5) return null  // 目標太接近進場，不計入
    return { actual: realizedR(t), target: tR }
  }).filter(Boolean)
  if (paired.length < 5) return null
  const avgTargetR = paired.reduce((a, b) => a + b.target, 0) / paired.length
  const avgActualWinR = paired.reduce((a, b) => a + b.actual, 0) / paired.length
  if (avgTargetR <= 1) return null
  const ratio = avgActualWinR / avgTargetR
  if (ratio >= 0.75) return null  // 達成率 75% 以上算正常
  return { avgTargetR, avgActualWinR, ratio, count: paired.length }
})

// TT2: 損益貢獻結構（贏單 R 合計 vs 輸單 R 合計）
const grossRDecomp = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  let grossWinR = 0, grossLossR = 0
  for (const t of cl) {
    const r = realizedR(t)
    if (r > 0) grossWinR += r; else grossLossR += r
  }
  if (!grossWinR) return null
  return { grossWinR, grossLossR }
})

// TT3: 計畫 R:R（目標/停損）vs 實際 R（中位數比較）
const planVsActual = computed(() => {
  const paired = closedTrades.value.filter(t =>
    t.target != null && Number(t.target) > 0
  ).map(t => {
    const risk = riskPerShare(t)
    if (risk <= 0) return null
    const plannedR = Math.abs((Number(t.target) - Number(t.entry)) / risk)
    if (plannedR <= 0.5) return null
    return { plannedR, actualR: realizedR(t) }
  }).filter(Boolean)
  if (paired.length < 5) return null
  const sortedP = [...paired].sort((a, b) => a.plannedR - b.plannedR)
  const sortedA = [...paired].sort((a, b) => a.actualR - b.actualR)
  const mid = Math.floor(paired.length / 2)
  const medP = paired.length % 2 ? sortedP[mid].plannedR : (sortedP[mid - 1].plannedR + sortedP[mid].plannedR) / 2
  const medA = paired.length % 2 ? sortedA[mid].actualR : (sortedA[mid - 1].actualR + sortedA[mid].actualR) / 2
  return { medianPlannedR: medP, medianActualR: medA, count: paired.length }
})

// TT4: 月份績效（按出場月份分組，累計 R）
const monthlyPerf = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const byMonth = {}
  for (const t of cl) {
    if (!t.exitDate) continue
    const month = t.exitDate.slice(0, 7)
    byMonth[month] = (byMonth[month] || 0) + realizedR(t)
  }
  const months = Object.entries(byMonth).sort(([a], [b]) => a < b ? -1 : 1)
  if (months.length < 2) return null
  return months.map(([month, totalR]) => ({ month, totalR }))
})

// TT4 月份績效圖表參數
const monthlyPerfBars = computed(() => {
  const months = monthlyPerf.value
  if (!months) return null
  const n = months.length
  const H = 80, bw = 32, pad = 6
  const W = Math.max(n * (bw + pad) + pad * 2, 300)
  const maxAbs = Math.max(...months.map(m => Math.abs(m.totalR)), 0.1)
  return {
    bars: months.map((m, i) => {
      const h = Math.max(2, (Math.abs(m.totalR) / maxAbs) * (H / 2))
      const positive = m.totalR >= 0
      return {
        x: pad + i * (bw + pad),
        w: bw,
        y: positive ? H / 2 - h : H / 2,
        h,
        positive,
        lx: pad + i * (bw + pad) + bw / 2,
        label: m.month.slice(2),
        totalR: m.totalR,
      }
    }),
    W, H, svgH: H + 20, zeroY: H / 2,
  }
})

// TT9: 勝率 × 盈虧比象限圖（SVG）
const quadrantChart = computed(() => {
  const s = stats.value
  if (s.count < 5 || s.avgWinR <= 0 || s.avgLossR >= 0) return null
  const payoffRatio = s.avgWinR / Math.abs(s.avgLossR)
  const maxX = Math.max(3, Math.ceil(payoffRatio * 1.6))
  const W = 260, H = 150, ML = 40, MT = 10, MB = 26
  const scX = (x) => ML + (x / maxX) * W
  const scY = (y) => MT + H - y * H
  const pts = []
  for (let i = 0; i <= 60; i++) {
    const bx = (i / 60) * maxX
    const by = bx === 0 ? 1 : 1 / (1 + bx)
    pts.push(`${scX(bx).toFixed(1)},${scY(by).toFixed(1)}`)
  }
  const curvePath = 'M' + pts.join('L')
  const dotX = scX(Math.min(payoffRatio, maxX * 0.98)).toFixed(1)
  const dotY = scY(Math.min(Math.max(s.winRate, 0.01), 0.99)).toFixed(1)
  const above = s.winRate > 1 / (1 + payoffRatio)
  const xTicks = [0, Math.round(maxX / 2 * 10) / 10, maxX].map(v => ({ x: scX(v).toFixed(1), label: v.toFixed(1) }))
  const yTicks = [0, 0.5, 1].map(v => ({ y: scY(v).toFixed(1), label: Math.round(v * 100) + '%' }))
  return {
    curvePath, dotX, dotY, above, px: payoffRatio.toFixed(1), py: (s.winRate * 100).toFixed(0),
    xTicks, yTicks,
    svgW: W + ML + 14, svgH: H + MT + MB,
    ax1: ML, ax2: ML + W, ay1: MT, ay2: MT + H,
  }
})

// E15 複盤教練：純用既有統計（stats/byTag）產生規則式建議，不打任何 API。
// tone 排序 bad > warn > good > info；最多顯示 6 條，避免資訊過載。
const coachInsights = computed(() => {
  const s = stats.value
  const out = []
  if (!s.count) return out

  // 1. 賺賠不對稱：平均獲利遠小於平均虧損（賺一點就跑、賠了拗單）
  if (s.avgWinR > 0 && s.avgLossR < 0 && s.avgWinR < Math.abs(s.avgLossR) * 0.8) {
    out.push({
      tone: 'bad', icon: '✂️',
      text: `平均獲利 ${s.avgWinR.toFixed(2)}R 小於平均虧損 ${Math.abs(s.avgLossR).toFixed(2)}R——典型「賺一點就跑、賠了拗單」。就算勝率不低也難賺錢，建議停損照設定執行、目標價至少拉到 1.5 倍風險。`,
    })
  }

  // 2. 停損執行紀律：虧損交易常常凹單超過原本設定的停損
  const sa = stopAdherence.value
  if (sa) {
    out.push({
      tone: 'bad', icon: '⛔',
      text: `近 ${sa.total} 筆虧損交易中，有 ${sa.count} 筆（${(sa.ratio * 100).toFixed(0)}%）實際出場價比原本設定的停損還差——代表停損常常沒有照計畫執行、放任虧損擴大（凹單）。這些凹過頭的交易平均 ${sa.avgBlownR.toFixed(2)}R，通常比乾脆照停損出場更慘。停損要嘛照設定執行、要嘛出場前先改單，別盤中臨時凹單。`,
    })
  }

  // 2b. F8 持有期處置效應：獲利抱太短、虧損抱太長
  const hd = holdingDisposition.value
  if (hd) {
    out.push({
      tone: 'bad', icon: '⏳',
      text: `虧損交易平均持有 ${hd.lossHold.toFixed(0)} 天，獲利交易卻只抱 ${hd.winHold.toFixed(0)} 天就了結——典型「砍贏單、凹輸單」的處置效應，長期會嚴重侵蝕期望值。建議讓獲利部位照原訂目標價運行、虧損部位到停損就出場，別反過來。`,
    })
  }

  // 3. 連續虧損過多：情緒最容易在此時被放大成報復性下單
  if (s.maxConsecLoss >= 4) {
    out.push({
      tone: 'warn', icon: '🌊',
      text: `最長連續虧損 ${s.maxConsecLoss} 筆。連虧到第 3 筆之後最容易報復性下單、越做越大——建議連虧 3 筆就強制停手一天，冷靜後再上場。`,
    })
  }

  // SS8: 連勝後過度自信偵測
  if (s.maxConsecWin >= 4) {
    out.push({
      tone: 'warn', icon: '🔥',
      text: `最長連續獲利 ${s.maxConsecWin} 筆。連勝後最容易「感覺很好」而輕敵——不自覺放大部位、跳過進場條件、追高進場。建議連勝後仍嚴格對照每筆是否符合原本的進場條件，把連勝視為測試紀律的時刻，而非「我悟了」的訊號。`,
    })
  }

  // SS6: 贏單實際 R vs 設定目標 R — 提前出場偵測
  const ts = targetShortfall.value
  if (ts) {
    out.push({
      tone: 'warn', icon: '🎯',
      text: `設有目標價的 ${ts.count} 筆獲利交易，平均目標 +${ts.avgTargetR.toFixed(1)}R，實際卻只達到 +${ts.avgActualWinR.toFixed(1)}R（達成率 ${(ts.ratio * 100).toFixed(0)}%）——代表你習慣在到達目標之前提前出場（恐懼回吐獲利）。建議按目標執行或預設分批出場，避免因短期波動砍掉本來可以跑到的獲利。`,
    })
  }

  // 4. 整體期望值為負且樣本夠大：目前做法長期是虧錢的
  if (s.count >= 10 && s.expectancyR < 0) {
    out.push({
      tone: 'bad', icon: '📉',
      text: `近 ${s.count} 筆交易整體期望值為 ${s.expectancyR.toFixed(2)}R（負值）——照目前的做法長期會虧錢。先停手複盤找出問題，別急著加碼攤平想扳回來。`,
    })
  }

  // 5. 最拖累績效的型態：筆數夠多、期望值為負
  const tags = byTag.value
  const worstTag = tags.find(g => g.count >= 5 && g.expectancyR < 0)
  if (worstTag) {
    out.push({
      tone: 'warn', icon: '🚫',
      text: `「${worstTag.tag}」型態做了 ${worstTag.count} 次，期望值 ${worstTag.expectancyR.toFixed(2)}R——是拖累績效的主因，建議先停用這個 setup 或重新檢視進場條件。`,
    })
  }

  // 6. 表現最好的型態：值得集中火力
  const bestTag = tags.find(g => g.count >= 3 && g.expectancyR >= 0.3)
  if (bestTag) {
    out.push({
      tone: 'good', icon: '🎯',
      text: `「${bestTag.tag}」型態勝率 ${(bestTag.winRate * 100).toFixed(0)}%、期望值 +${bestTag.expectancyR.toFixed(2)}R，是目前表現最好的設定——之後可以優先找這種形態進場。`,
    })
  }

  // 7. 部位大小一致性：押得比平常大的那些單，表現反而更差
  const sc = sizeConsistency.value
  if (sc && sc.oversizedR < sc.normalR - 0.3) {
    out.push({
      tone: 'warn', icon: '⚖️',
      text: `押注明顯偏大（風險金額 ≥ 平時 1.5 倍）的 ${sc.count} 筆，平均 ${sc.oversizedR.toFixed(2)}R，比一般大小的 ${sc.normalR.toFixed(2)}R 還差——加碼的那幾筆常是情緒化決策而非紀律決策，建議把單筆風險金額固定下來，別憑感覺放大。`,
    })
  }

  // 8. 期望值趨勢：最近表現比先前基準明顯轉差（邊際衰退）
  const et = expectancyTrend.value
  if (et && et.earlierR > 0.1 && et.recentR < et.earlierR - 0.4) {
    out.push({
      tone: 'warn', icon: '🕰️',
      text: `最近 ${et.recentN} 筆期望值 ${et.recentR.toFixed(2)}R，比先前 ${et.earlierN} 筆的 ${et.earlierR.toFixed(2)}R 明顯轉差——留意是策略邊際真的在衰退、市場體制變了，還是自己執行紀律開始鬆動（提早出場、追高進場）。建議先降低部位到有把握的水準，重新檢視最近的交易。`,
    })
  }

  // 9. 過度交易：某天筆數暴增，不管賺賠都是衝動下單的訊號
  const ot = overtradingDay.value
  if (ot) {
    out.push({
      tone: 'warn', icon: '🌀',
      text: `${ot.day} 那天做了 ${ot.count} 筆交易，是你平常一天（中位數 ${ot.median} 筆）的 ${(ot.count / ot.median).toFixed(1)} 倍——單日爆量下單常是衝動/報復性交易的訊號，不管那天賺賠，都建議設下每日交易筆數上限。`,
    })
  }

  // 10. 樣本數不足：統計還不太可靠
  if (s.count < 15) {
    out.push({
      tone: 'info', icon: 'ℹ️',
      text: `目前只有 ${s.count} 筆已平倉紀錄，統計上還不太可靠。建議累積到至少 20-30 筆，再認真檢討要不要調整策略。`,
    })
  }

  // 11. 沒有任何警訊時的正向回饋
  if (!out.some(x => x.tone === 'bad' || x.tone === 'warn') && s.count >= 10 && s.expectancyR > 0 && s.profitFactor >= 1.5) {
    out.push({
      tone: 'good', icon: '✅',
      text: `期望值 +${s.expectancyR.toFixed(2)}R、獲利因子 ${s.profitFactor === Infinity ? '∞' : s.profitFactor.toFixed(2)}，目前紀律執行得不錯——繼續保持，別因為手癢而破壞已經有效的作法。`,
    })
  }

  const order = { bad: 0, warn: 1, good: 2, info: 3 }
  return out.sort((a, b) => order[a.tone] - order[b.tone]).slice(0, 8)
})

// UU1: Sortino Ratio — 只用下行波動（負 R）計算風險，比 Sharpe 更貼近交易實情
// 機構標準：> 1.0 優秀，0-1 尚可，< 0 系統問題
const sortinoRatio = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const Rs = cl.map(realizedR)
  const mean = Rs.reduce((a, b) => a + b, 0) / Rs.length
  const downR = Rs.filter(r => r < 0)
  if (!downR.length) return mean > 0 ? Infinity : null
  const downStd = Math.sqrt(downR.reduce((a, r) => a + r * r, 0) / downR.length)
  return downStd > 0 ? mean / downStd : null
})

// UU2: 多空分開統計 — Minervini: 知道自己在哪個方向有真正優勢，把資本集中在那裡
const bySide = computed(() => {
  const cl = closedTrades.value
  return ['long', 'short'].map(side => {
    const arr = cl.filter(t => t.side === side)
    if (!arr.length) return null
    const Rs = arr.map(realizedR)
    const wins = Rs.filter(r => r > 0)
    return { side, count: arr.length, winRate: wins.length / arr.length, expectancyR: Rs.reduce((a, b) => a + b, 0) / arr.length, totalR: Rs.reduce((a, b) => a + b, 0) }
  }).filter(Boolean)
})

// UU4: R 分布偏態係數 — 右偏 = 截虧讓利（好），左偏 = 凹單或跑太快（差）
// Minervini/Seykota「截斷虧損、讓利潤奔跑」的結果會反映在右偏分布上
const rSkewness = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 3) return null
  const n = Rs.length
  const mean = Rs.reduce((a, b) => a + b, 0) / n
  const variance = Rs.reduce((a, r) => a + (r - mean) ** 2, 0) / n
  const std = Math.sqrt(variance)
  if (std < 0.001) return null
  return Rs.reduce((a, r) => a + ((r - mean) / std) ** 3, 0) / n
})

// UU7: 依星期幾績效分析 — 識別個人化弱勢交易日，系統性規避
const byDayOfWeek = computed(() => {
  const labels = ['週一', '週二', '週三', '週四', '週五']
  const groups = labels.map(() => [])
  for (const t of closedTrades.value) {
    if (!t.exitDate) continue
    const d = new Date(t.exitDate).getDay() // 0=Sun
    const idx = d - 1 // 0=Mon...4=Fri
    if (idx >= 0 && idx <= 4) groups[idx].push(realizedR(t))
  }
  return labels.map((label, i) => {
    const Rs = groups[i]
    if (!Rs.length) return { label, count: 0, totalR: 0, winRate: null }
    const wins = Rs.filter(r => r > 0)
    return { label, count: Rs.length, totalR: Rs.reduce((a, b) => a + b, 0), winRate: wins.length / Rs.length }
  })
})
const dayOfWeekHasData = computed(() => byDayOfWeek.value.some(d => d.count > 0))

// UU8: 型態近5筆表現 — 動態資本配置，集中在近期有效策略
const byTagWithRecent = computed(() => {
  const cl = [...closedTrades.value].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  return byTag.value.map(g => {
    const last5 = cl.filter(t => (t.tag && String(t.tag).trim() || '未分類') === g.tag).slice(-5)
    const recent5Rs = last5.map(realizedR)
    const recent5Exp = last5.length >= 3 ? recent5Rs.reduce((a, b) => a + b, 0) / last5.length : null
    return { ...g, recent5Exp, recent5Count: last5.length }
  })
})

// UU10: 系統績效健康總分（Ed Seykota 整合評估）
// 5 個維度各 20 分，讓交易者一眼判斷目前系統狀態
const systemHealth = computed(() => {
  const s = stats.value
  if (s.count < 10) return null
  const items = [
    { label: '勝率 ≥ 50%', ok: s.winRate >= 0.5, detail: `${(s.winRate * 100).toFixed(0)}%` },
    { label: '期望值 > 0', ok: s.expectancyR > 0, detail: `${s.expectancyR.toFixed(2)}R` },
    { label: '獲利因子 ≥ 1.5', ok: s.profitFactor >= 1.5, detail: s.profitFactor === Infinity ? '∞' : s.profitFactor.toFixed(2) },
    { label: '最大連虧 ≤ 4', ok: s.maxConsecLoss <= 4, detail: `${s.maxConsecLoss} 筆` },
    { label: '平均盈虧比 ≥ 1', ok: s.avgLossR < 0 && s.avgWinR >= Math.abs(s.avgLossR), detail: s.avgLossR < 0 ? `${(s.avgWinR / Math.abs(s.avgLossR)).toFixed(2)}` : '—' },
  ]
  const score = items.filter(i => i.ok).length * 20
  return { score, items }
})

// VV1: 當前連勝/連敗條數（Mark Douglas: 狀態覺察，連敗 ≥ 3 提示復仇交易風險）
const currentStreak = computed(() => {
  const cl = [...closedTrades.value].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  if (!cl.length) return null
  const lastWin = realizedR(cl[cl.length - 1]) > 0
  let count = 0
  for (let i = cl.length - 1; i >= 0; i--) {
    if ((realizedR(cl[i]) > 0) === lastWin) count++
    else break
  }
  return { type: lastWin ? 'win' : 'loss', count }
})

// VV2: 回報回撤比 Recovery Factor（CTA 業界標準）
// RF = 累計 R ÷ R 曲線最大回撤；> 3 優秀，1-3 尚可，< 1 需要改善
const recoveryFactor = computed(() => {
  const pts = equityPoints.value
  if (pts.length < 5) return null
  const totalR = pts[pts.length - 1]
  let peak = 0, maxDD = 0
  for (const p of pts) {
    if (p > peak) peak = p
    maxDD = Math.max(maxDD, peak - p)
  }
  if (!maxDD || peak <= 0) return null
  return { rf: totalR / maxDD, totalR, maxDD }
})

// VV3: 催化劑/進場理由分析（O'Neil CAN SLIM：知道「為什麼進場」決定勝率天花板）
// 按 catalyst 欄位分組，取前 5 高期望值的進場理由
const byCatalyst = computed(() => {
  const cl = closedTrades.value.filter(t => t.catalyst && String(t.catalyst).trim())
  if (cl.length < 3) return []
  const groups = {}
  for (const t of cl) {
    const key = String(t.catalyst).trim()
    if (!groups[key]) groups[key] = []
    groups[key].push(realizedR(t))
  }
  return Object.entries(groups)
    .map(([catalyst, Rs]) => {
      const wins = Rs.filter(r => r > 0)
      return { catalyst, count: Rs.length, winRate: wins.length / Rs.length, expectancyR: Rs.reduce((a, b) => a + b, 0) / Rs.length, totalR: Rs.reduce((a, b) => a + b, 0) }
    })
    .sort((a, b) => b.expectancyR - a.expectancyR)
    .slice(0, 5)
})

// VV4: 交易頻率警告（Van Tharp: 過度交易是系統失效的早期訊號）
// > 3 筆/週 = 過度交易警告
const tradeFreqPerWeek = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 2) return null
  const sorted = [...cl].sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const first = new Date(sorted[0].exitDate || 0)
  const last = new Date(sorted[sorted.length - 1].exitDate || 0)
  const weeks = Math.max(1, (last - first) / (7 * 24 * 3600 * 1000))
  const freq = cl.length / weeks
  return { freq, elevated: freq > 3 }
})

// VV7: 標的集中度（John Templeton: 分散是防止無知的保護，單一標的 > 30% 集中警告）
const bySymbolConc = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 3) return null
  const Rs = cl.map(realizedR)
  const totalAbsR = Rs.reduce((a, r) => a + Math.abs(r), 0)
  if (!totalAbsR) return null
  const groups = {}
  for (let i = 0; i < cl.length; i++) {
    const sym = cl[i].symbol || '?'
    if (!groups[sym]) groups[sym] = 0
    groups[sym] += Math.abs(Rs[i])
  }
  const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]).slice(0, 5)
  const [topSym, topAbs] = sorted[0]
  const topPct = topAbs / totalAbsR * 100
  return { top: sorted.map(([sym, absR]) => ({ sym, absR, pct: absR / totalAbsR * 100 })), concentrated: topPct > 30, topSym, topPct }
})

// VV8: 進行中部位總熱度（Van Tharp Total Heat: 整體風險曝露不能超過帳戶的 6-10%）
const openHeatPct = computed(() => {
  const open = openTrades.value
  if (!open.length) return null
  let accountSize = 0
  try { accountSize = Number(localStorage.getItem('finlab_sizing_account')) || 0 } catch {}
  if (!accountSize) return null
  const totalRisk = open.reduce((a, t) => {
    const risk = Math.abs((Number(t.entry) || 0) - (Number(t.stop) || 0)) * (Number(t.lots) || 0) * 1000
    return a + risk
  }, 0)
  return { pct: totalRisk / accountSize * 100, totalRisk, accountSize }
})

// VV10: 異常交易依賴分析（Taleb: 若獲利集中在少數幾筆，系統本質上是脆弱的）
// 前三名大贏 > 50% 總正R = 脆弱警告：結果取決於極少數幸運交易
const outlierFrailty = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const Rs = cl.map(realizedR)
  const posRs = Rs.filter(r => r > 0)
  if (!posRs.length) return null
  const totalPosR = posRs.reduce((a, b) => a + b, 0)
  const top3Sum = [...posRs].sort((a, b) => b - a).slice(0, 3).reduce((a, b) => a + b, 0)
  const pct = top3Sum / totalPosR * 100
  return { pct, fragile: pct > 50 }
})

// WW1: 贏單 vs 輸單平均持倉天數（Livermore: 知道你的時間框架；Darvas: 截虧快、讓利潤跑）
// 輸單持倉比贏單長 = 凹單傾向；贏單比輸單長 = 趨勢跟隨
const holdTimeAnalysis = computed(() => {
  const cl = [...closedTrades.value]
    .filter(t => t.openDate && t.exitDate)
    .map(t => {
      const days = Math.max(0, (new Date(t.exitDate) - new Date(t.openDate)) / 86400000)
      return { days, win: realizedR(t) > 0 }
    })
  if (cl.length < 3) return null
  const wins = cl.filter(t => t.win)
  const losses = cl.filter(t => !t.win)
  const avgWin = wins.length ? wins.reduce((a, t) => a + t.days, 0) / wins.length : 0
  const avgLoss = losses.length ? losses.reduce((a, t) => a + t.days, 0) / losses.length : 0
  return { avgWin, avgLoss, holdsLonger: avgLoss > avgWin, winsCount: wins.length, lossCount: losses.length }
})

// WW2: 滾動10筆勝率趨勢（Druckenmiller: 系統轉好還是轉差，要早發現）
// 使用滑動窗口計算，sparkline 顯示動態
const rollingWinRatePoints = computed(() => {
  const cl = [...closedTrades.value]
    .sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  const W = 10
  if (cl.length < W) return []
  const pts = []
  for (let i = W; i <= cl.length; i++) {
    const slice = cl.slice(i - W, i)
    const wins = slice.filter(t => realizedR(t) > 0).length
    pts.push(wins / W)
  }
  return pts
})
const rollingWrW = 200, rollingWrH = 40
const { points: rollingWrPolyline } = useSparkline(rollingWinRatePoints, { width: rollingWrW, height: rollingWrH, includeValue: 0.5 })

// WW3: 張數一致性（Tom Basso: 系統化不只是進場訊號，連部位大小也要一致）
// CV（變異係數）= 標準差/平均，越低越一致，> 40% 代表感情用事調整部位
const lotConsistency = computed(() => {
  const lots = closedTrades.value.map(t => Number(t.lots) || 0).filter(v => v > 0)
  if (lots.length < 5) return null
  const mean = lots.reduce((a, b) => a + b, 0) / lots.length
  if (!mean) return null
  const std = Math.sqrt(lots.reduce((a, v) => a + (v - mean) ** 2, 0) / lots.length)
  const cv = std / mean * 100
  return { cv, mean, std, consistent: cv < 20 }
})

// WW4: 近零報酬交易滲漏（Larry Williams: 小贏和小輸都是資本浪費）
// |R| < 0.3 的交易：消耗滑價、手續費、注意力，卻無績效貢獻
const nearZeroLeak = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 5) return null
  const leaks = Rs.filter(r => Math.abs(r) < 0.3)
  return { count: leaks.length, total: Rs.length, pct: leaks.length / Rs.length * 100 }
})

// WW5: R/天 資本效率（Druckenmiller: 同樣獲利，佔用資金越少天越有效率）
// Total R ÷ 總交易天數（以最早進場到最晚出場的日曆天計算）
const rPerDay = computed(() => {
  const cl = closedTrades.value.filter(t => t.openDate && t.exitDate)
  if (cl.length < 3) return null
  const sorted = [...cl].sort((a, b) => new Date(a.openDate) - new Date(b.openDate))
  const spanDays = Math.max(1, (new Date(sorted[sorted.length - 1].exitDate) - new Date(sorted[0].openDate)) / 86400000)
  const totalR = stats.value.totalR
  return { rPerDay: totalR / spanDays, spanDays: Math.round(spanDays), totalR }
})

// WW7: 最近8週週績效（機構標準: 週為最小績效評估單位）
const weeklyPerf = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 2) return null
  const getWeekKey = (d) => {
    const dt = new Date(d)
    const day = dt.getDay() || 7
    dt.setDate(dt.getDate() + 1 - day) // Monday
    return dt.toISOString().slice(0, 10)
  }
  const groups = {}
  for (const t of cl) {
    const wk = getWeekKey(t.exitDate)
    if (!groups[wk]) groups[wk] = []
    groups[wk].push(realizedR(t))
  }
  let cum = 0
  const weeks = Object.keys(groups).sort().slice(-8).map(wk => {
    const Rs = groups[wk]
    const weekR = Rs.reduce((a, b) => a + b, 0)
    cum += weekR
    return { week: wk, trades: Rs.length, weekR, cumR: cum }
  })
  return weeks.length >= 2 ? weeks : null
})

// WW8: 目標達成率＋平均獲利捕捉率（PTJ: 只做你知道會成功的交易，事後驗證預測準不準）
// 目標達成 = exit >= target (long) ；捕捉率 = actualR / targetR
const targetAchievement = computed(() => {
  const cl = closedTrades.value.filter(t => t.target && Number(t.target) > 0)
  if (cl.length < 3) return null
  let hits = 0, totalCapture = 0
  for (const t of cl) {
    const target = Number(t.target)
    const entry = Number(t.entry)
    const exit = Number(t.exit) || 0
    const stop = Number(t.stop)
    const isLong = t.side === 'long' || entry > stop
    const hit = isLong ? exit >= target : exit <= target
    if (hit) hits++
    const plannedRR = Math.abs(target - entry) / Math.abs(entry - stop)
    const actualRR = Math.abs(exit - entry) / Math.abs(entry - stop)
    if (plannedRR > 0) totalCapture += Math.min(actualRR / plannedRR, 2) // cap at 200%
  }
  const hitRate = hits / cl.length
  const avgCapture = totalCapture / cl.length
  return { hitRate, avgCapture, count: cl.length, hits }
})

// XX1: Kelly Fraction 倉位建議（Ed Thorp: 數學上最優的賭注比例，超賭必輸）
// full Kelly = p - q/b；1/4 Kelly 為實戰建議；b = 平均賠率
const kellyFraction = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 10) return null
  const wins = Rs.filter(r => r > 0)
  const losses = Rs.filter(r => r < 0)
  if (!wins.length || !losses.length) return null
  const p = wins.length / Rs.length
  const q = 1 - p
  const b = wins.reduce((a, r) => a + r, 0) / wins.length / (Math.abs(losses.reduce((a, r) => a + r, 0) / losses.length) || 1)
  const full = p - q / b
  return { full: Math.max(0, full) * 100, quarter: Math.max(0, full / 4) * 100, p, b }
})

// XX2: 權益曲線動能信號（Nick Radge: 交易自己的權益曲線；曲線低於均線時應縮手）
// cumR 最近 10 筆移動平均，若最新 cumR < SMA → PAUSE
const ecMomentum = computed(() => {
  const pts = equityPoints.value
  if (pts.length < 12) return null
  const W = 10
  const sma = pts.slice(pts.length - W).reduce((a, b) => a + b, 0) / W
  const current = pts[pts.length - 1]
  return { current, sma, trade: current >= sma }
})

// XX5: R 四分位分布（Michael Covel: 趨勢跟蹤者靠右尾肥賺錢，P75 < 1.5R = 讓利潤跑不夠）
const rQuartile = computed(() => {
  const Rs = [...closedTrades.value.map(realizedR)].sort((a, b) => a - b)
  if (Rs.length < 8) return null
  const at = (pct) => {
    const i = (Rs.length - 1) * pct
    const lo = Math.floor(i), hi = Math.ceil(i)
    return Rs[lo] + (Rs[hi] - Rs[lo]) * (i - lo)
  }
  return { p25: at(0.25), p50: at(0.5), p75: at(0.75), thinRightTail: at(0.75) < 1.5 }
})

// XX6: 月獲利因子趨勢（CTA 標準: PF = 月正R總和 / 月負R總和絕對值，< 1 = 負期望）
const monthlyPFPoints = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 6) return []
  const byMonth = {}
  for (const t of cl) {
    const mo = String(t.exitDate).slice(0, 7)
    if (!byMonth[mo]) byMonth[mo] = []
    byMonth[mo].push(realizedR(t))
  }
  const months = Object.keys(byMonth).sort().slice(-6)
  return months.map(mo => {
    const Rs = byMonth[mo]
    const pos = Rs.filter(r => r > 0).reduce((a, b) => a + b, 0)
    const neg = Math.abs(Rs.filter(r => r < 0).reduce((a, b) => a + b, 0))
    return neg > 0 ? pos / neg : (pos > 0 ? 3 : 1)
  })
})
const pfW = 200, pfH = 40
const { points: pfPolyline } = useSparkline(monthlyPFPoints, { width: pfW, height: pfH, includeValue: 1 })

// XX8: 停損觸發恢復成本（Martin Schwartz: 輸家不知道輸一筆要贏幾筆才能回來）
// 若此開倉觸停 = -1R 損失；需要均值贏單 N 筆才能回本
const stopRecoveryCost = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  const wins = Rs.filter(r => r > 0)
  if (wins.length < 3 || !openTrades.value.length) return null
  const avgWin = wins.reduce((a, b) => a + b, 0) / wins.length
  return openTrades.value.map(t => {
    const riskR = 1 // hitting stop = -1R per trade definition
    return { symbol: t.symbol || '?', lots: t.lots, recoveryTrades: riskR / avgWin, avgWin }
  })
})

// XX9: 當前連勝/連敗機率（George Soros: 極端連勝後勿加碼、極端連敗後勿放棄）
// P(streak ≥ N) = 1 - P(streak < N)；二項分佈近似
const streakProb = computed(() => {
  const cl = [...closedTrades.value]
    .filter(t => t.exitDate)
    .sort((a, b) => new Date(a.exitDate || 0) - new Date(b.exitDate || 0))
  if (cl.length < 10) return null
  const Rs = cl.map(realizedR)
  const wins = Rs.filter(r => r > 0)
  const p = wins.length / Rs.length
  const q = 1 - p
  // find current streak (same result type)
  const last = Rs[Rs.length - 1] > 0
  let n = 0
  for (let i = Rs.length - 1; i >= 0; i--) {
    if ((Rs[i] > 0) === last) n++
    else break
  }
  // P(at least one run of length >= n in cl.length independent trials)
  // Approx: P(streak >= n) ≈ 1 - (1 - pk^n)^(N/n) where pk = p or q
  const pk = last ? p : q
  const pRun = Math.pow(pk, n)
  const trials = cl.length / n
  const pAtLeast = 1 - Math.pow(1 - pRun, trials)
  return { type: last ? 'win' : 'loss', n, p: pk, pAtLeast, rare: pAtLeast < 0.1 }
})

// XX10: 交易評分分布（William O'Neil/IBD: 只做 A 級設定，不做 C 級妥協）
// A: hit target AND R ≥ avgWin; B: one of two; C: neither but positive; D: loss
const tradeGrades = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 5) return null
  const avgWin = Rs.filter(r => r > 0).length ? Rs.filter(r => r > 0).reduce((a, b) => a + b, 0) / Rs.filter(r => r > 0).length : 1
  const counts = { A: 0, B: 0, C: 0, D: 0 }
  closedTrades.value.forEach((t, i) => {
    const r = Rs[i]
    const target = Number(t.target) || 0
    const exit = Number(t.exit) || 0
    const entry = Number(t.entry)
    const stop = Number(t.stop)
    const isLong = t.side === 'long' || entry > stop
    const hitTarget = target > 0 && (isLong ? exit >= target : exit <= target)
    const aboveAvg = r >= avgWin
    if (r < 0) counts.D++
    else if (hitTarget && aboveAvg) counts.A++
    else if (hitTarget || aboveAvg) counts.B++
    else counts.C++
  })
  const total = Rs.length
  return { counts, total, pct: { A: counts.A/total*100, B: counts.B/total*100, C: counts.C/total*100, D: counts.D/total*100 } }
})

// YY1: 系統品質分數 SQN（Van Tharp：數學化評估交易系統品質）
// SQN = mean(R)/σ(R)×√N；≥ 2.5 可穩定交易，≥ 3.0 優秀，< 1.6 需檢視系統
const sqn = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 20) return null
  const N = Math.min(Rs.length, 100)
  const recent = Rs.slice(-N)
  const mean = recent.reduce((a, b) => a + b, 0) / N
  const variance = recent.reduce((a, b) => a + (b - mean) ** 2, 0) / N
  const std = Math.sqrt(variance)
  if (std === 0) return null
  const value = mean / std * Math.sqrt(N)
  const label = value >= 3.0 ? '優秀' : value >= 2.0 ? '良好' : value >= 1.0 ? '普通' : '差'
  const cls = value >= 2.0 ? 'up' : value >= 1.0 ? 'warn' : 'down'
  return { value, label, cls, N }
})

// YY2: 催化劑績效分層（Paul Tudor Jones：只做最強的設定類型，知道哪個 setup 才是真正的優勢）
const catalystPerf = computed(() => {
  const trades = closedTrades.value.filter(t => t.catalyst && String(t.catalyst).trim())
  if (trades.length < 4) return null
  const groups = {}
  for (const t of trades) {
    const cat = String(t.catalyst).trim()
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(t)
  }
  const rows = Object.entries(groups)
    .filter(([, ts]) => ts.length >= 2)
    .map(([cat, ts]) => {
      const Rs = ts.map(realizedR)
      const wins = Rs.filter(r => r > 0)
      const losses = Rs.filter(r => r < 0)
      const avgR = Rs.reduce((a, b) => a + b, 0) / Rs.length
      const gw = wins.reduce((a, b) => a + b, 0)
      const gl = Math.abs(losses.reduce((a, b) => a + b, 0))
      const pf = gl > 0 ? gw / gl : (gw > 0 ? 3 : 1)
      return { cat, count: ts.length, winRate: wins.length / Rs.length * 100, avgR, pf }
    })
    .sort((a, b) => b.avgR - a.avgR)
  return rows.length >= 2 ? rows : null
})

// YY3: 月份勝率模式（Ed Seykota：了解系統的季節性特徵，有些月份天生適合或不適合）
const monthlyWinRate = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 6) return null
  const byMonth = {}
  for (const t of cl) {
    const mo = new Date(t.exitDate).getMonth()
    if (!byMonth[mo]) byMonth[mo] = []
    byMonth[mo].push(realizedR(t))
  }
  const months = Array.from({ length: 12 }, (_, i) => {
    const Rs = byMonth[i] || []
    return { month: i, wr: Rs.length >= 2 ? Rs.filter(r => r > 0).length / Rs.length : null, count: Rs.length }
  })
  const filled = months.filter(m => m.wr !== null)
  if (filled.length < 2) return null
  const sorted = [...filled].sort((a, b) => b.wr - a.wr)
  return { months, best: sorted[0], worst: sorted[sorted.length - 1] }
})

// YY4: 倉位大小績效相關（Tom Basso：系統化者的倉位大小不應與情緒相關，大小單勝率應接近）
const lotSizeEffect = computed(() => {
  const cl = closedTrades.value.filter(t => t.lots)
  if (cl.length < 8) return null
  const lots = cl.map(t => Number(t.lots) || 1).sort((a, b) => a - b)
  const median = lots[Math.floor(lots.length / 2)]
  const big = cl.filter(t => (Number(t.lots) || 1) > median)
  const small = cl.filter(t => (Number(t.lots) || 1) <= median)
  if (!big.length || !small.length) return null
  const bigRs = big.map(realizedR)
  const smallRs = small.map(realizedR)
  const bigWR = bigRs.filter(r => r > 0).length / bigRs.length * 100
  const smallWR = smallRs.filter(r => r > 0).length / smallRs.length * 100
  const bigAvgR = bigRs.reduce((a, b) => a + b, 0) / bigRs.length
  const smallAvgR = smallRs.reduce((a, b) => a + b, 0) / smallRs.length
  return { bigWR, smallWR, bigAvgR, smallAvgR, emotional: bigWR < smallWR - 5, median }
})

// YY5: 離群贏單貢獻度（Seykota/Covel：讓贏單奔跑；前 10% 大贏佔總獲利 > 40% = 健康右尾）
const outlierContribution = computed(() => {
  const Rs = closedTrades.value.map(realizedR)
  if (Rs.length < 10) return null
  const wins = [...Rs.filter(r => r > 0)].sort((a, b) => b - a)
  if (wins.length < 3) return null
  const topN = Math.max(1, Math.ceil(wins.length * 0.1))
  const topSum = wins.slice(0, topN).reduce((a, b) => a + b, 0)
  const totalWins = wins.reduce((a, b) => a + b, 0)
  const pct = totalWins > 0 ? topSum / totalWins * 100 : 0
  const totalR = Rs.reduce((a, b) => a + b, 0)
  return { pct, topN, topSum, totalR, withoutOutliers: totalR - topSum, healthy: pct > 40 }
})

// ZZ1: 連虧重入率（Jesse Livermore：永遠不要攤平虧損，虧損後立即重入同標的是最常見的情緒交易行為）
const avgDownDetector = computed(() => {
  const cl = closedTrades.value.filter(t => t.symbol && t.exitDate)
  if (cl.length < 5) return null
  const bySymbol = {}
  cl.forEach(t => {
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = []
    bySymbol[t.symbol].push(t)
  })
  let incidents = 0, total = 0
  Object.values(bySymbol).forEach(trades => {
    const sorted = [...trades].sort((a, b) => new Date(a.openDate) - new Date(b.openDate))
    for (let i = 0; i < sorted.length - 1; i++) {
      if (realizedR(sorted[i]) < 0) {
        total++
        const gap = (new Date(sorted[i + 1].openDate) - new Date(sorted[i].exitDate)) / 86400000
        if (gap >= 0 && gap <= 14) incidents++
      }
    }
  })
  if (total === 0) return null
  return { incidents, total, rate: incidents / total, risky: incidents / total > 0.3 }
})

// ZZ2: 波動制度績效（Nassim Taleb：反脆弱系統在緊縮與寬鬆停損制度下均有優勢，而非只在單一環境有效）
const volatilityRegime = computed(() => {
  const trades = closedTrades.value.filter(t => t.entry && t.stop && t.exit)
  if (trades.length < 5) return null
  const buckets = { tight: [], medium: [], loose: [] }
  trades.forEach(t => {
    const stopPct = Math.abs(t.entry - t.stop) / t.entry * 100
    const R = realizedR(t)
    if (stopPct < 2) buckets.tight.push(R)
    else if (stopPct < 4) buckets.medium.push(R)
    else buckets.loose.push(R)
  })
  const tiers = [
    { label: '緊(<2%)', arr: buckets.tight },
    { label: '中(2-4%)', arr: buckets.medium },
    { label: '寬(>4%)', arr: buckets.loose },
  ].map(t => ({
    label: t.label,
    n: t.arr.length,
    avgR: t.arr.length ? t.arr.reduce((a, b) => a + b, 0) / t.arr.length : 0,
  })).filter(t => t.n > 0)
  if (tiers.length < 2) return null
  return { tiers }
})

// ZZ4: 高信念倉位驗證（Stan Druckenmiller：只有在真正有信念時才放大部位，且大倉應有更好的平均R）
const convictionAvgR = computed(() => {
  const trades = closedTrades.value
  if (trades.length < 10) return null
  const lotsArr = trades.map(t => t.lots || 1).sort((a, b) => a - b)
  const median = lotsArr[Math.floor(lotsArr.length / 2)]
  const big = trades.filter(t => (t.lots || 1) > median).map(realizedR)
  const small = trades.filter(t => (t.lots || 1) <= median).map(realizedR)
  if (!big.length || !small.length) return null
  const bigAvg = big.reduce((a, b) => a + b, 0) / big.length
  const smallAvg = small.reduce((a, b) => a + b, 0) / small.length
  return { bigAvg, smallAvg, healthy: bigAvg > smallAvg, gap: bigAvg - smallAvg }
})

// ZZ5: 持倉天數甜蜜點（Larry Williams：每個策略都有最佳持倉週期，識別它才能在最適時機出場）
const holdDurationSweetSpot = computed(() => {
  const trades = closedTrades.value.filter(t => t.openDate && t.exitDate)
  if (trades.length < 5) return null
  const buckets = [
    { label: '≤1天', min: 0, max: 1, Rs: [] },
    { label: '2-5天', min: 2, max: 5, Rs: [] },
    { label: '6-14天', min: 6, max: 14, Rs: [] },
    { label: '≥15天', min: 15, max: Infinity, Rs: [] },
  ]
  trades.forEach(t => {
    const days = Math.round((new Date(t.exitDate) - new Date(t.openDate)) / 86400000)
    const b = buckets.find(bk => days >= bk.min && days <= bk.max)
    if (b) b.Rs.push(realizedR(t))
  })
  return buckets.map(b => ({
    label: b.label, n: b.Rs.length,
    avgR: b.Rs.length ? b.Rs.reduce((a, v) => a + v, 0) / b.Rs.length : null,
  }))
})

// ZZ6: 標的淨貢獻排名（Peter Lynch：了解你持有的每一個標的，知道哪些真正在幫你創造Alpha）
const symbolNetPnl = computed(() => {
  if (closedTrades.value.length < 5) return null
  const bySymbol = {}
  closedTrades.value.forEach(t => {
    const R = realizedR(t)
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = { symbol: t.symbol, netR: 0, n: 0 }
    bySymbol[t.symbol].netR += R
    bySymbol[t.symbol].n++
  })
  const syms = Object.values(bySymbol).sort((a, b) => b.netR - a.netR)
  if (syms.length < 2) return null
  const topN = Math.min(3, syms.length)
  const botN = syms.length > 3 ? Math.min(3, syms.length - topN) : 0
  const top = syms.slice(0, topN)
  const bottom = botN > 0 ? [...syms.slice(syms.length - botN)].reverse() : []
  return { top, bottom, total: syms.length }
})

// AAA1: 最佳標的集中度效益（Warren Buffett：你的最佳構想應該是你最好的持倉，集中度是有紀律的，不是分散風險）
const concentrationEfficiency = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const bySymbol = {}
  cl.forEach(t => {
    const R = realizedR(t)
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = { symbol: t.symbol, Rs: [], n: 0 }
    bySymbol[t.symbol].Rs.push(R)
    bySymbol[t.symbol].n++
  })
  const syms = Object.values(bySymbol)
  if (syms.length < 2) return null
  syms.forEach(s => { s.avgR = s.Rs.reduce((a, b) => a + b, 0) / s.Rs.length })
  syms.sort((a, b) => b.avgR - a.avgR)
  const top = syms[0]
  const rest = syms.slice(1)
  const restRs = rest.flatMap(s => s.Rs)
  const restAvgR = restRs.reduce((a, b) => a + b, 0) / restRs.length
  return { topSymbol: top.symbol, topAvgR: top.avgR, topN: top.n, restAvgR, restCount: rest.length }
})

// AAA4: 同標的再進場反身性（George Soros：市場自我強化——盈利後加倉是反身性操作，但須確認你的系統在再進場時仍有優勢）
const reflexivityReentry = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const bySymbol = {}
  const sorted = [...cl].sort((a, b) => new Date(a.openDate) - new Date(b.openDate))
  sorted.forEach(t => {
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = []
    bySymbol[t.symbol].push(realizedR(t))
  })
  const symbols = Object.entries(bySymbol)
    .filter(([, rs]) => rs.length >= 2)
    .map(([symbol, rs]) => ({
      symbol,
      firstAvgR: rs[0],
      reAvgR: rs.slice(1).reduce((a, b) => a + b, 0) / rs.slice(1).length,
      reN: rs.length - 1,
    }))
  if (symbols.length < 1) return null
  return { symbols: symbols.slice(0, 3) }
})

// AAA5: 勝損持倉時長不對稱（David Ricardo：讓贏家奔跑、快速停損——若持虧單比持贏單更久，代表系統方向性紀律倒置）
const durationAsymmetry = computed(() => {
  const cl = closedTrades.value.filter(t => t.openDate && t.exitDate)
  if (cl.length < 6) return null
  const wins = cl.filter(t => realizedR(t) > 0)
  const losses = cl.filter(t => realizedR(t) < 0)
  if (wins.length < 3 || losses.length < 3) return null
  const days = t => Math.max(0, (new Date(t.exitDate) - new Date(t.openDate)) / 86400000)
  const avgWinDays = wins.reduce((a, t) => a + days(t), 0) / wins.length
  const avgLossDays = losses.reduce((a, t) => a + days(t), 0) / losses.length
  if (avgLossDays === 0) return null
  return { avgWinDays, avgLossDays, ratio: avgWinDays / avgLossDays }
})

// AAA7: 序列自相關（Victor Niederhoffer：若勝負嚴重叢聚，交易者可能正在受心理狀態驅動，而非系統驅動）
const serialCorrelation = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 10) return null
  const sorted = [...cl].filter(t => t.exitDate).sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  const seq = sorted.map(t => realizedR(t) > 0 ? 1 : 0)
  let nWW = 0, nWL = 0, nLW = 0, nLL = 0
  for (let i = 1; i < seq.length; i++) {
    if (seq[i - 1] === 1 && seq[i] === 1) nWW++
    else if (seq[i - 1] === 1 && seq[i] === 0) nWL++
    else if (seq[i - 1] === 0 && seq[i] === 1) nLW++
    else nLL++
  }
  const totalAfterW = nWW + nWL
  const totalAfterL = nLW + nLL
  if (totalAfterW < 2 || totalAfterL < 2) return null
  const pWinGivenWin = nWW / totalAfterW
  const pWinGivenLoss = nLW / totalAfterL
  const clustered = Math.abs(pWinGivenWin - pWinGivenLoss) > 0.2
  return { pWinGivenWin, pWinGivenLoss, nWW, nLW, clustered }
})

// AAA8: 星期幾績效（Marty Schwartz：偉大交易員了解自己的節奏，週幾最清醒？週幾最衝動？）
const weekdayPerf = computed(() => {
  const cl = closedTrades.value.filter(t => t.openDate)
  if (cl.length < 5) return null
  const labels = ['一', '二', '三', '四', '五']
  const buckets = labels.map(label => ({ label, Rs: [] }))
  cl.forEach(t => {
    const dow = new Date(t.openDate).getDay()
    if (dow >= 1 && dow <= 5) buckets[dow - 1].Rs.push(realizedR(t))
  })
  const active = buckets.filter(b => b.Rs.length > 0)
  if (active.length < 2) return null
  return buckets.map(b => ({ label: b.label, n: b.Rs.length, avgR: b.Rs.length ? b.Rs.reduce((a, v) => a + v, 0) / b.Rs.length : 0 }))
})

// BBB1: 最優倉位尺寸（Ralph Vince：Optimal f 是讓幾何成長率最大化的下注比例，Kelly 準則的 R 單位版本）
const optimalF = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 10) return null
  const Rs = cl.map(realizedR)
  const wins = Rs.filter(r => r > 0)
  const losses = Rs.filter(r => r < 0)
  if (!wins.length || !losses.length) return null
  const p = wins.length / Rs.length
  const W = wins.reduce((a, b) => a + b, 0) / wins.length
  const L = Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length)
  const edge = p * W - (1 - p) * L
  const f = W > 0 ? edge / W : 0
  return { f: Math.max(0, Math.min(1, f)), edge, healthy: f > 0 }
})

// BBB3: 贏單出場品質（Bernard Baruch：適時的利潤了結是交易成功的另一半——量化你是否在出場時捕捉到足夠的計劃利潤）
const exitQuality = computed(() => {
  const cl = closedTrades.value.filter(t => t.entry && t.stop && t.target && t.exit)
  if (cl.length < 5) return null
  const winners = cl.filter(t => realizedR(t) > 0)
  if (winners.length < 3) return null
  const ratios = winners.map(t => {
    const entry = Number(t.entry), target = Number(t.target), exit = Number(t.exit)
    const targetMove = Math.abs(target - entry)
    if (!targetMove) return 0
    const exitMove = (exit - entry) * (target > entry ? 1 : -1)
    return Math.max(0, exitMove / targetMove)
  })
  const avgRatio = ratios.reduce((a, b) => a + b, 0) / ratios.length
  const nearTargetPct = ratios.filter(r => r >= 0.9).length / ratios.length
  return { avgRatio, nearTargetPct, n: ratios.length }
})

// BBB6: 倉位集中度基尼係數（Gerald Loeb：集中在你最有信念的機會——均等配置是缺乏信念的表現，Gini > 0.3 代表有意義的差異化）
const lotGini = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const lots = cl.map(t => t.lots || 1).sort((a, b) => a - b)
  const n = lots.length
  const sum = lots.reduce((a, b) => a + b, 0)
  if (!sum) return null
  let giniNum = 0
  lots.forEach((x, i) => { giniNum += (2 * (i + 1) - n - 1) * x })
  const gini = Math.max(0, giniNum / (n * sum))
  return { gini, concentrated: gini > 0.3, min: Math.min(...lots), max: Math.max(...lots), mean: sum / n }
})

// BBB7: 月頻率 vs 績效相關（Michael Steinhardt：對比觀點需要極高的選擇性——Pearson r 衡量多交易是否真的帶來更好績效）
const frequencyCorrelation = computed(() => {
  const cl = closedTrades.value.filter(t => t.exitDate)
  if (cl.length < 10) return null
  const byMonth = {}
  cl.forEach(t => {
    const key = t.exitDate.slice(0, 7)
    if (!byMonth[key]) byMonth[key] = []
    byMonth[key].push(realizedR(t))
  })
  const months = Object.values(byMonth)
  if (months.length < 4) return null
  const points = months.map(m => ({ count: m.length, avgR: m.reduce((a, b) => a + b, 0) / m.length }))
  const n = points.length
  const meanX = points.reduce((a, p) => a + p.count, 0) / n
  const meanY = points.reduce((a, p) => a + p.avgR, 0) / n
  const cov = points.reduce((a, p) => a + (p.count - meanX) * (p.avgR - meanY), 0) / n
  const stdX = Math.sqrt(points.reduce((a, p) => a + (p.count - meanX) ** 2, 0) / n)
  const stdY = Math.sqrt(points.reduce((a, p) => a + (p.avgR - meanY) ** 2, 0) / n)
  if (!stdX || !stdY) return null
  return { r: cov / (stdX * stdY) }
})

// BBB10: 持倉天數分位數（Philip Fisher：好公司需要時間驗證——P25/P50/P75 完整描述持倉分布，贏單中位數應長於虧單）
const holdingPercentiles = computed(() => {
  const cl = closedTrades.value.filter(t => t.openDate && t.exitDate)
  if (cl.length < 6) return null
  const days = t => Math.max(0, Math.round((new Date(t.exitDate) - new Date(t.openDate)) / 86400000))
  const wins = cl.filter(t => realizedR(t) > 0).map(days).sort((a, b) => a - b)
  const losses = cl.filter(t => realizedR(t) < 0).map(days).sort((a, b) => a - b)
  if (wins.length < 3 || losses.length < 3) return null
  const pct = (arr, p) => arr[Math.max(0, Math.floor(p * (arr.length - 1)))]
  return {
    win: { p25: pct(wins, 0.25), p50: pct(wins, 0.5), p75: pct(wins, 0.75) },
    loss: { p25: pct(losses, 0.25), p50: pct(losses, 0.5), p75: pct(losses, 0.75) },
    wellManaged: pct(wins, 0.5) >= pct(losses, 0.5),
  }
})

// CCC1: 計劃風報比分布（Jesse Livermore：只進有利預期值機會——計劃R/R桶狀分析）
const plannedRRDist = computed(() => {
  const cl = closedTrades.value.filter(t => t.target && t.entry && t.stop && Number(t.entry) !== Number(t.stop))
  if (cl.length < 5) return null
  const buckets = [{ label: '<1R', count: 0 }, { label: '1–2R', count: 0 }, { label: '≥2R', count: 0 }]
  cl.forEach(t => {
    const rr = Math.abs((Number(t.target) - Number(t.entry)) / (Number(t.entry) - Number(t.stop)))
    if (rr < 1) buckets[0].count++
    else if (rr < 2) buckets[1].count++
    else buckets[2].count++
  })
  const total = cl.length
  buckets.forEach(b => { b.pct = b.count / total * 100 })
  return { buckets, qualityPct: buckets[2].pct, total }
})

// CCC2: 標的選擇性指數（Nicolas Darvas：深研後才操作——重複標的代表選擇性不足？）
const symbolSelectivity = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const counts = {}
  cl.forEach(t => { const s = t.symbol || '?'; counts[s] = (counts[s] || 0) + 1 })
  const symbols = Object.entries(counts)
  const uniqueSymbols = symbols.length
  const onceOnly = symbols.filter(([, c]) => c === 1).length
  const top = [...symbols].sort((a, b) => b[1] - a[1])[0]
  return { uniqueSymbols, avgTradesPerSymbol: cl.length / uniqueSymbols, onceOnlyPct: onceOnly / uniqueSymbols * 100, topSymbol: top[0], topCount: top[1] }
})

// CCC3: 催化劑勝率分析（William O'Neil CAN SLIM：N=新催化劑是買進信號——哪種催化劑勝率更高？）
const catalystWinRate = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 8) return null
  const groups = {}
  cl.forEach(t => {
    const key = (t.catalyst && t.catalyst.trim()) || '未標記'
    if (!groups[key]) groups[key] = { wins: 0, total: 0 }
    groups[key].total++
    if (realizedR(t) > 0) groups[key].wins++
  })
  const catalysts = Object.entries(groups)
    .filter(([, v]) => v.total >= 2)
    .map(([label, v]) => ({ label, winRate: v.wins / v.total * 100, total: v.total }))
    .sort((a, b) => b.winRate - a.winRate)
  if (catalysts.length < 2) return null
  return { catalysts }
})

// CCC6: 入場緊度 vs 實現R（Mark Minervini VCP：緊縮型態下的緊停損應帶來更高R）
const vcpCorrelation = computed(() => {
  const cl = closedTrades.value.filter(t => t.entry && t.stop && Number(t.entry) !== Number(t.stop))
  if (cl.length < 8) return null
  const pairs = cl.map(t => ({ riskPct: Math.abs(Number(t.entry) - Number(t.stop)) / Number(t.entry), R: realizedR(t) })).filter(p => isFinite(p.riskPct) && p.riskPct > 0)
  if (pairs.length < 8) return null
  const n = pairs.length
  const mx = pairs.reduce((s, p) => s + p.riskPct, 0) / n
  const my = pairs.reduce((s, p) => s + p.R, 0) / n
  let num = 0, dx2 = 0, dy2 = 0
  pairs.forEach(p => { const a = p.riskPct - mx, b = p.R - my; num += a * b; dx2 += a * a; dy2 += b * b })
  const r = (dx2 && dy2) ? num / Math.sqrt(dx2 * dy2) : 0
  return { r }
})

// CCC7: R倍數分布（Paul Tudor Jones：尋求5:1機會——系統裡有多少大贏單？）
const rBinDist = computed(() => {
  const cl = closedTrades.value
  if (cl.length < 5) return null
  const bins = [{ label: '<0R', count: 0 }, { label: '0–1R', count: 0 }, { label: '1–2R', count: 0 }, { label: '2–3R', count: 0 }, { label: '≥3R', count: 0 }]
  cl.forEach(t => {
    const r = realizedR(t)
    if (r < 0) bins[0].count++
    else if (r < 1) bins[1].count++
    else if (r < 2) bins[2].count++
    else if (r < 3) bins[3].count++
    else bins[4].count++
  })
  const total = cl.length
  bins.forEach(b => { b.pct = b.count / total * 100 })
  return { bins, bigWinPct: bins[4].pct, total }
})

// CCC10: 贏單持倉天數趨勢（Richard Donchian：趨勢跟蹤者越來越能讓贏家奔跑）
const winDurationTrend = computed(() => {
  const cl = closedTrades.value.filter(t => t.openDate && t.exitDate).sort((a, b) => new Date(a.exitDate) - new Date(b.exitDate))
  if (cl.length < 10) return null
  const daysFn = t => Math.max(0, Math.round((new Date(t.exitDate) - new Date(t.openDate)) / 86400000))
  const wins = cl.filter(t => realizedR(t) > 0)
  if (wins.length < 6) return null
  const half = Math.floor(wins.length / 2)
  const early = wins.slice(0, half).map(daysFn).sort((a, b) => a - b)
  const recent = wins.slice(half).map(daysFn).sort((a, b) => a - b)
  const p50 = arr => arr[Math.floor((arr.length - 1) / 2)]
  return { earlyP50: p50(early), recentP50: p50(recent), improving: p50(recent) >= p50(early) }
})

function fmt(v) {
  if (v == null || (typeof v === 'number' && isNaN(v))) return '—'
  if (v === Infinity) return '∞'
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function fmtInt(v) { return (v == null || isNaN(v)) ? '—' : Math.round(v).toLocaleString('en-US') }

function save() { saveJournal(trades.value) }
function load() { trades.value = loadJournal() }

function addTrade() {
  formError.value = ''
  const symbol = String(form.symbol || '').trim().toUpperCase()
  const entry = Number(form.entry), stop = Number(form.stop), lots = Math.floor(Number(form.lots) || 0)
  if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop) {
    formError.value = '請填代碼、有效的進場/停損價（不可相等）與至少 1 張。'
    return
  }
  const id = Date.now() + '-' + Math.random().toString(36).slice(2, 7)
  trades.value.unshift({
    id,
    symbol, name: symbol, side: form.side, entry, stop,
    target: Number(form.target) > 0 ? Number(form.target) : null,
    lots, tag: String(form.tag || '').trim(), catalyst: String(form.catalyst || '').trim(),
    openDate: localDateStr(), status: 'open',
    exit: null, exitDate: null,
  })
  save()
  resolveName(id, symbol) // 補上股票名稱（背景，代號伴隨名稱）
  form.symbol = ''; form.entry = null; form.stop = null; form.target = null; form.lots = 1; form.tag = ''; form.catalyst = ''
  catalystAssessment.value = ''
  catalystError.value = ''
}

// 手動輸入只有代號 → 用搜尋 API 補中文名（best-effort，不阻塞新增）
async function resolveName(id, symbol) {
  const name = await resolveStockName(symbol)
  if (!name) return
  const t = trades.value.find(x => x.id === id)
  if (t) { t.name = name; save() }
}

function closeTrade(t) {
  const exit = Number(t._exitInput)
  if (!(exit > 0)) { formError.value = '請在該筆輸入有效的平倉價。'; return }
  formError.value = ''
  t.exit = exit
  t.exitDate = localDateStr()
  t.status = 'closed'
  delete t._exitInput
  save()
}

function removeTrade(id) {
  if (!window.confirm('確定要刪除這筆交易紀錄嗎？')) return
  trades.value = trades.value.filter(t => t.id !== id); save()
}
function clearAll() {
  if (!window.confirm(`確定要清空全部 ${trades.value.length} 筆交易紀錄嗎？localStorage 是唯一儲存位置，清掉就救不回來了。`)) return
  trades.value = []; save()
}

// A3 CSV 匯入：localStorage 是這份日誌唯一的儲存位置，瀏覽器清資料就全沒
// 了。既有的匯出 CSV 因此也是備份手段——但少了匯入就還原不了。這裡吃匯出
// 的同一種格式（欄位名相同即可，欄位順序不限），R/pnl 欄為衍生值直接忽略。
const csvFileInput = ref(null)
const csvMsg = ref('')
const CSV_MAX_BYTES = 5 * 1024 * 1024 // F5：一筆交易頂多百來個字元，5MB 已遠超正常日誌大小，超過視為誤選檔案，避免把大檔讀進來卡住畫面。

function triggerImport() { csvFileInput.value?.click() }

function importCsv(event) {
  const file = event.target.files?.[0]
  event.target.value = '' // 允許重選同一個檔案
  if (!file) return
  if (file.size > CSV_MAX_BYTES) {
    csvMsg.value = `匯入失敗：檔案 ${(file.size / 1024 / 1024).toFixed(1)}MB 超過上限 ${CSV_MAX_BYTES / 1024 / 1024}MB，請確認選對檔案。`
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    try { applyCsvImport(String(reader.result || '')) } catch (e) { csvMsg.value = '匯入失敗：' + (e?.message || '格式錯誤') }
  }
  reader.onerror = () => { csvMsg.value = '匯入失敗：讀取檔案錯誤。' }
  reader.readAsText(file)
}

function parseCsvText(text) {
  const s = String(text).replace(/^﻿/, '')
  const rows = []
  let row = [], cell = '', inQuotes = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') { cell += '"'; i++ } else inQuotes = false
      } else cell += c
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(cell); cell = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++
      row.push(cell); cell = ''
      if (row.some(v => v !== '')) rows.push(row)
      row = []
    } else {
      cell += c
    }
  }
  row.push(cell)
  if (row.some(v => v !== '')) rows.push(row)
  return rows
}

function applyCsvImport(text) {
  const rows = parseCsvText(text)
  if (rows.length < 2) { csvMsg.value = '匯入失敗：CSV 沒有資料列。'; return }
  const header = rows[0].map(h => h.trim())
  const idx = (name) => header.indexOf(name)
  for (const col of ['symbol', 'side', 'entry', 'stop', 'lots', 'openDate', 'status']) {
    if (idx(col) === -1) { csvMsg.value = `匯入失敗：缺少欄位 ${col}。`; return }
  }
  const get = (row, name) => { const i = idx(name); return i === -1 ? '' : (row[i] ?? '') }
  const dupKey = (t) => [t.symbol, t.side, t.entry, t.stop, t.lots, t.openDate, t.status, t.exit ?? '', t.exitDate ?? ''].join('|')
  const existing = new Set(trades.value.map(dupKey))
  let added = 0, skippedDup = 0, invalid = 0
  for (const row of rows.slice(1)) {
    const symbol = String(get(row, 'symbol')).trim().toUpperCase()
    const side = String(get(row, 'side')).trim() === 'short' ? 'short' : 'long'
    const entry = Number(get(row, 'entry'))
    const stop = Number(get(row, 'stop'))
    const lots = Math.floor(Number(get(row, 'lots')) || 0)
    const status = String(get(row, 'status')).trim() === 'closed' ? 'closed' : 'open'
    const exit = Number(get(row, 'exit'))
    if (!symbol || !(entry > 0) || !(stop > 0) || !(lots >= 1) || entry === stop || (status === 'closed' && !(exit > 0))) {
      invalid += 1
      continue
    }
    const openDate = String(get(row, 'openDate')).slice(0, 10) || localDateStr()
    const exitDate = String(get(row, 'exitDate')).slice(0, 10)
    const t = {
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
      symbol, name: symbol, side, entry, stop,
      target: Number(get(row, 'target')) > 0 ? Number(get(row, 'target')) : null,
      lots, tag: String(get(row, 'tag') || '').trim(), catalyst: String(get(row, 'catalyst') || '').trim(),
      openDate, status,
      exit: status === 'closed' ? exit : null,
      exitDate: status === 'closed' ? (exitDate || openDate) : null,
    }
    if (existing.has(dupKey(t))) { skippedDup += 1; continue }
    existing.add(dupKey(t))
    trades.value.push(t)
    added += 1
  }
  save()
  csvMsg.value = `已匯入 ${added} 筆`
    + (skippedDup ? `、略過重複 ${skippedDup} 筆` : '')
    + (invalid ? `、忽略無效 ${invalid} 筆` : '') + '。'
}

function exportCsv() {
  if (!trades.value.length) return
  const cols = ['symbol', 'side', 'entry', 'stop', 'target', 'lots', 'tag', 'catalyst', 'openDate', 'status', 'exit', 'exitDate', 'R', 'pnl']
  const rows = trades.value.map((t) => {
    const R = t.status === 'closed' ? realizedR(t).toFixed(3) : ''
    const p = t.status === 'closed' ? Math.round(pnl(t)) : ''
    return [t.symbol, t.side, t.entry, t.stop, t.target ?? '', t.lots, t.tag ?? '', t.catalyst ?? '', t.openDate, t.status, t.exit ?? '', t.exitDate ?? '', R, p]
  })
  downloadCsv(timestampedFilename('trade-journal'), cols, rows)
}

async function importOpenPositions() {
  importMsg.value = ''
  let positions = []
  try { const raw = JSON.parse(localStorage.getItem('portfolio_heat_positions') || '[]'); if (Array.isArray(raw)) positions = raw } catch { /* ignore */ }
  if (!positions.length) { importMsg.value = '投組是空的（先到「投組風險」建立部位）。'; return }
  const existing = new Set(openTrades.value.map(t => t.symbol))
  let added = 0
  for (const p of positions) {
    const symbol = String(p.symbol || '').trim().toUpperCase()
    const entryN = Number(p.entry), stopN = Number(p.stop)
    if (!symbol || existing.has(symbol)) continue
    if (!entryN || !stopN || entryN === stopN) continue  // AA6: R=0 would break downstream calcs
    trades.value.unshift({
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 7),
      symbol, name: p.name || symbol, side: entryN >= stopN ? 'long' : 'short',
      entry: entryN, stop: stopN, target: null,
      lots: Math.max(1, Math.floor(Number(p.lots) || 1)),
      openDate: localDateStr(), status: 'open', exit: null, exitDate: null,
    })
    added += 1
  }
  save()
  importMsg.value = added ? `已從投組帶入 ${added} 筆進行中交易。` : '投組標的都已在進行中交易內。'
}

onMounted(() => {
  checkAiConfigured()
  load()
})
</script>

<style scoped>
.journal-view { display: flex; flex-direction: column; gap: 16px; }
.head-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.head-row h2, .head-row h3 { margin: 0; }
.head-actions { display: flex; gap: 8px; }
.hidden-file { display: none; }
.csv-msg { margin: 4px 0 0; }
.inp { background: var(--bg-well); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; }
.w110 { width: 110px; } .w90 { width: 90px; } .w160 { width: 160px; }

.stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }
.scard { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; }
.slabel { font-size: 0.74rem; color: var(--text-muted); }
.sval { font-size: 1.35rem; }
.sc-row { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 4px; }
.sc-val { display: flex; flex-direction: column; gap: 2px; }
.sc-val strong { font-size: 1.25rem; }
.scard-hint { font-size: 0.76rem; margin-top: 4px; line-height: 1.4; }
.shint { font-size: 0.72rem; color: var(--text-muted); }

.equity { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.equity-svg { width: 100%; height: 120px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.eq-line { fill: none; stroke: #ef4444; stroke-width: 2; vector-effect: non-scaling-stroke; }
.eq-line.down { stroke: #22c55e; }
.eq-zero { stroke: var(--border-color); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 4 4; }

.add-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.table-wrap { overflow-x: auto; margin-top: 8px; }
.j-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.j-table th, .j-table td { text-align: right; padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
.j-table th:first-child, .j-table td:first-child { text-align: left; }
.j-table th { color: var(--text-muted); font-weight: 500; font-size: 0.74rem; }
.sym small { color: var(--text-muted); }
.actions { display: flex; gap: 6px; align-items: center; justify-content: flex-end; }
.btn.xs { padding: 4px 10px; font-size: 0.78rem; }
.del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; }
.del:hover { color: #ef4444; }
.paper-tag { display: inline-block; margin-left: 10px; font-size: 0.74rem; font-weight: 400; vertical-align: middle; }
.row-breach { background: rgba(239, 68, 68, 0.06); }
.breach-tag { display: inline-block; margin-left: 4px; font-size: 0.7rem; color: #ef4444; white-space: nowrap; }
.event-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.catalyst-tag { display: inline-block; margin-left: 4px; font-size: 0.72rem; cursor: help; }
.giveback-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.ema-tag { display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #f59e0b; white-space: nowrap; cursor: help; }
.sample-warn { font-size: 0.7rem; color: #f59e0b; }

.analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 8px; }
@media (max-width: 900px) { .analytics-grid { grid-template-columns: 1fr; } }
.an-block { display: flex; flex-direction: column; gap: 8px; }
.an-block--full { grid-column: 1 / -1; }

/* UU1 Sortino + UU10 Health */
.health-score { position: relative; }
.health-total { font-size: 0.7rem; color: var(--text-muted); margin-left: 2px; }
.health-breakdown { display: flex; gap: 4px; margin-top: 4px; }
.health-dot { font-size: 0.9rem; cursor: help; }
.dot-ok { color: var(--up, #22c55e); }
.dot-no { color: var(--down, #ef4444); }

/* UU4 Skewness */
.skew-row { display: flex; align-items: flex-start; gap: 14px; flex-wrap: wrap; }
.skew-val strong { font-size: 1.4rem; }
.skew-text { font-size: 0.8rem; margin: 0; flex: 1; min-width: 160px; }

/* UU7 Day-of-week grid */
.dow-grid { display: flex; gap: 8px; flex-wrap: wrap; }
.dow-cell { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border-color); background: var(--bg-well); min-width: 60px; }
.dow-label { font-size: 0.72rem; color: var(--text-muted); }
.dow-r { font-size: 1rem; font-weight: 700; }
.dow-count { font-size: 0.68rem; }
.dow-up { border-color: rgba(34,197,94,0.5); background: rgba(34,197,94,0.08); }
.dow-up .dow-r { color: var(--up, #22c55e); }
.dow-down { border-color: rgba(239,68,68,0.5); background: rgba(239,68,68,0.08); }
.dow-down .dow-r { color: var(--down, #ef4444); }
.dow-empty .dow-r { color: var(--text-muted); }

/* VV3 catalyst label */
.catalyst-label { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.82rem; }

/* VV7 symbol concentration bars */
.conc-row { display: flex; flex-direction: column; gap: 8px; }
.conc-bar-wrap { display: flex; flex-direction: column; gap: 3px; }
.conc-label-row { display: flex; justify-content: space-between; font-size: 0.78rem; }
.conc-sym { font-weight: 600; }
.conc-pct { color: var(--text-muted); }
.conc-bar-track { height: 8px; border-radius: 999px; background: var(--bg-well); border: 1px solid var(--border-color); overflow: hidden; }
.conc-bar-fill { height: 100%; border-radius: 999px; background: rgba(59,130,246,0.6); transition: width 0.3s ease; }
.conc-warn { background: rgba(239,68,68,0.65); }

/* TT2 損益貢獻 */
.contrib-bars { display: flex; flex-direction: column; gap: 8px; }
.contrib-row { display: grid; grid-template-columns: 60px 1fr 80px; align-items: center; gap: 10px; }
.contrib-label { font-size: 0.76rem; color: var(--text-muted); }
.contrib-track { background: var(--bg-well); border-radius: 999px; height: 10px; overflow: hidden; border: 1px solid var(--border-color); }
.contrib-fill { height: 100%; border-radius: 999px; }
.contrib-win { background: rgba(239, 68, 68, 0.7); }
.contrib-loss { background: rgba(34, 197, 94, 0.7); }

/* TT3 計畫 vs 實際 */
.pva-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.pva-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 10px 14px; display: flex; flex-direction: column; gap: 4px; min-width: 100px; }
.pva-ok { border-color: rgba(34, 197, 94, 0.5); }
.pva-warn { border-color: rgba(245, 158, 11, 0.5); }
.pva-arrow { font-size: 1.2rem; color: var(--text-muted); }

/* WW2 sparkline */
.sparkline-svg { display: block; color: var(--color-up); overflow: visible; }

/* WW7 weekly table */
.ww-weekly-table td, .ww-weekly-table th { font-size: 0.82rem; }

/* XX recovery + grade tables */
.xx-recovery-table td, .xx-recovery-table th { font-size: 0.82rem; }
.xx-grade-row { display: flex; gap: 0.75rem; margin: 0.5rem 0; }
.xx-grade-cell { display: flex; flex-direction: column; align-items: center; min-width: 64px; padding: 0.5rem; border-radius: 6px; background: var(--color-surface); }
.xx-grade-cell small { font-size: 1.1rem; font-weight: 700; }
.grade-a small { color: #22c55e; }
.grade-b small { color: #60a5fa; }
.grade-c small { color: #facc15; }
.grade-d small { color: #f87171; }

/* TT4 月份績效 */
.month-wrap { overflow-x: auto; }
.month-svg { display: block; }

/* YY cycle */
.yy-catalyst-table td, .yy-catalyst-table th { font-size: 0.82rem; }
.yy-month-bars { display: flex; gap: 3px; align-items: flex-end; height: 52px; margin: 0.5rem 0; }
.yy-month-bar-col { display: flex; flex-direction: column; align-items: center; flex: 1; height: 100%; }
.yy-month-bar-bg { flex: 1; width: 100%; background: var(--color-surface); border-radius: 2px; display: flex; align-items: flex-end; }
.yy-month-bar-fill { width: 100%; border-radius: 2px; }
.yy-bar-good { background: var(--color-up, #22c55e); opacity: 0.85; }
.yy-bar-warn { background: var(--warn, #f59e0b); opacity: 0.85; }
.yy-bar-bad { background: var(--color-down, #ef4444); opacity: 0.85; }
.yy-month-label { font-size: 0.65rem; color: var(--text-muted); margin-top: 2px; }
.month-label { fill: var(--text-muted); font-size: 9px; }

/* TT9 象限圖 */
.quad-svg { width: 100%; height: auto; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.quad-positive { fill: rgba(239, 68, 68, 0.06); }
.quad-curve { fill: none; stroke: #ef4444; stroke-width: 1.5; stroke-dasharray: 5 3; }
.quad-axis { stroke: var(--border-color); stroke-width: 1; }
.quad-tick { stroke: var(--border-color); stroke-width: 1; }
.quad-label { fill: var(--text-muted); font-size: 10px; }
.dot-up { fill: #ef4444; stroke: var(--bg-well); stroke-width: 2; }
.dot-down { fill: #22c55e; stroke: var(--bg-well); stroke-width: 2; }
.rhist-svg { width: 100%; height: 120px; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 12px; }
.bar-up { fill: rgba(239, 68, 68, 0.75); } .bar-down { fill: rgba(34, 197, 94, 0.75); }
.rh-zero { stroke: var(--text-muted); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 3 3; }
.rhist-axis { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); }

.coach-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.coach-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 10px; font-size: 0.86rem; line-height: 1.55; border: 1px solid var(--border-color); }
.coach-icon { flex-shrink: 0; font-size: 1rem; }
.coach-text { flex: 1; }
.coach-bad { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.35); }
.coach-warn { background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.35); }
.coach-good { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.35); }
.coach-info { background: var(--bg-well); color: var(--text-muted); }

/* W6：AI 複盤 */
.coach-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.coach-head h3 { margin: 0; }
.ai-coach-box { margin-top: 10px; border: 1px dashed var(--border-color); border-radius: 10px; padding: 10px 12px; font-size: 0.86rem; }
.ai-coach-box p { margin: 6px 0; color: var(--text-secondary); line-height: 1.7; }
.ai-coach-box :deep(strong) { color: var(--text-primary); }
/* ZZ1-ZZ6 */
.zz-dur-bars { display: flex; gap: 4px; align-items: flex-end; height: 60px; margin: 0.75rem 0; }
.zz-dur-col { display: flex; flex-direction: column; align-items: center; flex: 1; height: 100%; gap: 2px; }
.zz-dur-bar-bg { flex: 1; width: 100%; background: var(--color-surface); border-radius: 3px; display: flex; align-items: flex-end; }
.zz-dur-bar-fill { width: 100%; border-radius: 3px; }
.zz-bar-up { background: var(--color-up, #22c55e); opacity: 0.85; }
.zz-bar-down { background: var(--color-down, #ef4444); opacity: 0.85; }
.zz-symbol-row { display: flex; gap: 1.25rem; margin-top: 0.5rem; flex-wrap: wrap; }
.zz-symbol-group { display: flex; flex-direction: column; gap: 4px; min-width: 110px; }
.zz-symbol-item { display: flex; gap: 6px; align-items: center; }
.zz-sym-code { font-size: 0.82rem; }
/* AAA1-AAA8 */
.aaa-weekday-bars { display: flex; gap: 4px; align-items: flex-end; height: 64px; margin: 0.75rem 0; }
.aaa-wd-col { display: flex; flex-direction: column; align-items: center; flex: 1; height: 100%; gap: 2px; }
.aaa-wd-bar-bg { flex: 1; width: 100%; background: var(--color-surface); border-radius: 3px; display: flex; align-items: flex-end; }
.aaa-wd-bar-fill { width: 100%; border-radius: 3px; min-height: 4px; }
/* CCC1-CCC7/CCC10 */
.ccc-rrplan, .ccc-selectivity, .ccc-catalyst, .ccc-vcp, .ccc-rbins, .ccc-duration-trend { margin-bottom: 0; }
.ccc-catalyst-grid { display: flex; flex-direction: column; gap: 6px; }
.ccc-catalyst-row { display: flex; align-items: center; gap: 8px; }
.ccc-catalyst-bar-bg { flex: 1; height: 10px; background: var(--color-surface); border-radius: 4px; overflow: hidden; }
.ccc-catalyst-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
</style>
