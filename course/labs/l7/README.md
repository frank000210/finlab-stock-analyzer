# Lab L7：狀態列與快捷鍵

## 1. 狀態列

1. 把本資料夾的 `statusline.py` 複製到 `~/.claude/statusline.py`
2. 在 `~/.claude/settings.json` 加上：

   ```json
   {
     "statusLine": { "type": "command", "command": "python ~/.claude/statusline.py" }
   }
   ```

3. 開新 session，底部應該出現 `[模型] 資料夾 @ 分支 | context xx% | $x.xx`
4. 改造它：加上你覺得有用的資訊（例如 context 超過 70% 時加一個 ⚠️）

手動測試：

```bash
echo '{"model":{"display_name":"Opus"},"workspace":{"current_dir":"/tmp/demo"},"context_window":{"used_percentage":42},"cost":{"total_cost_usd":0.12}}' | python ~/.claude/statusline.py
```

## 2. 快捷鍵

輸入 `/keybindings`，在 `Chat` 情境加一個綁定，例如把 `meta+g` 綁到 `command:compact`。存檔後立刻試用。

## 驗收

```bash
python check.py ~/.claude/statusline.py
```
