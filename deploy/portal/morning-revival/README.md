# 晨興聖言（/morning-revival/）

入口頁底下的靜態頁：左欄是各週標題選單，右欄是該週的「鳥瞰」與「生活應用」。

## 檔案

- `index.html`：外框（左右兩欄、參考來源連結）。
- `mr.css`、`mr.js`：樣式與載入邏輯。顏色用 `/theme/theme.css` 的變數，6 個色彩主題都適用。
- `weeks.json`：選單。依訓練分組，`latest` 是沒指定週次時預設開啟的那一週。
- `weeks/<id>.html`：每週一個 HTML 片段（不含 `<html>`、`<head>`），點選單時才載入。

## 每週新增一課

1. 複製最近一週的片段，改成新檔名，例如 `weeks/2026-09-w03.html`，再換掉內容。
2. 在 `weeks.json` 對應的訓練底下加一筆 `{ "id": …, "no": "第三週", "title": … }`，並把 `latest` 改成新的 id。
   新的訓練就在 `trainings` 最前面加一組。
3. `python scripts/check-morning-revival.py` 通過後 commit，跑 `deploy/scripts/ship.sh config`。
   推送只改這個資料夾時，pre-push 會改跑這支靜態檢查，不跑整套 E2E。

整套每週流程（NotebookLM → 核對 → 做網頁）寫在使用者層級的 skill `morning-revival-weekly`。

## 經文

片段裏不放經文本文，只寫出處，由 `mr.js` 在讀者打開時即時向網上聖經恢復本取全文：

```html
<ul class="verses">
  <li data-ref="1:17:1,9-10">創十七1，9～10</li>
</ul>
```

- `data-ref` 是「書卷編號:章:節」，書卷編號同恢復本網站（創世記 1、出埃及記 2 …… 馬太福音 40 …… 啟示錄 66）。
- 節可寫範圍與逗號：`2-4`、`1,16-19`。跨章就寫兩組，用空白分開：`1:17:27 1:18:1`。
- 好處是經文一定和恢復本一致，不必再人工校對；恢復本網站連不上時，會顯示「請點出處到恢復本網站看」。

## 版面元件（風格⑦筆記本＋⑧手繪圖，第四週起使用）

- `.sticky` 便利貼（每週一則，放最重要的一個數字）、`.sum` 一句話摘要（`.key` 紅字、`.hl` 螢光筆，各最多 2 處）。
- `.cards` 色卡，顏色有固定意義：藍 `.card`＝經文要點，紫 `.card.purple`＝負擔與建議，橘 `.card.orange`＝問題或待補。
- `.groups` + `.zone` 虛線框＝中點分組。
- `figure.sketch` 手繪流程圖：寬螢幕 `svg.h`、窄螢幕 `svg.v` 各畫一張；線色 藍＝起點、綠＝過程、橘＝結果，每張圖都要有 `.legend` 圖例。
  兩張 SVG 的 filter／marker id 要不同（例如 `rough-h`／`rough-v`）。範例見 `weeks/2026-09-w04.html`。

## 內容原則

- 引用書報原文或屬靈前輩的見證，要先對照原書核實才放；沒核實的寫一個 `.note` 說明暫不放。
- 晨興聖言課文本身不轉貼，只放自己的整理（鳥瞰、生活應用），並在左欄連到參考來源。
- 這個站台開了 Caddy templates，HTML 片段裏不能出現連續兩個左大括號。
