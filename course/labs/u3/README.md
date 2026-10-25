# Lab U3：參考型與動作型 skill

## 1. 動作型 skill：/daily-report

建立 `.claude/skills/daily-report/SKILL.md`（可以從本資料夾的 `daily-report/SKILL.md` 開始），要求：

- `description` 寫清楚觸發情境
- `disable-model-invocation: true`（日報由你決定何時產生）
- 至少一個 `` !`指令` `` 動態注入（例如今天的 git log）
- 有 `allowed-tools` 限定只能用到的 git 指令

測試：`/clear` 開新 session，輸入 `/daily-report`。

## 2. 參考型 skill

挑一份你專案裡「偶爾才需要」的知識（API 規範、命名慣例、資料表說明），做成 `.claude/skills/<名稱>/SKILL.md`：

- `user-invocable: false`
- `description` 寫出**什麼時候**該參考它
- 長的內容拆到同資料夾的另一個 `.md`，在 SKILL.md 裡用連結指過去

測試：開新 session，提出一個需要這份知識的需求，觀察 Claude 有沒有自己載入它。換三種不同說法試試看。

## 3. 反思（寫在 skill 的 README 或筆記裡）

- 哪些內容原本在 CLAUDE.md、現在搬進 skill？省下多少行？
- description 改過幾次才讓觸發變準？

## 驗收

```bash
python check.py .
```
