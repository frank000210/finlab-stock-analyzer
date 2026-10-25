"""Lab L7 驗收：狀態列腳本能處理範例輸入，且已在使用者設定中註冊。"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
script = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.claude/statusline.py").expanduser().resolve()
results = []


def check(ok, msg, hint=""):
    results.append(bool(ok))
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


sample = {"model": {"display_name": "Opus"}, "workspace": {"current_dir": "/tmp/demo"},
          "context_window": {"used_percentage": 42}, "cost": {"total_cost_usd": 0.12}}

check(script.exists(), f"找到狀態列腳本 {script}")
if script.exists():
    proc = subprocess.run([sys.executable, str(script)], input=json.dumps(sample), capture_output=True,
                          text=True, encoding="utf-8", timeout=20)
    out = proc.stdout.strip()
    check(proc.returncode == 0 and out, f"腳本正常輸出：{out[:80]}", proc.stderr.strip()[:200])
    check("Opus" in out, "輸出包含模型名稱")
    proc = subprocess.run([sys.executable, str(script)], input="{}", capture_output=True, text=True,
                          encoding="utf-8", timeout=20)
    check(proc.returncode == 0, "欄位缺漏時不會當掉", "用 .get() 並給預設值")

settings = Path("~/.claude/settings.json").expanduser()
try:
    cfg = json.loads(settings.read_text(encoding="utf-8")).get("statusLine", {})
except Exception:  # noqa: BLE001
    cfg = {}
check(cfg.get("type") == "command" and cfg.get("command"), "~/.claude/settings.json 已設定 statusLine")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
