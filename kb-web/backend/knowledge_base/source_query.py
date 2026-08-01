"""
source_query.py — Query the source code knowledge base.

Collections:
  code_menu:        codefunction (menu hierarchy + JSP paths)
  code_e2e_chain:   BackingBean + BD delegates + action methods
  code_table_index: table_name -> DAO classes + SQL constants
  code_bd_methods:  BD public methods with DTO refs
  code_source:      full-text search index over Java source chunks
"""
from __future__ import annotations
import re
from typing import Any


def _table_exists(db: Any, term: str) -> bool:
    t = term.lower()
    return db.code_table_index.count_documents(
        {"table_name": {"$regex": f"^{re.escape(t)}$", "$options": "i"}}
    ) > 0


def query_table_chain(db: Any, table_name: str, limit: int = 5) -> str:
    """Given a DB table name, return the full program chain."""
    doc = db.code_table_index.find_one(
        {"table_name": {"$regex": f"^{re.escape(table_name)}$", "$options": "i"}}
    )
    if not doc:
        doc = db.code_table_index.find_one(
            {"table_name": {"$regex": re.escape(table_name), "$options": "i"}}
        )
    if not doc:
        return f"找不到 DB 表 `{table_name}`。"

    lines = [f"## DB 表影響分析：`{doc['table_name']}`\n"]
    lines.append(f"- **讀取 SQL 數**: {doc.get('sql_read_count', 0)}")
    lines.append(f"- **寫入 SQL 數**: {doc.get('sql_write_count', 0)}")

    daos = doc.get("dao_classes", [])
    if daos:
        lines.append(f"- **DAO 類別**: {', '.join(f'`{d}`' for d in daos[:6])}")

    bds = doc.get("bd_classes", [])
    if bds:
        lines.append(f"- **BD 層**: {', '.join(f'`{b}`' for b in bds[:5])}")

    bbs = doc.get("backingbeans", [])
    if bbs:
        lines.append(f"- **BackingBean**: {', '.join(f'`{b}`' for b in bbs[:5])}")

    frags = doc.get("sql_fragments", [])
    if frags:
        lines.append("\n**SQL 片段範例**:")
        for frag in frags[:3]:
            lines.append(f"```sql\n{frag[:200]}\n```")

    bd_methods = list(
        db.code_bd_methods.find(
            {"dto_refs": {"$regex": table_name, "$options": "i"}},
            {"bd_class": 1, "method_name": 1, "return_type": 1, "params": 1},
            limit=8,
        )
    )
    if bd_methods:
        lines.append("\n**相關 BD 方法**:")
        for m in bd_methods:
            p = (m.get("params") or "")[:50]
            lines.append(
                f"- `{m['bd_class']}.{m['method_name']}({p})` -> `{m.get('return_type','')[:30]}`"
            )

    return "\n".join(lines)


def query_fulltext(db: Any, term: str, limit: int = 5) -> str:
    """Full-text search over Java source chunks."""
    results = list(
        db.code_source.find(
            {"$text": {"$search": term}},
            {
                "class_name": 1, "module": 1, "file_path": 1,
                "chunk_start": 1, "content": 1,
                "score": {"$meta": "textScore"},
            },
        )
        .sort([("score", {"$meta": "textScore"})])
        .limit(limit)
    )
    if not results:
        return f"找不到含有 `{term}` 的程式碼。"

    lines = [f"## 程式碼全文搜尋：`{term}`\n"]
    for i, doc in enumerate(results):
        fpath = doc.get("file_path", "").split("MOrderSource/")[-1]
        start = doc.get("chunk_start", 0)
        lines.append(f"### [{i+1}] `{doc['module']}/{doc['class_name']}`")
        lines.append(f"- 路徑: `{fpath}` (約第 {start} 行)")
        content = doc.get("content", "")
        idx = content.lower().find(term.lower())
        if idx >= 0:
            snippet = content[max(0, idx - 50): idx + 150].replace("\n", " ")
            lines.append(f"- 片段: `...{snippet}...`")
        lines.append("")
    return "\n".join(lines)


def query_source_chain(db: Any, search_term: str, limit: int = 5) -> str:
    """Unified entry point: route to table / BD-method / menu / fulltext search."""
    term = search_term.strip()

    # Route 1: DB table
    if _table_exists(db, term):
        return query_table_chain(db, term, limit)

    # Route 2: BD method (e.g. "QueryBD.queryContractByAcctno")
    if "." in term and "BD" in term.split(".")[0]:
        bd_class, method_name = term.split(".", 1)
        docs = list(
            db.code_bd_methods.find(
                {
                    "bd_class": {"$regex": re.escape(bd_class), "$options": "i"},
                    "method_name": {"$regex": re.escape(method_name), "$options": "i"},
                },
                limit=3,
            )
        )
        if docs:
            lines = [f"## BD 方法查詢：`{term}`\n"]
            for doc in docs:
                lines.append(f"### `{doc['bd_class']}.{doc['method_name']}`")
                lines.append(f"- **回傳**: `{doc.get('return_type','')}`")
                lines.append(f"- **參數**: `{(doc.get('params') or '')[:100]}`")
                if doc.get("dto_refs"):
                    lines.append(
                        f"- **DTOs**: {', '.join(f'`{d}`' for d in doc['dto_refs'][:6])}"
                    )
                preview = (doc.get("body_preview") or "")[:300]
                if preview:
                    lines.append(f"\n```java\n{preview}\n```")
                lines.append("")
            return "\n".join(lines)

    # Route 3: Menu / BackingBean
    results: list[tuple[str, dict]] = []
    seen: set[str] = set()

    for doc in db.code_menu.find(
        {
            "$or": [
                {"base_code": {"$regex": f"^{re.escape(term)}", "$options": "i"}},
                {"code": {"$regex": f"^{re.escape(term)}", "$options": "i"}},
            ]
        },
        limit=limit,
    ):
        key = doc.get("base_code", "")
        if key not in seen:
            results.append(("menu", doc))
            seen.add(key)

    if len(results) < limit:
        for doc in db.code_menu.find(
            {"content": {"$regex": re.escape(term), "$options": "i"}, "channel": "MBMS"},
            limit=limit,
        ):
            key = doc.get("base_code", "")
            if key not in seen:
                results.append(("menu", doc))
                seen.add(key)

    if len(results) < limit:
        for doc in db.code_e2e_chain.find(
            {
                "$or": [
                    {"content": {"$regex": re.escape(term), "$options": "i"}},
                    {"backing_bean": {"$regex": re.escape(term), "$options": "i"}},
                    {"backing_bean_short": {"$regex": re.escape(term), "$options": "i"}},
                ]
            },
            limit=limit,
        ):
            key = doc.get("base_code", "")
            if key not in seen:
                results.append(("chain", doc))
                seen.add(key)

    # Route 4: Fallback full-text
    if not results:
        return query_fulltext(db, term, limit)

    lines: list[str] = [f"## 原始碼知識庫查詢：{term}\n"]
    for idx, (src, doc) in enumerate(results[:limit]):
        code = doc.get("base_code") or doc.get("code", "")
        chain = db.code_e2e_chain.find_one({"base_code": code}) if src == "menu" else doc
        menu = db.code_menu.find_one({"base_code": code, "channel": "MBMS"}) or doc

        lines.append(f"### [{idx+1}] {menu.get('content', code)}")
        lines.append(f"- **選單路徑**: {menu.get('menu_path_str', '---')}")
        lines.append(f"- **管道**: {menu.get('channel', '---')}")
        lines.append(f"- **Code**: `{code}`")

        jsp = (chain or {}).get("jsp_path") or menu.get("jsp_path")
        if jsp:
            lines.append(f"- **JSP路徑**: `{jsp}`")

        if chain:
            bb = chain.get("backing_bean")
            bb_short = chain.get("backing_bean_short")
            if bb:
                lines.append(f"- **BackingBean**: `{bb}`")
            elif bb_short:
                lines.append(f"- **BackingBean**: `{bb_short}` (全名未解析)")

            if chain.get("extends_class"):
                lines.append(f"- **繼承**: `{chain['extends_class']}`")

            delegates = chain.get("delegates") or []
            if delegates:
                lines.append(f"- **Delegate**: {', '.join(f'`{d}`' for d in delegates)}")
                bd_calls = chain.get("bd_calls") or {}
                for bd in delegates[:3]:
                    methods = bd_calls.get(bd, [])
                    if methods:
                        lines.append(
                            f"  - `{bd}` -> {', '.join(f'`{m}`' for m in methods[:6])}"
                        )

            actions = chain.get("action_methods") or []
            if actions:
                lines.append(f"- **Action方法**: {', '.join(f'`{m}`' for m in actions[:8])}")

            java = chain.get("java_source_path")
            if java:
                short = java.split("MOrderSource/")[-1] if "MOrderSource/" in java else java
                lines.append(f"- **Java來源**: `{short}`")
        else:
            lines.append("- *(BackingBean鏈未建立)*")

        lines.append("")

    return "\n".join(lines)
