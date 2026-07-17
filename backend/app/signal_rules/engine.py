"""Custom signal rule engine with a restricted Python execution environment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..ai_agent.signal_generator import (
    MarketSnapshot,
    SignalCondition,
    SignalItem,
    clear_signal_cache,
    generate_default_signal,
)

_SCRIPT_TIMEOUT_SECONDS = 5


class SignalRule(BaseModel):
    id: str
    name: str
    description: str
    script: str
    isDefault: bool = False
    isActive: bool = False
    createdAt: datetime
    updatedAt: datetime


class SignalRuleCreate(BaseModel):
    name: str
    description: str = ""
    script: str
    isActive: bool = False


class SignalRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    script: str | None = None
    isActive: bool | None = None


def _execute_rule_script_worker(script: str, context: dict[str, Any], queue: Any) -> None:
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "sum": sum,
        "zip": zip,
    }
    local_vars = dict(context)
    local_vars.update(
        {
            "signal": "HOLD",
            "confidence": 0.5,
            "conditions": [],
            "reasoning": "",
        }
    )
    try:
        exec(script, {"__builtins__": safe_builtins}, local_vars)
        queue.put(
            {
                "ok": True,
                "signal": local_vars.get("signal", "HOLD"),
                "confidence": float(local_vars.get("confidence", 0.5)),
                "conditions": list(local_vars.get("conditions", [])),
                "reasoning": str(local_vars.get("reasoning", "")),
            }
        )
    except Exception as exc:
        queue.put({"ok": False, "error": str(exc)})


class SignalRuleEngine:
    def __init__(self) -> None:
        now = datetime.utcnow()
        default_rule = SignalRule(
            id="default",
            name="Built-in technical analysis",
            description="Default weighted RSI/MACD/SMA/Bollinger/volume rule.",
            script="",
            isDefault=True,
            isActive=True,
            createdAt=now,
            updatedAt=now,
        )
        self._rules: dict[str, SignalRule] = {default_rule.id: default_rule}

    # S1：自訂規則原本只存在這個 process 的記憶體字典，重啟/重新部署就全部
    # 消失，使用者會在不知情的狀況下悄悄變回預設規則（因為 get_active_rule/
    # execute_rule 直接決定 AI 訊號跟交易建議邏輯）。現在改成 Mongo 持久化：
    # 啟動時 load_rules() 把存檔的自訂規則載回記憶體快取，讀取路徑
    # （list_rules/get_active_rule/execute_rule）維持同步、只讀記憶體，不因
    # 為要 await DB 而拖慢訊號產生的熱路徑；只有異動（新增/修改/刪除/啟用）
    # 才 await 寫回 DB。
    async def load_rules(self) -> None:
        """啟動時從 Mongo 載入使用者自訂規則，跟預設規則合併。"""
        try:
            from ..db.cache import get_setting

            saved = await get_setting("signal_rules", [])
            for item in saved or []:
                try:
                    rule = SignalRule(**item)
                    self._rules[rule.id] = rule
                except Exception:
                    continue
        except Exception:
            pass  # Mongo 不可用時退回只有預設規則，不影響行程啟動

    async def _persist(self) -> None:
        """把目前所有規則（含預設）存回 Mongo，best-effort。"""
        try:
            from ..db.cache import set_setting

            await set_setting("signal_rules", [r.model_dump(mode="json") for r in self._rules.values()])
        except Exception:
            pass  # Mongo 短暫不可用時不擋掉這次操作本身，下次異動會再嘗試存檔

    def list_rules(self) -> list[SignalRule]:
        return sorted(self._rules.values(), key=lambda item: item.createdAt)

    async def create_rule(self, payload: SignalRuleCreate) -> SignalRule:
        now = datetime.utcnow()
        rule = SignalRule(
            id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            script=payload.script,
            isActive=bool(payload.isActive),
            createdAt=now,
            updatedAt=now,
        )
        self._rules[rule.id] = rule
        if rule.isActive:
            await self.activate_rule(rule.id)
        clear_signal_cache()
        await self._persist()
        return self._rules[rule.id]

    async def update_rule(self, rule_id: str, payload: SignalRuleUpdate) -> SignalRule:
        rule = self._get_rule(rule_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(rule, key, value)
        rule.updatedAt = datetime.utcnow()
        self._rules[rule.id] = rule
        if payload.isActive:
            await self.activate_rule(rule.id)
        clear_signal_cache()
        await self._persist()
        return rule

    async def delete_rule(self, rule_id: str) -> None:
        rule = self._get_rule(rule_id)
        if rule.isDefault:
            raise ValueError("Default rule cannot be deleted")
        del self._rules[rule_id]
        clear_signal_cache()
        await self._persist()

    async def activate_rule(self, rule_id: str) -> SignalRule:
        target = self._get_rule(rule_id)
        for rule in self._rules.values():
            rule.isActive = False
            rule.updatedAt = datetime.utcnow()
        target.isActive = True
        target.updatedAt = datetime.utcnow()
        self._rules[target.id] = target
        clear_signal_cache()
        await self._persist()
        return target

    def get_active_rule(self) -> SignalRule:
        for rule in self._rules.values():
            if rule.isActive:
                return rule
        return self._rules["default"]

    def execute_rule(self, rule_id: str, snapshot: MarketSnapshot) -> SignalItem:
        rule = self._get_rule(rule_id)
        if rule.isDefault:
            return generate_default_signal(snapshot)

        context = {
            "prices": snapshot.prices,
            "volumes": snapshot.volumes,
            "rsi": snapshot.rsi,
            "macd": snapshot.macd,
            "macd_signal": snapshot.macd_signal,
            "sma20": snapshot.sma20,
            "bb_upper": snapshot.bb_upper,
            "bb_lower": snapshot.bb_lower,
            "symbol": snapshot.symbol,
        }
        result = self._run_script(rule.script, context)
        conditions = [
            SignalCondition(
                name=str(item.get("name", "custom-condition")),
                met=bool(item.get("met", False)),
                value=str(item.get("value", "")),
            )
            for item in result["conditions"]
            if isinstance(item, dict)
        ]
        signal = str(result["signal"]).upper()
        if signal not in {"BUY", "SELL", "HOLD"}:
            signal = "HOLD"
        confidence = max(0.0, min(1.0, float(result["confidence"])))
        return SignalItem(
            symbol=snapshot.symbol,
            signal=signal,
            confidence=round(confidence, 2),
            price=snapshot.price,
            reasoning=result["reasoning"] or f"Executed custom rule: {rule.name}",
            conditions=conditions,
            indicators={
                "rsi14": snapshot.rsi,
                "macd": snapshot.macd,
                "macd_signal": snapshot.macd_signal,
                "sma20": snapshot.sma20,
                "bb_upper": snapshot.bb_upper,
                "bb_lower": snapshot.bb_lower,
            },
            volume_ratio=snapshot.volume_ratio,
            generated_at=datetime.utcnow(),
        )

    def _run_script(self, script: str, context: dict[str, Any]) -> dict[str, Any]:
        class _LocalQueue:
            def __init__(self) -> None:
                self._item: dict[str, Any] | None = None

            def put(self, value: dict[str, Any]) -> None:
                self._item = value

            def get(self) -> dict[str, Any] | None:
                return self._item

        queue = _LocalQueue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_rule_script_worker, script, context, queue)
            try:
                future.result(timeout=_SCRIPT_TIMEOUT_SECONDS)
            except FuturesTimeoutError as exc:
                raise ValueError("Rule execution timed out after 5 seconds") from exc

        result = queue.get()
        if result is None:
            raise ValueError("Rule execution returned no result")
        if not result.get("ok"):
            raise ValueError(result.get("error", "Rule execution failed"))
        return result

    def _get_rule(self, rule_id: str) -> SignalRule:
        rule = self._rules.get(rule_id)
        if not rule:
            raise ValueError(f"Rule {rule_id} not found")
        return rule


rule_engine = SignalRuleEngine()
