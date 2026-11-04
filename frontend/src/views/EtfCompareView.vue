<template>
  <div class="etf-page">
    <PageFocusBanner text="最多 10 檔 ETF／個股放在同一頁比：五維評分、含息還原走勢、歷年配息與填息、急跌後的反彈。所有數字由 FinMind 日線與除息紀錄即時算出，不是手寫的。" />

    <!-- 選擇標的 -->
    <section class="card pick-card">
      <div class="preset-row">
        <span class="row-label">一鍵情境</span>
        <button v-for="p in presets" :key="p.key" type="button" class="chip-btn" :data-preset="p.key" @click="applyPreset(p)">
          {{ p.label }}
        </button>
        <button type="button" class="chip-btn ghost" :disabled="!selected.length" @click="resetAll">重設</button>
      </div>

      <div class="portfolio-row" data-testid="portfolio-row">
        <span class="row-label">我的組合</span>
        <span v-for="p in portfolios" :key="p.id" class="pf-chip" :data-portfolio="p.name"
              :class="{ active: p.id === activePortfolioId, modified: p.id === activePortfolioId && portfolioDirty }">
          <button type="button" class="pf-load" :title="p.symbols.join('、')" @click="applyPortfolio(p)">{{ p.name }} <small>{{ p.symbols.length }} 檔</small><small v-if="p.id === activePortfolioId && portfolioDirty" class="pf-unsaved" data-testid="pf-unsaved">未儲存</small></button>
          <button type="button" class="pf-del" :aria-label="`刪除組合 ${p.name}`" @click="deletePortfolio(p)">✕</button>
        </span>
        <span v-if="!portfolios.length" class="muted small">還沒有存過組合。選好標的後取個名字存起來，下次一鍵載入。</span>
        <button type="button" class="chip-btn ghost" data-testid="import-watchlist" @click="importWatchlist">從觀察清單匯入</button>
      </div>

      <div class="add-row">
        <div ref="searchShell" class="search-shell">
          <input
            v-model="searchInput"
            type="text"
            class="inp"
            data-testid="etf-search"
            placeholder="輸入代碼或名稱，例如 0056 / 高股息 / 2330"
            :disabled="selected.length >= MAX_SYMBOLS"
            @focus="dropdownOpen = true"
            @keydown.enter.prevent="submitSearchInput"
          />
          <ul v-if="dropdownOpen && dropdownItems.length" class="search-dropdown" role="listbox">
            <li v-for="item in dropdownItems" :key="item.symbol" role="option" tabindex="0"
                @click="addSymbol(item.symbol, item.name)" @keydown.enter.prevent="addSymbol(item.symbol, item.name)">
              <strong>{{ item.symbol }}</strong>
              <span class="dd-name">{{ item.name }}</span>
              <span class="cat-tag">{{ categoryLabel(item.category) }}</span>
            </li>
          </ul>
        </div>
        <button class="btn btn-primary" type="button" data-testid="etf-run" :disabled="!selected.length || loading" @click="load()">
          <span v-if="loading" class="loading-spinner btn-spinner" aria-hidden="true"></span>{{ result ? '更新比較' : '開始比較' }}
        </button>
      </div>

      <div class="cat-row" role="group" aria-label="分類篩選">
        <span class="row-label">分類</span>
        <button v-for="c in CATEGORY_FILTERS" :key="c.key" type="button" class="cat-btn"
                :class="{ active: categoryFilter === c.key }" @click="setCategory(c.key)">{{ c.label }}</button>
      </div>

      <div v-if="selected.length" class="chip-row" data-testid="chip-row">
        <span v-for="(s, i) in selected" :key="s.symbol" class="chip" :data-symbol="s.symbol" draggable="true"
              :class="{ dragging: dragFrom === i, 'drag-over': dragOver === i && dragFrom !== i }"
              @dragstart="onDragStart(i, $event)" @dragover.prevent="dragOver = i" @dragleave="dragOver = -1"
              @drop.prevent="onDrop(i)" @dragend="dragFrom = -1; dragOver = -1">
          <button type="button" class="chip-mv" :disabled="i === 0" :aria-label="`${s.symbol} 往前移`" @click="moveSymbol(i, -1)">◀</button>
          <i class="dot" :style="{ background: s.color }"></i>
          <strong>{{ s.symbol }}</strong> {{ s.name }}
          <button type="button" class="chip-mv" :disabled="i === selected.length - 1" :aria-label="`${s.symbol} 往後移`" @click="moveSymbol(i, 1)">▶</button>
          <button type="button" class="chip-x" :aria-label="`移除 ${s.symbol}`" @click="removeSymbol(s.symbol)">✕</button>
        </span>
      </div>
      <p v-if="activePortfolio && selected.length" class="pf-state" data-testid="portfolio-state" :data-dirty="portfolioDirty ? '1' : '0'">
        目前組合：<strong>{{ activePortfolio.name }}</strong>
        <span v-if="portfolioDirty" class="dirty">已修改、尚未儲存（已存 {{ activePortfolio.symbols.length }} 檔 → 現在 {{ selected.length }} 檔）</span>
        <span v-else class="muted">（內容與已存的相同）</span>
      </p>
      <form v-if="selected.length" class="save-row" @submit.prevent="savePortfolio">
        <input v-model="portfolioName" type="text" class="inp" maxlength="20" data-testid="portfolio-name" placeholder="替這組取個名字，例如：高股息核心" />
        <button v-if="activePortfolio" class="btn btn-primary xs" type="button" data-testid="portfolio-update"
                :disabled="!portfolioDirty" :title="portfolioDirty ? '用目前的標的與順序覆蓋這個組合' : '目前的內容和已存的一樣，不需要更新'"
                @click="updateActivePortfolio">更新「{{ activePortfolio.name }}」</button>
        <button class="btn btn-secondary xs" type="submit" data-testid="portfolio-save"
                :disabled="!portfolioName.trim()" :title="portfolioName.trim() ? '' : '請先在左邊欄位輸入組合名稱'">{{ saveLabel }}</button>
        <button class="btn btn-secondary xs" type="button" data-testid="push-watchlist" @click="pushToWatchlist">全部加入觀察清單</button>
      </form>
      <p v-if="selected.length && nameClash && !(activePortfolio && nameClash.id === activePortfolio.id)" class="warn-text small" data-testid="name-clash">
        已有同名組合「{{ nameClash.name }}」，按「{{ saveLabel }}」會用目前的內容覆蓋它。
      </p>
      <p v-if="selected.length && !portfolioName.trim()" class="muted small" data-testid="name-hint">要存成新組合，請先在上面的欄位輸入名稱。</p>
      <p class="muted small">
        最多 {{ MAX_SYMBOLS }} 檔（目前 {{ selected.length }} 檔）。拖曳標的或按 ◀ ▶ 調整順序，圖例、各表格與 CSV 都依這個順序。<span v-if="dirty" class="dirty">選擇已變更，按「{{ result ? '更新比較' : '開始比較' }}」套用。</span>
      </p>
      <p v-if="portfolioMsg" class="notice-text" role="status" data-testid="portfolio-msg">{{ portfolioMsg }}</p>
      <p v-if="catalogError" class="warn-text">{{ catalogError }}</p>
      <p v-if="errorMessage" class="error-text" role="alert">{{ errorMessage }}</p>
      <p v-if="retryLeft > 0" class="warn-text" role="status" data-testid="rate-limit-note">
        目前查詢太頻繁，{{ result ? '畫面上已有的結果會保留，' : '' }}還要等 {{ retryLabel }}，時間到會自動重新查詢。
      </p>
    </section>

    <div v-if="loading && !result" class="state-box"><span class="loading-spinner" aria-hidden="true"></span> 正在向 FinMind 取得日線與除息資料…</div>

    <div v-if="!result && !loading && !errorMessage" class="state-box empty">
      先點上方「一鍵情境」，或搜尋加入至少一檔標的，再按「開始比較」。
    </div>

    <template v-if="result">
      <p class="asof muted small">
        資料至 {{ result.asof }}（FinMind 日線；價格已處理分割、走勢含息還原）。
        <span v-if="result.failed.length" class="warn-text">
          查無資料：{{ result.failed.map(f => `${f.symbol}${f.name ? ' ' + f.name : ''}`).join('、') }}（{{ result.failed[0].reason }}）。
        </span>
      </p>

      <!-- 圖表一：五維評分 -->
      <section class="card" data-section="radar">
        <div class="section-head">
          <h2>五維評分 <InfoTooltip v-bind="metricGlossary.etfRadar" /></h2>
          <button class="btn xs" type="button" @click="exportCsv">📥 匯出 CSV</button>
        </div>
        <div class="radar-grid">
          <div class="radar-col">
            <EtfRadar :series="radarVisible" />
            <p v-if="!radarVisible.length" class="radar-empty" data-testid="radar-empty">已隱藏全部標的，點右側表格的標的就會顯示。</p>
          </div>
          <div class="table-scroll">
            <div class="legend-tools radar-tools">
              <button type="button" class="chip-btn" data-testid="radar-show-all" @click="showAllRadar">全部顯示</button>
              <button type="button" class="chip-btn" data-testid="radar-hide-all" @click="hideAllRadar">全部隱藏</button>
              <span class="muted small">點標的開關雷達圖上的線，連點兩下只看這一檔。</span>
            </div>
            <table class="score-table" data-testid="score-table">
              <thead>
                <tr>
                  <th>標的</th><th>總分</th><th>報酬</th><th>抗跌</th><th>夏普</th><th>殖利率</th><th>填息</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in ranked" :key="row.symbol" :data-symbol="row.symbol" :class="{ 'radar-off': isRadarHidden(row.symbol) }">
                  <td>
                    <span class="rank">{{ i + 1 }}</span>
                    <button type="button" class="radar-toggle" :data-symbol="row.symbol" data-testid="radar-toggle"
                            :aria-pressed="!isRadarHidden(row.symbol)" title="點一下顯示／隱藏雷達圖上的線；連點兩下只看這一檔"
                            @click="toggleRadar(row.symbol)" @dblclick="soloRadar(row.symbol)">
                      <i class="dot" :style="radarDotStyle(row.symbol)"></i>
                      <strong>{{ row.symbol }}</strong> <span class="nm">{{ row.name }}</span>
                    </button>
                    <span v-if="row.metrics.short_history" class="mini-badge" title="上市未滿一年，樣本短，數字僅供參考">未滿1年</span>
                  </td>
                  <td class="total">
                    <span class="score" :style="scoreStyle(row.scores.total)">{{ score(row.scores.total) }}</span>
                    <small v-if="axisCount(row) < 5" class="axes-n" :title="`總分只平均 ${axisCount(row)} 項有值的評分，與滿 5 項的標的不完全可比`">{{ axisCount(row) }}項</small>
                  </td>
                  <td :title="axisTip(row, 'return')">{{ score(row.scores.return) }}</td>
                  <td :title="axisTip(row, 'defense')">{{ score(row.scores.defense) }}</td>
                  <td :title="axisTip(row, 'sharpe')">{{ score(row.scores.sharpe) }}</td>
                  <td :title="axisTip(row, 'yield')">{{ score(row.scores.yield) }}</td>
                  <td :title="axisTip(row, 'fill')">{{ score(row.scores.fill) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="muted small">「—」代表該項不適用（不配息、無已結案的除息、或上市太短），不會被當成 0 分，總分只平均有值的項目（少於 5 項的會在總分旁標示項數，與滿 5 項者不完全可比）。報酬潛力不足 3 年的標的改用上市以來年化報酬。</p>
          </div>
        </div>
      </section>

      <!-- 圖表二：累積走勢 -->
      <section class="card" data-section="trend">
        <div class="section-head">
          <h2>累積走勢（含息還原，起點 = 100） <InfoTooltip v-bind="metricGlossary.etfTotalReturn" /></h2>
          <div class="tf-tabs" role="tablist" aria-label="走勢區間">
            <button v-for="t in TIMEFRAMES" :key="t" type="button" role="tab" class="tf-btn"
                    :class="{ active: timeframe === t }" :aria-selected="timeframe === t" @click="timeframe = t">{{ t }}</button>
          </div>
        </div>
        <div class="legend-row" role="group" aria-label="走勢圖圖例">
          <button v-for="l in legend" :key="l.symbol" type="button" class="legend-item legend-btn"
                  :class="{ off: isHidden(l.symbol) }" :aria-pressed="!isHidden(l.symbol)" :data-symbol="l.symbol"
                  title="點一下顯示／隱藏這條線；連點兩下只看這一條" @click="toggleSeries(l.symbol)" @dblclick="soloSeries(l.symbol)">
            <i class="dot" :style="legendDotStyle(l)"></i>
            {{ l.symbol }} {{ l.name }}
            <strong :class="cls(l.ret)">{{ pct(l.ret, 1, true) }}</strong>
            <span v-if="l.late" class="mini-badge" title="這段區間內才上市，從上市日起算">較晚上市</span>
          </button>
        </div>
        <div class="legend-tools">
          <button type="button" class="chip-btn" data-testid="series-show-all" @click="showAllSeries">全部顯示</button>
          <button type="button" class="chip-btn" data-testid="series-hide-all" @click="hideAllSeries">全部隱藏</button>
          <button type="button" class="chip-btn" data-testid="chart-reset" @click="resetZoom">重設縮放</button>
          <span class="muted small">點圖例開關單條線，連點兩下只看這一條。</span>
        </div>
        <div ref="chartHost" class="chart-host" data-testid="trend-chart" :data-visible="visibleSymbols.join(',')"></div>

        <div class="table-scroll">
          <table data-testid="perf-table">
            <thead>
              <tr>
                <th>標的</th><th>近 1 年報酬</th><th>3 年年化</th><th>年化波動</th>
                <th>夏普 <InfoTooltip v-bind="metricGlossary.etfSharpe" /></th>
                <th>最大回撤 <InfoTooltip v-bind="metricGlossary.etfMdd" /></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in orderedRows" :key="row.symbol" :data-symbol="row.symbol">
                <td><i class="dot" :style="{ background: colorOf(row.symbol) }"></i><strong>{{ row.symbol }}</strong> <span class="nm">{{ row.name }}</span>
                  <span v-if="row.metrics.short_history" class="mini-badge" :title="`資料起日 ${row.metrics.first_date}，上市未滿一年`">上市未滿1年</span></td>
                <td :class="cls(row.metrics.return_1y)">{{ pct(row.metrics.return_1y, 1, true) }}</td>
                <td :class="cls(row.metrics.cagr_3y)" :title="row.metrics.cagr_3y == null ? '上市不足 3 年' : ''">{{ pct(row.metrics.cagr_3y, 1, true) }}</td>
                <td>{{ pct(row.metrics.ann_vol, 1) }}</td>
                <td>{{ num(row.metrics.sharpe) }}</td>
                <td :class="cls(row.metrics.mdd)">{{ pct(row.metrics.mdd, 1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small">近 1 年報酬、3 年年化皆為含息還原；「—」代表上市時間不夠長，不硬算。夏普的無風險利率採 {{ pct(result.method.risk_free, 1) }}。</p>
      </section>

      <!-- 圖表三：配息與填息 -->
      <section class="card" data-section="dividend">
        <div class="section-head">
          <h2>歷年配息與填息 <InfoTooltip v-bind="metricGlossary.etfFill" /></h2>
          <div class="tf-tabs" role="tablist" aria-label="配息顯示方式">
            <button type="button" role="tab" class="tf-btn" :class="{ active: divMode === 'amount' }" @click="divMode = 'amount'">金額（元）</button>
            <button type="button" role="tab" class="tf-btn" :class="{ active: divMode === 'yield' }" @click="divMode = 'yield'">殖利率（%）</button>
          </div>
        </div>
        <div class="legend-row">
          <span v-for="l in legend" :key="l.symbol" class="legend-item"><i class="dot" :style="{ background: l.color }"></i>{{ l.symbol }} {{ l.name }}</span>
        </div>
        <EtfDividendBars :series="divSeries" :mode="divMode" />
        <p class="muted small">殖利率 = 該年累計現金股利 ÷ 該年最後一個交易日收盤價；今年為累計至最新交易日。不配息的標的長條為「–」。</p>

        <div class="table-scroll">
          <table data-testid="div-table">
            <thead>
              <tr>
                <th>標的</th><th>近 12 月殖利率</th><th>近 12 月配息</th><th>填息成功率</th><th>平均填息天數</th><th>近 3 年除息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in orderedRows" :key="row.symbol" :data-symbol="row.symbol">
                <td><i class="dot" :style="{ background: colorOf(row.symbol) }"></i><strong>{{ row.symbol }}</strong> <span class="nm">{{ row.name }}</span></td>
                <template v-if="row.dividends.pays_dividend">
                  <td>{{ pct(row.dividends.yield_ttm, 2) }}</td>
                  <td>{{ num(row.dividends.ttm_amount) }} 元</td>
                  <td>{{ pct(row.fill.success_rate, 0) }}</td>
                  <td>{{ row.fill.avg_days == null ? '—' : row.fill.avg_days.toFixed(1) + ' 天' }}</td>
                  <td class="fill-detail">{{ fillDetail(row.fill) }}</td>
                </template>
                <template v-else>
                  <td colspan="5" class="muted">近 5 年沒有除息紀錄（不配息或尚未配息）</td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small">填息 = 除息後收盤價站回「除息前一天收盤價」；{{ result.method.fill_window_days }} 個交易日內沒站回算失敗，尚未滿觀察期的算「未結案」、不計入成功率。僅統計最近 {{ result.method.fill_lookback_years }} 年。</p>
      </section>

      <!-- 圖表三之一：配息體檢（高殖利率撐不撐得住） -->
      <section class="card" data-section="div-health">
        <div class="section-head">
          <h2>配息體檢：這個殖利率撐得住嗎？ <InfoTooltip v-bind="metricGlossary.etfDivHealth" /></h2>
        </div>
        <p class="muted small health-intro">股價大跌時，殖利率（過去配息 ÷ 現價）會被分母變小撐高，但過去配得出來不代表以後也配得出來。這裡用同一份除息紀錄做四項檢查：殖利率是不是被跌價撐大、每次配息穩不穩、最近有沒有縮水、配息有沒有被價格下跌吃掉。</p>
        <EtfDividendHealth :rows="orderedRows" :color-of="colorOf" :thresholds="result.method.health" />
      </section>

      <!-- 圖表三之二：急跌與反彈 -->
      <section class="card" data-section="event">
        <div class="section-head">
          <h2>急跌與反彈 <InfoTooltip v-bind="metricGlossary.etfEvent" /></h2>
        </div>
        <div class="event-bar">
          <p v-if="result.event" class="event-desc" data-testid="event-desc">
            比較區間 <strong>{{ result.event.start }} ～ {{ result.event.end }}</strong>
            <span v-if="result.event.source === 'auto'" class="muted">（自動偵測：{{ result.event.anchor || autoAnchor }} {{ lookbackLabel(result.event.lookback_days || autoLookback) }}最大回落 {{ pct(result.event.drop, 1) }}）</span>
            <span v-else class="muted">（自訂區間）</span>
          </p>
          <p v-else class="event-desc muted" data-testid="event-desc">{{ autoAnchor }} {{ lookbackLabel(autoLookback) }}沒有達 5% 的明顯急跌，可調整下方的偵測設定，或手動指定區間。</p>
        </div>
        <div v-if="!customEvent" class="auto-set" data-testid="auto-settings">
          <span class="row-label">自動偵測設定</span>
          <label class="field"><span>偵測基準</span>
            <select v-model="autoAnchor" class="inp" data-testid="auto-anchor" :disabled="loading" @change="rerunAuto">
              <option v-for="o in anchorOptions" :key="o.symbol" :value="o.symbol">{{ o.symbol }} {{ o.name }}{{ o.symbol === '0050' ? '（預設）' : '' }}</option>
            </select>
          </label>
          <label class="field"><span>回看期間</span>
            <select v-model.number="autoLookback" class="inp" data-testid="auto-lookback" :disabled="loading" @change="rerunAuto">
              <option v-for="d in LOOKBACKS" :key="d" :value="d">{{ lookbackLabel(d) }}{{ d === 180 ? '（預設）' : '' }}</option>
            </select>
          </label>
          <span class="muted small">在回看期間內，找基準標的最大的一段「高點→低點」回落（至少 5%）當比較區間。</span>
        </div>
        <div class="event-bar">
          <form class="event-form" @submit.prevent="applyEventRange">
            <label class="field"><span>起</span><input v-model="eventStart" type="date" class="inp" /></label>
            <label class="field"><span>迄</span><input v-model="eventEnd" type="date" class="inp" /></label>
            <button class="btn btn-secondary xs" type="submit" data-testid="apply-range" :disabled="!eventStart || !eventEnd || loading">套用區間</button>
            <button v-if="customEvent" class="btn btn-secondary xs" type="button" :disabled="loading" @click="resetEventRange">回到自動偵測</button>
          </form>
          <div class="quick-range" role="group" aria-label="快速指定區間">
            <span class="row-label">快速區間</span>
            <button v-for="q in QUICK_RANGES" :key="q.key" type="button" class="chip-btn" :data-quick="q.key" :disabled="loading" @click="applyQuickRange(q)">{{ q.label }}</button>
          </div>
        </div>

        <div v-if="result.event" class="table-scroll event-wrap">
          <table data-testid="event-table">
            <thead>
              <tr>
                <th>標的</th>
                <th title="整段區間內（不分先後）最低的日內低點">區間最低</th>
                <th title="整段區間內最高的日內高點">區間最高</th>
                <th title="區間最高點之後的最低點；回落與反彈都以它為準">其後最低</th>
                <th>回落</th>
                <th>反彈高點</th><th>反彈幅度</th>
                <th title="最新交易日的收盤價（已處理分割、不含息）">目前價位</th>
                <th title="最新收盤 ÷ 其後最低 − 1；沒反彈時也看得出目前離低點多遠">目前價距低點</th><th>區間內除息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in orderedRows" :key="row.symbol" :data-symbol="row.symbol">
                <td>
                  <i class="dot" :style="{ background: colorOf(row.symbol) }"></i><strong>{{ row.symbol }}</strong> <span class="nm">{{ row.name }}</span>
                  <button type="button" class="row-chart-btn" data-testid="show-chart" :aria-label="`看 ${row.symbol} 的走勢圖`" @click="showChart(row.symbol)">走勢圖</button>
                </td>
                <template v-if="row.event">
                  <td data-testid="window-low">{{ price(row.event.window_low ?? row.event.low) }} <span class="dt">{{ md(row.event.window_low_date ?? row.event.low_date) }}</span></td>
                  <td>{{ price(row.event.high) }} <span class="dt">{{ md(row.event.high_date) }}</span></td>
                  <td>{{ price(row.event.low) }} <span class="dt">{{ md(row.event.low_date) }}</span></td>
                  <td :class="cls(row.event.drawdown)">{{ pct(row.event.drawdown, 1) }}</td>
                  <template v-if="row.event.rebound_high != null">
                    <td>{{ price(row.event.rebound_high) }} <span class="dt">{{ md(row.event.rebound_date) }}</span></td>
                    <td :class="cls(row.event.rebound_pct)">{{ pct(row.event.rebound_pct, 1, true) }}</td>
                  </template>
                  <td v-else colspan="2" class="no-rebound" data-testid="no-rebound"
                      :title="`最低點 ${row.event.low_date} 就是最新交易日，之後還沒有資料可以算反彈，不是缺資料。`">
                    <span class="na-tag">尚未反彈</span>
                    <span class="dt">最低點就是最新交易日 {{ md(row.event.low_date) }}</span>
                  </td>
                  <td data-testid="last-price">{{ price(row.metrics.last_close) }} <span class="dt">{{ md(row.metrics.last_date) }}</span></td>
                  <td :class="cls(fromLow(row))" data-testid="from-low">{{ pct(fromLow(row), 1, true) }}</td>
                  <td>
                    <template v-if="row.event.dividends_in_window > 0">{{ row.event.dividends_in_window.toFixed(2) }} 元</template>
                    <template v-else-if="!row.dividends.pays_dividend">
                      <span class="na-tag" data-testid="no-div" title="近幾年沒有除息紀錄：不配息，或上市至今還沒配過息。">尚未配息</span>
                    </template>
                    <template v-else>
                      <span class="na-tag" data-testid="no-div" :title="`${result.event.start} ～ ${result.event.end} 之間沒有除息日，不是缺資料。`">無除息</span>
                      <span v-if="exNeighbors(row)" class="dt">{{ exNeighbors(row) }}</span>
                    </template>
                    <span v-if="row.event.partial" class="mini-badge" title="這檔在區間起點之後才上市">區間內才上市</span></td>
                </template>
                <template v-else>
                  <td colspan="9" class="muted">此區間內沒有日線資料</td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- 個股走勢：把上表的項目標在圖上，才看得出先後順序；下方同步的 KD -->
        <div v-if="result.event && chartRow" ref="chartPanel" class="event-chart-panel" data-testid="event-chart-panel">
          <div class="chart-panel-head">
            <h3>個股走勢</h3>
            <span class="muted small">上表的項目標在走勢圖上，看得出先後順序；下方是同步的 KD。</span>
          </div>
          <div class="chart-chips" role="group" aria-label="選擇要看走勢的標的">
            <button v-for="r in orderedRows" :key="r.symbol" type="button" class="chip-btn"
                    :class="{ active: r.symbol === chartRow.symbol }" :aria-pressed="r.symbol === chartRow.symbol"
                    :data-testid="`chart-chip-${r.symbol}`" @click="chartSymbol = r.symbol">
              <i class="dot" :style="{ background: colorOf(r.symbol) }"></i>{{ r.symbol }} <span class="nm">{{ r.name }}</span>
            </button>
          </div>
          <EtfEventChart :symbol="chartRow.symbol" :name="chartRow.name" :range="result.event"
                         :event="chartRow.event" :last-close="chartRow.metrics.last_close" :last-date="chartRow.metrics.last_date" />
        </div>
        <p class="muted small">價格為日內最高／最低、已處理分割、<strong>不含息</strong>（看盤軟體上看到的價格）；因此回落幅度會比上表「最大回撤（含息、收盤）」更深。區間內有除息的標的，部分跌幅是配息造成的。反彈幅度 =（其後最低之後的最高 ÷ 其後最低）− 1。</p>
        <p class="muted small">
          <strong>「區間最低」</strong>是整段區間（不分先後）的最低價；<strong>「其後最低」</strong>只看區間最高點之後，回落與反彈都以它為準，所以低點若出現在高點之前，兩者會不同。
          <strong>「目前價位」</strong>是最新交易日的收盤價。
        </p>
        <p class="muted small">
          <strong>「尚未反彈」</strong>＝區間最低點就是最新交易日，之後還沒有資料可算，不是缺資料（此時看「目前價距低點」）；
          <strong>「無除息」</strong>＝這段期間沒有除息日，旁邊小字是前後最近的除息日；<strong>「尚未配息」</strong>＝近幾年沒有除息紀錄（例如剛上市的 ETF）。
        </p>
      </section>

      <!-- 圖表四：持股明細 -->
      <section class="card holdings-card" data-section="holdings">
        <div class="section-head"><h2>持股明細與重疊度</h2></div>
        <p class="holdings-note" data-testid="holdings-note">
          這張圖需要各 ETF 的「成分股與權重」。FinMind 免費帳號沒有這份資料，而主要財經網站的使用條款禁止自動抓取，
          所以目前不顯示，也<strong>不會用手寫的數字充數</strong>。要補上這張圖，需要改接各投信官網的持股揭露（每家格式不同）或付費資料源。
        </p>
      </section>

      <details class="card method">
        <summary>計算方式與資料限制</summary>
        <ul>
          <li><strong>資料來源</strong>：FinMind 免費帳號的 TaiwanStockPrice（原始日線）與 TaiwanStockDividendResult（除息日、除息前收盤、參考價、每股現金股利）。同一標的結果快取 6 小時。</li>
          <li><strong>分割處理</strong>：原始日線沒有處理分割（例：0050 在 2025-06 一拆四，收盤從 188.65 掉到 47.57）。單日漲跌超過 ±40% 視為分割並依倍率還原，否則最大回撤會被算成 −75%。</li>
          <li><strong>含息還原</strong>：除息日把除息前一天收盤 → 除息參考價的比例，連乘到之前所有日期，等於配息在除息日再投入。</li>
          <li><strong>夏普</strong>：（年化報酬 − {{ pct(result.method.risk_free, 1) }}）÷ 年化波動，使用最近 1 年日報酬。上市不滿 1 年但至少 {{ result.method.min_stats_days }} 個交易日者仍會計算，並標示「上市未滿1年」；不足 {{ result.method.min_stats_days }} 個交易日則顯示「—」。</li>
          <li><strong>五維評分</strong>：報酬 = 3 年年化 ÷ 30%；抗跌 = 100 −（|最大回撤| − 14%）× 3.5（限 30–95）；夏普 = 夏普 ÷ 1.4；殖利率 = 近 12 月殖利率 ÷ 10%；填息 = 60% 成功率 + 40% 速度。各項上限 100，總分為有值項目的平均。</li>
          <li><strong>持股明細</strong>：目前沒有合法可用的資料來源（見該區塊說明），所以不顯示。</li>
          <li><strong>分類</strong>：FinMind 沒有 ETF 子類別，市值型／高股息／主動型是依名稱規則判斷，個別標的可能判錯。</li>
          <li><strong>不是建議</strong>：這是歷史資料的整理，不是預測，也不構成投資建議。</li>
        </ul>
      </details>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createChart } from 'lightweight-charts'
import PageFocusBanner from '../components/PageFocusBanner.vue'
import InfoTooltip from '../components/InfoTooltip.vue'
import EtfRadar from '../components/etf/EtfRadar.vue'
import EtfDividendBars from '../components/etf/EtfDividendBars.vue'
import EtfEventChart from '../components/etf/EtfEventChart.vue'
import EtfDividendHealth from '../components/etf/EtfDividendHealth.vue'
import { metricGlossary } from '../lib/metricGlossary'
import { useChartTheme } from '../composables/useChartTheme'
import { downloadCsv, timestampedFilename } from '../lib/csvExport'
import { loadWatchlist, saveWatchlist } from '../lib/watchlist'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const MAX_SYMBOLS = 10
const STORAGE_KEY = 'finlab.etfCompare.symbols'
const PORTFOLIO_KEY = 'finlab.etfCompare.portfolios'
const MAX_PORTFOLIOS = 20
const ACTIVE_PF_KEY = 'finlab.etfCompare.activePortfolio'
const CATALOG_KEY = 'finlab.etfCompare.catalog'
const CATALOG_TTL_MS = 12 * 60 * 60 * 1000 // 標的清單一天內幾乎不變；存在瀏覽器，重新整理不必再問後端
const BENCHMARK = '0050'
const DEFAULT_LOOKBACK = 180
const LOOKBACKS = [30, 90, 180, 365, 730] // 後端上限 730 天
const QUICK_RANGES = [
  { key: '3m', label: '近 3 個月', months: 3 },
  { key: '6m', label: '近 6 個月', months: 6 },
  { key: 'ytd', label: '今年以來', ytd: true },
  { key: '1y', label: '近 1 年', months: 12 },
]
const SYMBOL_RE = /^[0-9A-Z]{3,8}$/
const TW_CODE_RE = /^\d{4,6}[A-Z]?$/
const TIMEFRAMES = ['6M', 'YTD', '1Y', '3Y', '5Y']
const CATEGORY_FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'market', label: '市值型' },
  { key: 'dividend', label: '高股息' },
  { key: 'active', label: '主動型' },
  { key: 'other', label: '其他 ETF' },
  { key: 'stock', label: '個股' },
]

const theme = useChartTheme()
// 紅／綠留給漲跌語意，系列色避開它們
const PALETTE = [theme.blue, theme.purple, theme.cyan, theme.warn, '#ec4899', '#6366f1', '#fb923c', '#94a3b8', '#d946ef', '#38bdf8']

const route = useRoute()
const router = useRouter()

const catalog = ref({ etfs: [], category_labels: {} })
const presets = ref([])
const catalogError = ref('')
const selected = ref([]) // [{ symbol, name, color }]
const searchInput = ref('')
const remoteResults = ref([])
const dropdownOpen = ref(false)
const categoryFilter = ref('all')
const searchShell = ref(null)

const loading = ref(false)
const errorMessage = ref('')
const result = ref(null)
const loadedKey = ref('')
const timeframe = ref('1Y')
// 預設看殖利率：不同價位的標的（例如 2,000 元的個股 vs 30 元的 ETF）比「配息金額」沒有意義
const divMode = ref('yield')
const eventStart = ref('')
const eventEnd = ref('')
const customEvent = ref(false)
// 自動偵測設定：用哪一檔、往回看幾天找最大的一段回落
const autoAnchor = ref(BENCHMARK)
const autoLookback = ref(DEFAULT_LOOKBACK)
// 被限流時剩幾秒；時間到自動重試上一次失敗的查詢
const retryLeft = ref(0)
let retryTimer = null
let retryRange = null

const chartHost = ref(null)
let chartInstance = null
let seriesBySymbol = new Map() // symbol -> lightweight-charts series（圖例開關要用）
let loadSeq = 0
let searchSeq = 0
let searchTimer = null
let msgTimer = null

// 我的組合（存在本機瀏覽器）與已選標的的排序
const portfolios = ref([]) // [{ id, name, symbols }]
const portfolioName = ref('')
const portfolioMsg = ref('')
const activePortfolioId = ref('') // 目前載入（或剛存好）的是哪一組，用來判斷「已修改、尚未儲存」
const dragFrom = ref(-1)
const dragOver = ref(-1)
// 走勢圖、雷達圖被使用者關掉的線（各自獨立，只影響各自的圖）
const hiddenSymbols = ref([])
const hiddenRadar = ref([])

// ── 標的選擇 ────────────────────────────────────────────────────────────────
const selectedKey = computed(() => selected.value.map(s => s.symbol).join(','))
const sameSet = (a, b) => a.length === b.length && [...a].sort().join(',') === [...b].sort().join(',')
// 只調整順序不算「變更」：資料已經在手上，不必再打一次 API
const dirty = computed(() => !!selected.value.length &&
  !sameSet(selected.value.map(s => s.symbol), loadedKey.value.split(',').filter(Boolean)))

function categoryLabel(key) {
  return catalog.value.category_labels?.[key] || CATEGORY_FILTERS.find(c => c.key === key)?.label || ''
}

function nextColor() {
  const used = new Set(selected.value.map(s => s.color))
  return PALETTE.find(c => !used.has(c)) || PALETTE[selected.value.length % PALETTE.length]
}

function nameFromCatalog(symbol) {
  return catalog.value.etfs.find(e => e.symbol === symbol)?.name || ''
}

function addSymbol(symbol, name) {
  const sym = String(symbol || '').trim().toUpperCase()
  if (!SYMBOL_RE.test(sym)) {
    errorMessage.value = `「${symbol}」不是有效的台股代碼。`
    return
  }
  if (selected.value.length >= MAX_SYMBOLS || selected.value.some(s => s.symbol === sym)) return
  errorMessage.value = ''
  selected.value = [...selected.value, { symbol: sym, name: name || nameFromCatalog(sym), color: nextColor() }]
  searchInput.value = ''
  remoteResults.value = []
  dropdownOpen.value = false
}

function removeSymbol(symbol) {
  selected.value = selected.value.filter(s => s.symbol !== symbol)
}

// ── 順序（拖曳或 ◀ ▶） ─────────────────────────────────────────────────────
function afterReorder() {
  saveSelection()
  if (result.value && !dirty.value) {
    loadedKey.value = selectedKey.value
    router.replace({ query: { symbols: selectedKey.value } }).catch(() => {})
  }
}

function moveSymbol(i, delta) {
  const j = i + delta
  if (j < 0 || j >= selected.value.length) return
  const arr = [...selected.value]
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  selected.value = arr
  afterReorder()
}

function onDragStart(i, e) {
  dragFrom.value = i
  if (e?.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', String(i)) } catch { /* 部分瀏覽器不允許，不影響拖曳 */ }
  }
}

function onDrop(i) {
  const from = dragFrom.value
  dragFrom.value = -1
  dragOver.value = -1
  if (from < 0 || from === i || from >= selected.value.length) return
  const arr = [...selected.value]
  const [moved] = arr.splice(from, 1)
  arr.splice(i, 0, moved)
  selected.value = arr
  afterReorder()
}

// ── 我的組合 ────────────────────────────────────────────────────────────────
function say(text) {
  portfolioMsg.value = text
  clearTimeout(msgTimer)
  msgTimer = setTimeout(() => { portfolioMsg.value = '' }, 6000)
}

function readPortfolios() {
  try {
    const raw = JSON.parse(localStorage.getItem(PORTFOLIO_KEY) || '[]')
    if (!Array.isArray(raw)) return []
    return raw
      .filter(p => p && typeof p.name === 'string' && Array.isArray(p.symbols))
      .map(p => ({ id: String(p.id || p.name), name: p.name, symbols: p.symbols.map(String).filter(s => SYMBOL_RE.test(s)).slice(0, MAX_SYMBOLS) }))
      .filter(p => p.symbols.length)
  } catch { return [] }
}

function persistPortfolios() {
  try {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(portfolios.value))
    return true
  } catch {
    say('瀏覽器封鎖了本機儲存空間（無痕模式？），組合只能在這次瀏覽期間使用。')
    return false
  }
}

function savePortfolio() {
  const name = portfolioName.value.trim().slice(0, 20)
  if (!name || !selected.value.length) return
  const symbols = selected.value.map(s => s.symbol)
  const idx = portfolios.value.findIndex(p => p.name === name)
  if (idx >= 0) {
    portfolios.value = portfolios.value.map((p, i) => (i === idx ? { ...p, symbols } : p))
    activePortfolioId.value = portfolios.value[idx].id
    persistPortfolios() && say(`已更新組合「${name}」（${symbols.length} 檔）。`)
  } else {
    if (portfolios.value.length >= MAX_PORTFOLIOS) {
      say(`最多存 ${MAX_PORTFOLIOS} 組，請先刪除不用的組合。`)
      return
    }
    const id = `pf-${Date.now().toString(36)}`
    portfolios.value = [...portfolios.value, { id, name, symbols }]
    activePortfolioId.value = id
    persistPortfolios() && say(`已存成組合「${name}」（${symbols.length} 檔），之後點它就能載入。`)
  }
}

// 載入組合後再刪減／調整順序：一鍵用目前的內容覆蓋「目前這一組」，不必重打名稱
function updateActivePortfolio() {
  const p = activePortfolio.value
  if (!p || !selected.value.length) return
  const symbols = selected.value.map(s => s.symbol)
  const before = p.symbols.length
  portfolios.value = portfolios.value.map(x => (x.id === p.id ? { ...x, symbols } : x))
  persistPortfolios() && say(`已更新組合「${p.name}」：${before} 檔 → ${symbols.length} 檔。`)
}

function applyPortfolio(p) {
  setSelection(p.symbols)
  activePortfolioId.value = p.id
  portfolioName.value = p.name
  errorMessage.value = ''
  customEvent.value = false
  load()
}

function deletePortfolio(p) {
  if (!window.confirm(`確定刪除組合「${p.name}」嗎？`)) return
  portfolios.value = portfolios.value.filter(x => x.id !== p.id)
  if (activePortfolioId.value === p.id) {
    activePortfolioId.value = ''
    portfolioName.value = ''
  }
  persistPortfolios()
  say(`已刪除組合「${p.name}」。`)
}

// 從觀察清單「補進來」而不是整個取代：已選的標的與順序不動
function importWatchlist() {
  const wl = loadWatchlist().filter(s => SYMBOL_RE.test(s))
  if (!wl.length) { say('觀察清單是空的，請先到「觀察清單」加入股票。'); return }
  const have = new Set(selected.value.map(s => s.symbol))
  const fresh = wl.filter(s => !have.has(s))
  if (!fresh.length) { say('觀察清單的標的都已經在比較清單裡。'); return }
  const room = Math.max(MAX_SYMBOLS - selected.value.length, 0)
  if (!room) { say(`已滿 ${MAX_SYMBOLS} 檔，先移除幾檔再匯入。`); return }
  const take = fresh.slice(0, room)
  take.forEach(sym => addSymbol(sym, ''))
  const skipped = fresh.length - take.length
  say(`已從觀察清單加入 ${take.length} 檔${skipped ? `（另有 ${skipped} 檔超過 ${MAX_SYMBOLS} 檔上限沒加入）` : ''}，按「${result.value ? '更新比較' : '開始比較'}」套用。`)
}

// 只「新增」到觀察清單，不覆蓋：觀察清單是作戰台、訊號掃描等頁共用的同一份
function pushToWatchlist() {
  const wl = loadWatchlist()
  const have = new Set(wl)
  const add = selected.value.map(s => s.symbol).filter(s => !have.has(s))
  if (!add.length) { say('這些標的都已經在觀察清單裡。'); return }
  saveWatchlist([...add, ...wl])
  say(`已把 ${add.length} 檔加入觀察清單（原有的 ${wl.length} 檔不受影響）。`)
}

function setSelection(symbols) {
  const list = []
  for (const sym of symbols.slice(0, MAX_SYMBOLS)) {
    list.push({ symbol: sym, name: nameFromCatalog(sym), color: PALETTE[list.length % PALETTE.length] })
  }
  selected.value = list
}

function applyPreset(p) {
  setSelection(p.symbols)
  activePortfolioId.value = '' // 一鍵情境是另一批標的，不再算「某個組合的修改」
  errorMessage.value = ''
  customEvent.value = false
  load()
}

function resetAll() {
  loadSeq++ // 讓進行中的請求作廢
  clearRetry()
  selected.value = []
  hiddenSymbols.value = []
  hiddenRadar.value = []
  activePortfolioId.value = ''
  portfolioName.value = ''
  autoAnchor.value = BENCHMARK
  autoLookback.value = DEFAULT_LOOKBACK
  result.value = null
  loadedKey.value = ''
  errorMessage.value = ''
  customEvent.value = false
  saveSelection()
  router.replace({ query: {} }).catch(() => {})
}

function setCategory(key) {
  categoryFilter.value = key
  dropdownOpen.value = true
}

function submitSearchInput() {
  const q = searchInput.value.trim()
  if (!q) return
  const exact = dropdownItems.value.find(it => it.symbol.toUpperCase() === q.toUpperCase())
  if (exact) addSymbol(exact.symbol, exact.name)
  else if (SYMBOL_RE.test(q.toUpperCase())) addSymbol(q.toUpperCase(), '')
  else if (dropdownItems.value.length) addSymbol(dropdownItems.value[0].symbol, dropdownItems.value[0].name)
}

const dropdownItems = computed(() => {
  const q = searchInput.value.trim().toLowerCase()
  const chosen = new Set(selected.value.map(s => s.symbol))
  const cat = categoryFilter.value
  let list = []
  if (cat !== 'stock') {
    list = catalog.value.etfs.filter(e =>
      !chosen.has(e.symbol) && (cat === 'all' || e.category === cat) &&
      (!q || e.symbol.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)))
  }
  if (cat === 'all' || cat === 'stock') {
    const known = new Set(list.map(e => e.symbol))
    list = list.concat(remoteResults.value.filter(r => !chosen.has(r.symbol) && !known.has(r.symbol)))
  }
  if (!q && cat === 'all') return [] // 沒輸入也沒選分類時不展開，避免一長串清單
  return list.slice(0, 14)
})

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    const q = searchInput.value.trim()
    if (!q || categoryFilter.value === 'market' || categoryFilter.value === 'dividend' || categoryFilter.value === 'active') {
      remoteResults.value = []
      return
    }
    const seq = ++searchSeq
    try {
      const resp = await fetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(q)}`)
      const payload = await resp.json().catch(() => ({}))
      if (seq !== searchSeq) return
      remoteResults.value = (payload?.data?.items || [])
        .filter(it => TW_CODE_RE.test(String(it.symbol || '')))
        .map(it => ({ symbol: it.symbol, name: it.name_zh || it.name || '', category: 'stock' }))
    } catch {
      if (seq === searchSeq) remoteResults.value = []
    }
  }, 250)
}
watch(searchInput, () => { dropdownOpen.value = true; onSearchInput() })

function onDocClick(e) {
  if (searchShell.value && !searchShell.value.contains(e.target)) dropdownOpen.value = false
}

// ── 載入比較 ────────────────────────────────────────────────────────────────
function saveSelection() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selected.value.map(s => s.symbol)))
  } catch { /* 無痕模式或被封鎖：不影響功能 */ }
}

async function load(range) {
  if (!selected.value.length) return
  const seq = ++loadSeq
  loading.value = true
  errorMessage.value = ''
  const symbols = selectedKey.value
  const params = new URLSearchParams({ symbols })
  const useRange = range || (customEvent.value && eventStart.value && eventEnd.value ? { start: eventStart.value, end: eventEnd.value } : null)
  if (useRange) {
    params.set('event_start', useRange.start)
    params.set('event_end', useRange.end)
  } else {
    // 自動偵測：基準若已不在已選標的裡（被移除了）就退回 0050，不然後端會拒絕
    if (!anchorOptions.value.some(o => o.symbol === autoAnchor.value)) autoAnchor.value = BENCHMARK
    params.set('auto_anchor', autoAnchor.value)
    params.set('auto_lookback', String(autoLookback.value))
  }
  try {
    const resp = await fetch(`${API_BASE}/api/v1/etf-compare/compare?${params}`)
    const payload = await resp.json().catch(() => ({}))
    if (seq !== loadSeq) return
    if (!resp.ok || !payload?.success) {
      errorMessage.value = payload?.detail || `查詢失敗（HTTP ${resp.status}）`
      // 被限流：畫面上已有的結果原封不動，倒數後自動重試（後端用固定視窗，等到就一定解鎖）
      if (resp.status === 429) startRetry(resp.headers.get('Retry-After'), range || null)
      return
    }
    clearRetry()
    result.value = payload.data
    loadedKey.value = symbols
    // 圖例開關：只保留還在結果裡的標的
    const inResult = new Set(payload.data.symbols.map(s => s.symbol))
    hiddenSymbols.value = hiddenSymbols.value.filter(s => inResult.has(s))
    hiddenRadar.value = hiddenRadar.value.filter(s => inResult.has(s))
    // 名稱以後端回傳為準（個股不在 ETF 清單裡時才有名稱）
    const names = new Map(payload.data.symbols.map(s => [s.symbol, s.name]))
    selected.value = selected.value.map(s => ({ ...s, name: names.get(s.symbol) || s.name }))
    if (payload.data.event) {
      eventStart.value = payload.data.event.start
      eventEnd.value = payload.data.event.end
    }
    saveSelection()
    router.replace({ query: { symbols } }).catch(() => {})
  } catch (e) {
    if (seq === loadSeq) errorMessage.value = e?.message || '查詢失敗'
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function startRetry(retryAfter, range) {
  const secs = Math.min(Math.max(parseInt(retryAfter, 10) || 60, 5), 900)
  clearRetry()
  retryRange = range
  retryLeft.value = secs
  retryTimer = setInterval(() => {
    retryLeft.value -= 1
    if (retryLeft.value > 0) return
    const again = retryRange
    clearRetry()
    load(again)
  }, 1000)
}

function clearRetry() {
  clearInterval(retryTimer)
  retryTimer = null
  retryRange = null
  retryLeft.value = 0
}

const retryLabel = computed(() => {
  const s = retryLeft.value
  return s >= 60 ? `${Math.floor(s / 60)} 分 ${String(s % 60).padStart(2, '0')} 秒` : `${s} 秒`
})

// 改了偵測基準或回看期間：維持自動偵測，只是用新的條件重新找區間
function rerunAuto() {
  load(null)
}

function lookbackLabel(days) {
  if (days === 365) return '近 1 年'
  if (days === 730) return '近 2 年'
  return `近 ${days} 天`
}

// 快速區間：以最新資料日往回推，一鍵套用成自訂區間
function applyQuickRange(q) {
  const asof = result.value?.asof
  if (!asof) return
  const d = new Date(`${asof}T00:00:00Z`)
  if (!q.ytd) d.setUTCMonth(d.getUTCMonth() - q.months)
  eventStart.value = q.ytd ? `${asof.slice(0, 4)}-01-01` : d.toISOString().slice(0, 10)
  eventEnd.value = asof
  applyEventRange()
}

function applyEventRange() {
  if (!eventStart.value || !eventEnd.value) return
  if (eventStart.value >= eventEnd.value) {
    errorMessage.value = '急跌區間的起日必須早於迄日。'
    return
  }
  customEvent.value = true
  load({ start: eventStart.value, end: eventEnd.value })
}

function resetEventRange() {
  customEvent.value = false
  load(null)
}

// ── 衍生資料 ────────────────────────────────────────────────────────────────
function colorOf(symbol) {
  const hit = selected.value.find(s => s.symbol === symbol)
  if (hit) return hit.color
  const i = result.value ? result.value.symbols.findIndex(s => s.symbol === symbol) : 0
  return PALETTE[Math.max(i, 0) % PALETTE.length]
}

// 結果依「已選標的的順序」排列（後端依請求順序回傳；使用者調整順序後不必重打 API）
const orderedRows = computed(() => {
  if (!result.value) return []
  const order = new Map(selected.value.map((s, i) => [s.symbol, i]))
  return [...result.value.symbols].sort((a, b) => (order.get(a.symbol) ?? 99) - (order.get(b.symbol) ?? 99))
})

const ranked = computed(() => {
  if (!result.value) return []
  return [...orderedRows.value].sort((a, b) => (b.scores.total ?? -1) - (a.scores.total ?? -1))
})

// ── 急跌與反彈：個股走勢圖（品管 11/02、11/03）───────────────────────────────
// 一次只畫一檔（10 檔各畫一組 K 線＋KD 太長，手機上更是）；預設第一檔，
// 表格每列的「走勢」按鈕與上方晶片都可以切換。
const chartSymbol = ref('')
const chartPanel = ref(null)
const chartRow = computed(() => orderedRows.value.find(r => r.symbol === chartSymbol.value) || orderedRows.value[0] || null)
function showChart(symbol) {
  chartSymbol.value = symbol
  nextTick(() => chartPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

const radarSeries = computed(() =>
  (orderedRows.value).map(s => ({ symbol: s.symbol, color: colorOf(s.symbol), scores: s.scores })))

// ── 雷達圖開關（跟累積走勢同一套操作：點一下開關、連點兩下只看這一條）──────────
const isRadarHidden = symbol => hiddenRadar.value.includes(symbol)
const radarVisible = computed(() => radarSeries.value.filter(s => !isRadarHidden(s.symbol)))
const radarDotStyle = symbol => (isRadarHidden(symbol)
  ? { background: 'transparent', border: `2px solid ${colorOf(symbol)}`, boxSizing: 'border-box' }
  : { background: colorOf(symbol) })

function toggleRadar(symbol) {
  hiddenRadar.value = isRadarHidden(symbol)
    ? hiddenRadar.value.filter(s => s !== symbol)
    : [...hiddenRadar.value, symbol]
}

function soloRadar(symbol) {
  const all = radarSeries.value.map(s => s.symbol)
  const alreadySolo = radarVisible.value.length === 1 && radarVisible.value[0].symbol === symbol
  hiddenRadar.value = alreadySolo ? [] : all.filter(s => s !== symbol)
}

const showAllRadar = () => { hiddenRadar.value = [] }
const hideAllRadar = () => { hiddenRadar.value = radarSeries.value.map(s => s.symbol) }

// ── 急跌與反彈：自動偵測的基準選項（0050 ＋ 目前已選的標的）───────────────────
const anchorOptions = computed(() => {
  const opts = [{ symbol: BENCHMARK, name: nameFromCatalog(BENCHMARK) || '元大台灣50' }]
  for (const s of selected.value) if (s.symbol !== BENCHMARK) opts.push({ symbol: s.symbol, name: s.name })
  return opts
})
watch(anchorOptions, opts => {
  if (!opts.some(o => o.symbol === autoAnchor.value)) autoAnchor.value = BENCHMARK
})

// ── 我的組合：目前這一組有沒有被改過 ─────────────────────────────────────────
const activePortfolio = computed(() => portfolios.value.find(p => p.id === activePortfolioId.value) || null)
// 順序也算內容（組合就是「這幾檔依這個順序」），所以調順序也算已修改
const portfolioDirty = computed(() => !!activePortfolio.value && selectedKey.value !== activePortfolio.value.symbols.join(','))
const nameClash = computed(() => {
  const n = portfolioName.value.trim()
  return n ? portfolios.value.find(p => p.name === n) || null : null
})
const saveLabel = computed(() => (nameClash.value ? '覆蓋同名組合' : activePortfolio.value ? '另存新組合' : '存成我的組合'))

const divSeries = computed(() =>
  (orderedRows.value).map(s => ({
    symbol: s.symbol, name: s.name, color: colorOf(s.symbol),
    by_year: s.dividends.by_year, pays: s.dividends.pays_dividend,
  })))

function tfStart(asof, tf) {
  const d = new Date(`${asof}T00:00:00Z`)
  if (tf === 'YTD') return `${d.getUTCFullYear()}-01-01`
  const months = { '6M': 6, '1Y': 12, '3Y': 36, '5Y': 60 }[tf] || 12
  d.setUTCMonth(d.getUTCMonth() - months)
  return d.toISOString().slice(0, 10)
}

// 依選定區間把每檔重新以 100 起算；上市較晚的從它的第一天起算
const trend = computed(() => {
  if (!result.value) return []
  const start = tfStart(result.value.asof, timeframe.value)
  const slack = new Date(`${start}T00:00:00Z`)
  slack.setUTCDate(slack.getUTCDate() + 10)
  const lateAfter = slack.toISOString().slice(0, 10)
  return orderedRows.value.map(s => {
    const { dates, adj } = s.series
    const i0 = dates.findIndex(d => d >= start)
    if (i0 < 0 || adj.length - i0 < 2) return { symbol: s.symbol, name: s.name, color: colorOf(s.symbol), points: [], ret: null, late: false }
    const base = adj[i0]
    const points = []
    for (let i = i0; i < dates.length; i++) points.push({ time: dates[i], value: Number(((adj[i] / base) * 100).toFixed(2)) })
    return {
      symbol: s.symbol, name: s.name, color: colorOf(s.symbol), points,
      ret: points[points.length - 1].value / 100 - 1,
      late: dates[i0] > lateAfter,
    }
  })
})

const legend = computed(() => trend.value.map(t => ({ symbol: t.symbol, name: t.name, color: t.color, ret: t.ret, late: t.late })))

// ── 走勢圖圖例開關 ──────────────────────────────────────────────────────────
const isHidden = symbol => hiddenSymbols.value.includes(symbol)
const visibleSymbols = computed(() => legend.value.filter(l => !isHidden(l.symbol)).map(l => l.symbol))
const legendDotStyle = l => (isHidden(l.symbol)
  ? { background: 'transparent', border: `2px solid ${l.color}`, boxSizing: 'border-box' }
  : { background: l.color })

function toggleSeries(symbol) {
  hiddenSymbols.value = isHidden(symbol)
    ? hiddenSymbols.value.filter(s => s !== symbol)
    : [...hiddenSymbols.value, symbol]
}

// 連點兩下：只看這一條；已經是「只看這一條」時再連點兩下，回到全部顯示
function soloSeries(symbol) {
  const all = legend.value.map(l => l.symbol)
  const alreadySolo = visibleSymbols.value.length === 1 && visibleSymbols.value[0] === symbol
  hiddenSymbols.value = alreadySolo ? [] : all.filter(s => s !== symbol)
}

const showAllSeries = () => { hiddenSymbols.value = [] }
const hideAllSeries = () => { hiddenSymbols.value = legend.value.map(l => l.symbol) }

function applySeriesVisibility() {
  if (!chartInstance) return
  seriesBySymbol.forEach((series, symbol) => series.applyOptions({ visible: !isHidden(symbol) }))
  // 關掉高點很高的那條線之後，Y 軸要重新貼合剩下的線
  chartInstance.priceScale('right').applyOptions({ autoScale: true })
}
watch(hiddenSymbols, applySeriesVisibility)

function resetZoom() {
  if (!chartInstance) return
  chartInstance.timeScale().fitContent()
  chartInstance.priceScale('right').applyOptions({ autoScale: true })
}

// ── 圖表 ────────────────────────────────────────────────────────────────────
function destroyChart() {
  seriesBySymbol = new Map()
  if (chartInstance) {
    chartInstance.remove()
    chartInstance = null
  }
}

function renderChart() {
  if (!chartHost.value) return
  destroyChart()
  const chart = createChart(chartHost.value, {
    width: chartHost.value.clientWidth,
    height: 360,
    layout: { background: { color: 'transparent' }, textColor: theme.textSoft },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
  })
  // 基準線 100 用獨立的一條虛線：不跟著任何一檔，哪條被關掉都還在
  const withPoints = trend.value.filter(t => t.points.length)
  if (withPoints.length) {
    const first = withPoints.map(t => t.points[0].time).sort()[0]
    const last = withPoints.map(t => t.points[t.points.length - 1].time).sort().at(-1)
    const base = chart.addLineSeries({
      color: theme.muted, lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false,
      crosshairMarkerVisible: false, priceFormat: { type: 'custom', formatter: v => v.toFixed(1) },
    })
    base.setData([{ time: first, value: 100 }, { time: last, value: 100 }])
  }
  trend.value.forEach(t => {
    if (!t.points.length) return
    const series = chart.addLineSeries({
      color: t.color, lineWidth: 2, title: t.symbol, visible: !isHidden(t.symbol),
      priceFormat: { type: 'custom', formatter: v => v.toFixed(1) },
    })
    series.setData(t.points)
    seriesBySymbol.set(t.symbol, series)
  })
  chart.timeScale().fitContent()
  chartInstance = chart
}

watch([() => result.value, timeframe], async () => {
  if (!result.value) { destroyChart(); return }
  await nextTick()
  renderChart()
})

// 只改寬度不夠：lightweight-charts 會沿用舊的 barSpacing，資料被擠在右側一小塊，
// 加上 fitContent 才會重新鋪滿（實測視窗由窄變寬時曲線只佔右邊約 15%）。
function handleResize() {
  if (!chartInstance || !chartHost.value) return
  chartInstance.applyOptions({ width: chartHost.value.clientWidth })
  chartInstance.timeScale().fitContent()
}

// ── 格式化 ──────────────────────────────────────────────────────────────────
const pct = (x, d = 1, sign = false) => (x == null ? '—' : `${sign && x > 0 ? '+' : ''}${(x * 100).toFixed(d)}%`)
const num = (x, d = 2) => (x == null ? '—' : Number(x).toFixed(d))
const score = x => (x == null ? '—' : Math.round(x))
const cls = x => (x == null || x === 0 ? '' : x > 0 ? 'up' : 'down')
const md = iso => (iso ? iso.slice(5).replace('-', '/') : '')
// 最新收盤 ÷ 區間最低 − 1（兩者都是已處理分割、未含息的看盤價，口徑一致）
function fromLow(row) {
  const last = row.metrics?.last_close
  const low = row.event?.low
  return last != null && low ? last / low - 1 : null
}
// 「無除息」旁的小字：區間外最近的前一次／下一次除息日，讓人看得出為什麼這段期間沒有
function exNeighbors(row) {
  const ev = result.value?.event
  const list = row.dividends?.events || []
  if (!ev || !list.length) return ''
  const before = [...list].reverse().find(e => e.date < ev.start)
  const after = list.find(e => e.date > ev.end)
  const show = iso => (iso.slice(0, 4) === ev.start.slice(0, 4) ? md(iso) : iso.replace(/-/g, '/'))
  const parts = []
  if (before) parts.push(`前次 ${show(before.date)}`)
  if (after) parts.push(`下次 ${show(after.date)}`)
  return parts.join('・')
}
function price(x) {
  if (x == null) return '—'
  const big = x >= 1000
  return Number(x).toLocaleString('en-US', { minimumFractionDigits: big ? 0 : 2, maximumFractionDigits: big ? 0 : 2 })
}
function scoreStyle(x) {
  if (x == null) return {}
  return { background: `linear-gradient(90deg, rgba(59,130,246,0.28) ${Math.max(0, Math.min(100, x))}%, transparent ${Math.max(0, Math.min(100, x))}%)` }
}
function fillDetail(f) {
  if (!f.n) return '—'
  const parts = [`${f.filled} 次填息`]
  if (f.failed) parts.push(`${f.failed} 次未填`)
  if (f.pending) parts.push(`${f.pending} 次未結案`)
  return parts.join('、')
}
const AXES = ['return', 'defense', 'sharpe', 'yield', 'fill']
const axisCount = row => AXES.filter(k => row.scores[k] != null).length
function axisTip(row, key) {
  if (row.scores[key] != null) return ''
  if (key === 'yield') return row.dividends.pays_dividend ? '殖利率資料不足' : '不配息，此項不適用'
  if (key === 'fill') return row.dividends.pays_dividend ? '沒有已結案的除息，無法計算' : '不配息，此項不適用'
  if (key === 'defense' || key === 'sharpe') return '上市交易日不足，無法計算'
  return '資料不足'
}

function exportCsv() {
  if (!result.value) return
  const ev = result.value.event
  const cols = ['代號', '名稱', '分類', '總分', '報酬分', '抗跌分', '夏普分', '殖利率分', '填息分', '近1年報酬%', '3年年化%', '年化波動%',
    '夏普', '最大回撤%', '近12月殖利率%', '近12月配息(元)', '填息成功率%', '平均填息天數',
    '急跌區間起', '急跌區間迄', '區間最低', '區間最高', '其後最低', '回落%', '反彈高點', '反彈幅度%', '目前價位', '目前價距低點%', '區間內除息(元)']
  const p = (x, d = 2) => (x == null ? '' : (x * 100).toFixed(d))
  const rows = orderedRows.value.map(s => [
    s.symbol, s.name, categoryLabel(s.category), s.scores.total ?? '', s.scores.return ?? '', s.scores.defense ?? '', s.scores.sharpe ?? '',
    s.scores.yield ?? '', s.scores.fill ?? '', p(s.metrics.return_1y), p(s.metrics.cagr_3y), p(s.metrics.ann_vol),
    s.metrics.sharpe == null ? '' : s.metrics.sharpe.toFixed(2), p(s.metrics.mdd), p(s.dividends.yield_ttm), s.dividends.ttm_amount ?? '',
    p(s.fill.success_rate, 0), s.fill.avg_days == null ? '' : s.fill.avg_days.toFixed(1),
    ev?.start ?? '', ev?.end ?? '', s.event ? (s.event.window_low ?? s.event.low) : '', s.event?.high ?? '', s.event?.low ?? '', p(s.event?.drawdown),
    s.event?.rebound_high ?? '', p(s.event?.rebound_pct), s.metrics.last_close ?? '', p(fromLow(s)), s.event?.dividends_in_window ?? '',
  ])
  downloadCsv(timestampedFilename('etf-compare'), cols, rows)
}

// ── 生命週期 ────────────────────────────────────────────────────────────────
function applyCatalog(data) {
  catalog.value = data
  presets.value = data.presets || []
}

function readCatalogCache() {
  try {
    const raw = JSON.parse(localStorage.getItem(CATALOG_KEY) || 'null')
    if (raw && typeof raw.at === 'number' && raw.data?.etfs?.length) return raw
  } catch { /* 無痕模式或資料壞了：當作沒有快取 */ }
  return null
}

// 標的清單存在瀏覽器 12 小時：重新整理不必再問後端；後端暫時不通時，舊清單比沒有好
async function loadCatalog() {
  const cached = readCatalogCache()
  if (cached && Date.now() - cached.at < CATALOG_TTL_MS) {
    applyCatalog(cached.data)
    return
  }
  try {
    const resp = await fetch(`${API_BASE}/api/v1/etf-compare/catalog`)
    const payload = await resp.json().catch(() => ({}))
    if (!resp.ok || !payload?.success) throw new Error(payload?.detail || `HTTP ${resp.status}`)
    applyCatalog(payload.data)
    try { localStorage.setItem(CATALOG_KEY, JSON.stringify({ at: Date.now(), data: payload.data })) } catch { /* 存不進去不影響功能 */ }
  } catch (e) {
    if (cached) { applyCatalog(cached.data); return }
    catalogError.value = `ETF 清單暫時無法載入（${e?.message || '未知錯誤'}），仍可直接輸入代碼加入。`
  }
}

function restoreSelection() {
  const fromUrl = typeof route.query.symbols === 'string' ? route.query.symbols : ''
  let symbols = fromUrl.split(',').map(s => s.trim().toUpperCase()).filter(s => SYMBOL_RE.test(s))
  if (!symbols.length) {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      if (Array.isArray(raw)) symbols = raw.map(String).filter(s => SYMBOL_RE.test(s))
    } catch { symbols = [] }
  }
  symbols = [...new Set(symbols)]
  if (symbols.length) {
    setSelection(symbols)
    load()
  }
}

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  document.addEventListener('click', onDocClick)
  portfolios.value = readPortfolios()
  // 重新整理後仍記得「目前是哪一組」，刪減後才找得到「更新這個組合」
  try {
    const keep = portfolios.value.find(p => p.id === localStorage.getItem(ACTIVE_PF_KEY))
    if (keep) { activePortfolioId.value = keep.id; portfolioName.value = keep.name }
  } catch { /* 無痕模式：不記得也不影響 */ }
  await loadCatalog()
  restoreSelection()
})
watch(activePortfolioId, id => {
  try {
    if (id) localStorage.setItem(ACTIVE_PF_KEY, id)
    else localStorage.removeItem(ACTIVE_PF_KEY)
  } catch { /* 同上 */ }
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', onDocClick)
  clearTimeout(searchTimer)
  clearTimeout(msgTimer)
  clearRetry()
  loadSeq++
  searchSeq++
  destroyChart()
})
</script>

<style scoped>
.etf-page { display: flex; flex-direction: column; gap: 16px; }
.muted { color: var(--text-muted); }
.small { font-size: 0.78rem; margin: 0; line-height: 1.55; }
.warn-text { color: var(--chart-warn, #f59e0b); font-size: 0.82rem; margin: 0; }
.error-text { color: var(--color-up); font-size: 0.84rem; margin: 0; }
.dirty { color: var(--accent-blue); font-weight: 600; }

.pick-card { display: flex; flex-direction: column; gap: 10px; }
.preset-row, .cat-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.row-label { font-size: 0.76rem; font-weight: 700; color: var(--text-muted); min-width: 4.5em; }
.chip-btn, .cat-btn, .tf-btn {
  padding: 5px 12px; border-radius: 999px; border: 1px solid var(--border-color);
  background: var(--bg-secondary); color: var(--text-secondary); font-size: 0.8rem; cursor: pointer;
}
.chip-btn:hover, .cat-btn:hover, .tf-btn:hover { color: var(--text-primary); border-color: var(--accent-blue); }
.chip-btn.ghost { background: transparent; }
.chip-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.cat-btn.active, .tf-btn.active { background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; font-weight: 600; }

.add-row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.search-shell { position: relative; flex: 1; min-width: 240px; }
.inp { padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); width: 100%; box-sizing: border-box; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 0.78rem; color: var(--text-secondary); }
.search-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 20;
  background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 10px;
  list-style: none; margin: 0; padding: 4px; max-height: 300px; overflow-y: auto;
}
.search-dropdown li { display: flex; align-items: baseline; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.search-dropdown li:hover, .search-dropdown li:focus { background: var(--bg-well, rgba(148, 163, 184, 0.1)); outline: none; }
.dd-name { flex: 1; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-tag { font-size: 0.7rem; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 999px; padding: 1px 8px; white-space: nowrap; }

.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: var(--bg-well, rgba(148, 163, 184, 0.1)); border: 1px solid var(--border-color); font-size: 0.82rem; }
.chip-x { border: none; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 0.75rem; }
.chip-x:hover { color: var(--color-up); }
.chip[draggable='true'] { cursor: grab; }
.chip.dragging { opacity: 0.45; }
.chip.drag-over { border-color: var(--accent-blue); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25); }
.chip-mv { border: none; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 0.62rem; padding: 2px 2px; }
.chip-mv:hover:not(:disabled) { color: var(--accent-blue); }
.chip-mv:disabled { opacity: 0.25; cursor: default; }

.portfolio-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.pf-chip { display: inline-flex; align-items: center; border: 1px solid var(--border-color); border-radius: 999px; background: var(--bg-secondary); overflow: hidden; }
.pf-load { border: none; background: transparent; color: var(--text-secondary); font-size: 0.8rem; cursor: pointer; padding: 5px 4px 5px 12px; }
.pf-load:hover { color: var(--text-primary); }
.pf-load small { color: var(--text-muted); font-size: 0.7rem; }
.pf-del { border: none; background: transparent; color: var(--text-muted); font-size: 0.7rem; cursor: pointer; padding: 5px 10px 5px 4px; }
.pf-del:hover { color: var(--color-up); }
.save-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.save-row .inp { width: auto; flex: 1; min-width: 200px; max-width: 320px; }
.notice-text { color: var(--accent-blue); font-size: 0.82rem; margin: 0; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; margin-right: 6px; }
.chip .dot { margin-right: 0; }

.state-box { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 32px 16px; color: var(--text-muted); font-size: 0.9rem; }
.state-box.empty { border: 1px dashed var(--border-color); border-radius: var(--radius); }
.asof { margin: 0; }

.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.section-head h2 { margin: 0; font-size: 1.05rem; }
.health-intro { margin: 0 0 12px; }
.btn.xs { padding: 5px 12px; font-size: 0.78rem; }
.tf-tabs { display: flex; gap: 6px; flex-wrap: wrap; }

.radar-grid { display: grid; grid-template-columns: minmax(280px, 380px) minmax(0, 1fr); gap: 20px; align-items: start; }
.table-scroll { overflow-x: auto; display: flex; flex-direction: column; gap: 8px; }
.table-scroll table { min-width: 520px; }
.rank { display: inline-block; width: 1.4em; color: var(--text-muted); font-size: 0.75rem; }
.nm { color: var(--text-muted); font-weight: 400; }
.total { font-weight: 700; white-space: nowrap; }
.axes-n { margin-left: 4px; font-size: 0.68rem; font-weight: 500; color: var(--text-muted); }
.score { display: inline-block; min-width: 3.2em; padding: 2px 8px; border-radius: 6px; text-align: center; }
.mini-badge { display: inline-block; margin-left: 6px; padding: 1px 7px; border-radius: 999px; font-size: 0.68rem; font-weight: 600; background: rgba(245, 158, 11, 0.14); color: var(--chart-warn, #f59e0b); border: 1px solid rgba(245, 158, 11, 0.35); white-space: nowrap; }

.legend-row { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 0.84rem; margin-bottom: 8px; }
.legend-item { display: inline-flex; align-items: center; gap: 4px; }
.legend-btn { border: 1px solid transparent; background: transparent; color: inherit; font: inherit; padding: 2px 8px; border-radius: 999px; cursor: pointer; }
.legend-btn:hover { border-color: var(--border-color); background: var(--bg-well, rgba(148, 163, 184, 0.1)); }
.legend-btn:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 1px; }
.legend-btn.off { opacity: 0.45; text-decoration: line-through; }
.legend-btn .dot { margin-right: 4px; }
.legend-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.legend-tools .chip-btn { padding: 3px 10px; font-size: 0.75rem; }
.na-tag { color: var(--text-muted); font-size: 0.8rem; }
.no-rebound .na-tag { margin-right: 6px; }
.chart-host { width: 100%; height: 360px; margin-bottom: 14px; }

.fill-detail { font-size: 0.78rem; color: var(--text-muted); }
.event-bar { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.event-desc { margin: 0; font-size: 0.88rem; }
.event-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px; }
.event-wrap table { min-width: 1000px; }
.auto-set { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 14px; margin-bottom: 12px; padding: 10px 12px; border: 1px dashed var(--border-color); border-radius: var(--radius-sm); }
.auto-set .inp { width: auto; min-width: 150px; padding: 6px 8px; }
.auto-set .row-label { align-self: center; }
.quick-range { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.quick-range .chip-btn { padding: 3px 10px; font-size: 0.75rem; }
.dt { color: var(--text-muted); font-size: 0.72rem; margin-left: 2px; }
.row-chart-btn { margin-left: 8px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border-color); background: transparent; color: var(--accent-blue); font-size: 0.72rem; cursor: pointer; white-space: nowrap; }
.row-chart-btn:hover { border-color: var(--accent-blue); }
.row-chart-btn:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 1px; }

/* 個股走勢：放在急跌表下面，淡淡的邊框與表格區隔 */
.event-chart-panel { margin: 16px 0 12px; padding: 14px; display: flex; flex-direction: column; gap: 10px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--bg-well, rgba(148, 163, 184, 0.04)); min-width: 0; }
.chart-panel-head { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; }
.chart-panel-head h3 { margin: 0; font-size: 0.98rem; }
.chart-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chart-chips .chip-btn { display: inline-flex; align-items: center; gap: 2px; padding: 3px 10px; font-size: 0.78rem; }
.chip-btn.active { background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; font-weight: 600; }
.chip-btn.active .nm { color: rgba(255, 255, 255, 0.8); }

.radar-col { display: flex; flex-direction: column; gap: 8px; align-items: center; }
.radar-empty { margin: 0; font-size: 0.82rem; color: var(--text-muted); text-align: center; }
.radar-tools { margin-bottom: 0; }
.radar-toggle { border: 1px solid transparent; background: transparent; color: inherit; font: inherit; padding: 2px 8px; border-radius: 999px; cursor: pointer; text-align: left; }
.radar-toggle:hover { border-color: var(--border-color); background: var(--bg-well, rgba(148, 163, 184, 0.1)); }
.radar-toggle:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: 1px; }
tr.radar-off .radar-toggle { opacity: 0.5; text-decoration: line-through; }
tr.radar-off td:not(:first-child) { opacity: 0.5; }

.pf-state { margin: 0; font-size: 0.84rem; }
.pf-state .dirty, .pf-state .muted { margin-left: 8px; }
.pf-chip.active { border-color: var(--accent-blue); }
.pf-chip.modified { border-style: dashed; }
.pf-unsaved { margin-left: 6px; padding: 0 6px; border-radius: 999px; font-size: 0.66rem; font-weight: 600; background: rgba(59, 130, 246, 0.16); color: var(--accent-blue); }
.pf-load small.pf-unsaved { color: var(--accent-blue); }

.holdings-card .holdings-note { margin: 0; font-size: 0.86rem; line-height: 1.7; color: var(--text-secondary); }
.method summary { cursor: pointer; font-weight: 600; }
.method ul { margin: 10px 0 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 6px; font-size: 0.82rem; line-height: 1.65; color: var(--text-secondary); }

@media (max-width: 860px) {
  .radar-grid { grid-template-columns: 1fr; }
  .row-label { min-width: 0; width: 100%; }
}
</style>
