"""Lab U4 驗收：迴圈拆解筆記。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


note = root / "notes" / "u4-trace.md"
check(note.exists(), "notes/u4-trace.md 存在", "從本 lab 的 trace-template.md 複製")
if note.exists():
    text = note.read_text(encoding="utf-8")
    sections = {m.group(1).strip(): m.end() for m in re.finditer(r"^##\s+(.+)$", text, re.M)}

    def body(title):
        start = sections.get(title)
        if start is None:
            return ""
        nxt = min([pos for t, pos in sections.items() if pos > start] or [len(text)])
        return re.sub(r"^##.*$", "", text[start:nxt], flags=re.M)

    for title in ("蒐集", "行動", "驗證", "計畫審查"):
        items = [ln for ln in body(title).splitlines() if re.match(r"\s*-\s*\S", ln)]
        check(items, f"「{title}」至少有一筆內容（{len(items)} 筆）")

    task = body("任務描述")
    check(re.search(r"(test|pytest|npm|通過|驗證)", task, re.I), "任務描述包含驗證方式",
          "例如：pytest 要全部通過")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
