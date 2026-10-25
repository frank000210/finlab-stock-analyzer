# Lab U1：寫出好的 CLAUDE.md 與自訂 output style

在你的練習 repo（或一個你熟悉的小專案）完成以下三件事。

## 1. CLAUDE.md

1. 先執行 `/init` 讓 Claude 產生草稿
2. 照課程原則修改：
   - 至少一條**建置或測試指令**（用反引號包起來，例如 `` `npm test` ``）
   - 至少一條**具體可驗證**的程式碼慣例
   - 用 `##` 標題分段
   - **200 行以內**

## 2. 路徑限定規則

建立 `.claude/rules/` 底下至少一個 `.md` 檔，frontmatter 有 `paths`：

```markdown
---
paths:
  - "src/**/*.py"
---

# Python 規則
- 函式都要有型別註記
```

## 3. 自訂 output style

建立 `.claude/output-styles/coach.md`，frontmatter 至少有 `name` 和 `description`。可以參考本資料夾的 `coach.md` 範例。

完成後執行 `/output-style`，確認清單裡看得到你的 style，切換過去問一個問題，觀察回答方式的變化。

## 驗收

```bash
python check.py .
```
