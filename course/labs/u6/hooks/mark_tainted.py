"""PostToolUse hook：讀過外部內容（網頁、搜尋、MCP）就替這個 session 做記號。

搭配 taint_gate.py：有記號的 session，之後的高風險指令一律改成要人確認。
記號檔放在 .claude/state/，記得加進 .gitignore。
"""
import json
import pathlib
import sys

data = json.load(sys.stdin)
state = pathlib.Path(data.get("cwd") or ".") / ".claude" / "state"
state.mkdir(parents=True, exist_ok=True)
(state / f"tainted-{data.get('session_id', 'unknown')}").write_text(data.get("tool_name", ""), encoding="utf-8")
sys.exit(0)
