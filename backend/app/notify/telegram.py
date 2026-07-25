import httpx


async def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    # EE10：跟 LineNotifier.send() 一樣把例外包在函式自己裡面——之前這裡沒包，
    # 網路暫時性錯誤（DNS/逾時/連線被拒）會整個往外丟，讓呼叫端（例如
    # admin.py 的 /notify/test）收到未處理的 500，跟 LINE 那條路徑同樣失敗
    # 情境卻回傳乾淨的錯誤訊息不一致。
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
            return resp.status_code == 200
    except Exception:
        return False
