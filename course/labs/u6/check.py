"""Lab U6 驗收：實際執行 hook 腳本，確認擋下、放行與降級行為。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
hooks = root / ".claude" / "hooks"
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


def run(script, payload):
    proc = subprocess.run([sys.executable, str(script)], input=json.dumps(payload), capture_output=True,
                          text=True, encoding="utf-8", timeout=20)
    return proc.returncode, proc.stdout, proc.stderr


def bash(cmd, cwd, session="lab-check"):
    return {"session_id": session, "cwd": str(cwd), "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": cmd}}


# ── settings 註冊 ──
try:
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    settings = {}
hook_cfg = settings.get("hooks", {})


def registered(event, script_name, matcher_part):
    for group in hook_cfg.get(event, []):
        if matcher_part in group.get("matcher", "") and any(script_name in h.get("command", "") for h in group.get("hooks", [])):
            return True
    return False


check(registered("PreToolUse", "block_dangerous.py", "Bash"), "block_dangerous.py 註冊為 PreToolUse / Bash")
check(registered("PostToolUse", "mark_tainted.py", "WebFetch"), "mark_tainted.py 註冊為 PostToolUse（含 WebFetch）")
check(registered("PreToolUse", "taint_gate.py", "Bash"), "taint_gate.py 註冊為 PreToolUse / Bash")

# ── block_dangerous 行為 ──
block = hooks / "block_dangerous.py"
if block.exists():
    for cmd in ("rm -rf /", "git push --force origin main", "git push -f", "git reset --hard HEAD~1"):
        code, _, err = run(block, bash(cmd, root))
        check(code == 2 and err.strip(), f"擋下：{cmd}", "exit 2，並把原因寫到 stderr")
    for cmd in ("npm test", "git push origin feature", "git status", "rm -rf build/"):
        code, _, _ = run(block, bash(cmd, root))
        check(code == 0, f"放行：{cmd}")
else:
    check(False, ".claude/hooks/block_dangerous.py 存在", "從本 lab 複製 hooks/")

# ── 汙染降級 ──
mark, gate = hooks / "mark_tainted.py", hooks / "taint_gate.py"
if mark.exists() and gate.exists():
    with tempfile.TemporaryDirectory() as tmp:
        code, out, _ = run(gate, bash("git push origin main", tmp))
        check(code == 0 and not out.strip(), "未讀外部內容時，git push 不受影響")
        run(mark, {"session_id": "lab-check", "cwd": tmp, "hook_event_name": "PostToolUse",
                   "tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}})
        code, out, _ = run(gate, bash("git push origin main", tmp))
        try:
            decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
        except Exception:  # noqa: BLE001
            decision = None
        check(decision == "ask", "讀過外部內容後，git push 改成 ask")
        code, out, _ = run(gate, bash("npm test", tmp))
        check(not out.strip(), "讀過外部內容後，一般指令不受影響")
else:
    check(False, "mark_tainted.py 與 taint_gate.py 存在")

gitignore = root / ".gitignore"
check(gitignore.exists() and ".claude/state" in gitignore.read_text(encoding="utf-8"), ".gitignore 包含 .claude/state")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
