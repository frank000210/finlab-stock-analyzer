"""Claude Code 狀態列：從 stdin 讀 session JSON，印出一行文字。"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
data = json.load(sys.stdin)
model = data.get("model", {}).get("display_name", "?")
folder = os.path.basename(data.get("workspace", {}).get("current_dir", "") or "")
pct = data.get("context_window", {}).get("used_percentage") or 0
cost = data.get("cost", {}).get("total_cost_usd") or 0

try:
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=2).stdout.strip()
except Exception:  # noqa: BLE001
    branch = ""

print(f"[{model}] {folder}{' @ ' + branch if branch else ''} | context {pct:.0f}% | ${cost:.2f}")
