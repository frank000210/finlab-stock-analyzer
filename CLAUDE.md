<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->

## Knowledge Base MCP Server (kb-web)

A **global MCP server** (`kb-web`) is installed at `C:\Users\frank\.claude\mcp-servers\kb-web\server.py` and registered in `~/.claude.json`. It is available in **every local Claude Code session** without any extra setup.

Three tools are exposed:

| Tool | Purpose |
|---|---|
| `kb_ask(question, domain?)` | 向知識庫提問，回傳 AI 答案 + 引用來源 |
| `kb_list_domains()` | 列出所有領域與文件數 |
| `kb_write(content, domain, title)` | 匯入 markdown 文件（post-commit 優化紀錄用） |

**When to use:**
- Before implementing a feature that might overlap with past decisions, call `kb_ask` to check for prior art or constraints.
- After every successful `git push`, call `kb_write` with `domain='dev_note'` to record what changed, what problems were encountered, and reusable lessons learned.

Auth is automatic: `KB_API_TOKEN` is read from the process env, falling back to the Windows User environment registry (`HKCU\Environment`).

## Post-push dev notes

After every successful `git push`, a PostToolUse hook (`.claude/hooks/post_push_devnote.py`) reminds Claude to write a markdown dev note (what changed, observations, lessons) and import it into the kb-web knowledge base (self-hosted, `https://kb.43-133-44-216.sslip.io`) using the `kb_write` MCP tool (preferred) or `scripts/import-dev-note.sh` as fallback. One note per batch of changes — skip on retry pushes.

## PC／雲端交接（開工／收工／接手）

使用者晚上 8–12 點在 PC（`F:\github\finlab-stock-analyzer`）工作，白天在雲端的 Claude Code 接續前一晚沒做完的事；上線一律留到晚上在 PC 做。三句口令兩邊通用，聽到就照下面做，不必再問流程。

東西放哪裡：

- **GitHub**：程式、網頁、交接單正本 `docs/handoff/交接單.md`（最新一筆在最上面）。
- **知識庫**（kb-web，domain=`handoff`）：兩邊要分享的資料——交接單副本、`docs/handoff/` 下的文件、新增或大改的規格／說明文件。開發筆記照舊用 domain=`dev_note`。
- **Google Drive**：原始素材（NotebookLM 稿、逐字稿），只讀。

寫進知識庫時檔名一律帶日期（`handoff-YYYY-MM-DD-pc.md`、`handoff-YYYY-MM-DD-cloud.md`），同 domain 同檔名會互相覆蓋。

**只有 PC 能讀寫知識庫**（`kb_write`／`kb_ask`）。雲端連不到 `kb.43-133-44-216.sslip.io`：雲端環境的工具不接受這種由 IP 組成的主機名，2026-11-17 試過加入允許清單與存憑證都被拒絕。所以雲端要分享的東西一律放進 `docs/handoff/`，由 PC 在「開工」時代為寫進知識庫；雲端要查過去的資料就讀 `docs/handoff/` 與 `docs/`。主機換成正式網域後，雲端可改用 `scripts/import-dev-note.sh <檔案> handoff` 直接寫，屆時再改這一段。

### 「收工」（PC，晚上結束時）

1. `git status`；把當晚的改動 commit。做到一半、還不能進 master 的，放到 `wip/<日期>-<主題>` 分支再 commit。
2. 在 `docs/handoff/交接單.md` 最上面加一筆：今晚做完什麼、還剩什麼（寫到雲端可以直接接著做的程度：檔案、下一步、驗收方式）、卡在哪、哪些只能在 PC 做。
3. push（含交接單）。
4. 交接單這一筆與當晚新增的文件寫進知識庫（domain=`handoff`）。
5. 回報三件事各自成功與否：已推送、交接單已更新、知識庫已寫入。

### 「接手」（雲端，白天）

1. `git fetch origin`，從最新的 `origin/master`（交接單若指到 `wip/` 分支就從那裡）開 `cloud/<日期>` 分支。
2. 讀交接單最上面一筆，照「還剩什麼」往下做；標明只能在 PC 做的項目不碰。
3. 每完成一段就 commit 並 push 到 `cloud/<日期>`。**不推 master、不部署。**
4. 結束前在交接單最上面加一筆：白天做完什麼、怎麼驗證的、哪些等著上線（各要跑哪個 `ship.sh`）、留給晚上的事、要請 PC 寫進知識庫的檔案清單；push。推送後的開發筆記 hook 在雲端做不了，把筆記內容寫在交接單裡，由 PC 歸檔。
5. 雲端跑不了整套 Playwright（沒有 FinMind 金鑰與正式資料），只跑後端 pytest、前端建置、靜態檢查；交接單要寫清楚哪些沒驗到。

### 「開工」（PC，晚上開始時）

1. `git fetch origin`，找出還沒合併進 master 的 `cloud/*` 分支。
2. 讀該分支上的交接單最上面一筆，向使用者報告：白天做了什麼、哪些沒驗到、哪些等著上線。
3. 把雲端這一筆交接單（標題 `handoff-YYYY-MM-DD-cloud`）和它列出的檔案用 `kb_write` 寫進知識庫（domain=`handoff`），並回報寫入結果。
4. 先不合併。使用者說「合併」才合進 master；說「上線」才合併＋跑整套 E2E＋`deploy/scripts/ship.sh <服務>`。
5. 合併後刪掉已合併的 `cloud/*` 分支。
