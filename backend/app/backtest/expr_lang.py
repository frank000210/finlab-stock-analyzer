"""買進/賣出條件運算式語言（BB1/BB2）。

使用者（或 AI）用像 `RSI(14) < 30 AND VOLUME_RATIO(20) > 1.5` 這樣的運算式
描述進出場條件。這裡**不是**執行任意程式碼——tokenizer/parser 只認得白名單
裡的指標名稱跟固定的文法，parse 不過就是不過，整個模組沒有 eval/exec，AI
生成的字串只能落在這個語法能表達的範圍內。

文法（NOT 優先權最高、AND 次之、OR 最低）：
    condition  := or_expr
    or_expr    := and_expr (OR and_expr)*
    and_expr   := not_expr (AND not_expr)*
    not_expr   := NOT not_expr | comparison
    comparison := term ( (COMPARE_OP | CROSS_OP) term )?
    term       := NUMBER | IDENT [ '(' NUMBER (',' NUMBER)* ')' ] | '(' or_expr ')'

comparison 的頂層一定要是 compare/cross/and/or/not 節點，不能只有一個裸指標
或裸數字（`RSI(14)` 單獨一條不構成合法條件，必須要有比較符號）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd


class ExpressionError(ValueError):
    """語法或語意錯誤。訊息設計成可以直接顯示給使用者看，不含內部細節。"""


# ---------------------------------------------------------------------------
# 指標詞彙表
# ---------------------------------------------------------------------------
ZERO_ARG_INDICATORS = {
    "CLOSE", "OPEN", "HIGH", "LOW", "VOLUME",
    "MACD_DIF", "MACD_DEA", "MACD_HIST",
    "BB_UPPER", "BB_MIDDLE", "BB_LOWER",
    "KD_K", "KD_D",
    "ADX", "PLUS_DI", "MINUS_DI",
}
ONE_ARG_INDICATORS = {"MA", "EMA", "RSI", "ATR", "VOLUME_RATIO"}
ALL_INDICATORS = ZERO_ARG_INDICATORS | ONE_ARG_INDICATORS

CROSS_ALIASES = {
    "CROSSES_ABOVE": "above", "CROSS_ABOVE": "above", "CROSS_UP": "above", "GOLDEN_CROSS": "above",
    "CROSSES_BELOW": "below", "CROSS_BELOW": "below", "CROSS_DOWN": "below", "DEATH_CROSS": "below",
}
_KEYWORDS = {"AND", "OR", "NOT"} | set(CROSS_ALIASES)

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"""
    (?P<NUMBER>-?\d+\.?\d*)
  | (?P<OP>>=|<=|==|!=|>|<)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<COMMA>,)
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
""", re.VERBOSE)


def _normalize(text: str) -> str:
    text = text.upper()
    # AI 生成有時候會用空白分隔兩個字的關鍵字，正規化成底線版本。
    text = re.sub(r"CROSSES?\s+ABOVE", "CROSSES_ABOVE", text)
    text = re.sub(r"CROSSES?\s+BELOW", "CROSSES_BELOW", text)
    text = re.sub(r"GOLDEN\s+CROSS", "GOLDEN_CROSS", text)
    text = re.sub(r"DEATH\s+CROSS", "DEATH_CROSS", text)
    return text


@dataclass
class Token:
    kind: str
    value: str
    pos: int


def tokenize(text: str) -> list[Token]:
    text = _normalize(text)
    tokens: list[Token] = []
    pos, n = 0, len(text)
    while pos < n:
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ExpressionError(f"無法辨識的字元：「{text[pos:pos + 10]}」（位置 {pos}）")
        kind = m.lastgroup
        tokens.append(Token(kind, m.group(kind), pos))
        pos = m.end()
    tokens.append(Token("EOF", "", n))
    return tokens


# ---------------------------------------------------------------------------
# Parser：遞迴下降，輸出純資料的 dict 節點（不是程式碼）。
# ---------------------------------------------------------------------------
class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, kind: str) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ExpressionError(f"語法錯誤：預期 {kind}，但看到「{tok.value or 'EOF'}」（位置 {tok.pos}）")
        return self._advance()

    def _is_kw(self, word: str) -> bool:
        tok = self._peek()
        return tok.kind == "IDENT" and tok.value == word

    def parse(self) -> dict:
        node = self._parse_or()
        if self._peek().kind != "EOF":
            tok = self._peek()
            raise ExpressionError(f"語法錯誤：多餘的內容「{tok.value}」（位置 {tok.pos}）")
        _validate_boolean(node)
        return node

    def _parse_or(self) -> dict:
        left = self._parse_and()
        while self._is_kw("OR"):
            self._advance()
            left = {"type": "or", "left": left, "right": self._parse_and()}
        return left

    def _parse_and(self) -> dict:
        left = self._parse_not()
        while self._is_kw("AND"):
            self._advance()
            left = {"type": "and", "left": left, "right": self._parse_not()}
        return left

    def _parse_not(self) -> dict:
        if self._is_kw("NOT"):
            self._advance()
            return {"type": "not", "operand": self._parse_not()}
        return self._parse_comparison()

    def _parse_comparison(self) -> dict:
        left = self._parse_term()
        tok = self._peek()
        if tok.kind == "OP":
            self._advance()
            return {"type": "compare", "op": tok.value, "left": left, "right": self._parse_term()}
        if tok.kind == "IDENT" and tok.value in CROSS_ALIASES:
            self._advance()
            return {"type": "cross", "direction": CROSS_ALIASES[tok.value], "left": left, "right": self._parse_term()}
        return left  # 裸 term，_validate_boolean 會擋掉不合法的情況

    def _parse_term(self) -> dict:
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            return {"type": "number", "value": float(tok.value)}
        if tok.kind == "LPAREN":
            self._advance()
            node = self._parse_or()
            self._expect("RPAREN")
            return node
        if tok.kind == "IDENT":
            name = tok.value
            if name in _KEYWORDS:
                raise ExpressionError(f"語法錯誤：這裡不能放關鍵字「{name}」（位置 {tok.pos}）")
            if name not in ALL_INDICATORS:
                raise ExpressionError(f"不認得的指標名稱「{name}」（位置 {tok.pos}）。可用指標：{', '.join(sorted(ALL_INDICATORS))}")
            self._advance()
            args: list[float] = []
            if self._peek().kind == "LPAREN":
                self._advance()
                if name in ZERO_ARG_INDICATORS:
                    raise ExpressionError(f"「{name}」不需要參數，不要加括號。")
                args.append(float(self._expect("NUMBER").value))
                while self._peek().kind == "COMMA":
                    self._advance()
                    args.append(float(self._expect("NUMBER").value))
                self._expect("RPAREN")
            elif name in ONE_ARG_INDICATORS:
                raise ExpressionError(f"「{name}」需要指定週期參數，例如 {name}(14)。")
            return {"type": "indicator", "name": name, "args": args}
        raise ExpressionError(f"語法錯誤：預期數字、指標或括號，但看到「{tok.value or 'EOF'}」（位置 {tok.pos}）")


def _validate_boolean(node: dict) -> None:
    """遞迴確認整棵樹最終都會是布林值——裸指標/裸數字不構成合法條件。"""
    t = node["type"]
    if t in ("and", "or"):
        _validate_boolean(node["left"])
        _validate_boolean(node["right"])
    elif t == "not":
        _validate_boolean(node["operand"])
    elif t in ("compare", "cross"):
        return
    else:
        raise ExpressionError("條件必須是比較式（例如 RSI(14) < 30），不能只有一個指標或數字、也不能省略比較符號。")


def parse_condition(text: str) -> dict:
    """字串 → AST。語法或語意錯誤一律丟 ExpressionError，訊息可直接顯示給使用者。"""
    if not text or not text.strip():
        raise ExpressionError("條件不能是空的。")
    return _Parser(tokenize(text)).parse()


# ---------------------------------------------------------------------------
# Evaluator：AST + OHLCV DataFrame → 布林訊號序列。純 pandas 計算，每個指標
# 公式都是寫死的（不依賴 TA-Lib，跟 technical.py 的手算 fallback邏輯一致），
# 沒有任何 eval/exec。
# ---------------------------------------------------------------------------
def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def _bollinger(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(20).mean()
    std = close.rolling(20).std()
    return middle + 2 * std, middle, middle - 2 * std


def _kd(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    period, d_period = 9, 3
    low_min = df["low"].rolling(period).min()
    high_max = df["high"].rolling(period).max()
    rsv = (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan) * 100
    k = rsv.ewm(com=d_period - 1, adjust=False).mean()
    d = k.ewm(com=d_period - 1, adjust=False).mean()
    return k, d


def _adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Wilder's DM/ADX 標準公式。"""
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr = _true_range(df).ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def _get_group(cache: dict, group_key: str, compute):
    if group_key not in cache:
        cache[group_key] = compute()
    return cache[group_key]


def _indicator_series(name: str, args: list[float], df: pd.DataFrame, cache: dict) -> pd.Series:
    key = (name, tuple(args))
    if key in cache:
        return cache[key]

    close, high, low = df["close"], df["high"], df["low"]
    volume = df["volume"].astype(float)

    if name == "CLOSE":
        series = close
    elif name == "OPEN":
        series = df["open"]
    elif name == "HIGH":
        series = high
    elif name == "LOW":
        series = low
    elif name == "VOLUME":
        series = volume
    elif name == "MA":
        series = close.rolling(int(args[0])).mean()
    elif name == "EMA":
        series = close.ewm(span=int(args[0]), adjust=False).mean()
    elif name == "RSI":
        series = _rsi(close, int(args[0]))
    elif name == "ATR":
        series = _true_range(df).rolling(int(args[0])).mean()
    elif name == "VOLUME_RATIO":
        n = int(args[0])
        series = volume / volume.rolling(n).mean()
    elif name in ("MACD_DIF", "MACD_DEA", "MACD_HIST"):
        dif, dea, hist = _get_group(cache, "_macd", lambda: _macd(close))
        series = {"MACD_DIF": dif, "MACD_DEA": dea, "MACD_HIST": hist}[name]
    elif name in ("BB_UPPER", "BB_MIDDLE", "BB_LOWER"):
        upper, middle, lower = _get_group(cache, "_bb", lambda: _bollinger(close))
        series = {"BB_UPPER": upper, "BB_MIDDLE": middle, "BB_LOWER": lower}[name]
    elif name in ("KD_K", "KD_D"):
        k, d = _get_group(cache, "_kd", lambda: _kd(df))
        series = k if name == "KD_K" else d
    elif name in ("ADX", "PLUS_DI", "MINUS_DI"):
        adx, plus_di, minus_di = _get_group(cache, "_adx", lambda: _adx(df))
        series = {"ADX": adx, "PLUS_DI": plus_di, "MINUS_DI": minus_di}[name]
    else:  # pragma: no cover - parser 已經擋過，這裡是防禦
        raise ExpressionError(f"不認得的指標名稱「{name}」")

    cache[key] = series
    return series


def _eval_term(node: dict, df: pd.DataFrame, cache: dict) -> pd.Series:
    if node["type"] == "number":
        return pd.Series(node["value"], index=df.index)
    if node["type"] == "indicator":
        return _indicator_series(node["name"], node["args"], df, cache)
    raise ExpressionError("內部錯誤：非預期的節點型別")  # pragma: no cover


_COMPARE_FNS = {
    ">": lambda a, b: a > b, "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
}


def eval_condition(node: dict, df: pd.DataFrame, cache: dict | None = None) -> pd.Series:
    """回傳布林 Series（跟 df 同 index），True 代表那根 K 棒符合條件。"""
    cache = cache if cache is not None else {}
    t = node["type"]
    if t == "and":
        return (eval_condition(node["left"], df, cache) & eval_condition(node["right"], df, cache)).fillna(False)
    if t == "or":
        return (eval_condition(node["left"], df, cache) | eval_condition(node["right"], df, cache)).fillna(False)
    if t == "not":
        return (~eval_condition(node["operand"], df, cache)).fillna(False)
    if t == "compare":
        left = _eval_term(node["left"], df, cache)
        right = _eval_term(node["right"], df, cache)
        return _COMPARE_FNS[node["op"]](left, right).fillna(False)
    if t == "cross":
        left = _eval_term(node["left"], df, cache)
        right = _eval_term(node["right"], df, cache)
        prev_left, prev_right = left.shift(1), right.shift(1)
        if node["direction"] == "above":
            result = (left > right) & (prev_left <= prev_right)
        else:
            result = (left < right) & (prev_left >= prev_right)
        return result.fillna(False)
    raise ExpressionError("內部錯誤：非預期的節點型別")  # pragma: no cover
