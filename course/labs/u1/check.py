"""Lab U1 驗收：CLAUDE.md、路徑限定規則、自訂 output style。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


def frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    return m.group(1) if m else ""


md = next((p for p in (root / "CLAUDE.md", root / ".claude" / "CLAUDE.md") if p.exists()), None)
check(md, "找到 CLAUDE.md", "在專案根目錄執行 /init 產生草稿")
if md:
    text = md.read_text(encoding="utf-8")
    lines = text.count("\n") + 1
    check(lines <= 200, f"CLAUDE.md 共 {lines} 行（上限 200）", "把只跟部分檔案有關的規則搬到 .claude/rules/")
    check(re.search(r"^##\s+\S", text, re.M), "用 ## 標題分段")
    check(re.search(r"`[^`\n]*(test|build|lint|run|pytest|npm|make)[^`\n]*`", text, re.I),
          "包含用反引號標示的建置／測試指令", "例如：commit 前執行 `npm test`")

rules = list((root / ".claude" / "rules").glob("**/*.md"))
scoped = [r for r in rules if re.search(r"^paths\s*:", frontmatter(r.read_text(encoding="utf-8")), re.M)]
check(scoped, f".claude/rules/ 有設定 paths 的規則（找到 {len(scoped)} 個）", "在 frontmatter 加上 paths 清單")

styles = list((root / ".claude" / "output-styles").glob("*.md"))
good = [s for s in styles if all(re.search(rf"^{k}\s*:", frontmatter(s.read_text(encoding="utf-8")), re.M)
                                 for k in ("name", "description"))]
check(good, f".claude/output-styles/ 有含 name 與 description 的 style（找到 {len(good)} 個）",
      "可以先複製本 lab 的 coach.md")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
