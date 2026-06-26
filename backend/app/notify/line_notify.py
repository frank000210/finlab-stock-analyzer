"""LINE Notify integration for trading alerts."""

import httpx
from typing import Optional
from ..config.settings import get_settings


class LineNotifier:
    """Send notifications via LINE Notify API."""

    NOTIFY_URL = "https://notify-api.line.me/api/notify"

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_settings().line_notify_token

    async def send(self, message: str) -> bool:
        """Send a LINE notification message."""
        if not self.token:
            return False

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"message": message}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.NOTIFY_URL, headers=headers, data=payload
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def send_trading_alert(
        self, symbol: str, signal: str, price: float, strategy: str, reason: str
    ) -> bool:
        """Send a formatted trading alert."""
        emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "⚪"
        msg = (
            f"\n{emoji} {signal.upper()} Signal - {symbol}"
            f"\n💰 Price: {price}"
            f"\n📊 Strategy: {strategy}"
            f"\n📝 Reason: {reason}"
        )
        return await self.send(msg)

    async def test_connection(self) -> bool:
        """Test LINE Notify connection."""
        return await self.send("\n✅ FinLab Stock Analyzer 連線測試成功！")
