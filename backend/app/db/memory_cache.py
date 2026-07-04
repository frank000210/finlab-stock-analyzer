"""程序內記憶體快取註冊表。

finmind_client / twse_public / social_buzz 各自維護模組層級的
in-memory TTL 快取,過去不受 /api/v1/cache 清除端點管轄。
它們在 import 時把自己註冊進來,cache API 即可統一查看與清除。
"""

from __future__ import annotations

from typing import Callable

# name -> (取得目前筆數, 清空並回傳清除筆數)
_REGISTRY: dict[str, tuple[Callable[[], int], Callable[[], int]]] = {}


def register(name: str, size_fn: Callable[[], int], clear_fn: Callable[[], int]) -> None:
    """註冊一個 in-memory 快取(重複註冊以最後一次為準)。"""
    _REGISTRY[name] = (size_fn, clear_fn)


def sizes() -> dict[str, int]:
    """回傳各記憶體快取目前筆數。"""
    return {name: size_fn() for name, (size_fn, _) in _REGISTRY.items()}


def clear(name: str | None = None) -> dict[str, int]:
    """清除指定(或全部)記憶體快取,回傳各自清除筆數。"""
    cleared: dict[str, int] = {}
    for cache_name, (_, clear_fn) in _REGISTRY.items():
        if name is None or cache_name == name:
            cleared[cache_name] = clear_fn()
    return cleared
