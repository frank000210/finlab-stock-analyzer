"""PreToolUse hook：讀過外部內容的 session，高風險指令改成先問人。

不擋死（deny），而是回傳 permissionDecision = "ask"：
平常不打擾，只有在風險真的升高時才停下來讓人確認。
"""
import json
import pathlib
import re
import sys

data = json.load(sys.stdin)
marker = pathlib.Path(data.get("cwd") or ".") / ".claude" / "state" / f"tainted-{data.get('session_id', 'unknown')}"
command = data.get("tool_input", {}).get("command", "")
RISKY = r"\b(git\s+push|curl|wget|scp|ssh|rm\s+-r|npm\s+publish)\b"

if marker.exists() and re.search(RISKY, command):
    source = marker.read_text(encoding="utf-8") or "外部工具"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"本 session 讀過外部內容（{source}），高風險指令需要人工確認。",
        }
    }))  # 保留預設的 ensure_ascii：中文轉成 \uXXXX，Windows 主控台編碼不是 UTF-8 時也不會 crash
sys.exit(0)
