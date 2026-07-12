# FinLab Stock Analyzer 台股個股深度分析平台

單一台股個股深度分析 Web 應用，提供技術面、基本面、籌碼面分析與策略回測。

## 功能特色

- 📈 **技術分析**：K 線圖 + MA / Bollinger / MACD / KD / RSI 等指標，含成交量分佈（Volume Profile）與每日漲跌日曆熱力圖
- 📊 **基本面**：月營收、EPS、獲利率、負債比，含本益比河流圖（PE/PB Band）與營收成長圖
- 🏦 **籌碼面**：三大法人買賣超、持股比、融資融券、主力成本
- 🕸️ **觀察股關聯圖**：力導向圖／階層邊綁定／相關矩陣熱力圖三種檢視，追蹤標的間的領先落後與資金流向
- 🔁 **類股輪動**：RRG 象限圖、Horizon chart、Chord diagram，觀察類股輪動與資金擴散路徑
- 🤖 **AI 預測與決策面板**：Random Forest 機器學習漲跌預測，全市場 BUY/SELL/HOLD 一覽
- 🔄 **策略回測**：FinLab 風格回測引擎，支援多種內建策略
- 🛡️ **風控監控**：熔斷狀態、最大回撤、報酬分布 Histogram/KDE
- 📱 **LINE 通知**：買賣訊號即時推播

完整頁面清單見 [`docs/06-頁面觀測重點與改動清單.md`](docs/06-頁面觀測重點與改動清單.md)（每頁的觀測重點）與 [`docs/07-UIUX交接摘要.md`](docs/07-UIUX交接摘要.md)（設計 token 與視覺待辦）。

## 技術架構

| 層級 | 技術 |
|------|------|
| 前端 | Vue 3 + TradingView Lightweight Charts |
| 後端 | FastAPI (Python) |
| 資料來源 | FinMind API (主) + yfinance (備援) |
| ML | scikit-learn Random Forest |
| 部署 | Docker → Zeabur |

## 快速開始

### 後端
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env  # 填入 token
uvicorn app.main:app --reload
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker build -t finlab-stock-analyzer .
# 容器內服務跑在 8080；本機測試習慣把 host 埠對應到 8000。
docker run -p 8000:8080 --env-file .env finlab-stock-analyzer
```

本機一鍵啟動（含 MongoDB、從 Windows 環境變數帶入 `FINMIND_TOKEN`、自動 build 該路徑下的最新程式碼）：
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

**同時開多個 Claude Code session / worktree 時**：預設的 image/container 名稱與 port（8000）是共用的，兩個 session 都跑預設值會互搶同一個容器，導致其中一邊的 pre-push 測試意外打到另一邊的（可能是別的分支）程式碼。用 `-Name`/`-Port`/`-ProjPath` 給每個 session 自己的身分：
```powershell
scripts\run-local.ps1 -Name shaw -Port 8001 -ProjPath /mnt/f/github/finlab-stock-analyzer/.claude/worktrees/<worktree-name>
```
接著讓 e2e（含 `git push` 的 pre-push hook）指向這個獨立實例：
```powershell
$env:BASE_URL = "http://localhost:8001"
```

**WSL 在測試跑到一半自己斷線（container 秒斷、`wsl -l -v` 顯示 Stopped）**：這台機器上遇過的根因不是
Windows 睡眠（`powercfg` 顯示的閒置睡眠計時器可以用 `SetThreadExecutionState`(ES_SYSTEM_REQUIRED) 擋掉，
但擋住睡眠後 WSL 還是會斷），而是 **WSL 對單一 distro 的閒置關閉機制**：只要沒有一個 `wsl.exe`
client 持續 attach 著該 distro，WSL 就會把它關掉，即使裡面的 dockerd 背景服務還在跑也一樣——`.wslconfig`
的 `vmIdleTimeout` 對這個情況沒有幫助（那是控制「所有 distro 都停止後」整個共用工具 VM 多久關閉，跟單一
distro 自己被關掉是兩回事）。解法是背景常駐一個持續 attach 著該 distro 的 client：
```powershell
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-Command','while ($true) { wsl -d Ubuntu -u root -- bash -c "while true; do sleep 20; done"; Start-Sleep -Seconds 1 }'
```
驗證過：套用後跑完整套 e2e（~4 分鐘）與閒置 8 分鐘都沒有再斷線。

## API 文件
啟動後訪問 http://localhost:8000/api/docs (Swagger UI)

## 內建策略
- **MA Crossover** - 均線交叉
- **MACD Trend** - MACD 趨勢
- **Bollinger Breakout** - 布林通道突破
- **RSI Reversion** - RSI 反轉

## License
Private - All rights reserved.
