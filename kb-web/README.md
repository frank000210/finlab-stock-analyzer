# 知識庫網頁 (kb-web)

Vue + FastAPI 網頁，讓知識庫（patent / finlab / 未來更多領域）可以透過網頁匯入資料、並用 Claude 做對話式問答。規格書見 [`docs/08-知識庫網頁規格.md`](../docs/08-知識庫網頁規格.md)。

## 本機開發

### 後端

```powershell
cd kb-web/backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt

$env:KB_MONGO_URI="mongodb://localhost:27017"
$env:KB_MONGO_DB="knowledge_base"
$env:KB_WEB_PASSWORD="<選一個密碼>"
$env:KB_API_TOKEN="<選一個 token>"
$env:JWT_SECRET="<隨機字串>"
$env:ANTHROPIC_API_KEY="<你的 Claude API key，留空則問答功能回 503>"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8090 --reload
```

跑測試：`.\.venv\Scripts\python.exe -m pytest tests/ -v`

### 前端

```powershell
cd kb-web/frontend
npm install
npm run dev
```

開 `http://localhost:5174`，vite.config.js 已把 `/api` proxy 到 `http://localhost:8090`。

## 環境變數（部署時在 Zeabur 服務設定）

| 變數 | 說明 |
|---|---|
| `KB_MONGO_URI` | MongoDB 連線字串；連到既有 Zeabur Mongo 時記得帶 `?authSource=admin` |
| `KB_MONGO_DB` | 固定 `knowledge_base` |
| `KB_WEB_PASSWORD` | 網頁登入密碼 |
| `KB_API_TOKEN` | 給 CLI/AI 工具用的獨立 token |
| `JWT_SECRET` | 簽 session token 用，隨機字串 |
| `ANTHROPIC_API_KEY` | 問答功能用 |
| `CORS_ORIGINS` | 允許的前端來源，逗號分隔 |

## CLI / AI 工具怎麼查詢

不用瀏覽器登入、不用知道 MongoDB 密碼，直接打 `/api/ask`：

```bash
curl -X POST https://<部署網址>/api/ask \
  -H "Authorization: Bearer $KB_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"上位語下位語怎麼判斷","domain":"patent"}'
```

回傳 `{"answer": "...", "citations": [{"title": "...", "source": "..."}]}`。

查有哪些領域、各幾篇：

```bash
curl https://<部署網址>/api/notebooks -H "Authorization: Bearer $KB_API_TOKEN"
```

## 已知限制

- 網頁上傳只接受 `.docx` / `.pptx` / `.pdf` / `.md` / `.txt`；`.doc` / `.ppt` 舊格式需要 LibreOffice 轉檔，請改用 `F:\knowledge_base` 的本機 CLI（見該目錄下 `knowledge-base-setup-guide.md`）。
- 網址匯入只能抓靜態/伺服器端渲染頁面，抓不到需要 JavaScript 才會顯示內容的動態網站。
