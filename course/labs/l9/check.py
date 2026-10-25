"""Lab L9 驗收：marketplace.json 格式、相對路徑、名稱一致性。"""
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


try:
    mk = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    mk = None
check(mk is not None, ".claude-plugin/marketplace.json 存在且是合法 JSON")
mk = mk or {}
check(re.fullmatch(r"[a-z0-9][a-z0-9-]*", mk.get("name", "")), f"marketplace name 合法（{mk.get('name') or '未設定'}）")
check((mk.get("owner") or {}).get("name"), "有 owner.name")
plugins = mk.get("plugins") or []
check(plugins, f"plugins 至少一個（{len(plugins)} 個）")

for entry in plugins:
    pname, source = entry.get("name", "?"), entry.get("source")
    if isinstance(source, str):
        check(".." not in source, f"{pname}：相對路徑沒有使用 ..", "路徑從 marketplace 根目錄算起")
        pdir = (root / source).resolve()
        check(pdir.is_dir(), f"{pname}：source 目錄存在（{source}）")
        try:
            inner = json.loads((pdir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            inner = {}
        check(inner.get("name") == pname, f"{pname}：項目名稱與 plugin.json 的 name 一致（{inner.get('name')}）")
    else:
        check(isinstance(source, dict) and source.get("source"), f"{pname}：source 物件有 source 類型")

exe = shutil.which("claude")
if exe:
    proc = subprocess.run([exe, "plugin", "validate", str(root)], capture_output=True, text=True, timeout=120)
    check(proc.returncode == 0, "claude plugin validate 通過", (proc.stdout + proc.stderr).strip()[-400:])
else:
    print("ℹ️  找不到 claude 指令，略過 claude plugin validate")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
