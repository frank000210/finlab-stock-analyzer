#!/usr/bin/env python3
"""把「人工對照投信收益分配公告後整理的 CSV」驗證並併進 backend/app/data/etf_distribution_sources.json。

CSV 欄位（第一列是標題）：
  symbol,ex_date,income,gain,equalization,principal,source,source_url,as_of
單位＝每受益權單位、元。source 寫來源名稱，source_url 必須是 https 公告連結，as_of 是公告日。
每一筆都要有出處；驗證不過的列會被列出並略過，不會悄悄寫進去。

用法（在專案根目錄）：
  python scripts/etf_distribution_import.py my_rows.csv --dry-run   # 只檢查、不寫檔
  python scripts/etf_distribution_import.py my_rows.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.analysis import etf_distribution as ed  # noqa: E402


def read_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                per_unit = {k: float(r[k]) for k in ed.PARTS}
            except (KeyError, TypeError, ValueError):
                per_unit = {k: r.get(k) for k in ed.PARTS}  # 交給 validate_entry 報錯
            rows.append({
                "symbol": (r.get("symbol") or "").strip().upper(),
                "ex_date": (r.get("ex_date") or "").strip(),
                "per_unit": per_unit,
                "source": (r.get("source") or "").strip(),
                "source_url": (r.get("source_url") or "").strip(),
                "as_of": (r.get("as_of") or "").strip(),
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    existing = []
    if ed.DATA_PATH.exists():
        existing = json.loads(ed.DATA_PATH.read_text(encoding="utf-8")).get("entries", [])
    merged, report = ed.merge_entries(existing, read_rows(args.csv))
    print(f"新增 {report['added']} 筆、取代 {report['replaced']} 筆、拒收 {len(report['rejected'])} 筆")
    for r in report["rejected"]:
        print(f"  ✗ 第 {r['index'] + 2} 列 {r['symbol']}: {'；'.join(r['errors'])}")
    if args.dry_run:
        print("（dry-run，未寫檔）")
        return 1 if report["rejected"] else 0
    ed.DATA_PATH.write_text(ed.dump_document(merged), encoding="utf-8", newline="\n")
    print(f"已寫入 {ed.DATA_PATH.relative_to(ROOT)}（共 {len(merged)} 筆）")
    return 1 if report["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
