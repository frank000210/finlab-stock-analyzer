# 07 · UI/UX 交接摘要（給 Claude Design 新對話用）

> 用途：貼到 Claude Design 新對話開頭，讓設計端快速掌握現有視覺系統、頁面結構與已知待辦，不用重新看一次全站截圖。
> 正式站可直接開來看：`https://finlab-app.zeabur.app`（Dark mode，無 Light mode）。
> 程式碼接手另有 `交接SOP.md`（給 Claude Code 用），兩份文件互相獨立，設計端不需要看 git/後端細節。

---

## 一、技術限制（設計提案前要知道）

- 前端是 **Vue 3 `<script setup>` + scoped CSS**，沒有 Tailwind、沒有 UI 框架（不是 shadcn/MUI/Element Plus），所有樣式手寫。
- 財經走勢圖（K 線、均線）用 **TradingView `lightweight-charts`**，其餘客製圖表（熱力圖、矩陣、Sankey、Chord、Horizon 等，共 11 種）都是**手刻 D3.js**，畫在 `<svg>` 裡。
- 設計改動最終要落地成 CSS 變數 + Vue 元件，**不是**丟一個 Figma 檔就能直接用；建議設計輸出時盡量描述「改哪個 token 的值」或「這個元件的間距/字重規則」，會比純視覺稿更容易被下一個開發 session 執行。
- 只有 Dark mode，目前沒有 Light mode 需求。

---

## 二、目前的設計 Token（`frontend/src/assets/main.css`）

```css
/* 色彩 */
--bg-primary: #0b1121;       /* 頁面底色 */
--bg-secondary: #141d2f;     /* 導覽列底色 */
--bg-card: #1a2540;          /* 卡片底色 */
--bg-elevated: #1f2d47;      /* 浮起元素（dropdown 等） */
--bg-hover: rgba(37, 99, 235, 0.06);
--text-primary: #f1f5f9;
--text-secondary: #cbd5e1;
--text-muted: #8a99ad;
--accent-blue: #3b82f6;
--accent-purple: #8b5cf6;
--accent-cyan: #06b6d4;
--color-up: #10b981;         /* 漲/正向 */
--color-down: #ef4444;       /* 跌/負向 */
--color-warning: #f59e0b;
--border-color: rgba(148, 163, 184, 0.12);
--border-subtle: rgba(148, 163, 184, 0.06);

/* 陰影 / 圓角 */
--shadow-sm / --shadow-md / --shadow-lg
--radius-sm: 6px / --radius: 10px / --radius-lg: 14px / --radius-xl: 20px

/* 字型 */
--font-sans: 'Inter', ...       /* 內文、標題 */
--font-mono: 'JetBrains Mono', ...  /* 數字、代號 */

/* 間距（4px 為基準） */
--space-1: 4px ... --space-12: 48px
```

- 標題階層：`h1` 1.75rem/800、`h2` 1.35rem/700、`h3` 1.1rem/600、`h4` 0.95rem/600，字距都是負值（-0.01~-0.025em），偏緊湊、科技感。
- 導覽列（`.top-nav`）：56px 高、sticky、`backdrop-filter: blur(12px)`，內含 logo、搜尋框、頁面連結、一個漸層 CTA 按鈕。

**已知的 token 缺口（設計如果要做，可以順便定義）**：
- 各頁 `<style>` 裡有不少「淡色調」badge/底色是直接寫透明度疊色（如 `rgba(34,197,94,0.15)`），沒有對應的 `--color-up-soft` / `--color-down-soft` token，散落在 20+ 個檔案裡，難以一次調整整體飽和度或對比。
- D3/`lightweight-charts` 的圖表配色是寫死在 JS 裡的色碼（例如 `#4f8cff`、`rgba(239,68,68,0.85)`），沒有讀 CSS 變數，所以改 token 不會連動圖表顏色。如果要統一，需要用 `getComputedStyle(document.documentElement).getPropertyValue('--xxx')` 在 JS 裡讀值，屬於中型重構。

---

## 三、頁面總覽（21 個頁面，共用同一導覽列）

除首頁外，每頁最上方都有一個 `PageFocusBanner`（左側色條 + 一句話說明這頁該看什麼），這是刻意的資訊架構原則，設計改版時建議保留這個「先講觀測重點、再放圖表」的順序。

| 頁面 | 路徑 | 一句話定位 | 圖表/視覺重點 |
|---|---|---|---|
| 首頁 | `/` | 導覽入口 | 無 banner，簡單版本號/build time |
| 總覽 | `/overview` | 綜合健康度 | 雷達圖、每日類股熱力圖（Treemap） |
| 決策面板 | `/decision` | 今日 BUY/SELL/HOLD 一覽 | 信號卡片、篩選器 |
| 觀察股關聯圖 | `/graph` | 關聯強度與網絡結構 | 力導向圖/階層邊綁定/相關矩陣熱力圖，三種切換 |
| 類股輪動 | `/rotation` | 輪動與領先落後 | RRG 象限圖、Horizon chart、Chord diagram |
| 個股分析 | `/stocks/:symbol` | 技術面進出場時機 | K 線+指標、日曆熱力圖、Volume Profile |
| 回測 | `/stocks/:symbol/backtest` | 策略歷史績效 | 權益曲線 |
| 季節性 | `/stocks/:symbol/seasonal` | 季節性慣性 | 月報酬熱力圖、箱型圖 |
| 領先落後 | `/stocks/:symbol/lead-lag` | 與大盤的領先落後 | 力導向/時序圖 |
| 主力籌碼 | `/stocks/:symbol/major-players` | 主力成本與動向 | 成本分布 |
| 籌碼分析 | `/stocks/:symbol/chip` | 三大法人買賣超 | 柱狀/折線 |
| 社群熱度 | `/stocks/:symbol/social-buzz` | 社群討論熱度 | 時序圖 |
| 公開資訊 | `/stocks/:symbol/public-data` | 便宜或昂貴判斷 | PE/PB 河流圖、營收成長圖 |
| 交易儀表板 | `/trade-dashboard` | 投組/訊號/風控總覽 | KPI 卡片、AI 訊號 Sankey |
| AI 信號 | `/ai-signals` | 全市場訊號列表 | 表格/卡片 |
| 風控監控 | `/risk-monitor` | 風險是否可控 | 權益曲線、報酬分布 Histogram/KDE |
| 資料代理 | `/data-agent` | 資料抓取狀態 | 狀態列表 |
| 交易核准 | `/trade-approval` | 模擬下單核准 | 表單/列表 |
| 訊號規則 | `/signal-rules` | AI 訊號規則設定 | 表單 |
| 設定 | `/settings` | 帳號/追蹤清單 | 表單 |
| 後台管理 | `/admin` | 系統管理 | 表格 |

---

## 四、這次新增的 11 張 D3 圖表（可能需要視覺 polish）

這些都是這次新加的客製圖表，目前只求「資料正確、有標註來源」，**沒有特別做視覺打磨**，設計端如果要優化可以從這裡下手：

1. **Treemap**（Overview）— 方塊大小/顏色目前用預設 D3 配色插值，可能需要更精緻的漸層或邊框處理。
2. **Box plot**（Seasonal）— 箱型圖線條較細，行動裝置上可能不易點擊互動。
3. **相關矩陣熱力圖**（Graph）— 標籤是旋轉 -60 度文字，字級小，密集標的時容易重疊。
4. **Histogram/KDE**（RiskMonitor）— 長條圖 + 疊加曲線，兩者對比度可以再加強。
5. **Calendar 熱力圖**（Analysis）— GitHub 風格週曆，格子偏小（13px），手機上幾乎不可讀。
6. **Volume Profile**（Analysis）— 橫向長條圖，**這是近似估算值**（非真實逐筆分價量表），目前只用文字說明，可以考慮加視覺標記（如底紋/斜線）讓「這是估算」更醒目，避免使用者誤以為是真實數據。
7. **Chord diagram**（Rotation）— 弧形標籤在圓周上下兩側需要鏡像旋轉，文字方向已處理但視覺密度未特別優化。
8. **Sankey diagram**（TradeDashboard）— **手刻版面**（沒有用 d3-sankey 套件），ribbon 是簡化的貝茲曲線，視覺上比正規 Sankey 圖粗糙；同樣是示意性資料（非真實資金流），已有文字標註。
9. **Horizon chart**（Rotation）— 多列壓縮呈現，每列高度固定 26px，類股一多會很擠。
10. **PE/PB 河流圖**（PublicData）— 虛線分位帶 + 實線股價，配色是否需要圖例可再討論。
11. **營收成長圖**（PublicData）— 長條+折線疊加雙軸，Y 軸標籤密度可調整。

每張圖下方都有一行小字說明「參考：D3 gallery - <名稱>」與資料來源/限制，這個標註慣例建議保留（誠實揭露資料是估算還是真實，是這個專案一貫的原則）。

---

## 五、已知但還沒處理的視覺問題

- ~~全站的「淡色調」badge（如信號徽章、狀態標籤）顏色沒有統一 token~~ **已處理**：`main.css` 新增 `--up-soft`/`--down-soft`/`--warn-soft`，並把 10 個檔案、40 處一次性 rgba 疊色換成共用 token（湊不到剩下的 10 個檔案是因為裡面沒有符合的淡色調用色，不是漏改）。
- ~~圖表配色（D3 + lightweight-charts）不吃 CSS 變數~~ **已處理**：新增 `--chart-*` token 組 + `frontend/src/composables/useChartTheme.js`，10 個畫圖表的 view 都已改吃這個 composable。
- Volume Profile / Sankey 是資料層面的「近似值」：**視覺標記已補上**（`.badge-estimated` 斜紋徽章），Analysis 的 Volume Profile、TradeDashboard 的 Sankey、RiskMonitor 的模擬帳戶圖表都已加註，不用再只靠文字說明。
- 類股輪動頁新增了 Sankey 資金流向圖（沿用既有 Chord diagram 的 lead-lag 邊資料），Chord 本身也做了密度優化（加大 padAngle/弧寬、hover 聚焦淡出）。
- 首頁 Bento 特色卡圖示改為依類別上色（藍/青/紫/黃/綠），取代原本統一藍色。
- 尚未做過響應式（mobile）系統性檢視，部分圖表（Calendar、相關矩陣）在小螢幕上文字/格子會太密。
- **未完成**：設計稿裡逐頁的卡片陰影/光暈/間距細節沒有逐一比對落地——Decision、AISignals、SocialBuzz、Home 這幾頁本來就已經有相近水準的「交易終端機」視覺（頂部色條、半圓 gauge、玻璃質感卡片），這次沒有重做；其餘頁面也維持原有卡片語彙，只做了配色 token 化，沒有逐頁重新刻版面。如果要更貼近設計稿的逐頁像素級還原，需要再開一輪聚焦視覺細節的工作。

---

## 六、如何驗證改動

正式站是 Dark mode SPA，直接開 `https://finlab-app.zeabur.app` 對照設計稿即可；如果需要看某個客製圖表，路徑對照第三節表格。程式碼交給另一個 Claude Code 對話落地，這份文件只需要聚焦「畫面長什麼樣、token 有哪些、哪裡有已知問題」。
