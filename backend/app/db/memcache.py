"""Process-local TTL cache for read-heavy graph/rotation endpoints.

節點/邊資料的計算要掃 MongoDB 多個 collection，前端每次切日期/門檻都重打
一輪很慢。這裡把「DB 載入＋計算完成的結果」留在記憶體，同參數的請求直接
從記憶體回；/build 重抓原始資料時按前綴清空，避免拿到舊圖。

單進程 dict 快取即可：部署是單一 uvicorn service，不需要跨進程一致性。
"""

from __future__ import annotations

import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}
_MAX_ENTRIES = 512


def mem_get(key: str) -> Any | None:
    entry = _store.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        _store.pop(key, None)
        return None
    return value


def mem_set(key: str, value: Any, ttl_seconds: float = 600) -> None:
    if len(_store) >= _MAX_ENTRIES:
        # 超量時先掃掉過期項，仍滿則丟最舊的一批，避免無上限成長
        now = time.monotonic()
        for k in [k for k, (exp, _) in _store.items() if exp < now]:
            _store.pop(k, None)
        while len(_store) >= _MAX_ENTRIES:
            _store.pop(next(iter(_store)), None)
    _store[key] = (time.monotonic() + ttl_seconds, value)


def mem_clear(prefix: str = "") -> int:
    keys = [k for k in _store if k.startswith(prefix)]
    for k in keys:
        _store.pop(k, None)
    return len(keys)
