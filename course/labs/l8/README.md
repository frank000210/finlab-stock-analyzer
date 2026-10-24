# Lab L8：把設定打包成 plugin

把 U3–U6 在練習 repo 做的 skill、subagent、hook 打包成 `my-toolkit` plugin。

## 步驟

1. 建立結構（本資料夾的 `plugin.json` 是範本）：

   ```bash
   mkdir -p my-toolkit/.claude-plugin my-toolkit/hooks
   cp plugin.json my-toolkit/.claude-plugin/plugin.json   # 改成你的名字
   cp -r .claude/skills my-toolkit/
   cp -r .claude/agents my-toolkit/
   cp .claude/hooks/*.py my-toolkit/hooks/
   ```

2. 建立 `my-toolkit/hooks/hooks.json`：把 `.claude/settings.json` 的 `hooks` 物件搬過來，並把指令路徑改成 `${CLAUDE_PLUGIN_ROOT}/hooks/...`
3. 驗證：`claude plugin validate ./my-toolkit`
4. 載入測試：`claude --plugin-dir ./my-toolkit`，然後
   - 輸入 `/my-toolkit:daily-report`
   - 請 Claude「用 my-toolkit:code-reviewer 審查最近的修改」
   - 請它 `git push --force`，確認 hook 擋下
5. 確認沒問題後，刪掉 `.claude/` 裡的原始檔與 settings 的 `hooks`，避免重複

## 驗收

```bash
python check.py ./my-toolkit
```
