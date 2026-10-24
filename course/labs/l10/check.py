"""Lab L10 驗收：期末專題 repo（marketplace + plugin + 文件）。"""
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


try:
    mk = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    mk = {}
check(mk.get("plugins"), "repo 根目錄有 marketplace.json 且列出 plugin")

plugin_dirs = [(root / p["source"]).resolve() for p in mk.get("plugins", []) if isinstance(p.get("source"), str)]
kinds = set()
pre_tool_hook = False
for pdir in plugin_dirs:
    if list((pdir / "skills").glob("*/SKILL.md")):
        kinds.add("skill")
    if list((pdir / "agents").glob("*.md")):
        kinds.add("subagent")
    if (pdir / ".mcp.json").exists():
        kinds.add("MCP")
    hooks_json = pdir / "hooks" / "hooks.json"
    if hooks_json.exists():
        kinds.add("hook")
        try:
            pre_tool_hook = pre_tool_hook or bool(json.loads(hooks_json.read_text(encoding="utf-8")).get("hooks", {}).get("PreToolUse"))
        except Exception:  # noqa: BLE001
            pass
check(len(kinds) >= 3, f"plugin 涵蓋至少三種擴充點（{', '.join(sorted(kinds)) or '無'}）")
check(pre_tool_hook, "至少一個 PreToolUse hook 做安全把關")

readme = root / "README.md"
check(readme.exists() and len(readme.read_text(encoding="utf-8")) > 300, "README.md 存在且有實質內容（> 300 字）")

principles = root / "PRINCIPLES.md"
count = len(re.findall(r"^##\s+\S", principles.read_text(encoding="utf-8"), re.M)) if principles.exists() else 0
check(count >= 5, f"PRINCIPLES.md 至少 5 條原則（目前 {count} 條）")

leaks = []
for f in root.rglob("*"):
    if f.is_file() and f.suffix in {".json", ".md", ".py", ".sh", ".js"} and ".git" not in f.parts:
        if re.search(r"(sk-ant-|sk-|ghp_|xox[bp]-)[A-Za-z0-9_-]{12,}", f.read_text(encoding="utf-8", errors="ignore")):
            leaks.append(str(f.relative_to(root)))
check(not leaks, "沒有把金鑰寫進檔案", "、".join(leaks[:5]))

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
