# 學習中心教材：從 AI Agent 原理到 Claude Code 客製化

網站上的 `/learn` 頁面讀的就是這個資料夾。改教材只要改這裡的檔案，不用動程式碼。

## 結構

| 路徑 | 內容 |
|---|---|
| `catalog.json` | 階段（stages）與單元（units）清單：標題、摘要、學習目標、是否必修、是否有測驗、lab 路徑 |
| `units/<id>.md` | 單元內容（Markdown）。`##` 標題會變成網頁上的目錄與錨點 |
| `quizzes/<id>.json` | 單元測驗題庫；`placement.json` 是程度檢測 |
| `labs/<id>/` | 實作步驟 `README.md`、起始檔、自動驗收 `check.py` |

## 題庫格式

```json
{
  "pass_ratio": 0.8,
  "questions": [
    {
      "id": "q1",
      "question": "題目",
      "options": ["A", "B", "C", "D"],
      "answer": 1,
      "explain": "答錯時顯示的解析",
      "section": "對應單元裡的 ## 標題文字（完全一致）"
    }
  ]
}
```

- `answer` 是選項索引（從 0 開始），**只留在後端**，不會送到瀏覽器
- `section` 必須跟單元 Markdown 裡某個 `##`／`###` 標題**一字不差**，答錯時的「回到這一段複習」靠它定位
- `placement.json` 的每題改用 `tag`（單元 id）：某單元的題目全對，就視為已具備該單元

## 修改後的檢查

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_course.py -q
```

會檢查：每個單元都有 Markdown、題庫答案在選項範圍內、每題 `section` 都對得到標題、`catalog.json` 的 `quiz` 旗標與題庫檔案一致。

## 新增單元

1. 在 `catalog.json` 的 `units` 加一筆（`id` 用小寫英數，`order` 決定排序）
2. 新增 `units/<id>.md`
3. 有測驗就加 `quizzes/<id>.json`，並把 catalog 的 `quiz` 設成 `true`
4. 有 lab 就加 `labs/<id>/README.md` 與 `check.py`，並設定 catalog 的 `lab`
5. `required: true` 的單元會列入結業條件（送出期末專題前必須通過測驗）

## 相關程式

- 後端：`backend/app/api/course.py`（API）、`backend/app/course/`（讀教材、批改、AI 助教提示詞）
- 前端：`frontend/src/views/Learn*.vue`、`frontend/src/components/course/`
- MongoDB 集合：`course_users`（本機帳號）、`course_progress`（進度）、`course_projects`（期末專題與證書）
