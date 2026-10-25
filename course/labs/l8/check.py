"""Lab L8 驗收：plugin 結構、manifest、hook 路徑；有安裝 claude 時順便跑 validate。"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


manifest_path = root / ".claude-plugin" / "plugin.json"
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    manifest = None
check(manifest is not None, ".claude-plugin/plugin.json 存在且是合法 JSON")
name = (manifest or {}).get("name", "")
check(re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""), f"plugin name 合法（{name or '未設定'}）", "小寫英數與連字號，不要空白")
check((manifest or {}).get("description"), "plugin.json 有 description")

misplaced = [p.name for p in (root / ".claude-plugin").iterdir() if p.name != "plugin.json"] if manifest_path.exists() else []
check(not misplaced, "只有 plugin.json 放在 .claude-plugin/", f"把 {', '.join(misplaced)} 移到 plugin 根目錄")

skills = list((root / "skills").glob("*/SKILL.md"))
agents = list((root / "agents").glob("*.md"))
hooks_json = root / "hooks" / "hooks.json"
kinds = sum(bool(x) for x in (skills, agents, hooks_json.exists(), (root / ".mcp.json").exists()))
check(kinds >= 2, f"包含至少兩種元件（skills {len(skills)}、agents {len(agents)}、hooks {'有' if hooks_json.exists() else '無'}）")

if hooks_json.exists():
    try:
        hooks = json.loads(hooks_json.read_text(encoding="utf-8"))
        commands = [h.get("command", "") for groups in hooks.get("hooks", {}).values() for g in groups for h in g.get("hooks", [])]
        check(hooks.get("hooks"), "hooks.json 有頂層的 hooks 物件")
        local = [c for c in commands if re.search(r"\.(py|sh|js)\b", c) and "${CLAUDE_PLUGIN_ROOT}" not in c]
        check(not local, "hook 指令引用腳本時都用 ${CLAUDE_PLUGIN_ROOT}", "；".join(local[:3]))
    except Exception as exc:  # noqa: BLE001
        check(False, f"hooks.json 格式正確（{exc}）")

exe = shutil.which("claude")
if exe:
    proc = subprocess.run([exe, "plugin", "validate", str(root)], capture_output=True, text=True, timeout=120)
    check(proc.returncode == 0, "claude plugin validate 通過", (proc.stdout + proc.stderr).strip()[-400:])
else:
    print("ℹ️  找不到 claude 指令，略過 claude plugin validate")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
