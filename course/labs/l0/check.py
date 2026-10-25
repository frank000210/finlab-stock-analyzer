"""Lab L0 驗收：claude 指令可用、練習資料夾是 git repo。"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
results = []


def check(ok, msg, hint=""):
    results.append(ok)
    print(("✅ " if ok else "❌ ") + msg + ("" if ok or not hint else f"\n   → {hint}"))


exe = shutil.which("claude")
check(exe is not None, "找得到 claude 指令", "請先依官方 Quickstart 安裝，並確認 PATH 設定")
if exe:
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        check(bool(out), f"claude --version：{out or '（無輸出）'}")
    except Exception as exc:  # noqa: BLE001
        check(False, f"claude --version 執行失敗：{exc}")

check((root / ".git").exists(), f"{root.name} 是 git repo", "在練習資料夾執行 git init")
check((root / "README.md").exists(), "README.md 存在")

print(f"\n{sum(results)} / {len(results)} 項通過")
sys.exit(0 if all(results) else 1)
