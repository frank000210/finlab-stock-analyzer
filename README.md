# FinLab Stock Analyzer 台股個股深度分析平台

單一台股個股深度分析 Web 應用，提供技術面、基本面、籌碼面分析與策略回測。

## 功能特色

- 📈 **技術分析**：K 線圖 + MA / Bollinger / MACD / KD / RSI 等指標
- 📊 **基本面**：月營收、EPS、獲利率、負債比
- 🏦 **籌碼面**：三大法人買賣超、持股比、融資融券
- 🤖 **AI 預測**：Random Forest 機器學習漲跌預測
- 🔄 **策略回測**：FinLab 風格回測引擎，支援多種內建策略
- 📱 **LINE 通知**：買賣訊號即時推播

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
docker run -p 8000:8000 --env-file .env finlab-stock-analyzer
```

## API 文件
啟動後訪問 http://localhost:8000/api/docs (Swagger UI)

## 內建策略
- **MA Crossover** - 均線交叉
- **MACD Trend** - MACD 趨勢
- **Bollinger Breakout** - 布林通道突破
- **RSI Reversion** - RSI 反轉

## License
Private - All rights reserved.
