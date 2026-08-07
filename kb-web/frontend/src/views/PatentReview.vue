<script setup>
import { ref, reactive } from 'vue'

const reviewerName = ref('')
const reviewDate = ref('')
const overallComment = ref('')

const chapters = [
  { num: 'Ch.01', title: '執行摘要', criteria: '決策者在不閱讀全文下，可知主要競爭態勢、風險與立即行動建議。禁止僅列數字，必須提供判斷。' },
  { num: 'Ch.02', title: '分析範圍與目的', criteria: '明確說明分析目的、委託方背景、IPC 範圍、時間區間、資料庫覆蓋率；讀者可知道分析什麼、不分析什麼。' },
  { num: 'Ch.03', title: '分析方法', criteria: '方法論可重現：另一位分析師依此章節可得到相同結果。檢索式、噪音過濾條件、申請人標準化規則均須說明。' },
  { num: 'Ch.04', title: '專利申請年度趨勢', criteria: '須包含：①趨勢轉折點說明（外部事件驅動）、②技術生命週期判斷（萌芽/成長/成熟/衰退）、③對委託方的策略意涵。' },
  { num: 'Ch.05', title: '競爭佈局分析（地理 + 申請人）', criteria: '須包含：①國別集中度判斷（HHI）、②重點申請人技術焦點、③近三年趨勢變化、④可規避建議。' },
  { num: 'Ch.06', title: 'IPC 技術分類分析', criteria: '每個主要 IPC 子類必須解讀技術意涵與競爭態勢，不得只列數字。跨領域佈局趨勢（如 F28D → H01M）需特別說明。' },
  { num: 'Ch.07', title: '技術功效矩陣', criteria: '矩陣維度須由專利師與技術工程師共同確認。每個顯著空白區必須說明空白原因（技術不可行 vs 真正機會），並提出評估建議。' },
  { num: 'Ch.08', title: '關鍵專利與 Claims 分析', criteria: '每份「關鍵專利」必須有完整 Claims 拆解（Preamble / Transition / Body）與侵權評估意見，不得僅列摘要。' },
  { num: 'Ch.09', title: '研發空白與佈局建議', criteria: '每個建議佈局區域必須說明：①技術空白依據、②商業機會評估、③具體建議行動（原創 / 迴避設計 / 授權）。' },
  { num: 'Ch.10', title: '行動計畫與結論', criteria: '每條行動建議必須：①具體指名行動對象（哪份專利 / 哪個技術）、②說明預期效果、③指定時間點。' },
]

const expertQuestions = [
  { no: 'Q1', text: '技術功效矩陣的維度設定（技術手段 × 解決功效）是否符合板式換熱器實務分類標準？是否需要調整維度？' },
  { no: 'Q2', text: '高風險專利清單的篩選標準（comprising + 大族群）是否完整？是否遺漏其他重要篩選維度（如引用次數、家族大小）？' },
  { no: 'Q3', text: 'EV 熱管理的 IPC 分類（H01M 10/613）是否正確涵蓋板式換熱器在電池系統中的應用？是否需要補充其他 IPC？' },
  { no: 'Q4', text: 'Claims 結構分析中，「comprising 比例 71%」的解讀方式與法律意涵（侵權判斷門檻偏低）是否準確？' },
  { no: 'Q5', text: '各章節的解析段落格式（圖表 → 集中度判斷 → 策略意涵）是否達到可實際使用的深度？哪些章節需要強化？' },
  { no: 'Q6', text: '本示範報告欠缺真實專利資料，實際執行時需補充哪些步驟、工具或資料才能達到可提交客戶的品質？' },
]

const ratings = reactive({})
const comments = reactive({})
const qComments = reactive({})

chapters.forEach(ch => {
  ratings[ch.num] = ''
  comments[ch.num] = ''
})
expertQuestions.forEach(q => {
  qComments[q.no] = ''
})

const ratingOptions = [
  { value: 'ok', label: '✓ 符合要求', color: 'ok' },
  { value: 'revise', label: '△ 需要修改', color: 'revise' },
  { value: 'reject', label: '✗ 不符合，需重寫', color: 'reject' },
  { value: 'na', label: '— 本次不適用', color: 'na' },
]

const overallRating = ref('')
</script>

<template>
  <div class="review-page">

    <!-- HEADER -->
    <div class="review-header">
      <div class="header-badges">
        <span class="rbadge expert">專利師審查表</span>
        <span class="rbadge draft">板式熱交換器示範報告 v0.1</span>
      </div>
      <h1 class="review-title">審查備注</h1>
      <p class="review-subtitle">請專利分析師就各章節品質、分析架構及專業問題逐一填寫意見，協助確認本 AI 協作框架是否符合實務標準。</p>
      <div class="reviewer-row">
        <div class="field-group">
          <label>審查人姓名</label>
          <input v-model="reviewerName" type="text" placeholder="請填寫姓名 / 機構" />
        </div>
        <div class="field-group">
          <label>審查日期</label>
          <input v-model="reviewDate" type="date" />
        </div>
      </div>
    </div>

    <!-- HOW TO USE -->
    <div class="howto-card">
      <div class="howto-title">審查說明</div>
      <ol class="howto-list">
        <li>依序檢閱各章節後，選擇評級並填寫具體修改意見。</li>
        <li>針對六個專業問題（Q1–Q6）填寫您的判斷與建議。</li>
        <li>最後填寫整體評估與優先修改建議。</li>
        <li>建議同時對照「<a href="/patent-plan">規劃書</a>」的品質標準與「<a href="/patent-report">示範報告</a>」的具體內容。</li>
      </ol>
    </div>

    <!-- CHAPTER REVIEWS -->
    <section class="review-section">
      <div class="sec-eyebrow">逐章審查</div>
      <h2 class="sec-title">各章節品質評級與意見</h2>

      <div v-for="ch in chapters" :key="ch.num" class="chapter-review-card">
        <div class="cr-head">
          <span class="cr-num">{{ ch.num }}</span>
          <div class="cr-title-wrap">
            <div class="cr-title">{{ ch.title }}</div>
            <div class="cr-criteria">品質要求：{{ ch.criteria }}</div>
          </div>
        </div>
        <div class="cr-body">
          <div class="cr-rating-row">
            <span class="cr-rating-label">評級：</span>
            <label
              v-for="opt in ratingOptions"
              :key="opt.value"
              class="rating-option"
              :class="[`opt-${opt.color}`, { selected: ratings[ch.num] === opt.value }]"
            >
              <input type="radio" :name="`rating-${ch.num}`" :value="opt.value" v-model="ratings[ch.num]" />
              {{ opt.label }}
            </label>
          </div>
          <div class="cr-comment-row">
            <label class="comment-label">具體意見 / 修改建議：</label>
            <textarea
              v-model="comments[ch.num]"
              :placeholder="`請針對 ${ch.title} 填寫具體修改建議、遺漏事項或格式問題…`"
              rows="3"
            ></textarea>
          </div>
        </div>
      </div>
    </section>

    <!-- EXPERT QUESTIONS -->
    <section class="review-section">
      <div class="sec-eyebrow">專業問題</div>
      <h2 class="sec-title">六項重點專業問題</h2>
      <p class="sec-desc">這些問題涉及 AI 無法自我驗證的專業判斷，需要專利師明確表態。</p>

      <div v-for="q in expertQuestions" :key="q.no" class="question-card">
        <div class="q-head">
          <span class="q-num">{{ q.no }}</span>
          <p class="q-text">{{ q.text }}</p>
        </div>
        <div class="q-body">
          <label class="comment-label">您的判斷與建議：</label>
          <textarea
            v-model="qComments[q.no]"
            placeholder="請填寫您的專業判斷、確認或修正意見…"
            rows="4"
          ></textarea>
        </div>
      </div>
    </section>

    <!-- OVERALL -->
    <section class="review-section">
      <div class="sec-eyebrow">整體評估</div>
      <h2 class="sec-title">整體審查意見</h2>

      <div class="overall-rating-row">
        <span class="cr-rating-label">整體評級：</span>
        <label
          v-for="opt in ratingOptions"
          :key="opt.value"
          class="rating-option"
          :class="[`opt-${opt.color}`, { selected: overallRating === opt.value }]"
        >
          <input type="radio" name="overall-rating" :value="opt.value" v-model="overallRating" />
          {{ opt.label }}
        </label>
      </div>

      <div class="overall-comment-wrap">
        <label class="comment-label">整體意見、優先修改建議與後續步驟建議：</label>
        <textarea
          v-model="overallComment"
          placeholder="請說明：①本報告架構是否達到可提交客戶的標準？②最需要改善的 1–3 項重點？③建議的下一步驟？"
          rows="6"
        ></textarea>
      </div>

      <div class="summary-card">
        <div class="summary-title">審查摘要</div>
        <div class="summary-row">
          <span class="summary-label">審查人</span>
          <span class="summary-val">{{ reviewerName || '（未填寫）' }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">審查日期</span>
          <span class="summary-val">{{ reviewDate || '（未填寫）' }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">整體評級</span>
          <span class="summary-val" :class="`summary-${overallRating}`">
            {{ overallRating === 'ok' ? '✓ 符合要求' : overallRating === 'revise' ? '△ 需要修改' : overallRating === 'reject' ? '✗ 需重寫' : overallRating === 'na' ? '— 不適用' : '（未評級）' }}
          </span>
        </div>
        <div class="summary-row">
          <span class="summary-label">完成章節</span>
          <span class="summary-val">{{ Object.values(ratings).filter(v => v).length }} / {{ chapters.length }} 章</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">回答問題</span>
          <span class="summary-val">{{ Object.values(qComments).filter(v => v.trim()).length }} / {{ expertQuestions.length }} 題</span>
        </div>
      </div>

      <div class="notice-card">
        <strong>注意：</strong>本審查表為純前端介面，填寫的內容不會自動儲存。請在完成後複製整頁或截圖留存，或將意見整理後回傳給開發團隊。
      </div>
    </section>

  </div>
</template>

<style scoped>
.review-page { max-width: 900px; margin: 0 auto; padding: 0 24px 80px; }

/* HEADER */
.review-header { padding: 48px 0 32px; border-bottom: 1px solid var(--border); margin-bottom: 0; }
.header-badges { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.rbadge {
  display: inline-block; padding: 2px 9px; border-radius: 3px;
  font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; border: 1px solid;
}
.rbadge.expert { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); border-color: var(--success); }
.rbadge.draft  { background: color-mix(in srgb, var(--warn) 12%, transparent); color: var(--warn); border-color: var(--warn); }
.review-title { font-size: 1.9rem; font-weight: 700; line-height: 1.2; margin-bottom: 8px; }
.review-subtitle { color: var(--text-dim); font-size: 13.5px; max-width: 680px; line-height: 1.6; margin-bottom: 20px; }
.reviewer-row { display: flex; gap: 20px; flex-wrap: wrap; }
.field-group { display: flex; flex-direction: column; gap: 5px; }
.field-group label { font-size: 12px; font-weight: 600; color: var(--text-dim); }
.field-group input { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 7px 12px; color: var(--text); font-size: 13.5px; outline: none; min-width: 220px; }
.field-group input:focus { border-color: var(--accent); }

/* HOW TO USE */
.howto-card { margin: 24px 0 0; background: color-mix(in srgb, var(--accent) 6%, var(--surface)); border: 1px solid color-mix(in srgb, var(--accent) 25%, var(--border)); border-radius: 8px; padding: 16px 20px; }
.howto-title { font-weight: 700; font-size: 13px; color: var(--accent); margin-bottom: 8px; }
.howto-list { list-style: decimal; padding-left: 18px; font-size: 13px; color: var(--text-dim); line-height: 1.8; }
.howto-list a { color: var(--accent); }

/* SECTIONS */
.review-section { padding: 52px 0 0; }
.sec-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 5px; }
.sec-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 8px; }
.sec-desc { color: var(--text-dim); font-size: 13.5px; margin-bottom: 24px; max-width: 680px; line-height: 1.6; }

/* CHAPTER REVIEW CARDS */
.chapter-review-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 14px; }
.cr-head { display: flex; align-items: flex-start; gap: 12px; padding: 13px 17px; border-bottom: 1px solid var(--border); background: color-mix(in srgb, var(--surface) 60%, var(--bg)); }
.cr-num { font-size: 12px; font-weight: 700; color: var(--text-faint); flex-shrink: 0; min-width: 42px; padding-top: 2px; }
.cr-title { font-weight: 700; font-size: 14.5px; margin-bottom: 3px; }
.cr-criteria { font-size: 12px; color: var(--text-dim); line-height: 1.5; }
.cr-body { padding: 14px 17px; display: flex; flex-direction: column; gap: 12px; }
.cr-rating-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.cr-rating-label { font-size: 12px; font-weight: 600; color: var(--text-dim); flex-shrink: 0; }
.rating-option {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 4px 10px; border-radius: 4px;
  border: 1px solid var(--border); background: transparent;
  cursor: pointer; color: var(--text-dim); transition: all .15s;
  user-select: none;
}
.rating-option input[type=radio] { display: none; }
.rating-option:hover { border-color: var(--text-dim); color: var(--text); }
.rating-option.opt-ok.selected { background: color-mix(in srgb, var(--success) 15%, transparent); border-color: var(--success); color: var(--success); }
.rating-option.opt-revise.selected { background: color-mix(in srgb, var(--warn) 15%, transparent); border-color: var(--warn); color: var(--warn); }
.rating-option.opt-reject.selected { background: color-mix(in srgb, var(--error) 15%, transparent); border-color: var(--error); color: var(--error); }
.rating-option.opt-na.selected { background: color-mix(in srgb, var(--text-faint) 15%, transparent); border-color: var(--text-faint); color: var(--text-faint); }
.cr-comment-row { display: flex; flex-direction: column; gap: 5px; }
.comment-label { font-size: 12px; font-weight: 600; color: var(--text-dim); }
textarea {
  background: color-mix(in srgb, var(--surface) 60%, var(--bg));
  border: 1px solid var(--border); border-radius: 6px;
  padding: 9px 12px; color: var(--text); font-size: 13px;
  resize: vertical; outline: none; width: 100%; line-height: 1.6;
  font-family: inherit;
}
textarea:focus { border-color: var(--accent); }
textarea::placeholder { color: var(--text-faint); }

/* EXPERT QUESTIONS */
.question-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 14px; }
.q-head { display: flex; align-items: flex-start; gap: 14px; padding: 15px 17px; border-bottom: 1px solid var(--border); background: color-mix(in srgb, var(--accent) 5%, var(--surface)); }
.q-num { font-size: 13px; font-weight: 700; color: var(--accent); flex-shrink: 0; min-width: 28px; padding-top: 1px; }
.q-text { font-size: 14px; line-height: 1.55; font-weight: 500; }
.q-body { padding: 14px 17px; display: flex; flex-direction: column; gap: 5px; }

/* OVERALL */
.overall-rating-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.overall-comment-wrap { display: flex; flex-direction: column; gap: 5px; margin-bottom: 24px; }
.summary-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.summary-title { font-weight: 700; font-size: 13px; color: var(--text-dim); margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.summary-row { display: flex; justify-content: space-between; padding: 5px 0; font-size: 13.5px; border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent); }
.summary-row:last-child { border-bottom: none; }
.summary-label { color: var(--text-dim); }
.summary-val { font-weight: 600; }
.summary-ok     { color: var(--success); }
.summary-revise { color: var(--warn); }
.summary-reject { color: var(--error); }
.summary-na     { color: var(--text-faint); }
.notice-card { background: color-mix(in srgb, var(--warn) 8%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent); border-radius: 8px; padding: 14px 18px; font-size: 13px; color: var(--text-dim); line-height: 1.6; }
.notice-card strong { color: var(--warn); }

@media (max-width: 600px) {
  .reviewer-row { flex-direction: column; }
  .cr-rating-row { flex-direction: column; align-items: flex-start; }
}
</style>
