# Lab U5：唯讀審查 subagent 與平行稽核 skill

## 1. code-reviewer subagent

把本資料夾的 `code-reviewer.md` 複製到練習 repo 的 `.claude/agents/`，依你的專案調整審查重點。要求：

- `tools` **不能**包含 `Edit`、`Write`、`Bash`（唯讀）
- `description` 寫出什麼時候該派工給它

測試：改一段程式，然後說「用 code-reviewer 審查剛剛的修改」。觀察主對話只收到摘要，而不是它讀過的所有檔案。

## 2. 平行稽核 skill

建立 `.claude/skills/audit/SKILL.md`：

- `disable-model-invocation: true`
- 內文要求 Claude **平行派出至少兩個 subagent**，各自負責不同面向，最後合併報告
- 用 `$ARGUMENTS` 接收要稽核的目錄

測試：`/audit src/`

## 3. （選做）在 subagent 中執行的 skill

做一個 frontmatter 有 `context: fork` 與 `agent: Explore` 的 skill，例如「找出專案裡所有讀取環境變數的地方並列表」。

## 驗收

```bash
python check.py .
```
