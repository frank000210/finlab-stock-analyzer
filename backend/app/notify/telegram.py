import httpx


async def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    # EE10：跟 LineNotifier.send() 一樣把例外包在函式自己裡面——之前這裡沒包，
    # 網路暫時性錯誤（DNS/逾時/連線被拒）會整個往外丟，讓呼叫端（例如
    # admin.py 的 /notify/test）收到未處理的 500，跟 LINE 那條路徑同樣失敗
    # 情境卻回傳乾淨的錯誤訊息不一致。
    # LL1：先前用 parse_mode="HTML"，但所有呼叫端（risk.py 的 /notify、
    # 每日日報、價格警報觸發）傳進來的都是純文字，從未用到 HTML 標籤——
    # /notify 端點會把使用者從前端傳來、完全未跳脫的字串原樣塞進這裡，等於
    # 讓任何呼叫端都能在站主自己的 Telegram 裡插入粗體/可點擊連結，冒充
    # 合法警報做社交工程。改成純文字，沒有任何呼叫端需要 HTML 格式。
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message},
            )
            return resp.status_code == 200
    except Exception:
        return False
