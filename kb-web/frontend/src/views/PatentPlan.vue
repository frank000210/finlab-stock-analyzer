<script setup>
const phases = [
  {
    num: 'Ph.1',
    name: '需求釐清與範圍定義',
    lead: 'both',
    ai: ['解析委託方需求描述，初步建議 IPC 範圍', '生成技術關鍵字清單草稿', '提供競爭對手初步名單'],
    human: ['確認分析目的（FTO / 佈局 / 白地 / 競爭）', '核定 IPC 範圍與檢索策略', '確定報告受眾與決策情境'],
    output: '確認需求文件：分析目的、IPC 範圍、競爭標的、預算',
    gate: '委託方書面確認範圍，避免後段重做',
  },
  {
    num: 'Ph.2',
    name: '資料蒐集與結構化',
    lead: 'ai',
    ai: ['跨 DB 批量檢索（USPTO/EPO/WIPO/JPO/CNIPA）', '噪音過濾（非相關申請人 / 過期 / 廢止）', '申請人標準化（集團合併、前後母子公司）', '輸出結構化資料集（CSV / JSON）'],
    human: ['抽樣驗證 AI 篩選結果（5–10%）', '確認申請人分類正確', '補充 DB 未涵蓋的技術標準專利'],
    output: '乾淨資料集：有效專利件數、申請人、IPC、日期、族群',
    gate: '人工驗錯率 < 5% 方可進入下一階段',
  },
  {
    num: 'Ph.3',
    name: '初步分析與視覺化',
    lead: 'ai',
    ai: ['年度趨勢、國別、申請人排名', '技術功效矩陣（IPC × 關鍵字）', '初步 Claims 統計（comprising 比例、獨立項均數）', '生成摘要段落草稿'],
    human: ['驗證圖表數據與原始資料一致', '標注異常值與解讀假說', '決定哪些圖表進入正式報告'],
    output: '分析草稿：12–15 張圖表 + AI 生成摘要段落',
  },
  {
    num: 'Ph.4',
    name: '專業解讀與語意判斷',
    lead: 'human',
    ai: ['提供相關先前技術文獻', '協助解析 Claims 技術特徵', '生成技術術語對照表'],
    human: ['逐份解讀核心專利 Claims 結構', '評估法律效力（有效性 / 可規避性）', '判斷技術白地的商業可行性', '評估 FTO 風險等級'],
    output: 'Claims 分析表：重點專利逐項拆解 + 侵權風險評級',
    gate: '每份高風險專利須有專利師書面判斷意見',
  },
  {
    num: 'Ph.5',
    name: '策略轉化',
    lead: 'both',
    ai: ['依分析結果生成策略選項矩陣', '提供同業策略行為的歷史案例', '生成行動計畫初稿'],
    human: ['評估策略可行性（研發能力 / 預算 / 時程）', '確定優先行動項目', '加入市場、法律、營運限制'],
    output: '策略建議：3 個時間維度（即時 / 3M / 6M）× 具體行動',
  },
  {
    num: 'Ph.6',
    name: '報告產出與品管',
    lead: 'both',
    ai: ['依範本組裝各章節', '生成執行摘要草稿', '格式檢查（圖表標注、引用格式）'],
    human: ['全文審閱與修訂', '確認策略建議與委託方情境一致', '簽署品質確認（QA Sign-off）'],
    output: '交付報告（PDF） + 原始資料包 + Claim Chart 附件',
    gate: '專利師 QA Sign-off 後方可交付',
  },
]

const chapterGroups = [
  {
    label: '核心必備（每份報告均須包含）',
    chapters: [
      {
        num: 'Ch.01',
        title: '執行摘要',
        purpose: 'Executive Summary',
        ai: ['生成關鍵數字統計（件數 / 成長率 / 集中度）', '初步列點發現'],
        human: ['撰寫策略意涵與決策建議', '確認摘要與報告正文一致'],
        quality: '決策者在不閱讀全文的情況下，可知道：①最重要的競爭態勢、②主要風險、③立即應採取的行動。禁止僅列數字，必須提供判斷。',
      },
      {
        num: 'Ch.02',
        title: '分析範圍與目的',
        purpose: '分析邊界聲明',
        ai: ['整理確認需求文件'],
        human: ['聲明分析目的、委託方背景、IPC 範圍、時間區間、資料庫來源'],
        quality: '讀者可以清楚知道：此報告分析什麼、不分析什麼、資料庫覆蓋率。',
      },
      {
        num: 'Ch.03',
        title: '分析方法',
        purpose: '可重現的方法論',
        ai: ['生成檢索式文件', 'IPC 代號對照表', '申請人標準化說明'],
        human: ['確認方法論合理性', '標注任何已知資料限制'],
        quality: '另一位分析師可依此章節重現相同的分析結果。',
      },
    ],
  },
  {
    label: '管理面分析',
    chapters: [
      {
        num: 'Ch.04',
        title: '專利申請年度趨勢',
        purpose: '技術生命週期判斷',
        ai: ['生成年度折線圖 / 柱狀圖', '計算 CAGR', '生成段落草稿'],
        human: ['判斷技術生命週期（萌芽 / 快速成長 / 成熟 / 衰退）', '分析外部事件對趨勢的影響'],
        quality: '不只呈現「圖表」，必須包含：①趨勢轉折點說明（如 2019 EV 影響）、②生命週期判斷、③對委託方的策略意涵。',
      },
      {
        num: 'Ch.05',
        title: '競爭佈局分析',
        purpose: '地理 + 申請人競爭格局',
        ai: ['生成國別分佈圖 + Top 10 申請人排名', '標記近三年快速成長者'],
        human: ['判斷集中度（HHI）', '解讀申請人策略意圖', '提供可規避建議'],
        quality: '必須包含：①各國集中度判斷、②重點申請人的技術焦點描述、③近三年趨勢變化、④策略意涵。',
      },
    ],
  },
  {
    label: '技術面分析',
    chapters: [
      {
        num: 'Ch.06',
        title: 'IPC 技術分類分析',
        purpose: '技術架構定位',
        ai: ['IPC 三階統計', '生成技術分類圖', '識別快速成長子類'],
        human: ['解讀技術趨勢轉移', '識別跨領域佈局（如 F28D → H01M）', '判斷各子類的防禦 vs 進攻性質'],
        quality: '必須解讀每個主要 IPC 的技術意涵與競爭態勢，不得只列數字。',
      },
      {
        num: 'Ch.07',
        title: '技術功效矩陣',
        purpose: '白地識別',
        ai: ['生成技術手段 × 解決功效矩陣初稿', '標記密集區與空白區'],
        human: ['核定矩陣維度是否符合技術實務', '判斷空白區是「技術機會」還是「不可行組合」', '評估進入各熱點區的侵權風險'],
        quality: '矩陣維度須由專利師與技術工程師共同確認。每個顯著空白區必須說明空白原因與評估建議。',
      },
      {
        num: 'Ch.08',
        title: '關鍵專利與 Claims 分析',
        purpose: '技術核心識別',
        ai: ['統計 comprising / consisting 比例', 'Claims 數量統計', '初步識別高引用專利'],
        human: ['逐份拆解高風險專利 Claims 結構（Preamble / Transition / Body）', '判斷法律效力與可規避性', '撰寫 Claim Chart'],
        quality: '每份列為「關鍵專利」的專利必須有完整的 Claims 拆解與侵權評估意見，不得僅列摘要。',
      },
    ],
  },
  {
    label: '策略面輸出',
    chapters: [
      {
        num: 'Ch.09',
        title: '研發空白與佈局建議',
        purpose: '機會識別',
        ai: ['彙整矩陣空白區清單', '提供相關先前技術摘要'],
        human: ['評估技術可行性', '確認市場規模與商業吸引力', '建議申請策略（原創 / 迴避設計 / 授權）'],
        quality: '每個建議佈局區域必須說明：①技術空白的技術依據、②商業機會評估、③具體建議行動。',
      },
      {
        num: 'Ch.10',
        title: '行動計畫與結論',
        purpose: '可執行決策建議',
        ai: ['生成行動項目初稿'],
        human: ['確認行動項目與委託方資源 / 策略一致', '排定優先順序與責任人', '設定追蹤里程碑'],
        quality: '每條行動建議必須：①具體指名行動對象（哪份專利 / 哪個技術）、②說明預期效果、③指定時間點。',
      },
    ],
  },
]

const qualityTiers = [
  { tier: 'T1', name: '資料整理', who: '大部分公司', grade: 'bad', stop: '多數公司停在這裡' },
  { tier: 'T2', name: '圖表呈現', who: '大部分供應商', grade: 'bad', stop: '' },
  { tier: 'T3', name: '文字解析', who: '少數分析師', grade: 'min', stop: '' },
  { tier: 'T4', name: '策略判斷', who: '資深 IP 顧問', grade: 'good', stop: '' },
  { tier: 'T5', name: '行動建議', who: '頂尖 IP × 商業', grade: 'best', stop: '' },
]

const comparisons = [
  { dim: '申請趨勢', bad: '2019 年申請量 267 件，比 2018 年增加 29 件。', good: '2019 年受 EV 電動化觸媒影響，申請量加速至 267 件（年增 12%），為近 10 年首次突破 10% 年增，顯示技術進入快速成長期，佈局時機窗口正開放。' },
  { dim: '競爭格局', bad: 'Alfa Laval 申請量最多（312 件），排名第一。', good: 'Alfa Laval 在釺焊板式熱交換器核心工藝（F28F 21/08）的佔比達 31%，遠超其整體市佔 10%，顯示其刻意在技術壁壘最高的子類集中佈局；若委託方計畫進入此子類，建議優先進行完整 FTO 分析。' },
  { dim: '技術空白', bad: '「冷媒流路 × 重量輕量化」矩陣格為空白。', good: '「冷媒流路 × 重量輕量化」顯示零件數空白，可能原因有三：①材料限制導致技術上不可行；②市場需求不足；③為真正的先行佈局機會。建議先進行先前技術搜索確認原因後，再評估申請策略。' },
  { dim: 'Claims 分析', bad: 'comprising 比例 71%，獨立項均值 2.8 件。', good: 'comprising（開放式）佔 71%，意味侵權判斷門檻偏低，即使加入額外元件仍可能構成侵權；平均獨立項 2.8 件高於業界均值 2.1 件（高出 33%），顯示主要申請人積極多維度保護，委託方進入同一技術範圍須格外謹慎。' },
]
</script>

<template>
  <div class="plan-page">

    <!-- HEADER -->
    <div class="plan-header">
      <div class="header-badges">
        <span class="pbadge draft">草案 v0.1</span>
        <span class="pbadge review">待專利師審查</span>
      </div>
      <h1 class="plan-title">專利分析 AI 協作系統</h1>
      <p class="plan-subtitle">人機協作流程設計 × 分析報告標準範本</p>
      <div class="plan-meta-row">
        <span>日期：<strong>2026-08-06</strong></span>
        <span>版本：<strong>0.1 草案</strong></span>
        <span>審查對象：<strong>專利分析師 / IP 工程師</strong></span>
        <span>知識庫依據：<strong>49 篇專利分析文獻</strong></span>
      </div>
    </div>

    <!-- ANALYSIS TYPES -->
    <section class="plan-section">
      <div class="sec-eyebrow">背景說明</div>
      <h2 class="sec-title">分析服務類型與設計原則</h2>
      <p class="sec-desc">本系統涵蓋四種主要專利分析服務類型。AI 負責結構化、重複性的工作；專業人員負責語義判斷、策略洞察與風險評估。</p>
      <div class="type-grid">
        <div class="type-card">
          <div class="type-name accent">技術佈局分析</div>
          <div class="type-desc">Technology Landscape — 掌握某技術領域的整體專利佈局態勢與競爭格局</div>
        </div>
        <div class="type-card">
          <div class="type-name green">FTO 自由實施評估</div>
          <div class="type-desc">Freedom-to-Operate — 評估特定產品或方法是否可能侵犯他人現有有效專利</div>
        </div>
        <div class="type-card">
          <div class="type-name warn">白地分析</div>
          <div class="type-desc">White Space Analysis — 識別技術 × 功效矩陣中的未佈局空間，尋找申請機會</div>
        </div>
        <div class="type-card">
          <div class="type-name dim">競爭對手監控</div>
          <div class="type-desc">Competitor Watch — 持續追蹤競爭對手的專利申請動向，預判技術策略</div>
        </div>
      </div>
    </section>

    <!-- 6-PHASE WORKFLOW -->
    <section class="plan-section">
      <div class="sec-eyebrow">協作流程</div>
      <h2 class="sec-title">六階段人機協作流程</h2>
      <p class="sec-desc">AI 負責結構化、重複性的工作；專利師負責語義判斷、策略洞察與風險評估。每個通過條件（🔒）均需人工書面確認。</p>

      <div class="timeline">
        <div v-for="p in phases" :key="p.num" class="phase" :class="`lead-${p.lead}`">
          <div class="phase-dot">{{ p.num.replace('Ph.', '') }}</div>
          <div class="phase-card">
            <div class="phase-head">
              <span class="phase-num">{{ p.num }}</span>
              <span class="phase-name">{{ p.name }}</span>
              <span class="phase-lead-badge" :class="`badge-${p.lead}`">
                {{ p.lead === 'ai' ? 'AI 主導' : p.lead === 'human' ? '人工主導' : 'AI + 人工' }}
              </span>
            </div>
            <div class="phase-body">
              <div class="task-col ai-col">
                <div class="task-col-title">AI 執行</div>
                <ul>
                  <li v-for="item in p.ai" :key="item">{{ item }}</li>
                </ul>
              </div>
              <div class="task-col human-col">
                <div class="task-col-title">人工判斷</div>
                <ul>
                  <li v-for="item in p.human" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>
            <div class="phase-output">產出：<strong>{{ p.output }}</strong></div>
            <div v-if="p.gate" class="phase-gate">{{ p.gate }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- CHAPTER TEMPLATE -->
    <section class="plan-section">
      <div class="sec-eyebrow">報告範本</div>
      <h2 class="sec-title">標準專利分析報告章節架構</h2>
      <p class="sec-desc">每章均標注 AI 可執行事項與人工判斷範圍，以及最低品質要求（◎ 品質要求）。</p>

      <div v-for="group in chapterGroups" :key="group.label" class="chapter-group">
        <div class="chapter-group-label">{{ group.label }}</div>
        <div v-for="ch in group.chapters" :key="ch.num" class="chapter-card">
          <div class="chapter-head">
            <span class="chapter-num">{{ ch.num }}</span>
            <div class="chapter-title-wrap">
              <div class="chapter-title">{{ ch.title }}</div>
              <div class="chapter-purpose">{{ ch.purpose }}</div>
            </div>
          </div>
          <div class="chapter-body">
            <div class="chapter-col">
              <div class="chapter-col-title accent">AI 可執行</div>
              <ul>
                <li v-for="item in ch.ai" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="chapter-col">
              <div class="chapter-col-title green">人工判斷</div>
              <ul>
                <li v-for="item in ch.human" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
          <div class="chapter-quality">{{ ch.quality }}</div>
        </div>
      </div>
    </section>

    <!-- QUALITY STANDARD -->
    <section class="plan-section">
      <div class="sec-eyebrow">品質標準</div>
      <h2 class="sec-title">五層價值鏈與品質要求</h2>
      <p class="sec-desc">多數公司停在 T1–T2（有資料、有圖表），但無法提供真正的策略判斷。目標是達到 T4–T5 層次。</p>

      <div class="value-chain">
        <div v-for="t in qualityTiers" :key="t.tier" class="vc-step" :class="t.grade">
          <div class="vc-tier">{{ t.tier }}</div>
          <div class="vc-name">{{ t.name }}</div>
          <div class="vc-who">{{ t.who }}</div>
          <div v-if="t.stop" class="vc-stop">← 多數公司到這裡</div>
        </div>
      </div>

      <h3 class="compare-title">好報告 vs 差報告：具體對比</h3>
      <div class="compare-table-wrap">
        <table class="compare-table">
          <thead>
            <tr>
              <th>分析維度</th>
              <th class="bad-th">差（僅數據）</th>
              <th class="good-th">好（含判斷與建議）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in comparisons" :key="c.dim">
              <td class="dim-cell">{{ c.dim }}</td>
              <td class="bad-cell">{{ c.bad }}</td>
              <td class="good-cell">{{ c.good }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="callout">
        <strong>核心原則：</strong>每張圖表下方必須包含三段解析——①集中度或趨勢的量化判斷、②與委託方情境的關聯、③具體的策略建議或警示。
      </div>
    </section>

  </div>
</template>

<style scoped>
.plan-page { max-width: 900px; margin: 0 auto; padding: 0 24px 80px; }

/* HEADER */
.plan-header {
  padding: 48px 0 36px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
}
.header-badges { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.pbadge {
  display: inline-block; padding: 2px 9px; border-radius: 3px;
  font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  border: 1px solid;
}
.pbadge.draft { background: color-mix(in srgb, var(--warn) 12%, transparent); color: var(--warn); border-color: var(--warn); }
.pbadge.review { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); border-color: var(--accent); }
.plan-title { font-size: 1.9rem; font-weight: 700; line-height: 1.2; margin-bottom: 6px; }
.plan-subtitle { color: var(--text-dim); font-size: 1rem; margin-bottom: 18px; }
.plan-meta-row { display: flex; gap: 20px; flex-wrap: wrap; font-size: 12.5px; color: var(--text-faint); }
.plan-meta-row strong { color: var(--text-dim); }

/* SECTIONS */
.plan-section { padding: 52px 0 0; }
.sec-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 5px; }
.sec-title { font-size: 1.35rem; font-weight: 700; margin-bottom: 8px; }
.sec-desc { color: var(--text-dim); font-size: 13.5px; margin-bottom: 28px; max-width: 680px; line-height: 1.6; }

/* TYPE GRID */
.type-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 0; }
.type-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
.type-name { font-weight: 700; font-size: 13.5px; margin-bottom: 5px; }
.type-desc { font-size: 12.5px; color: var(--text-dim); line-height: 1.5; }
.type-name.accent { color: var(--accent); }
.type-name.green { color: var(--success); }
.type-name.warn { color: var(--warn); }
.type-name.dim { color: var(--text-faint); }

/* TIMELINE */
.timeline { position: relative; }
.timeline::before {
  content: ""; position: absolute;
  left: 21px; top: 32px; bottom: 32px;
  width: 2px; background: var(--border);
}
.phase { display: flex; gap: 18px; margin-bottom: 20px; align-items: flex-start; }
.phase-dot {
  flex-shrink: 0; width: 42px; height: 42px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; z-index: 1;
  border: 2px solid var(--border); background: var(--surface); color: var(--text-dim);
}
.phase.lead-ai .phase-dot { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, var(--surface)); }
.phase.lead-human .phase-dot { border-color: var(--success); color: var(--success); background: color-mix(in srgb, var(--success) 10%, var(--surface)); }
.phase.lead-both .phase-dot { border-color: #38bdf8; color: #38bdf8; background: color-mix(in srgb, #38bdf8 10%, var(--surface)); }
.phase-card { flex: 1; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.phase-head {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 15px; border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 60%, var(--bg));
}
.phase-num { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--text-faint); }
.phase-name { font-weight: 700; font-size: 14px; flex: 1; }
.phase-lead-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 3px; }
.badge-ai { background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); }
.badge-human { background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); }
.badge-both { background: color-mix(in srgb, #38bdf8 12%, transparent); color: #38bdf8; }
.phase-body { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.task-col { padding: 13px 15px; font-size: 13px; }
.task-col + .task-col { border-left: 1px solid var(--border); }
.task-col-title { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 8px; }
.ai-col .task-col-title { color: var(--accent); }
.human-col .task-col-title { color: var(--success); }
.task-col ul { list-style: none; padding: 0; }
.task-col ul li { padding: 2px 0 2px 13px; position: relative; color: var(--text-dim); line-height: 1.5; font-size: 12.5px; }
.ai-col ul li::before { content: "▸"; position: absolute; left: 0; color: var(--accent); font-size: 10px; top: 5px; }
.human-col ul li::before { content: "▸"; position: absolute; left: 0; color: var(--success); font-size: 10px; top: 5px; }
.phase-output { padding: 9px 15px; border-top: 1px solid var(--border); font-size: 12.5px; color: var(--text-dim); background: color-mix(in srgb, var(--surface) 60%, var(--bg)); }
.phase-output strong { color: var(--text); }
.phase-gate { padding: 7px 15px; border-top: 1px solid var(--border); font-size: 12px; color: var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent); }
.phase-gate::before { content: "🔒 通過條件："; font-weight: 700; }

/* CHAPTERS */
.chapter-group { margin-bottom: 32px; }
.chapter-group-label { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-faint); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-bottom: 12px; }
.chapter-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 10px; }
.chapter-head { display: flex; align-items: flex-start; gap: 12px; padding: 13px 17px; border-bottom: 1px solid var(--border); }
.chapter-num { font-size: 12px; font-weight: 700; color: var(--text-faint); flex-shrink: 0; min-width: 42px; padding-top: 2px; }
.chapter-title { font-weight: 700; font-size: 14.5px; margin-bottom: 2px; }
.chapter-purpose { font-size: 12.5px; color: var(--text-dim); }
.chapter-body { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.chapter-col { padding: 13px 17px; font-size: 12.5px; }
.chapter-col + .chapter-col { border-left: 1px solid var(--border); }
.chapter-col-title { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 8px; }
.chapter-col-title.accent { color: var(--accent); }
.chapter-col-title.green { color: var(--success); }
.chapter-col ul { list-style: none; padding: 0; }
.chapter-col ul li { padding: 2px 0 2px 13px; position: relative; color: var(--text-dim); line-height: 1.5; }
.chapter-col ul li::before { content: "–"; position: absolute; left: 0; color: var(--text-faint); }
.chapter-quality { padding: 9px 17px; border-top: 1px solid var(--border); font-size: 12px; color: var(--accent); background: color-mix(in srgb, var(--accent) 6%, transparent); }
.chapter-quality::before { content: "◎ 品質要求："; font-weight: 700; }

/* QUALITY / VALUE CHAIN */
.value-chain { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 28px; }
.vc-step { padding: 14px; border-right: 1px solid var(--border); font-size: 13px; background: var(--surface); }
.vc-step:last-child { border-right: none; }
.vc-tier { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 4px; }
.vc-name { font-weight: 700; margin-bottom: 3px; }
.vc-who { font-size: 12px; color: var(--text-dim); }
.vc-stop { font-size: 11px; color: var(--warn); margin-top: 6px; font-weight: 600; }
.vc-step.bad { background: color-mix(in srgb, var(--error) 8%, var(--surface)); border-top: 3px solid var(--error); }
.vc-step.min { background: color-mix(in srgb, var(--warn) 8%, var(--surface)); border-top: 3px solid var(--warn); }
.vc-step.good { background: color-mix(in srgb, var(--success) 8%, var(--surface)); border-top: 3px solid var(--success); }
.vc-step.best { background: color-mix(in srgb, var(--accent) 8%, var(--surface)); border-top: 3px solid var(--accent); }

/* COMPARISON TABLE */
.compare-title { font-size: 1rem; font-weight: 700; margin: 32px 0 14px; }
.compare-table-wrap { overflow-x: auto; margin-bottom: 20px; }
.compare-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.compare-table th { text-align: left; padding: 9px 13px; background: color-mix(in srgb, var(--surface) 60%, var(--bg)); border: 1px solid var(--border); font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--text-dim); }
.compare-table td { padding: 10px 13px; border: 1px solid var(--border); vertical-align: top; line-height: 1.55; }
.compare-table tr:hover td { background: color-mix(in srgb, var(--surface) 40%, var(--bg)); }
.dim-cell { font-weight: 600; color: var(--text-dim); font-size: 12px; white-space: nowrap; }
.bad-th { color: var(--error); }
.good-th { color: var(--success); }
.bad-cell { color: color-mix(in srgb, var(--error) 80%, var(--text-dim)); }
.good-cell { color: var(--text); }

/* CALLOUT */
.callout { border-left: 3px solid var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent); padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 13.5px; margin: 20px 0; color: var(--text-dim); line-height: 1.6; }
.callout strong { color: var(--warn); }

/* RESPONSIVE */
@media (max-width: 600px) {
  .phase-body { grid-template-columns: 1fr; }
  .chapter-body { grid-template-columns: 1fr; }
  .value-chain { grid-template-columns: 1fr 1fr; }
  .plan-title { font-size: 1.4rem; }
}
@media (max-width: 400px) { .value-chain { grid-template-columns: 1fr; } }
</style>
