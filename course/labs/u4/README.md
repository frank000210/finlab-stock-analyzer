# Lab U4：拆解 Agent 迴圈、用 plan mode 做一個功能

## 1. 拆解一次 session

在練習 repo 請 Claude 完成一個小任務，並附上驗證方式，例如：

```text
新增一個 utils/slugify.py，把標題轉成網址用的 slug。
寫 tests/test_slugify.py 涵蓋中文、空白、大寫，pytest 要全部通過。
```

完成後按 **Ctrl+O** 打開詳細對話紀錄，把它的步驟分成三類，記到 `notes/u4-trace.md`（範本在本資料夾 `trace-template.md`）：

- **蒐集**：它讀了哪些檔案、搜尋了什麼
- **行動**：改了哪些檔案、跑了哪些指令
- **驗證**：怎麼確認做對了；有沒有失敗後再修正

## 2. 用 plan mode 做一個稍大的功能

1. 按 **Shift+Tab** 切到 Plan 模式
2. 提出一個會動到 2 個以上檔案的需求
3. 審它提出的計畫：有沒有漏掉的步驟？驗證方式夠不夠？在 `notes/u4-trace.md` 的「計畫審查」記下你修改了什麼
4. 確認後切回一般模式讓它執行

## 3. 練習 rewind

故意請它做一個你不想要的修改，然後用 **Esc 兩下** 或 `/rewind` 退回。

## 驗收

```bash
python check.py .
```
