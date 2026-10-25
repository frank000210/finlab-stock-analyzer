# Lab U6：用 hook 做護欄

把本資料夾的 `hooks/` 複製到練習 repo 的 `.claude/hooks/`。

## 1. 擋危險指令（PreToolUse）

打開 `.claude/hooks/block_dangerous.py`，完成 `TODO`：讓下面三種指令被擋下（exit 2），一般指令放行（exit 0）。

- `rm -rf /` 或 `rm -rf ~`
- `git push --force`（包含 `-f`）
- `git reset --hard`

在 `.claude/settings.json` 註冊為 `PreToolUse`、matcher `Bash` 的 hook。

**手動測試**（不用開 Claude）：

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force"}}' | python .claude/hooks/block_dangerous.py; echo "exit=$?"
```

應該看到 stderr 訊息與 `exit=2`。再開 Claude 請它「強制推送到 main」，確認被擋下、而且它收到了你寫的原因。

## 2. 讀過外部內容後降級

`mark_tainted.py`（PostToolUse）與 `taint_gate.py`（PreToolUse）已經寫好，請：

1. 讀懂兩支腳本在做什麼
2. 依課程內容在 `.claude/settings.json` 註冊：
   - `PostToolUse`，matcher `WebFetch|WebSearch|mcp__.*` → `mark_tainted.py`
   - `PreToolUse`，matcher `Bash` → `taint_gate.py`
3. 把 `.claude/state/` 加進 `.gitignore`
4. 測試：請 Claude 抓一個網頁，之後再請它 `git push`，應該會跳出確認，原因是「讀過外部內容」

## 3. 自動格式化（PostToolUse，選做）

加一個 `Edit|Write` 的 PostToolUse hook，對被修改的檔案執行你專案的格式化工具。

## 驗收

```bash
python check.py .
```

`check.py` 會用範例輸入實際執行你的 hook 腳本，確認擋下與放行的行為都正確。
