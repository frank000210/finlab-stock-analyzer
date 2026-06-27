"""Cache decorator for API endpoints."""

import functools
import json
from typing import Callable
from .cache import get_cache, set_cache


def cached(category: str, key_fn: Callable = None):
    """Decorator to cache async function results in MongoDB.
    
    Usage:
        @cached("stock_price", key_fn=lambda symbol, start, end: f"price:{symbol}:{start}:{end}")
        async def get_price(symbol, start, end): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                cache_key = f"{category}:{func.__name__}:{args}:{kwargs}"

            # Try cache first
            try:
                cached_data = await get_cache(cache_key)
                if cached_data is not None:
                    return cached_data
            except Exception:
                pass

            # Call original function
            result = await func(*args, **kwargs)

            # Store in cache (only if no error)
            if result and not (isinstance(result, dict) and result.get("error")):
                try:
                    await set_cache(cache_key, result, category)
                except Exception:
                    pass

            return result
        return wrapper
    return decorator
