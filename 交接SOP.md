# finlab-stock-analyzer 接手交接 SOP

> 用途：貼到新對話開頭，讓新 session 直接接續進度，不用重跑一次 code review。
> 這次交接同時要開兩個新對話：
> - **Claude Code**：接續程式開發 → 看第 1~5 節
> - **Claude Design**：接續 UI/UX 設計 → 看第 6 節，並改貼 `docs/07-UIUX交接摘要.md` 的內容（那份文件是專為設計對話寫的，比這份更聚焦視覺）

---

## 0. 專案基本資訊

- 本機路徑：`F:\github\finlab-stock-analyzer`
- Zeabur project-id：`6a3f6ff522d1fdaf7eb04d04`
- Zeabur service-id：`6a3f700322d1fdaf7eb04d06`（唯一服務，前後端合併映像）
- 部署網址：`https://finlab-app.zeabur.app`
- GitHub repo：`frank000210/finlab-stock-analyzer`，分支 `master`
- 專案文件：`docs/00~07` + `docs/README.md`，開發任何東西前先讀 `04-開發指引.md`（開發約定，內含「頁面觀測重點」規則）與 `03-技術架構.md`（架構）；UI/UX 相關先讀新增的 `docs/07-UIUX交接摘要.md`

---

## 1. 目前 git 狀態（截至這次交接）

**HEAD 與 `origin/master` 一致，已確認 push 完成**（`45359ac`）。工作目錄乾淨，沒有待 commit 的專案檔案變更。

> 有 3 個未追蹤、**跟本專案無關**的雜項檔案留在資料夾根目錄：`claude-usage/`、`claude_usage_app.py`（一個獨立的 Claude 用量統計 Tkinter 小工具，看起來是之前不小心存到這個資料夾，不是 finlab 專案的一部分）。沒有加進 git，新 session 可以忽略，若要清掉需先跟使用者確認再刪。

這次（2026-07-04～07-05）新增並已 push 的 22 個 commit，由舊到新：

```
9fd3cce feat(frontend): add PageFocusBanner component
8baba7f feat(frontend): add 觀測重點 focus banner to every page
7317058 docs: page-focus principle + per-page gap analysis
85cde08 fix(rotation): clear will-change after v-reveal animation so fullscreen overlay isn't trapped
6bc64f3 feat(rotation): add daily sector heatmap endpoint (D3 Treemap ref)
8336986 feat(overview): daily sector treemap heatmap (D3 gallery - Treemap)
fc47ace feat(seasonal): monthly return box plot (D3 gallery - Box plot)
0c009e0 docs: log D3 gallery-inspired chart backlog and mark 2 shipped
0b98485 feat(public-data): PE band + revenue growth charts (D3 gallery ref)
9f0bc18 feat(risk-monitor): return distribution histogram + KDE (D3 gallery ref)
d68bcf1 feat(analysis): per-stock calendar heatmap (D3 gallery - Calendar)
3b1c6b1 feat(graph): correlation matrix heatmap view mode (D3 gallery ref)
86800fd feat(rotation): horizon chart across all visible sectors (D3 gallery ref)
a06fe85 feat(analysis): add volume profile chart (D3 gallery - Contour/Hexbin)
ec91f49 feat(rotation): chord diagram for sector lead-lag flow (D3 gallery ref)
fd2f50e feat(trade-dashboard): AI signal Sankey diagram (D3 gallery ref)
4127e09 docs: mark all 11 D3 gallery chart backlog items as completed
c26ca06 fix(graph): lower default edge_threshold so the graph isn't empty by default
45359ac feat(graph): show loaded node/edge counts in hero badges
```
（另外還有 3 個更早的：`ad8165c`/`d906cd7`/`5b527a7`——首頁版本號/build time + PageCounter 修正，見上一版 SOP。再更早的 6 個 + `2f23f88` TA-Lib wheel 修正，都已 push，內容見 git log，不重複贅述。）

**這次沒有再發生**上一版 SOP 記錄的 `.git/index` 損毀或 `error: bad signature`；但發生了一個**新的、更隱蔽的變體**，細節見第 3 節「環境雷」。

---

## 2. 這次做了什麼（依時間序）

1. **頁面觀測重點（觀測重點 banner）**：每個非首頁頁面上方加一個 `PageFocusBanner` 元件，說明「這頁該看什麼」；同時寫了 `docs/06-頁面觀測重點與改動清單.md` 記錄每頁的觀測重點、現況落差、改動項目。
2. **Rotation 全螢幕 bug 修復**：根因是 `v-reveal` 動畫用完沒清 `will-change: transform`，導致 `position: fixed` 的全螢幕卡片相對於錯的 containing block 定位。修在共用的 `directives/reveal.js`，全站任何全螢幕/彈窗都受惠，不只 Rotation。
3. **研究 D3 gallery，列出 11 個可套用在股票分析的圖表**，寫進 `docs/06` 第五節，並**全部實作完成**（不是只列清單）：
   - Treemap（Overview，每日類股熱力圖）
   - Box plot（Seasonal，各月報酬箱型圖）
   - PE/PB 河流圖 + 營收成長圖（PublicData，沿用既有 fundamental 端點，沒加新後端）
   - Histogram/KDE（RiskMonitor，權益日變動分布）
   - Calendar 熱力圖（Analysis，個股每日漲跌）
   - 相關矩陣熱力圖（Graph，網絡圖的另一種檢視模式）
   - Horizon chart（Rotation，多類股 RS-Ratio 一次比較）
   - Volume Profile（Analysis，因只有日 OHLCV、無逐筆成交，採「當日量平均分攤到高低價區間」近似算法，畫面有標註）
   - Chord diagram（Rotation，沿用領先落後 `lead_edges` 資料）
   - Sankey diagram（TradeDashboard，因無真實部位/交易資料，改以 AI 訊號信心度為權重的示意圖，畫面有標註非真實資金流；手刻 ribbon 版面，因為沙盒 npm registry 擋掉 `d3-sankey` 安裝）
   - 每張圖下方都加註「參考：D3 gallery - <名稱>」
4. **修復 `/graph` 頁「只有節點沒有邊」的 production bug**：用 Chrome MCP 直接打正式站 API 驗證，發現預設門檻 `edge_threshold=0.35` 遠高於實際算出來的 fusion/lead/chip 權重（多落在 0.06~0.32），加上 FinMind 產業資料在正式站缺失（`industry` 恆為「未知產業」）讓 fusion 權重被結構性壓低，導致預設幾乎必為空圖。改成 0.12（貼近建邊門檻本身），前後端三處預設值一併修正，已用正式站 API 驗證有效。
5. **加上「已載入節點/邊」數量顯示**：`/graph` 頁 hero 區塊新增即時顯示目前層級載入的節點數與邊數，之後遇到類似空圖問題能一眼看出是門檻/層級造成的，不用再靠猜測。

---

## 3. 開發時踩過的環境雷（新 session 一定要知道）

> **重要**：以下大多是**這次交接時所在的 Cowork 沙盒環境**特有的雷，如果下一個 session 是 **Claude Code 直接跑在使用者自己的 Windows 機器上**（原生檔案系統，沒有沙盒掛載層），下列大部分問題應該不會重現。但 git 安全習慣（commit 前後驗證）是好習慣，建議繼續保留。

- **（沙盒特有）Edit 工具寫入的檔案，bash 讀出來會截斷或跟 Windows 側 Read 出來的內容不一致**：這是掛載層的快取問題，不是真的檔案壞掉。每次改完較大的檔案，一律用「`git show HEAD:<path>` 當基底 + Python 腳本原樣重做同一組 `old_string`/`new_string` 替換 + 直接 `open(path,'w').write()` 整份覆寫」，比信任 Edit 工具寫完之後 bash 立刻讀到的內容更可靠。
- **（沙盒特有、這次新發現的變體）`git add` 有時會「假裝」add 成功，但其實把舊內容的 blob 存進 index**：症狀是 `git diff --cached --stat` 顯示空白（看起來像沒有變更要 commit），但檔案內容其實已經改了。**判斷方式**：比對 `git hash-object <path>`（工作目錄實際內容的 hash）跟 `git rev-parse HEAD:<path>`（HEAD 版本的 hash），如果兩者相同但你確定檔案內容不同，就是踩到這個雷。**修法**：跟上一條一樣，透過 Python 直接重寫檔案（而不是用 Edit 工具寫完直接 `git add`），重寫後再 `git add`，並用 `git ls-files -s <path>` 的 hash 跟 `git hash-object <path>` 比對確認一致，才能放心 commit。這次在 `docs/06-...md`、`backend/app/api/graph.py`、`backend/app/analysis/watch_graph.py` 都各踩過一次，都靠這個方法抓出來並修正，**沒有留下錯誤的 commit**。
- **（沙盒特有）bash 沙盒對外網路連不到 `github.com`／`pypi.org`／`registry.npmjs.org`**：`git push`、`git fetch`、`pip install`、`npm install <新套件>` 全部會失敗（proxy 403）。這次因此無法安裝 `d3-sankey`，改用純 `d3.path` 手刻 ribbon 版面繞過；push 也一律靠使用者在自己機器上執行。
- **（一般性、建議保留）每次改完檔案，一定要做這三件事再進行下一步**：
  1. `wc -l` / `tail -N` 確認檔案結尾正常、沒有被截斷
  2. `python3 -c "print(open(f,'rb').read().count(b'\x00'))"` 確認沒有 null bytes
  3. 後端用 `python3 -m py_compile`；前端 `.vue` 用 `@vue/compiler-sfc` 的 `parse()` + `compileScript()`（要從 `frontend/` 目錄執行，讓 `node_modules` 解析得到）
- **（一般性、建議保留）commit 前後都用 `git diff --cached --stat` 確認變更範圍跟預期一致**，不要只看 `git status` 的清單就 commit——尤其如果 diff 顯示「沒有變更」但你確定改了檔案，先照上面那條懷疑並排查，不要直接跳過。
- **前端建置在 Cowork 沙盒裡跑不動**：`npm run build` 會因為缺 `@rollup/rollup-linux-x64-gnu` 原生模組失敗，這是沙盒環境本身的問題、跟程式碼改動無關。如果新 session 也是類似沙盒環境，一樣只能靠 `@vue/compiler-sfc` 做語法檢查，實際 build 驗證要請使用者在本機跑 `npm run build`。如果新 session 是 Claude Code 跑在使用者本機，這個限制應該不存在，可以直接跑 `npm run build` 驗證。

---

## 4. 開發約定（沿用專案既有規則，沒有變動）

- 每輪只做一個可驗證小增量，commit message 用 Conventional Commits（`feat/fix/docs/chore`）。
- 文案一律繁體中文。
- 後端 API 統一回傳 `{"success": true, "data": ...}`；金融數值防 NaN 靠 `SafeJSONResponse`。
- 前端樣式只用 `assets/main.css` 的 CSS 變數，不要硬編色碼；財經走勢圖用 `lightweight-charts`，其餘客製圖表（熱力圖/矩陣/Sankey/Chord 等）用 D3；動效用 `v-reveal`（內容預設可見＋failsafe，且已修正 will-change 洩漏問題）。
- **每個頁面（除首頁）要有 `PageFocusBanner` 說明觀測重點**，新增或修改頁面前先讀 `docs/06-頁面觀測重點與改動清單.md` 確認現有定位，改完要回頭同步這份文件的狀態欄。
- 秘密一律走環境變數（`config/settings.py` 讀），不可硬編碼。
- 詳細 SOP 見 `docs/00-開發流程.md`、開發約定見 `docs/04-開發指引.md`。

---

## 5. 已知可繼續的項目（非緊急，供下一輪參考）

- 各 view `<style>` 內非 token 的深淺變化色（badge 淡色調等）如要收斂，需新增 `--color-up-soft` 之類的 tint token 再分批換。
- `lightweight-charts` / D3 的 JS 內色碼（chart config 吃不到 CSS 變數，需 `getComputedStyle` 讀 token，屬較大重構）。
- **`/graph` 頁的產業關聯層長期是空的**：正式站 FinMind 回傳的產業資料全部是「未知產業」（`info_df` 抓不到或欄位對不上），導致 `industry` 層一直沒有邊、fusion 權重也因此被結構性壓低。這次只調整了預設門檻讓已有的 lead/chip 邊能顯示，沒有動 FinMind 產業資料抓取本身——如果要根治，需要查 `ingest_watchlist_raw()` 裡 `finmind.get_stock_info()` 為什麼在正式站抓不到 `Industry_category`。
- Volume Profile／Sankey 目前都是「近似/示意」算法（畫面已標註），如果未來拿到真實逐筆成交或真實部位資料，這兩張圖都可以換成真實資料版本。
- UI/UX 視覺優化尚未系統性做過，見新增的 `docs/07-UIUX交接摘要.md`，建議交給 Claude Design 那邊的新對話處理。

---

## 6. 頁面總覽（給接手的人快速定位）

完整清單與各頁「觀測重點」見 `docs/06-頁面觀測重點與改動清單.md`；路由定義在 `frontend/src/router.js`。重點頁面：

| 路徑 | 頁面 | 觀測重點（一句話） |
|---|---|---|
| `/` | 首頁 | 導覽入口，不套用觀測重點 banner |
| `/overview` | 總覽 | 綜合健康度，含每日類股熱力圖 |
| `/decision` | 決策面板 | 今日所有股票的 BUY/SELL/HOLD 一覽 |
| `/graph` | 觀察股關聯圖 | 關聯強度與網絡結構（力導向/階層邊綁定/矩陣三種檢視） |
| `/rotation` | 類股輪動 | RRG 象限、領先落後、Horizon chart、Chord diagram |
| `/stocks/:symbol` | 個股分析 | 技術面是否支持進出場，含日曆熱力圖、Volume Profile |
| `/stocks/:symbol/backtest` | 回測 | 策略歷史績效 |
| `/stocks/:symbol/seasonal` | 季節性 | 季節性慣性，含箱型圖 |
| `/stocks/:symbol/lead-lag` | 領先落後 | 個股與大盤/類股的領先落後關係 |
| `/stocks/:symbol/major-players` | 主力籌碼 | 主力成本與動向 |
| `/stocks/:symbol/chip` | 籌碼分析 | 三大法人買賣超 |
| `/stocks/:symbol/social-buzz` | 社群熱度 | 社群討論熱度 |
| `/stocks/:symbol/public-data` | 公開資訊 | 便宜或昂貴判斷，含 PE/PB 河流圖、營