"""PreToolUse hook：擋下危險的 shell 指令。

Claude Code 會把工具呼叫的資料用 JSON 從 stdin 傳進來：
    {"tool_name": "Bash", "tool_input": {"command": "..."}, ...}
exit 2 = 擋下（stderr 的內容會回饋給 Claude）；exit 0 = 沒有意見。
"""
import json
import re
import sys

# Windows 的主控台編碼可能不是 UTF-8，印中文會直接 crash（exit 1 而不是 2，等於沒擋）
sys.stderr.reconfigure(encoding="utf-8")
data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

DANGEROUS = [
    r"\brm\s+-rf\s+(/|~)(\s|$)",  # 刪根目錄或家目錄
    # TODO：加上 git push --force（也要擋 -f）
    # TODO：加上 git reset --hard
]

for pattern in DANGEROUS:
    if re.search(pattern, command):
        print(f"已擋下危險指令（規則：{pattern}）。請改用較安全的做法，或請使用者自己執行。", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
