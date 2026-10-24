# Lab U2：權限規則與第一個 MCP server

## 1. 權限規則

在練習 repo 建立 `.claude/settings.json`：

- `deny` 至少一條保護機密檔案的 `Read(...)` 規則（例如 `Read(./.env)`）
- `allow` 至少一條你常用、安全的 `Bash(...)` 指令（例如 `Bash(git status)`）
- `ask` 至少一條需要人確認的指令（例如 `Bash(git push *)`）

建立一個假的 `.env`（內容隨便寫），然後請 Claude「讀一下 .env 的內容」，確認它被擋下。

## 2. 第一個 MCP server

1. 安裝官方 SDK：`pip install mcp`
2. 把本資料夾的 `server.py` 複製到練習 repo，完成 `TODO`：再加一個工具 `reverse_text(text: str) -> str`，回傳反轉的字串
3. 加入 Claude Code（project scope 會寫進 `.mcp.json`）：

   ```bash
   claude mcp add --scope project --transport stdio course-demo -- python server.py
   ```

4. 重開 session，輸入 `/mcp` 確認 `course-demo` 已連線
5. 請 Claude「用 reverse_text 把『Claude Code』反轉」

## 3. 觀察真實案例（選做）

打開 finlab 專案的 `kb-web` MCP server（`C:\Users\<你>\.claude\mcp-servers\kb-web\server.py` 或 repo 的 `kb-web/`），看它如何定義 `kb_ask`、`kb_write` 兩個工具、如何從環境變數讀取 token。

## 驗收

```bash
python check.py .
```
