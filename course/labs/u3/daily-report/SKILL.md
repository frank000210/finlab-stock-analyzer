---
name: daily-report
description: 產生今日工作日報。使用者說「寫日報」「今天做了什麼」時使用。
disable-model-invocation: true
allowed-tools: Bash(git log *) Bash(git diff --stat *)
---

## 今天的 commit
!`git log --since=midnight --pretty="- %s" || true`

## 今天改動的檔案
!`git diff --stat "HEAD@{midnight}" HEAD || true`

## 任務
根據上面的資料寫一份日報，格式：
1. **完成事項**：用一般人看得懂的話描述，不要直接貼 commit 訊息
2. **遇到的問題**
3. **明日待辦**
