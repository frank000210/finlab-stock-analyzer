"""美股指數與各類股龍頭名單（yfinance 代號）。

用途：
- 代號判別（美股走 yfinance 直查，不套 .TW 後綴、不打 FinMind）
- 中文名稱/產業標示（FinMind 全市場 info 只涵蓋台股）
- 搜尋與 Ctrl+K 快速切換的美股候選

清單刻意精簡：主要指數 + 每個大類股 2~4 檔龍頭。任何其他美股代號
（純字母，如 ORCL）一樣可以分析，只是名稱會顯示代號本身。
"""

US_SYMBOLS: dict[str, dict[str, str]] = {
    # ── 指數 ──
    "^GSPC": {"name": "標普500指數", "industry": "美股指數"},
    "^IXIC": {"name": "那斯達克綜合指數", "industry": "美股指數"},
    "^NDX": {"name": "那斯達克100指數", "industry": "美股指數"},
    "^DJI": {"name": "道瓊工業指數", "industry": "美股指數"},
    "^SOX": {"name": "費城半導體指數", "industry": "美股指數"},
    "^RUT": {"name": "羅素2000指數", "industry": "美股指數"},
    "^VIX": {"name": "VIX恐慌指數", "industry": "美股指數"},
    # ── 科技/半導體 ──
    "AAPL": {"name": "蘋果", "industry": "科技"},
    "MSFT": {"name": "微軟", "industry": "科技"},
    "GOOGL": {"name": "Alphabet(谷歌)", "industry": "科技"},
    "AMZN": {"name": "亞馬遜", "industry": "電商/雲端"},
    "META": {"name": "Meta(臉書)", "industry": "科技"},
    "NVDA": {"name": "輝達", "industry": "半導體"},
    "AVGO": {"name": "博通", "industry": "半導體"},
    "AMD": {"name": "超微", "industry": "半導體"},
    "QCOM": {"name": "高通", "industry": "半導體"},
    "INTC": {"name": "英特爾", "industry": "半導體"},
    "TSM": {"name": "台積電ADR", "industry": "半導體"},
    "ORCL": {"name": "甲骨文", "industry": "軟體"},
    "CRM": {"name": "Salesforce", "industry": "軟體"},
    "NFLX": {"name": "網飛", "industry": "媒體"},
    # ── 電動車/工業 ──
    "TSLA": {"name": "特斯拉", "industry": "電動車"},
    "CAT": {"name": "開拓重工", "industry": "工業"},
    "BA": {"name": "波音", "industry": "航太"},
    "GE": {"name": "奇異航太", "industry": "航太"},
    # ── 金融 ──
    "JPM": {"name": "摩根大通", "industry": "金融"},
    "BAC": {"name": "美國銀行", "industry": "金融"},
    "GS": {"name": "高盛", "industry": "金融"},
    "V": {"name": "Visa", "industry": "支付"},
    "MA": {"name": "萬事達卡", "industry": "支付"},
    "BRK-B": {"name": "波克夏B", "industry": "多元控股"},
    # ── 醫療 ──
    "LLY": {"name": "禮來", "industry": "製藥"},
    "UNH": {"name": "聯合健康", "industry": "醫療保險"},
    "JNJ": {"name": "嬌生", "industry": "製藥"},
    "PFE": {"name": "輝瑞", "industry": "製藥"},
    # ── 能源 ──
    "XOM": {"name": "埃克森美孚", "industry": "能源"},
    "CVX": {"name": "雪佛龍", "industry": "能源"},
    # ── 消費 ──
    "WMT": {"name": "沃爾瑪", "industry": "零售"},
    "COST": {"name": "好市多", "industry": "零售"},
    "KO": {"name": "可口可樂", "industry": "飲料"},
    "PEP": {"name": "百事", "industry": "飲料"},
    "MCD": {"name": "麥當勞", "industry": "餐飲"},
    "NKE": {"name": "耐吉", "industry": "運動用品"},
}


def is_tw_symbol(symbol: str) -> bool:
    """台股代號：4~6 位數字，可帶一位英文尾碼（如 00878B）。"""
    import re

    return bool(re.fullmatch(r"\d{4,6}[A-Z]?", (symbol or "").strip().upper()))


def us_name(symbol: str) -> str:
    return US_SYMBOLS.get((symbol or "").strip().upper(), {}).get("name", "")


def us_industry(symbol: str) -> str:
    return US_SYMBOLS.get((symbol or "").strip().upper(), {}).get("industry", "")
