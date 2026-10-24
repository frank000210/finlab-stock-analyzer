# Lab L9：建立 marketplace 並在另一個專案安裝

## 步驟

1. 建立 marketplace 結構，把 L8 的 plugin 放進去：

   ```bash
   mkdir -p my-marketplace/.claude-plugin my-marketplace/plugins
   cp -r my-toolkit my-marketplace/plugins/
   cp marketplace.json my-marketplace/.claude-plugin/marketplace.json   # 本資料夾的範本，改成你的資訊
   ```

2. 驗證：`claude plugin validate ./my-marketplace`
3. 加入並安裝：

   ```bash
   claude plugin marketplace add ./my-marketplace
   claude plugin install my-toolkit@my-marketplace
   claude plugin list
   ```

4. 到**另一個**專案資料夾開 Claude，確認 `/my-toolkit:daily-report` 可以用
5. 改一下 plugin 的 skill、把 `version` 改成 `1.0.1`，觀察更新行為
6. （選做）把 `my-marketplace` 推到 GitHub 私有 repo，改用 `claude plugin marketplace add <owner>/<repo>` 加入

## 驗收

```bash
python check.py ./my-marketplace
```
