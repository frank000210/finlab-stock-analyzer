<script setup>
// 板式熱交換器與熱管理領域 — 專利分析示範報告
// 資料為根據業界公開資訊製作之示範，非真實資料庫爬取結果，供專業人士審查報告格式與分析框架

const meta = {
  title: '板式熱交換器與熱管理領域專利分析報告',
  domain: '板式熱交換器 (PHE) / 熱管理系統 (TMS)',
  dateRange: '2014–2024',
  corpus: 3247,
  databases: 'USPTO · EPO · WIPO · JPO · CNIPA · TIPO',
  cutoff: '2024-09-30',
  version: 'v0.1 示範稿',
  reviewer: '待專利分析師審查',
}

const trendData = [
  { year: 2014, count: 210 }, { year: 2015, count: 218 },
  { year: 2016, count: 225 }, { year: 2017, count: 231 },
  { year: 2018, count: 238 }, { year: 2019, count: 267 },
  { year: 2020, count: 298 }, { year: 2021, count: 356 },
  { year: 2022, count: 412 }, { year: 2023, count: 468 },
  { year: 2024, count: 324, partial: true },
]
const trendMax = Math.max(...trendData.map(d => d.count))

const countries = [
  { name: '中國', pct: 27, count: 878, flag: '🇨🇳', trend: '+↑' },
  { name: '美國', pct: 24, count: 779, flag: '🇺🇸', trend: '→' },
  { name: '日本', pct: 17, count: 551, flag: '🇯🇵', trend: '→' },
  { name: '德國', pct: 13, count: 422, flag: '🇩🇪', trend: '↓' },
  { name: '韓國', pct: 9,  count: 292, flag: '🇰🇷', trend: '↑' },
  { name: '其他', pct: 10, count: 325, flag: '🌐', trend: '→' },
]

const applicants = [
  { name: 'Alfa Laval',         count: 312, country: '🇸🇪', focus: '釺焊板式 / 工業用' },
  { name: 'Danfoss',            count: 247, country: '🇩🇰', focus: '冷媒系統 / HVAC' },
  { name: 'Parker Hannifin',    count: 198, country: '🇺🇸', focus: '航太 / 工業熱管理' },
  { name: 'GEA Group',          count: 176, country: '🇩🇪', focus: '食品工業 / 大型換熱' },
  { name: 'Samsung SDI',        count: 156, country: '🇰🇷', focus: 'EV 電池熱管理' },
  { name: 'SWEP International', count: 143, country: '🇸🇪', focus: '釺焊板式 (BPHE)' },
  { name: 'Modine Mfg.',        count: 128, country: '🇺🇸', focus: '汽車 / EV 冷卻' },
  { name: 'Kelvion Holdings',   count: 119, country: '🇩🇪', focus: '工業 / 數據中心' },
  { name: 'BorgWarner',         count: 108, country: '🇺🇸', focus: '汽車動力熱管理' },
  { name: 'Hanon Systems',      count: 97,  country: '🇰🇷', focus: 'EV 熱泵 / 空調' },
]
const appMax = applicants[0].count

const ipcData = [
  { code: 'F28D', desc: '熱交換裝置（板型/管型/整體構型）', pct: 42, tier3: 'F28D' },
  { code: 'F28F', desc: '熱交換裝置細部元件（板片/流道/材料）', pct: 28, tier3: 'F28F' },
  { code: 'H01M', desc: '電化學程序（電池熱管理）',              pct: 14, tier3: 'H01M' },
  { code: 'H05K', desc: '印刷電路基板（電子設備散熱冷卻）',     pct: 8,  tier3: 'H05K' },
  { code: 'F25B', desc: '冷凍/製冷裝置（冷媒換熱迴路）',        pct: 8,  tier3: 'F25B' },
]

// Technology-Function Matrix: rows=技術手段, cols=解決功效
// Value: patent count estimate; 0 = white space
const matrixTechs = ['板片幾何設計', '釺焊工藝', '冷媒流路設計', '材料技術', '系統整合控制']
const matrixFuncs = ['傳熱效率提升', '壓降降低', '重量輕量化', '製造成本降低', '耐久性提升', '熱均勻性']
const matrixData = [
  [210, 138, 45, 67,  88,  124],
  [156,  42, 18, 98, 112,   36],
  [178,  89,  0, 45,  67,  201],
  [ 67,  23,  0, 12,  88,   34],
  [ 45,  12,  0, 78,  34,  188],
]

function matrixColor(val) {
  if (val === 0) return 'cell-blank'
  if (val < 30)  return 'cell-low'
  if (val < 80)  return 'cell-mid'
  if (val < 150) return 'cell-high'
  return 'cell-hot'
}

const claimsStats = [
  { label: 'comprising（開放式）', pct: 71 },
  { label: 'consisting essentially of', pct: 18 },
  { label: 'consisting of（封閉式）', pct: 11 },
]

const riskPatents = [
  { no: 'US 10,677,534 B2', holder: 'Alfa Laval', title: 'Brazed plate heat exchanger with turbulence promoters', risk: '高', ipc: 'F28D 9/00', note: 'comprising，8 獨立項，族群 32 件，覆蓋主流板式設計' },
  { no: 'EP 3,425,321 B1',  holder: 'Danfoss',    title: 'Refrigerant distributor for plate heat exchangers',     risk: '高', ipc: 'F28F 9/02', note: 'comprising，冷媒分配領域核心布局，含台灣同族' },
  { no: 'US 11,268,773 B2', holder: 'Samsung SDI', title: 'Battery pack with plate-type cooling system',           risk: '中', ipc: 'H01M 10/613', note: '僅限 EV 電池應用，若非 EV 客戶則風險較低' },
]

const findings = [
  { no: '01', level: 'critical', text: 'EV 電池熱管理（H01M）為最快成長子領域，2019–2023 年 CAGR 達 38%，已成為各大廠重點佈局戰場。' },
  { no: '02', level: 'critical', text: '中國申請人自 2021 年起在年度申請量首次超越美國（各佔 29% vs 24%），顯示供應鏈本土化壓力加劇。' },
  { no: '03', level: 'high',     text: 'Alfa Laval 在釺焊板式熱交換器核心技術（F28F 21/08）的佔比達 31%，構成進入壁壘；建議優先進行 FTO 分析。' },
  { no: '04', level: 'high',     text: '資料中心液冷（H05K 7/20）近兩年申請量成長 67%，技術佈局仍在快速形成期，存在先行佈局機會。' },
  { no: '05', level: 'medium',   text: '技術功效矩陣顯示「壓降降低 × 材料技術」、「重量輕量化 × 冷媒流路 / 材料 / 系統整合」為三個顯著空白區，可評估申請可行性。' },
]

const actions = [
  { timing: '立即（0–1 個月）', items: ['對 US 10,677,534 B2 及 EP 3,425,321 B1 進行完整 FTO 分析（Claim Chart 比對）', '確認委託方現有產品是否落入 Alfa Laval 釺焊工藝獨立項'] },
  { timing: '3 個月內', items: ['在 F28D 9/00 次類針對壓降降低技術申請 2–3 件防禦性專利', '建立 EV 熱管理（H01M 10/613）的持續監控機制，重點追蹤三星、BorgWarner、Hanon'] },
  { timing: '6 個月內', items: ['評估資料中心液冷（H05K 7/20）的技術佈局可行性，委外評估報告', '針對「材料技術 × 壓降降低」空白區進行先行技術調查，確認是否無先前技術阻礙'] },
]
</script>

<template>
  <div class="page report-page">

    <!-- HEADER -->
    <div class="report-header">
      <div class="header-badges">
        <span class="rbadge draft">示範報告</span>
        <span class="rbadge review">待審查</span>
      </div>
      <h1 class="report-title">{{ meta.title }}</h1>
      <p class="report-subtitle">IPC 檢索範圍：F28D · F28F · H01M · H05K · F25B　｜　分析期間：{{ meta.dateRange }}</p>
      <div class="report-meta-row">
        <span>總件數：<strong>{{ meta.corpus.toLocaleString() }} 件</strong></span>
        <span>資料庫：{{ meta.databases }}</span>
        <span>截止日：{{ meta.cutoff }}</span>
        <span>版本：{{ meta.version }}</span>
      </div>
      <div class="report-notice">
        本報告為依據業界公開資訊製作之<strong>示範版本</strong>，數據僅供說明分析架構之用，非真實專利資料庫爬取結果。請專利分析師審查報告架構、分析格式與品質標準是否符合實務需求。
      </div>
    </div>

    <!-- EXECUTIVE SUMMARY -->
    <section class="report-section">
      <div class="sec-label">執行摘要</div>
      <h2 class="sec-title">Executive Summary</h2>
      <p class="sec-desc">供決策者在不閱讀全文的情況下做出初步判斷。</p>

      <div class="summary-grid">
        <div class="summary-stat">
          <div class="stat-num">3,247</div>
          <div class="stat-label">有效專利件數</div>
          <div class="stat-sub">11年，6 國資料庫</div>
        </div>
        <div class="summary-stat">
          <div class="stat-num">+22%</div>
          <div class="stat-label">年均成長率</div>
          <div class="stat-sub">2019–2023 CAGR</div>
        </div>
        <div class="summary-stat highlight-stat">
          <div class="stat-num">+38%</div>
          <div class="stat-label">EV 熱管理子領域 CAGR</div>
          <div class="stat-sub">H01M 10/613 — 最快成長</div>
        </div>
        <div class="summary-stat warn-stat">
          <div class="stat-num">2</div>
          <div class="stat-label">高風險專利需 FTO</div>
          <div class="stat-sub">Alfa Laval / Danfoss 核心布局</div>
        </div>
      </div>

      <div class="findings-list">
        <div v-for="f in findings" :key="f.no" class="finding-item" :class="f.level">
          <span class="finding-no">{{ f.no }}</span>
          <p>{{ f.text }}</p>
        </div>
      </div>
    </section>

    <!-- TREND -->
    <section class="report-section">
      <div class="sec-label">管理面分析 — Ch.4</div>
      <h2 class="sec-title">專利申請年度趨勢</h2>
      <p class="sec-desc chart-analysis">
        <strong>成長期判斷：</strong>2018 年前呈平穩成長（年增約 3%）；2019 年起受 EV 電動化趨勢與資料中心液冷市場帶動，申請量加速增長，2019–2023 年 CAGR 達 22%。技術生命週期判斷：<strong>快速成長期</strong>，尚未進入成熟期，仍具佈局機會窗口。
      </p>

      <div class="bar-chart">
        <div v-for="d in trendData" :key="d.year" class="bar-group">
          <div class="bar-wrap">
            <div
              class="bar"
              :class="{ 'bar-partial': d.partial, 'bar-highlight': d.count >= 380 }"
              :style="{ height: (d.count / trendMax * 160) + 'px' }"
            >
              <span class="bar-val">{{ d.count }}</span>
            </div>
          </div>
          <div class="bar-year">{{ d.year }}{{ d.partial ? '*' : '' }}</div>
        </div>
      </div>
      <p class="chart-note">* 2024 年資料截至 2024 Q3（約估全年 432 件），因 18 個月公開延遲，實際申請量可能高於顯示值。</p>
    </section>

    <!-- COUNTRY -->
    <section class="report-section">
      <div class="sec-label">管理面分析 — Ch.5</div>
      <h2 class="sec-title">專利權人國別分析</h2>
      <p class="sec-desc chart-analysis">
        <strong>集中度判斷：高度集中。</strong>中美日三國合計佔 68%，其中中國自 2021 年首次成為年度最大申請國（佔 29%），反映中國廠商在換熱技術的積極追趕，也顯示供應鏈本土化壓力持續加深。德國雖排名第四，但掌握 Alfa Laval（瑞典）、GEA、Kelvion 等核心技術廠商，技術實力與申請量不成比例，需特別關注其專利品質（大族群）。
      </p>
      <div class="country-bars">
        <div v-for="c in countries" :key="c.name" class="country-row">
          <div class="country-label">
            <span class="flag">{{ c.flag }}</span>
            <span class="cname">{{ c.name }}</span>
          </div>
          <div class="country-bar-wrap">
            <div class="country-bar" :style="{ width: c.pct + '%' }"></div>
          </div>
          <div class="country-stats">
            <span class="cpct">{{ c.pct }}%</span>
            <span class="ccount">({{ c.count.toLocaleString() }})</span>
            <span class="ctrend" :class="c.trend.includes('↑') ? 'up' : c.trend.includes('↓') ? 'down' : ''">{{ c.trend }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- TOP APPLICANTS -->
    <section class="report-section">
      <div class="sec-label">管理面分析 — Ch.5</div>
      <h2 class="sec-title">Top 10 主要專利申請人</h2>
      <p class="sec-desc chart-analysis">
        <strong>集中度判斷：中度集中。</strong>前五大申請人合計佔 34%，市場並無絕對壟斷者，但 Alfa Laval 在釺焊板式熱交換器核心工藝的佔比（約 31%）遠超過整體市佔率，具顯著技術壁壘。近 3 年 Samsung SDI、BorgWarner、Hanon Systems 等 EV 供應鏈廠商快速崛起，代表熱管理技術競爭正從傳統工業廠商向汽車電子廠商轉移。
      </p>
      <div class="applicant-list">
        <div v-for="(a, i) in applicants" :key="a.name" class="applicant-row">
          <div class="app-rank">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="app-info">
            <span class="app-flag">{{ a.country }}</span>
            <span class="app-name">{{ a.name }}</span>
            <span class="app-focus">{{ a.focus }}</span>
          </div>
          <div class="app-bar-wrap">
            <div class="app-bar" :style="{ width: (a.count / appMax * 100) + '%' }"></div>
          </div>
          <div class="app-count">{{ a.count }}</div>
        </div>
      </div>
    </section>

    <!-- IPC -->
    <section class="report-section">
      <div class="sec-label">技術面分析 — Ch.6</div>
      <h2 class="sec-title">IPC 技術領域分析（三階）</h2>
      <p class="sec-desc chart-analysis">
        <strong>集中度判斷：高度集中。</strong>F28D + F28F 合計佔 70%，顯示核心專利仍集中於換熱裝置本體設計。H01M（14%）代表 EV 電池熱管理的跨界佈局，近 3 年佔比從 8% 升至 14%，是最值得關注的成長向量。H05K（電子散熱）與 F25B（冷媒系統）相對分散，仍具佈局空間。
      </p>
      <div class="ipc-bars">
        <div v-for="d in ipcData" :key="d.code" class="ipc-row">
          <div class="ipc-code">{{ d.code }}</div>
          <div class="ipc-desc">{{ d.desc }}</div>
          <div class="ipc-bar-wrap">
            <div class="ipc-bar" :style="{ width: d.pct + '%' }"></div>
          </div>
          <div class="ipc-pct">{{ d.pct }}%</div>
        </div>
      </div>
    </section>

    <!-- TECH-FUNCTION MATRIX -->
    <section class="report-section">
      <div class="sec-label">技術面分析 — Ch.7</div>
      <h2 class="sec-title">技術功效矩陣</h2>
      <p class="sec-desc chart-analysis">
        <strong>熱點：</strong>「板片幾何設計 × 傳熱效率」（210 件）、「冷媒流路 × 熱均勻性」（201 件）為最密集佈局區，侵權風險最高，進入需謹慎。
        <strong>機會空白：</strong>「冷媒流路 × 重量輕量化」、「材料技術 × 重量輕量化 / 壓降降低」及「系統整合 × 重量輕量化」顯示零件數空白，建議確認是否為技術盲點或技術上不可行的組合，若可行則具佈局機會。
      </p>
      <div class="matrix-wrap">
        <table class="matrix-table">
          <thead>
            <tr>
              <th class="matrix-corner">技術手段 ╲ 功效</th>
              <th v-for="f in matrixFuncs" :key="f">{{ f }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(tech, ti) in matrixTechs" :key="tech">
              <td class="matrix-tech">{{ tech }}</td>
              <td
                v-for="(val, fi) in matrixData[ti]" :key="fi"
                :class="['matrix-cell', matrixColor(val)]"
              >
                <span v-if="val > 0">{{ val }}</span>
                <span v-else class="blank-mark">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="matrix-legend">
        <span class="legend-item cell-hot">201+ 高度佈局</span>
        <span class="legend-item cell-high">80–200 中高</span>
        <span class="legend-item cell-mid">30–79 中</span>
        <span class="legend-item cell-low">&lt;30 低密度</span>
        <span class="legend-item cell-blank">— 空白（機會區）</span>
      </div>
    </section>

    <!-- CLAIMS ANALYSIS -->
    <section class="report-section">
      <div class="sec-label">技術面分析 — Ch.8</div>
      <h2 class="sec-title">申請專利範圍（Claims）結構分析</h2>
      <p class="sec-desc chart-analysis">
        <strong>保護範圍廣度評估：</strong>comprising（開放式）佔 71%，意味多數專利採開放式解釋範圍，即系爭產品只要涵蓋全部技術特徵即構成侵權，即使具有額外元件亦然，侵權判斷門檻相對偏低。平均 Claim 數 16.4 件且平均獨立項 2.8 件，均高於換熱設備業界均值（14.2 件 / 2.1 件），顯示主要申請人對保護範圍佈局相當積極。
      </p>
      <div class="claims-stats">
        <div class="claim-row">
          <span class="claim-label">平均 Claims 數</span>
          <span class="claim-val accent">16.4 件</span>
          <span class="claim-note">業界均值 14.2 件（高出 15%）</span>
        </div>
        <div class="claim-row">
          <span class="claim-label">平均獨立項數</span>
          <span class="claim-val accent">2.8 件</span>
          <span class="claim-note">業界均值 2.1 件（高出 33%）</span>
        </div>
      </div>
      <div class="transition-chart">
        <div v-for="t in claimsStats" :key="t.label" class="trans-row">
          <div class="trans-label">{{ t.label }}</div>
          <div class="trans-bar-wrap">
            <div class="trans-bar" :class="{ 'trans-warn': t.pct > 60 }" :style="{ width: t.pct + '%' }"></div>
          </div>
          <div class="trans-pct">{{ t.pct }}%</div>
        </div>
      </div>
    </section>

    <!-- FTO RISK -->
    <section class="report-section">
      <div class="sec-label">侵權風險評估</div>
      <h2 class="sec-title">高風險專利清單（FTO 優先評估）</h2>
      <p class="sec-desc">下列專利依「comprising 型態 + 大族群 + 技術特徵覆蓋核心產品」標準篩選，建議委託方先行進行完整 Claim Chart 比對。</p>
      <div class="risk-table-wrap">
        <table class="risk-table">
          <thead>
            <tr>
              <th>專利號</th>
              <th>申請人</th>
              <th>技術摘要</th>
              <th>IPC</th>
              <th>風險</th>
              <th>備注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in riskPatents" :key="p.no">
              <td class="mono">{{ p.no }}</td>
              <td><strong>{{ p.holder }}</strong></td>
              <td>{{ p.title }}</td>
              <td class="mono small">{{ p.ipc }}</td>
              <td><span class="risk-badge" :class="p.risk === '高' ? 'risk-high' : 'risk-mid'">{{ p.risk }}</span></td>
              <td class="small dim">{{ p.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- CONCLUSIONS -->
    <section class="report-section">
      <div class="sec-label">結論與策略建議 — Ch.10</div>
      <h2 class="sec-title">策略行動建議</h2>
      <p class="sec-desc">依時間緊迫性排序，每條建議具體指向行動對象與預期效果。</p>

      <div class="action-list">
        <div v-for="a in actions" :key="a.timing" class="action-group">
          <div class="action-timing">{{ a.timing }}</div>
          <ul class="action-items">
            <li v-for="item in a.items" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- REVIEW NOTE -->
    <section class="report-section review-section">
      <div class="sec-label">審查備注</div>
      <h2 class="sec-title">請專利分析師重點審查事項</h2>
      <div class="review-grid">
        <div class="review-item">
          <div class="review-num">1</div>
          <div>技術功效矩陣的維度設定（技術手段 × 解決功效）是否符合板式換熱器實務分類標準？</div>
        </div>
        <div class="review-item">
          <div class="review-num">2</div>
          <div>高風險專利清單的篩選標準（comprising + 大族群）是否完整？是否遺漏其他重要篩選維度？</div>
        </div>
        <div class="review-item">
          <div class="review-num">3</div>
          <div>EV 熱管理的 IPC 分類（H01M 10/613）是否正確涵蓋板式換熱器在電池系統中的應用？</div>
        </div>
        <div class="review-item">
          <div class="review-num">4</div>
          <div>Claims 結構分析中，「comprising 比例 71%」的解讀方式與法律意涵是否準確？</div>
        </div>
        <div class="review-item">
          <div class="review-num">5</div>
          <div>各章節的「解析段落」格式（圖表 → 集中度判斷 → 策略意涵）是否達到可實際使用的深度？</div>
        </div>
        <div class="review-item">
          <div class="review-num">6</div>
          <div>本示範報告欠缺真實專利資料，實際執行時應補充哪些資訊才能達到可提交客戶的品質？</div>
        </div>
      </div>
    </section>

  </div>
</template>

<style scoped>
.report-page { max-width: 900px; margin: 0 auto; padding: 0 24px 80px; }

/* HEADER */
.report-header { padding: 32px 0 24px; border-bottom: 1px solid var(--border); margin-bottom: 4px; }
.header-badges { display: flex; gap: 8px; margin-bottom: 12px; }
.rbadge {
  display: inline-block;
  padding: 2px 9px; border-radius: 4px;
  font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
}
.rbadge.draft  { background: rgba(245,166,35,.15);  color: var(--warn);  border: 1px solid rgba(245,166,35,.3); }
.rbadge.review { background: rgba(124,92,255,.12);  color: var(--accent); border: 1px solid rgba(124,92,255,.3); }
.report-title { font-size: 22px; font-weight: 700; line-height: 1.3; letter-spacing: -.02em; margin-bottom: 6px; color: var(--text); }
.report-subtitle { font-size: 13px; color: var(--text-dim); margin-bottom: 12px; }
.report-meta-row { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12.5px; color: var(--text-faint); margin-bottom: 12px; }
.report-meta-row strong { color: var(--text-dim); }
.report-notice {
  background: rgba(245,166,35,.08); border: 1px solid rgba(245,166,35,.2);
  border-radius: var(--radius-sm); padding: 10px 14px;
  font-size: 12.5px; color: var(--text-dim); line-height: 1.6;
}
.report-notice strong { color: var(--warn); }

/* SECTIONS */
.report-section { padding: 36px 0 0; }
.sec-label {
  font-size: 10.5px; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 4px;
}
.sec-title { font-size: 17px; font-weight: 700; margin-bottom: 6px; color: var(--text); }
.sec-desc { font-size: 13.5px; color: var(--text-dim); margin-bottom: 16px; line-height: 1.7; }
.chart-analysis { color: var(--text-dim); }
.chart-analysis strong { color: var(--text); }

/* SUMMARY */
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
.summary-stat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 14px 16px;
}
.summary-stat.highlight-stat { border-color: rgba(34,197,94,.3); background: rgba(34,197,94,.06); }
.summary-stat.warn-stat { border-color: rgba(242,85,90,.3); background: rgba(242,85,90,.06); }
.stat-num { font-size: 26px; font-weight: 700; letter-spacing: -.03em; color: var(--text); margin-bottom: 2px; }
.highlight-stat .stat-num { color: var(--success); }
.warn-stat .stat-num { color: var(--error); }
.stat-label { font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 2px; }
.stat-sub { font-size: 11px; color: var(--text-faint); }

.findings-list { display: flex; flex-direction: column; gap: 8px; }
.finding-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 14px; border-radius: var(--radius-sm);
  background: var(--surface); border: 1px solid var(--border);
  font-size: 13.5px; color: var(--text-dim);
}
.finding-item.critical { border-color: rgba(242,85,90,.3); background: rgba(242,85,90,.05); }
.finding-item.high     { border-color: rgba(245,166,35,.3); background: rgba(245,166,35,.05); }
.finding-item.medium   { border-color: rgba(124,92,255,.3); background: rgba(124,92,255,.05); }
.finding-item p { margin: 0; color: var(--text-dim); font-size: 13.5px; line-height: 1.6; }
.finding-no {
  font-size: 10px; font-weight: 700; letter-spacing: .06em;
  background: var(--surface-2); border-radius: 3px; padding: 2px 6px;
  color: var(--text-faint); flex-shrink: 0; margin-top: 2px;
}
.finding-item.critical .finding-no { background: rgba(242,85,90,.2); color: var(--error); }
.finding-item.high     .finding-no { background: rgba(245,166,35,.2); color: var(--warn); }
.finding-item.medium   .finding-no { background: rgba(124,92,255,.2); color: var(--accent); }

/* TREND BAR CHART */
.bar-chart {
  display: flex; align-items: flex-end; gap: 6px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 20px 16px 0;
  height: 220px; overflow: hidden; margin-bottom: 8px;
}
.bar-group { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 0; }
.bar-wrap { flex: 1; display: flex; align-items: flex-end; width: 100%; }
.bar {
  width: 100%; background: var(--accent); border-radius: 3px 3px 0 0;
  transition: height 0.3s ease; position: relative; display: flex; align-items: flex-start; justify-content: center;
}
.bar.bar-partial { background: rgba(124,92,255,.45); }
.bar.bar-highlight { background: var(--success); }
.bar-val { font-size: 9px; color: rgba(255,255,255,.7); position: absolute; top: 3px; left: 50%; transform: translateX(-50%); white-space: nowrap; }
.bar-year { font-size: 10px; color: var(--text-faint); padding: 4px 0 6px; white-space: nowrap; }
.chart-note { font-size: 11.5px; color: var(--text-faint); }

/* COUNTRY */
.country-bars { display: flex; flex-direction: column; gap: 8px; }
.country-row { display: flex; align-items: center; gap: 10px; }
.country-label { display: flex; align-items: center; gap: 6px; width: 68px; flex-shrink: 0; }
.flag { font-size: 14px; }
.cname { font-size: 13px; color: var(--text-dim); }
.country-bar-wrap { flex: 1; background: var(--surface-2); border-radius: 2px; height: 8px; }
.country-bar { height: 8px; background: var(--accent); border-radius: 2px; }
.country-stats { display: flex; gap: 6px; width: 100px; flex-shrink: 0; font-size: 12px; }
.cpct { font-weight: 700; color: var(--text); width: 30px; }
.ccount { color: var(--text-faint); }
.ctrend { font-size: 11px; }
.ctrend.up { color: var(--error); }
.ctrend.down { color: var(--success); }

/* APPLICANTS */
.applicant-list { display: flex; flex-direction: column; gap: 6px; }
.applicant-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.app-rank { font-size: 11px; font-weight: 700; color: var(--text-faint); width: 20px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.app-info { display: flex; align-items: center; gap: 6px; width: 260px; flex-shrink: 0; overflow: hidden; }
.app-flag { font-size: 13px; flex-shrink: 0; }
.app-name { font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.app-focus { font-size: 11px; color: var(--text-faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.app-bar-wrap { flex: 1; background: var(--surface-2); border-radius: 2px; height: 6px; }
.app-bar { height: 6px; background: rgba(124,92,255,.6); border-radius: 2px; }
.app-count { font-variant-numeric: tabular-nums; font-size: 13px; color: var(--text-dim); width: 32px; text-align: right; flex-shrink: 0; }

/* IPC */
.ipc-bars { display: flex; flex-direction: column; gap: 10px; }
.ipc-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.ipc-code { font-weight: 700; color: var(--accent); width: 40px; flex-shrink: 0; font-family: var(--mono); font-size: 12px; }
.ipc-desc { width: 240px; flex-shrink: 0; color: var(--text-dim); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ipc-bar-wrap { flex: 1; background: var(--surface-2); border-radius: 2px; height: 8px; }
.ipc-bar { height: 8px; background: rgba(124,92,255,.55); border-radius: 2px; }
.ipc-pct { font-weight: 700; color: var(--text); width: 32px; text-align: right; flex-shrink: 0; font-size: 13px; }

/* MATRIX */
.matrix-wrap { overflow-x: auto; margin-bottom: 12px; }
.matrix-table { border-collapse: collapse; font-size: 12.5px; width: 100%; }
.matrix-table th, .matrix-table td { padding: 7px 10px; border: 1px solid var(--border); text-align: center; }
.matrix-corner { text-align: left; font-size: 11px; color: var(--text-faint); background: var(--surface-2); min-width: 110px; }
.matrix-table th { background: var(--surface-2); color: var(--text-dim); font-size: 11.5px; white-space: nowrap; }
.matrix-tech { text-align: left; color: var(--text-dim); font-size: 12px; white-space: nowrap; background: var(--surface); }
.matrix-cell { font-variant-numeric: tabular-nums; font-weight: 600; }
.cell-hot   { background: rgba(242,85,90,.25);  color: var(--error);   }
.cell-high  { background: rgba(245,166,35,.18); color: var(--warn);    }
.cell-mid   { background: rgba(124,92,255,.15); color: var(--accent);  }
.cell-low   { background: rgba(124,92,255,.06); color: var(--text-dim);}
.cell-blank { background: var(--surface-2); color: var(--text-faint); font-weight: 400; }
.blank-mark { font-size: 16px; }
.matrix-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11.5px; }
.legend-item { padding: 3px 10px; border-radius: 3px; border: 1px solid var(--border); }

/* CLAIMS */
.claims-stats { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.claim-row { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.claim-label { color: var(--text-dim); width: 130px; flex-shrink: 0; }
.claim-val.accent { color: var(--accent); font-weight: 700; font-size: 15px; }
.claim-note { font-size: 12px; color: var(--text-faint); }
.transition-chart { display: flex; flex-direction: column; gap: 8px; }
.trans-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.trans-label { width: 200px; flex-shrink: 0; color: var(--text-dim); font-family: var(--mono); font-size: 12px; }
.trans-bar-wrap { flex: 1; background: var(--surface-2); border-radius: 2px; height: 8px; }
.trans-bar { height: 8px; background: rgba(124,92,255,.5); border-radius: 2px; }
.trans-bar.trans-warn { background: rgba(242,85,90,.6); }
.trans-pct { font-weight: 700; color: var(--text); width: 36px; text-align: right; flex-shrink: 0; }

/* RISK TABLE */
.risk-table-wrap { overflow-x: auto; }
.risk-table { border-collapse: collapse; font-size: 12.5px; width: 100%; }
.risk-table th, .risk-table td { padding: 9px 12px; border: 1px solid var(--border); text-align: left; vertical-align: top; }
.risk-table th { background: var(--surface-2); color: var(--text-dim); font-size: 11.5px; white-space: nowrap; }
.risk-table tr:hover td { background: rgba(255,255,255,.02); }
.mono { font-family: var(--mono); font-size: 11.5px; white-space: nowrap; }
.small { font-size: 11.5px; }
.dim { color: var(--text-faint); }
.risk-badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 700; }
.risk-high { background: rgba(242,85,90,.2); color: var(--error); border: 1px solid rgba(242,85,90,.3); }
.risk-mid  { background: rgba(245,166,35,.2); color: var(--warn);  border: 1px solid rgba(245,166,35,.3); }

/* ACTIONS */
.action-list { display: flex; flex-direction: column; gap: 16px; }
.action-group { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.action-timing { padding: 9px 14px; background: var(--surface-2); font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--accent); border-bottom: 1px solid var(--border); }
.action-items { list-style: none; padding: 12px 14px; margin: 0; display: flex; flex-direction: column; gap: 7px; }
.action-items li { font-size: 13.5px; color: var(--text-dim); padding-left: 14px; position: relative; line-height: 1.6; }
.action-items li::before { content: "→"; position: absolute; left: 0; color: var(--accent); font-weight: 700; }

/* REVIEW */
.review-section { border: 1px solid rgba(245,166,35,.3); border-radius: var(--radius-sm); padding: 24px; background: rgba(245,166,35,.04); }
.review-section .sec-label { color: var(--warn); }
.review-grid { display: flex; flex-direction: column; gap: 10px; }
.review-item { display: flex; gap: 12px; align-items: flex-start; font-size: 13.5px; color: var(--text-dim); }
.review-num {
  flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%;
  background: rgba(245,166,35,.2); color: var(--warn);
  font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
  margin-top: 1px;
}

/* RESPONSIVE */
@media (max-width: 680px) {
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .app-focus { display: none; }
  .ipc-desc { width: 140px; }
}
@media (max-width: 440px) {
  .summary-grid { grid-template-columns: 1fr; }
  .country-row { flex-wrap: wrap; }
}
</style>
