#!/usr/bin/env python3
"""
kb-sync-source.py — 將 finlab-stock-analyzer 源碼匯入知識庫 (KB web)。

每個 Vue view 與後端 API 模組都作為獨立文件匯入，讓 KB 可以逐檔精確引用。

使用方式：
    python scripts/kb-sync-source.py

需要環境變數：
    KB_API_TOKEN  — KB web API token
    KB_WEB_URL    — 可選，預設 https://frank210-kb-web.zeabur.app
"""

import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("請先安裝 httpx: pip install httpx", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).parent.parent
KB_WEB_URL = os.environ.get("KB_WEB_URL", "https://frank210-kb-web.zeabur.app").rstrip("/")
KB_API_TOKEN = os.environ.get("KB_API_TOKEN", "")

# 要匯入的源碼目錄/檔案模式，格式: (glob pattern, domain, 說明前綴)
SOURCE_TARGETS = [
    ("frontend/src/views/*.vue", "finlab_source", "Vue 前端頁面"),
    ("frontend/src/components/AppSidebar.vue", "finlab_source", "Vue 元件"),
    ("backend/app/api/*.py", "finlab_source", "後端 API 端點"),
    ("backend/app/analysis/*.py", "finlab_source", "後端分析模組"),
    ("backend/app/config/settings.py", "finlab_source", "後端設定"),
]


def get_headers() -> dict[str, str]:
    if not KB_API_TOKEN:
        print("ERROR: KB_API_TOKEN 環境變數未設定", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {KB_API_TOKEN}"}


def import_file(filepath: Path, domain: str) -> bool:
    """將單一源碼檔案匯入 KB，以 markdown code block 包裝。"""
    suffix = filepath.suffix.lstrip(".")
    relative = filepath.relative_to(ROOT)
    content = f"# {relative}\n\n```{suffix}\n{filepath.read_text(encoding='utf-8', errors='replace')}\n```\n"

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{KB_WEB_URL}/api/import/file",
            headers=get_headers(),
            files={"file": (filepath.name + ".md", content.encode("utf-8"), "text/markdown")},
            data={"domain": domain},
        )

    if resp.status_code == 200:
        body = resp.json()
        print(f"  ✓  {relative}  →  {body.get('doc_ids', ['?'])[0]}")
        return True
    else:
        print(f"  ✗  {relative}  →  HTTP {resp.status_code}: {resp.text[:120]}")
        return False


def main():
    ok = fail = 0
    for pattern, domain, label in SOURCE_TARGETS:
        files = sorted(ROOT.glob(pattern))
        if not files:
            print(f"[{label}] 找不到符合 {pattern} 的檔案，略過")
            continue
        print(f"\n[{label}] {len(files)} 個檔案 → domain={domain}")
        for f in files:
            try:
                if import_file(f, domain):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"  ✗  {f.name}  →  例外：{e}")
                fail += 1
            time.sleep(0.3)  # 避免 KB API rate limit

    print(f"\n完成：{ok} 成功，{fail} 失敗")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
