"""Lab U3 驗收：動作型與參考型 skill。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


def parse(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields, m.group(2)


skills = {p.parent.name: parse(p) for p in (root / ".claude" / "skills").glob("*/SKILL.md")}
check(len(skills) >= 2, f"至少兩個 skill（找到：{', '.join(skills) or '無'}）")

for name, (fm, _) in skills.items():
    desc = fm.get("description", "")
    check(len(desc) >= 15, f"{name}：description 夠具體（{len(desc)} 字）", "寫出做什麼、什麼時候用")

action = [n for n, (fm, body) in skills.items() if fm.get("disable-model-invocation") == "true"]
check(action, f"有 disable-model-invocation: true 的動作型 skill（{', '.join(action) or '無'}）")
dynamic = [n for n, (_, body) in skills.items() if re.search(r"!`[^`]+`|```!", body)]
check(dynamic, f"有使用 !`指令` 動態注入的 skill（{', '.join(dynamic) or '無'}）")
scoped = [n for n, (fm, _) in skills.items() if fm.get("allowed-tools")]
check(scoped, f"有設定 allowed-tools 的 skill（{', '.join(scoped) or '無'}）")
reference = [n for n, (fm, _) in skills.items() if fm.get("user-invocable") == "false"]
check(reference, f"有 user-invocable: false 的參考型 skill（{', '.join(reference) or '無'}）")

for name, (_, body) in skills.items():
    lines = body.count("\n") + 1
    if lines > 500:
        check(False, f"{name}：SKILL.md {lines} 行，超過建議的 500 行", "把參考資料拆到支援檔")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
