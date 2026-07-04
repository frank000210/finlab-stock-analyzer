"""共用相關係數工具。

lead_lag 與 watch_graph 過去各自實作 cross-correlation(守門樣本數、
NaN/零變異處理不同),可能對同一組序列給出不一致結論。統一收斂到
這個模組,兩邊共用同一套演算法與參數。

慣例:lag > 0 代表序列 a 領先序列 b lag 天(比較 a[:-lag] 與 b[lag:])。
"""

from __future__ import annotations

import numpy as np

# 相關係數最少樣本數(低於此數視為不可信,回 0)
MIN_SAMPLES = 20


def safe_corr(values_a, values_b, min_samples: int = MIN_SAMPLES) -> float:
    """Pearson 相關係數,含樣本數/零變異/NaN 防護,異常一律回 0.0。"""
    arr_a = np.asarray(values_a, dtype=float)
    arr_b = np.asarray(values_b, dtype=float)
    if len(arr_a) < min_samples or len(arr_a) != len(arr_b):
        return 0.0
    if np.std(arr_a) == 0 or np.std(arr_b) == 0:
        return 0.0
    corr = float(np.corrcoef(arr_a, arr_b)[0, 1])
    return corr if np.isfinite(corr) else 0.0


def lagged_pair(values_a, values_b, lag: int):
    """回傳依 lag 對齊後的 (a, b) 切片;lag > 0 表 a 領先 b。"""
    if lag > 0:
        return values_a[:-lag], values_b[lag:]
    if lag < 0:
        return values_a[-lag:], values_b[:lag]
    return values_a, values_b


def cross_corr_at_lag(values_a, values_b, lag: int, min_samples: int = MIN_SAMPLES) -> float:
    """單一 lag 的 cross-correlation(套用 safe_corr 防護)。"""
    if lag != 0 and (len(values_a) <= abs(lag) or len(values_b) <= abs(lag)):
        return 0.0
    a, b = lagged_pair(values_a, values_b, lag)
    return safe_corr(a, b, min_samples)


def best_lag_corr(
    values_a,
    values_b,
    max_lag: int = 5,
    min_samples: int = MIN_SAMPLES,
) -> tuple[int, float]:
    """在 1..max_lag 中找 |corr| 最大的 lag(a 領先 b),找不到回 (0, 0.0)。"""
    best_lag = 0
    best_corr = 0.0
    for lag in range(1, max_lag + 1):
        corr = cross_corr_at_lag(values_a, values_b, lag, min_samples)
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag
    return best_lag, best_corr
