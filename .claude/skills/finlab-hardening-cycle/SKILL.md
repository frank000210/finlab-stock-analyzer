---
name: finlab-hardening-cycle
description: finlab-stock-analyzer 的「自主循環優化」流程（盤點 N 項 → M 次自我審查 → 實作 → 驗證 → 出貨 → 寫改善紀錄）。使用者說「自主循環優化」「自行盤點可優化項目」「進度回報」或要開下一個字母系列（NN、OO…）時使用。
---

# finlab 自主循環優化

使用者的觸發語：「自主循環優化，自行盤點可優化項目 10 項並進行 3 次自我審查，審查完成後再開發。工作完成後，將優化項目記錄到 finlab-stock-analyzer 改善紀錄」。
變體「…待我核准再開發」＝列清單後等明確核准才動手；上面這句＝**不設核准關卡**，一路做到 commit + push + merge。

判斷原則：實作細節的模稜兩可自己決定、事後在回報說明；只有商業/產品決策、不可逆動作、指示互相衝突才問人。

## 0. 開工前
1. `git status` 確認 worktree 狀態。**每完成一個可驗證的段落就先 commit**——worktree 會被回收，沒 commit 的東西會直接消失（2026-10 發生過一次，靠舊 Docker 容器才救回部分檔案）。
2. 讀 `docs/改善紀錄.html` 的 `DATA` 陣列：已修過什麼、最後一個系列字母（下一輪接下去）。
3. （盡力而為）用 `kb_ask`（domain=`dev_note`）查過去踩過的坑。回 404 / 工具不可用就跳過，改以改善紀錄為準，不要卡住。

## 1. 盤點（真讀 code，不是腦補）
- 預設派 3 個平行 Explore agent：後端安全/穩健、前端競態/UX、測試涵蓋缺口。prompt 必須要求「先讀改善紀錄，別重報已修的」。
- agent 可能撞到帳號 session 上限而中途失敗（只會有部分結果）——失敗的那一路改自己直接查，不要重派燒額度。
- 每一項 agent 回報的發現，**自己對照原始碼驗證**後才採用；agent 可能很有自信地講錯。

## 2. 三次自我審查
每輪都問：這個修法的範圍對嗎？會不會悄悄改變線上行為？有沒有更小的修法？
常見的修正方向：發現只補一支端點不夠（同一單例還有別的寫入口）→ 擴大；發現「統一程式碼」會改變訊號觸發行為 → 縮小。審查結果寫進回報。

## 3. 實作慣例（照既有模式，不要發明新原語）
- **快取 key 升版**：快取內容的形狀或「產生它的 prompt」變了，key 版號就要升（`xxx:v2` → `v3`）。key 即使含日期也要升，否則當天舊快取會持續服務舊內容。
- **新增節流**：用 `db/cache.py` 的 `increment_rate_limit(key, "rate_limit")`（原子 `$inc`）＋ `api/analytics.py` 的 `_get_client_ip(request)`（防 X-Forwarded-For 偽造）。**加之前先 grep 現有 e2e 對該端點的呼叫量**，門檻要明顯高於測試用量（LL2/LL4 曾因此自己打壞測試）。
- **無上限的儲存/參數**：加上限（筆數、欄位長度、symbols 數量），仿 `news_checks` 的「只留最近 N 筆」。
- **前端 async 載入**：module 層 `let requestToken = 0`，進函式 `const token = ++requestToken`，每個狀態寫入前 `if (token !== requestToken) return`。不同生命週期的操作用各自的 token，別共用。
- **非冪等 POST** 不要套 `fetchWithRetry`（重試會重複建立）。
- LLM 提示詞：LLM 只解讀已算好的數字；對「近期消息面」一律禁止憑訓練資料陳述（見 `analysis/major_cost_ai.py` 規則 5）。
- **每個修正配一個回歸測試**（`e2e/tests/`），打真實後端、節流類要測「剛好門檻通過、超過一次 429」。

## 4. 驗證（順序與坑）
1. `python -m py_compile` 改過的後端檔；`cd frontend && npm run build`。
2. WSL 建 image，**用自己的 tag 與 port**（別搶共用的 `finlab-test`/8000）：
   `wsl -d Ubuntu -u root -- bash -lc "cd /mnt/f/github/finlab-stock-analyzer/.claude/worktrees/<wt> && docker build -t finlab-stock-analyzer:<tag> ."`
3. 起容器（PowerShell 才拿得到 Windows 環境變數；`.env` 在**主 repo 根目錄**，不在 worktree）：
   `docker run -d --name finlab-<tag> --network finlab-net -p <port>:8080 --env-file /mnt/f/github/finlab-stock-analyzer/.env -e MONGODB_URI=mongodb://mongo:27017 -e FINMIND_TOKEN='$env:FINMIND_TOKEN' -e OPENCODE_API_KEY='$env:OPENCODE_API_KEY' finlab-stock-analyzer:<tag>`
   `FINMIND_TOKEN`、`OPENCODE_API_KEY` 只存在 Windows 使用者環境變數，不在 `.env`。
4. **Playwright 一律從 Windows 端跑**：`cd e2e && BASE_URL=http://localhost:<port> npx playwright test --reporter=list > <logfile> 2>&1`。
   - 不要在 WSL 裡跑：WSL 會呼叫 Windows 的 node.exe，`BASE_URL` 不會傳過去，全部打到預設的 8000 → 幾百個 `ERR_CONNECTION_REFUSED`。
   - 不要接 `| tail`：exit code 會變成 tail 的、摘要行也可能被截掉。看 logfile 結尾的 `N passed`。
5. 新跑出大量失敗時**先讀** `e2e/test-results/*/error-context.md` 的第一個錯誤，再下判斷。

## 5. 失敗分流
| 症狀 | 判斷 |
|---|---|
| `ERR_CONNECTION_REFUSED` 在 :8000 | BASE_URL 沒生效/跑在 WSL（見上） |
| 外部 API 全 timeout，`ping 8.8.8.8` 正常，`ip link show eth0` 顯示 mtu 1500 | PMTU blackhole，非額度。`ip link set dev eth0 mtu 1350` ＋ iptables TCPMSS clamp |
| FinMind 402/403，但 WSL 內 curl 快速回應 | 真的額度用盡，等 30 分鐘，別狂重試 |
| pre-push 單一不相關測試 `page.goto/reload` 逾時 | 連續整套重跑的資源壓力；單獨重跑通過就重推一次，連兩次必敗才當真 |

## 6. 出貨
1. 掃 diff 有沒有金鑰；commit 訊息結尾加系統指定的 Co-Authored-By 行。
2. push feature branch → pre-push hook 會跑整套 Playwright（需先設 `git config core.hooksPath .githooks`）→ 再 push/merge master。**不要 `--no-verify`**。
3. master 推上去就是上線（Zeabur 由 master 部署）。

## 7. 收尾（缺一不算完成）
1. 在 `docs/改善紀錄.html` 的 `DATA` 最前面加一筆：`{date:'<commit 時間 YYYY-MM-DD HH:mm>', range:'NN1–NN10', title, summary, items:[{code, tag, text}]}`，tag ∈ `critical`/`warn`/`good`/`neutral`；回報給使用者時若 commit 還沒落地，可先用 `date:'進行中', inProgress:true`。
2. 用 Artifact 工具重新發佈：`file_path` = 該檔，`url` = `https://claude.ai/code/artifact/6499a3cc-40d1-42af-a0fc-52bb0573965c`（帶 url 才會原地更新）。
3. 把這份改善紀錄 commit 進同一輪（或緊接的小 commit）。
4. （盡力而為）`kb_write`（domain=`dev_note`，標題 `dev-note-YYYY-MM-DD-主題`）寫入本輪的做了什麼 / 觀察 / 心得。上版 hook 若存在會提醒；服務不可用時略過並在回報註明。
5. 回報：做了哪些項目、哪些決定與理由、哪些被降範圍、有什麼值得再看一眼。
