"""Lab U2 驗收：權限規則與 MCP server。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


settings = load_json(root / ".claude" / "settings.json")
check(settings is not None, ".claude/settings.json 存在且是合法 JSON")
perms = (settings or {}).get("permissions", {})
check(any(re.match(r"Read\(.+\)", r) for r in perms.get("deny", [])), "deny 裡有保護檔案的 Read(...) 規則",
      '例如 "deny": ["Read(./.env)"]')
check(any(r.startswith("Bash(") for r in perms.get("allow", [])), "allow 裡有 Bash(...) 規則")
check(perms.get("ask"), "ask 裡至少有一條規則", '例如 "ask": ["Bash(git push *)"]')

mcp = load_json(root / ".mcp.json")
servers = (mcp or {}).get("mcpServers", {})
check(servers, f".mcp.json 設定了 MCP server（{', '.join(servers) or '無'}）",
      "用 claude mcp add --scope project ... 加入")
raw = (root / ".mcp.json").read_text(encoding="utf-8") if (root / ".mcp.json").exists() else ""
check(not re.search(r"(sk-|ghp_|xox[bp]-)[A-Za-z0-9]{8,}", raw), ".mcp.json 沒有直接寫入金鑰",
      "改用 ${ENV_VAR} 引用環境變數")

server = root / "server.py"
if server.exists():
    src = server.read_text(encoding="utf-8")
    tools = re.findall(r"@mcp\.tool\(\)\s*\ndef\s+(\w+)", src)
    check("reverse_text" in tools, f"server.py 定義了 reverse_text 工具（目前：{', '.join(tools)}）")
else:
    check(False, "練習 repo 裡有 server.py", "從本 lab 複製 server.py")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
