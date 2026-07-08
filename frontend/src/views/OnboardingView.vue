<template>
  <div class="guide-view">
    <header class="guide-hero" v-reveal>
      <h1>🚀 新手上路 — 用紀律打敗市場</h1>
      <p class="lead">這不只是看盤工具，而是一套完整的<strong>交易紀律系統</strong>。冠軍和散戶的差別不是勝率，是流程。跟著下面走一遍，你就有了冠軍的作業節奏。</p>
      <div class="creed">
        <span>紀律先於方向</span><i>·</i><span>先想「賠得起多少」，再想「會不會漲」</span><i>·</i><span>讓你的實戰數據決定下單量</span>
      </div>
    </header>

    <section class="flow-strip" v-reveal>
      <span v-for="(f, i) in flow" :key="f">
        <b>{{ f }}</b><em v-if="i < flow.length - 1">→</em>
      </span>
      <span class="loop">⟲ 複盤回灌</span>
    </section>

    <section class="steps">
      <article v-for="(s, i) in steps" :key="s.title" class="step" v-reveal>
        <div class="step-index">{{ i + 1 }}</div>
        <div class="step-body">
          <div class="step-head"><span class="step-emoji">{{ s.emoji }}</span><h3>{{ s.title }}</h3></div>
          <p class="why"><b>為什麼：</b>{{ s.why }}</p>
          <p class="what"><b>這裡做：</b>{{ s.what }}</p>
          <router-link v-if="s.to" class="step-go" :to="s.to">前往 {{ s.cta || s.title }} →</router-link>
          <span v-else class="step-note">{{ s.note }}</span>
        </div>
      </article>
    </section>

    <footer class="guide-foot" v-reveal>
      <h3>把它變成習慣</h3>
      <p>每天開盤前用「⚡ 作戰台」掃一遍、下單就「記錄」、收盤後到「📓 交易日誌」平倉並複盤——一週後系統就會用你<strong>自己的</strong>戰績建議部位。要現在就跳進去嗎？</p>
      <div class="foot-cta">
        <router-link class="btn btn-primary" to="/command">⚡ 打開作戰台</router-link>
        <router-link class="btn" to="/journal">📓 交易日誌</router-link>
      </div>
    </footer>
  </div>
</template>

<script setup>
const flow = ['選股', '定量', '執行', '控組合', '出場', '複盤']

const steps = [
  { emoji: '📡', title: '選股：訊號排名', cta: '訊號', to: '/signals',
    why: '不是所有股票都值得出手。先把觀察清單依「進場評分」排名，把注意力放在最強的設定上。',
    what: '掃觀察清單，看趨勢排列、RSI、量能、距波段高低與 0–100 進場評分。' },
  { emoji: '⚡', title: '作戰台：一站式', cta: '作戰台', to: '/command',
    why: '選股、定量、執行分散在多頁很累。作戰台把它們壓成一個畫面。',
    what: '掃描→依評分排名→用你實戰半凱利建議風險%→算出每檔建議張數→一鍵「記錄」進日誌；並警告高相關的重複下注。' },
  { emoji: '🛡️', title: '定量：部位風控', cta: '部位風控', to: '/risk-sizing',
    why: '真正殺死帳戶的是「賠太多」。先定停損與單筆可承受風險，再回推張數。',
    what: 'ATR 停損建議、依風險%算張數、凱利建議（可從回測或交易日誌帶入）、進場評分與紀律檢查。' },
  { emoji: '🎲', title: '壓測：風險模擬', cta: '蒙地卡羅', to: '/monte-carlo',
    why: '同一套勝率，運氣好壞會走出天差地別的曲線。先確認你的風險%不會讓你在噪音裡先陣亡。',
    what: '用勝率/盈虧比/風險%/筆數做蒙地卡羅，看破產機率、報酬分布與最大回撤。' },
  { emoji: '🔥', title: '控組合：投組風險', cta: '投組風險', to: '/portfolio-heat',
    why: '單筆控好，還會被「同時壓太多、又高度相關」的部位殺死。',
    what: '總風險熱度、產業集中度、相關矩陣（揪出不同產業卻同一注的隱性集中），可一鍵推播摘要。' },
  { emoji: '📈', title: '出場：ATR 移動停利', cta: '個股分析', to: '/stocks/2330',
    why: '進場有紀律，出場更要。趨勢單用吊燈出場線一路守住獲利。',
    what: '分析頁 K 線疊上 ATR 移動停利線與進場評分徽章，價格跌破就是離場訊號。' },
  { emoji: '📓', title: '複盤：交易日誌', cta: '交易日誌', to: '/journal',
    why: '系統要能從你的實戰學習。記錄每筆進出場，算出你「自己的」勝率、期望值與 R 分布。',
    what: '平倉算 R 倍數、權益曲線、依型態統計哪種設定最會賺；統計回灌部位試算，可匯出 CSV。' },
  { emoji: '🔔', title: '告警：Telegram 推播',
    note: '在後端設定 TELEGRAM_BOT_TOKEN / CHAT_ID 後，投組頁可把風險摘要推到你的手機。',
    why: '離開螢幕也要能被提醒。把總曝險與高相關警告推到手機。',
    what: '投組風險頁「🔔 推播風險摘要」把熱度、佔資金、未實現與高相關對送到 Telegram。' },
]
</script>

<style scoped>
.guide-view { display: flex; flex-direction: column; gap: 20px; max-width: 900px; margin: 0 auto; }
.guide-hero { text-align: center; padding: 8px 0 4px; }
.guide-hero h1 { margin: 0 0 10px; font-size: 1.9rem; }
.lead { color: var(--text-muted); font-size: 1.02rem; line-height: 1.7; }
.creed { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; color: var(--accent-blue); font-size: 0.86rem; }
.creed i { color: var(--text-muted); }

.flow-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; justify-content: center; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 999px; padding: 10px 16px; }
.flow-strip b { font-weight: 700; }
.flow-strip em { color: var(--text-muted); margin: 0 4px; font-style: normal; }
.flow-strip .loop { color: #22c55e; font-size: 0.86rem; margin-left: 6px; }

.steps { display: flex; flex-direction: column; gap: 14px; }
.step { display: flex; gap: 16px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 18px; }
.step-index { flex: 0 0 auto; width: 34px; height: 34px; border-radius: 50%; background: var(--bg-hover); display: flex; align-items: center; justify-content: center; font-weight: 800; color: var(--accent-blue); }
.step-body { flex: 1; min-width: 0; }
.step-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.step-emoji { font-size: 1.3rem; }
.step-head h3 { margin: 0; }
.why, .what { margin: 4px 0; font-size: 0.9rem; line-height: 1.6; color: var(--text-secondary, var(--text-muted)); }
.why b, .what b { color: var(--text-primary); }
.step-go { display: inline-block; margin-top: 10px; color: var(--accent-blue); font-weight: 600; text-decoration: none; }
.step-go:hover { text-decoration: underline; }
.step-note { display: inline-block; margin-top: 10px; font-size: 0.82rem; color: var(--text-muted); }

.guide-foot { text-align: center; background: var(--bg-well); border: 1px solid var(--border-color); border-radius: 16px; padding: 22px; }
.guide-foot h3 { margin: 0 0 8px; }
.guide-foot p { color: var(--text-muted); line-height: 1.7; }
.foot-cta { display: flex; gap: 10px; justify-content: center; margin-top: 14px; flex-wrap: wrap; }
</style>
