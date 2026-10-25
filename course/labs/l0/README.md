# Lab L0：跑起第一個 session

## 步驟

1. 依官方 Quickstart 安裝 Claude Code，確認終端機執行 `claude --version` 會印出版本
2. 建一個練習用的 repo：

   ```bash
   mkdir claude-lab && cd claude-lab
   git init
   echo "# Claude Lab" > README.md
   git add . && git commit -m "init"
   ```

3. 在這個資料夾執行 `claude`，請它：「幫我在 README 加一段說明這個 repo 是練習用的」
4. 允許編輯後，用 `git diff` 看它改了什麼
5. 輸入 `/context` 看看目前 context 的組成
6. 按 Esc 兩下打開 rewind，試著退回修改；再用 `git status` 確認檔案回到原狀

## 驗收

```bash
python check.py .
```
