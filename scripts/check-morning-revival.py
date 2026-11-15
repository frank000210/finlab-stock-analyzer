#!/usr/bin/env python3
"""晨興聖言頁（deploy/portal/morning-revival/）的靜態檢查。

pre-push 在「這次推送只改了晨興聖言頁」時跑這支，取代整套 Playwright
（那套測的是 finlab 主站，會打 FinMind，和這個靜態頁無關）。

檢查：
  1. weeks.json 可解析；每一週的 id 都有對應的 weeks/<id>.html；latest 指向存在的週。
  2. HTML 不含連續兩個左大括號（入口站台開了 Caddy templates，會被當成樣板）。
  3. 每個 data-ref 都是「書卷:章:節」格式，書卷 1–66。
  4. 片段內的頁內連結（href="#x"）都有對應的 id。
有問題就列出來並以 1 結束。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "deploy" / "portal" / "morning-revival"
REF = re.compile(r"^(\d{1,2}):(\d{1,3}):(\d{1,3}(-\d{1,3})?)(,\d{1,3}(-\d{1,3})?)*$")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 主控台預設不是 UTF-8
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    errors = []
    try:
        data = json.loads((ROOT / "weeks.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[morning-revival] weeks.json 讀不了：{exc}")
        return 1

    ids = [w["id"] for t in data.get("trainings", []) for w in t.get("weeks", [])]
    if len(ids) != len(set(ids)):
        errors.append("weeks.json 有重複的週 id")
    if data.get("latest") not in ids:
        errors.append(f"weeks.json 的 latest（{data.get('latest')}）不在週次清單裡")
    for wid in ids:
        if not (ROOT / "weeks" / f"{wid}.html").is_file():
            errors.append(f"缺少 weeks/{wid}.html")
    for f in sorted((ROOT / "weeks").glob("*.html")):
        if f.stem not in ids:
            errors.append(f"weeks/{f.name} 沒有列在 weeks.json")

    for f in [ROOT / "index.html", *sorted((ROOT / "weeks").glob("*.html"))]:
        text = f.read_text(encoding="utf-8")
        name = f.relative_to(ROOT).as_posix()
        if "{" * 2 in text:
            errors.append(f"{name} 含連續兩個左大括號（Caddy templates 會出錯）")
        for refs in re.findall(r'data-ref="([^"]*)"', text):
            for ref in refs.split():
                m = REF.match(ref)
                if not m or not 1 <= int(m.group(1)) <= 66:
                    errors.append(f"{name} 的 data-ref 格式不對：{ref}")
        if f.parent.name == "weeks":
            anchors = set(re.findall(r'\bid="([^"]+)"', text))
            for target in re.findall(r'href="#([^"]+)"', text):
                if target not in anchors:
                    errors.append(f"{name} 的頁內連結 #{target} 找不到對應的 id")

    if errors:
        print("[morning-revival] 靜態檢查沒過：")
        for e in errors:
            print("  - " + e)
        return 1
    print(f"[morning-revival] 靜態檢查通過（{len(ids)} 週）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
