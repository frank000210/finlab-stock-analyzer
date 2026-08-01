"""
source_ingest.py — Ingest MO2_Sourcetree source code into MongoDB.

Phases:
  1. codefunction (Informix tableutil) → code_menu
  2. faces-config.xml + JSP EL expressions → BackingBean mapping
  3. BackingBean Java files → BD delegates + action methods → code_e2e_chain

Requires:
  - Informix tableutil DB accessible via informix-db MCP (for Phase 1)
  - OR: a pre-exported JSON file of codefunction rows

Usage from CLI:
  python -m knowledge_base.cli source-ingest --source-root "C:\\...\\MO2_Sourcetree"
  python -m knowledge_base.cli source-ingest --codefunction-json path/to/codefunction.json
"""
from __future__ import annotations
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

# ── constants ──────────────────────────────────────────────────────────────────
CHANNELS = {"MBMS", "PARTNER", "ECMS", "CPMS_NEW"}
FACES_CONFIG_PATHS_RELATIVE = [
    "ORW1/src/main/webapp/WEB-INF/faces-config.xml",
    "ORWCP/src/main/webapp/WEB-INF/faces-config.xml",
    "ORWEC/src/main/webapp/WEB-INF/faces-config.xml",
]
JSP_ROOTS_RELATIVE = [
    "ORW1/src/main/webapp/ORW11/ORW11100/jsp",
    "ORW1/src/main/webapp/ORW11/ORW11100/xhtml",
    "ORWCP/src/main/webapp/jsp",
]
JAVA_SOURCE_ROOT_RELATIVE = "MOrderSource/src/main/java"

EL_EXCLUDE = {
    "fn", "empty", "null", "true", "false", "not",
    "sessionScope", "requestScope", "applicationScope",
    "param", "paramValues", "header", "headerValues",
    "cookie", "initParam", "facesContext", "view", "component",
}

PAT_EL = re.compile(r"#\{(\w+)\.")
PAT_COMMENT_BEAN = re.compile(r"\*\s*backingBean\s*:\s*(\w+)", re.IGNORECASE)
PAT_IMPORT_SPECIFIC = re.compile(
    r'import\s*=\s*"[^"]*?backingbean\.(\w+)[,"]', re.IGNORECASE
)
PAT_RESOLVEVARIABLE = re.compile(
    r"resolveVariable\s*\([^,]+,\s*\"(\w+)\"\s*\)", re.IGNORECASE
)
PAT_DELEGATE_IMPORT = re.compile(r"import\s+[\w.]+\.(\w+BD)\s*;")
PAT_BD_CALL = re.compile(r"\b(\w+BD)\s*\.\s*(\w+)\s*\(")
PAT_ACTION_METHOD = re.compile(
    r"public\s+(?:String|void|boolean|Object|List[\w<>]*|Map[\w<>]*)\s+"
    r"(do\w+|execute\w+|submit\w+|save\w+|query\w+|search\w+|update\w+|delete\w+|add\w+|check\w+|get\w+(?:List|Map|DTO|TO))\s*\(",
    re.IGNORECASE,
)
PAT_CLASS_DECL = re.compile(r"public\s+class\s+(\w+)(?:\s+extends\s+(\w+))?")

import pymongo


# ── helpers ────────────────────────────────────────────────────────────────────

def _read_text(path: str, maxbytes: int = 0) -> str:
    for enc in ("cp950", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as fh:
                return fh.read(maxbytes) if maxbytes else fh.read()
        except Exception:
            continue
    return ""


def _class_to_path(java_root: str, class_name: str) -> str:
    return os.path.join(java_root, class_name.replace(".", os.sep) + ".java")


def _get_menu_path(code: str, code_map: dict, visited: set | None = None) -> list[str]:
    if visited is None:
        visited = set()
    if code in visited:
        return []
    visited.add(code)
    row = code_map.get(code)
    if not row:
        return [code]
    parent = (row.get("parent") or "").strip()
    label = row.get("content") or code
    if not parent or parent == code or parent == "null":
        return [label]
    return _get_menu_path(parent, code_map, visited) + [label]


def _jsp_path(row: dict) -> str | None:
    code = (row.get("code") or "").strip()
    basedir = (row.get("basedir") or "").strip()
    directory = (row.get("directory") or "").strip()
    ext = (row.get("extension") or "jsp").strip()
    if not basedir:
        if code.startswith("http"):
            return code
        return None
    base_code = code.split("@")[0].strip()
    parts = [f"/{basedir}"]
    if directory:
        parts.append(directory)
    parts.append(f"{base_code}.{ext}")
    return "/".join(parts)


def _bean_from_jsp(jsp_full: str, bean_name_to_class: dict) -> tuple[str | None, str | None]:
    content = _read_text(jsp_full, maxbytes=8000)
    if not content:
        return None, None

    m = PAT_COMMENT_BEAN.search(content)
    if m:
        bn = m.group(1)
        return bn, bean_name_to_class.get(bn)

    m = PAT_IMPORT_SPECIFIC.search(content)
    if m:
        import_full = re.search(r'import\s*=\s*"([^"]*?backingbean\.\w+)', content, re.IGNORECASE)
        if import_full:
            full = import_full.group(1).split(",")[0].strip()
            short = full.split(".")[-1]
            return short, full
        bn = m.group(1)
        return bn, bean_name_to_class.get(bn)

    m = PAT_RESOLVEVARIABLE.search(content)
    if m:
        bn = m.group(1)
        return bn, bean_name_to_class.get(bn)

    names = PAT_EL.findall(content)
    filtered = [n for n in names if n not in EL_EXCLUDE and not n[0].isupper()]
    if filtered:
        bn = Counter(filtered).most_common(1)[0][0]
        return bn, bean_name_to_class.get(bn)

    return None, None


def _parse_backing_bean(java_path: str) -> dict:
    content = _read_text(java_path)
    if not content:
        return {}
    result: dict = {}
    m = PAT_CLASS_DECL.search(content)
    if m:
        result["extends"] = m.group(2)
    delegates = list(set(PAT_DELEGATE_IMPORT.findall(content)))
    result["delegates"] = delegates
    bd_calls: dict[str, set] = {}
    for m in PAT_BD_CALL.finditer(content):
        bd, method = m.group(1), m.group(2)
        bd_calls.setdefault(bd, set()).add(method)
    result["bd_calls"] = {k: sorted(v)[:20] for k, v in bd_calls.items()}
    result["action_methods"] = sorted(set(PAT_ACTION_METHOD.findall(content)))
    pkg = re.search(r"^package\s+([\w.]+)", content, re.MULTILINE)
    result["package"] = pkg.group(1) if pkg else None
    result["line_count"] = content.count("\n")
    return result


# ── main ingest ────────────────────────────────────────────────────────────────

def ingest_source_code(
    db: Any,
    source_root: str,
    codefunction_rows: list[dict] | None = None,
) -> dict:
    """
    Full ingestion pipeline: phases 1-3.

    Args:
        db: MongoDB database handle
        source_root: path to MO2_Sourcetree directory
        codefunction_rows: pre-loaded codefunction rows (skips Informix query if provided)
    """
    source_root = source_root.rstrip("/\\")
    java_root = os.path.join(source_root, *JAVA_SOURCE_ROOT_RELATIVE.split("/"))
    webapp_root = os.path.join(source_root, "ORW1", "src", "main", "webapp")

    counts: dict = {}

    # ── Phase 1: code_menu ────────────────────────────────────────────────────
    if codefunction_rows is None:
        raise ValueError("codefunction_rows must be provided (run informix query separately)")

    rows = codefunction_rows
    code_map = {(r.get("code") or "").strip(): r for r in rows if (r.get("code") or "").strip()}

    db.code_menu.drop()
    db.code_menu.create_index([("code", pymongo.TEXT), ("content", pymongo.TEXT)])
    db.code_menu.create_index("channel")
    db.code_menu.create_index("base_code")
    db.code_menu.create_index("code")

    menu_docs = []
    for r in rows:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        menu_path = _get_menu_path(code, code_map)
        jsp = _jsp_path(r)
        content = r.get("content") or ""
        or_codes = re.findall(r"\b([A-Z]{2,3}\d{4,})\b", content)
        menu_docs.append({
            "code": code,
            "base_code": code.split("@")[0].strip(),
            "content": content,
            "parent": (r.get("parent") or "").strip() or None,
            "sequence": r.get("sequence"),
            "channel": r.get("channel"),
            "basedir": (r.get("basedir") or "").strip() or None,
            "directory": (r.get("directory") or "").strip() or None,
            "extension": (r.get("extension") or "").strip() or None,
            "programmer": (r.get("programmer") or "").strip() or None,
            "menu_path": menu_path,
            "menu_path_str": " > ".join(menu_path),
            "jsp_path": jsp,
            "or_codes": or_codes,
            "is_leaf": bool((r.get("basedir") or "").strip() and (r.get("extension") or "").strip()),
        })

    db.code_menu.insert_many(menu_docs)
    counts["code_menu"] = len(menu_docs)

    # ── Phase 2: faces-config + JSP → BackingBean mapping ────────────────────
    import xml.etree.ElementTree as ET

    bean_name_to_class: dict[str, str] = {}
    beans_list: list[dict] = []

    for rel in FACES_CONFIG_PATHS_RELATIVE:
        config_path = os.path.join(source_root, *rel.split("/"))
        if not os.path.exists(config_path):
            continue
        try:
            tree = ET.parse(config_path)
            root_el = tree.getroot()
            ns = re.match(r"\{.*\}", root_el.tag)
            ns = ns.group(0) if ns else ""
            for mb in root_el.iter(f"{ns}managed-bean"):
                name_el = mb.find(f"{ns}managed-bean-name")
                class_el = mb.find(f"{ns}managed-bean-class")
                scope_el = mb.find(f"{ns}managed-bean-scope")
                if name_el is not None and class_el is not None:
                    bn = name_el.text.strip()
                    bc = class_el.text.strip()
                    scope = scope_el.text.strip() if scope_el is not None else ""
                    bean_name_to_class[bn] = bc
                    short = bc.split(".")[-1]
                    if short not in bean_name_to_class:
                        bean_name_to_class[short] = bc
                    if not bn.endswith("Bean"):
                        bean_name_to_class[bn + "Bean"] = bc
                    module = bc.split(".")[3] if len(bc.split(".")) > 3 else ""
                    beans_list.append({
                        "bean_name": bn,
                        "class_name": bc,
                        "class_short": short,
                        "scope": scope,
                        "module": module,
                        "java_exists": os.path.exists(_class_to_path(java_root, bc)),
                        "java_path": _class_to_path(java_root, bc).replace("\\", "/")
                            if os.path.exists(_class_to_path(java_root, bc)) else None,
                    })
        except Exception:
            pass

    db.code_beans.drop()
    db.code_beans.create_index("bean_name")
    db.code_beans.create_index([("class_name", pymongo.TEXT)])
    if beans_list:
        db.code_beans.insert_many(beans_list)
    counts["code_beans"] = len(beans_list)

    # Build JSP index
    jsp_index: dict[str, str] = {}
    for rel in JSP_ROOTS_RELATIVE:
        jsp_root = os.path.join(source_root, *rel.split("/"))
        if not os.path.isdir(jsp_root):
            continue
        for dirpath, _, filenames in os.walk(jsp_root):
            for fname in filenames:
                name_no_ext, ext = os.path.splitext(fname)
                if ext.lower() in (".jsp", ".xhtml", ".faces"):
                    rel_path = os.path.relpath(
                        os.path.join(dirpath, fname),
                        os.path.dirname(os.path.dirname(os.path.dirname(jsp_root)))
                    )
                    if name_no_ext not in jsp_index:
                        jsp_index[name_no_ext] = rel_path.replace("\\", "/")

    # Update code_menu with JSP + bean info
    for doc in db.code_menu.find():
        base_code = doc.get("base_code", "")
        updates: dict = {}

        # JSP path (filesystem-verified)
        if not doc.get("jsp_path"):
            jsp_rel = jsp_index.get(base_code)
            if jsp_rel:
                updates["jsp_path"] = "/" + jsp_rel

        # BackingBean from JSP EL
        jsp_path_to_check = updates.get("jsp_path") or doc.get("jsp_path")
        if jsp_path_to_check:
            jsp_full = os.path.join(webapp_root, jsp_path_to_check.lstrip("/").replace("/", os.sep))
            if os.path.exists(jsp_full):
                bn, bc = _bean_from_jsp(jsp_full, bean_name_to_class)
                if bn:
                    updates["backing_bean_short"] = bn
                    if bc:
                        updates["backing_bean"] = bc
                        java_path = _class_to_path(java_root, bc)
                        if os.path.exists(java_path):
                            updates["java_source_path"] = java_path.replace("\\", "/")

        if updates:
            db.code_menu.update_one({"_id": doc["_id"]}, {"$set": updates})

    # ── Phase 3: code_e2e_chain ───────────────────────────────────────────────
    db.code_e2e_chain.drop()
    db.code_e2e_chain.create_index("code")
    db.code_e2e_chain.create_index([("search_text", pymongo.TEXT), ("content", pymongo.TEXT)])
    db.code_e2e_chain.create_index("channel")

    chain_docs = []
    for menu_doc in db.code_menu.find({"java_source_path": {"$ne": None}}):
        java_path = menu_doc["java_source_path"].replace("/", os.sep)
        if not os.path.exists(java_path):
            continue
        java_info = _parse_backing_bean(java_path)
        if not java_info:
            continue
        search_text = " ".join(filter(None, [
            menu_doc.get("content", ""),
            menu_doc.get("menu_path_str", ""),
            menu_doc.get("backing_bean", ""),
            " ".join(java_info.get("delegates", [])),
            " ".join(java_info.get("action_methods", [])[:20]),
        ]))
        chain_docs.append({
            "code": menu_doc["code"],
            "base_code": menu_doc["base_code"],
            "content": menu_doc.get("content", ""),
            "channel": menu_doc.get("channel"),
            "menu_path_str": menu_doc.get("menu_path_str", ""),
            "jsp_path": menu_doc.get("jsp_path"),
            "backing_bean": menu_doc.get("backing_bean"),
            "backing_bean_short": menu_doc.get("backing_bean_short"),
            "java_source_path": menu_doc.get("java_source_path"),
            "extends_class": java_info.get("extends"),
            "delegates": java_info.get("delegates", []),
            "bd_calls": java_info.get("bd_calls", {}),
            "action_methods": java_info.get("action_methods", []),
            "java_package": java_info.get("package"),
            "java_line_count": java_info.get("line_count", 0),
            "search_text": search_text,
            "delegates_text": " ".join(java_info.get("delegates", [])),
        })

    if chain_docs:
        db.code_e2e_chain.insert_many(chain_docs)
    counts["code_e2e_chain"] = len(chain_docs)

    return counts
