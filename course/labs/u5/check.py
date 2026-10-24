"""Lab U5 驗收：唯讀 subagent 與平行稽核 skill。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


def frontmatter(path):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}, ""
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields, m.group(2)


agents = {p.name: frontmatter(p) for p in (root / ".claude" / "agents").glob("*.md")}
check(agents, f".claude/agents/ 有 subagent（{', '.join(agents) or '無'}）")
readonly = []
for name, (fm, _) in agents.items():
    has_basics = fm.get("name") and len(fm.get("description", "")) >= 10
    check(has_basics, f"{name}：有 name 與具體的 description")
    tools = {t.strip() for t in re.split(r"[,\s]+", fm.get("tools", "")) if t.strip()}
    if tools and not tools & {"Edit", "Write", "Bash", "PowerShell", "NotebookEdit"}:
        readonly.append(name)
check(readonly, f"至少一個 subagent 用 tools 限制成唯讀（{', '.join(readonly) or '無'}）",
      "tools: Read, Grep, Glob")

audit = root / ".claude" / "skills" / "audit" / "SKILL.md"
check(audit.exists(), ".claude/skills/audit/SKILL.md 存在")
if audit.exists():
    fm, body = frontmatter(audit)
    check(fm.get("disable-model-invocation") == "true", "audit skill 設定 disable-model-invocation: true")
    check("$ARGUMENTS" in body or re.search(r"\$\d|\$[a-z_]+", body), "audit skill 使用參數接收目錄")
    check(re.search(r"(subagent|子代理|平行|parallel)", body, re.I), "audit skill 要求派出 subagent 平行處理")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
