import httpx


async def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        )
        return resp.status_code == 200
