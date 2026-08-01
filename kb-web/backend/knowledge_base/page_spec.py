"""
page_spec: Given an operation name, produce a page specification.

Layers:
  1. Page info     ← code_e2e_chain (BackingBean, BD, JSP)
  2. Field list    ← BackingBean private fields in code_source
  3. Validation    ← code_bd_methods check/valid methods, translated to business language
  4. SRS/SDS       ← spec_docs semantic search
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Business condition → plain-language translation table
# Pattern (case-insensitive) -> 中文業務說明
# ---------------------------------------------------------------------------
_COND_TABLE: list[tuple[str, str]] = [
    (r'business\s*[=!]=?\s*["\']?08', "企業用戶 (business=08)"),
    (r'business\s*[=!]=?\s*["\']?02', "個人用戶 (business=02)"),
    (r'business\s*[=!]=?\s*["\']?04', "政府/學術用戶 (business=04)"),
    (r'department\s*[=!]=?\s*["\']?B', "直銷通路 (department=B)"),
    (r'channeltype\s*[=!]=?\s*["\']?01', "門市通路 (channeltype=01)"),
    (r'channeltype\s*[=!]=?\s*["\']?02', "電話通路 (channeltype=02)"),
    (r'projtypeid\s*[=!]=?\s*["\']?05', "企客方案 (projtypeid=05)"),
    (r'projtypeid\s*[=!]=?\s*["\']?04', "共享方案 (projtypeid=04)"),
    (r'corpno\b', "員眷公司統編 (corpno)"),
    (r'empDto|empoff|empDiscnt|EmpDiscnt', "員眷資料 (empDto)"),
    (r'mvpn|MVPN', "MVPN 企業網路群組"),
    (r'prepay|prepaid', "預付費用戶"),
    (r'exprepay', "到期預付費"),
    (r'officeCode|officecode', "辦公室/銷售點代碼"),
    (r'orderstatus|orderStatus', "訂單狀態"),
    (r'telnum|serviceNum|servicenum', "門號"),
    (r'promoprojid|promoplanid|promoplan', "優惠方案/專案 ID"),
    (r'startdate|startDate|enddate|endDate', "生效/到期日期"),
    (r'SCN|MR\d{4,5}', "SCN/MR 專案條件"),
]

_VALIDATION_METHOD_PAT = re.compile(
    r'check|chk|valid|verify|doOk|doAddr|doConfirm|mustInput',
    re.IGNORECASE,
)

_FIELD_DECL_PAT = re.compile(
    r'private\s+(?:static\s+)?(?:final\s+)?'
    r'([\w<>\[\], ]+?)\s+(\w+)\s*(?:=\s*[^;]+)?;'
)

# Field name → business hint mapping (common BackingBean fields)
_FIELD_HINT: dict[str, str] = {
    "telnum": "門號",
    "telnumList": "批次門號清單",
    "empDto": "員眷資料 DTO",
    "serviceID": "作業代碼",
    "email": "Email",
    "upfile": "上傳檔案",
    "add_Del": "增/刪模式 (add/del)",
    "corpno": "員眷公司統編",
    "selectPlan": "選擇優惠方案",
    "selectProj": "選擇優惠專案",
    "planItems": "方案下拉選單項目",
    "projItems": "專案下拉選單項目",
    "prodItems": "產品下拉選單項目",
    "startDiscntDay": "優惠生效日",
    "addDiscntCheck": "增優惠確認旗標",
    "delDiscntCheck": "刪優惠確認旗標",
    "compMsg": "完成訊息",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _translate_conditions(body: str) -> list[str]:
    found = []
    for pattern, desc in _COND_TABLE:
        if re.search(pattern, body, re.IGNORECASE):
            found.append(desc)
    return found


def _extract_bb_fields(db: Any, bean_class: str) -> list[dict]:
    fields: list[dict] = []
    seen: set[str] = set()
    skip_types = {"serialVersionUID", "logger", "Logger", "log"}

    for chunk in db.code_source.find(
        {
            "class_name": bean_class,
            "content": {"$regex": r"private\s+\w", "$options": "i"},
        },
        {"content": 1},
        limit=12,
    ):
        content = chunk.get("content", "") or ""
        for m in _FIELD_DECL_PAT.finditer(content):
            type_name = m.group(1).strip()
            field_name = m.group(2).strip()
            if field_name in skip_types or field_name in seen:
                continue
            if re.fullmatch(r'[A-Z_]+', field_name):  # skip ALL_CAPS constants
                continue
            seen.add(field_name)
            hint = _FIELD_HINT.get(field_name, "")
            fields.append({"name": field_name, "type": type_name, "hint": hint})
    return fields


def _get_validation_methods(db: Any, delegates: list[str]) -> list[dict]:
    methods: list[dict] = []
    for bd_class in delegates:
        for m in db.code_bd_methods.find(
            {
                "bd_class": bd_class,
                "method_name": {"$regex": r'check|chk|valid|verify|mustInput', "$options": "i"},
            },
            {"method_name": 1, "params": 1, "return_type": 1, "body_preview": 1},
            limit=8,
        ):
            body = m.get("body_preview", "") or ""
            conditions = _translate_conditions(body)
            methods.append({
                "bd": bd_class,
                "method": m.get("method_name", ""),
                "params": (m.get("params", "") or "")[:80],
                "return": m.get("return_type", "") or "",
                "body": body[:400],
                "conditions": conditions,
            })
    return methods


def _get_error_messages(db: Any, bean_class: str, delegates: list[str]) -> list[dict]:
    """Extract error messages (string literals that look like UI messages) from source."""
    messages: list[dict] = []
    # Search BackingBean for error message strings
    classes = [bean_class] + (delegates or [])
    for cls in classes:
        for chunk in db.code_source.find(
            {
                "class_name": cls,
                "content": {
                    "$regex": r'(?:error|msg|message|訊息|必須|請務必|不可|不得|限|無效|已)',
                    "$options": "i",
                },
            },
            {"content": 1},
            limit=5,
        ):
            content = chunk.get("content", "") or ""
            # Extract string literals that look like messages (>4 chars, non-ASCII or contain Chinese-style words)
            for lit in re.findall(r'"([^"]{5,120})"', content):
                if re.search(r'[\u4e00-\u9fff]|must|error|please|invalid', lit, re.IGNORECASE):
                    messages.append({"class": cls, "message": lit})
    # Deduplicate
    seen: set[str] = set()
    out: list[dict] = []
    for m in messages:
        if m["message"] not in seen:
            seen.add(m["message"])
            out.append(m)
    return out[:15]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query_page_spec(db: Any, operation_name: str, top_k: int = 3) -> dict:
    """
    Given an operation name (Chinese or base_code), produce a page specification dict.
    """
    from knowledge_base.semantic_search import semantic_search

    # Step 1: Find page in code_e2e_chain
    chain = db.code_e2e_chain.find_one(
        {
            "$or": [
                {"content": {"$regex": operation_name, "$options": "i"}},
                {"base_code": {"$regex": operation_name, "$options": "i"}},
            ]
        }
    )

    if not chain:
        return {"error": f"找不到作業：{operation_name}"}

    base_code = chain.get("base_code", "")
    content = chain.get("content", "")
    bean_full = chain.get("backing_bean", "") or ""
    bean_class = bean_full.split(".")[-1] if bean_full else ""
    delegates = chain.get("delegates", []) or []
    bd_calls = chain.get("bd_calls", {}) or {}
    jsp_path = chain.get("jsp_path", "")

    # Step 2: BackingBean field declarations
    bb_fields = _extract_bb_fields(db, bean_class) if bean_class else []

    # Step 3: Validation methods from BD delegates
    val_methods = _get_validation_methods(db, delegates)

    # Step 4: Error messages from source
    error_msgs = _get_error_messages(db, bean_class, delegates)

    # Step 5: Semantic search for SRS/SDS rules
    query_str = f"{content} {operation_name} 欄位 必輸 檢查規則"
    srs_hits = semantic_search(db, query_str, top_k=top_k, scope="spec")
    srs_matches = []
    for h in srs_hits:
        doc = h.get("doc", {})
        body = doc.get("body", "") or ""
        # Find relevant excerpt
        excerpt = ""
        for kw in [operation_name, content, "欄位", "必輸", "檢查"]:
            idx = body.find(kw)
            if idx >= 0:
                excerpt = body[max(0, idx - 30) : idx + 200].replace("\n", " ")
                break
        srs_matches.append(
            {
                "score": round(h.get("semantic_score", 0), 3),
                "title": doc.get("title", ""),
                "excerpt": excerpt or body[:200].replace("\n", " "),
            }
        )

    return {
        "page_info": {
            "operation": content,
            "base_code": base_code,
            "backing_bean": bean_class,
            "backing_bean_full": bean_full,
            "jsp_path": jsp_path,
            "delegates": delegates,
            "bd_calls_summary": {
                bd: methods[:3] for bd, methods in bd_calls.items()
            },
        },
        "fields": bb_fields,
        "validation_rules": val_methods,
        "error_messages": error_msgs,
        "srs_matches": srs_matches,
    }


def render_page_spec(spec: dict) -> str:
    """Render page spec as Markdown report."""
    if "error" in spec:
        return f"❌ {spec['error']}"

    pi = spec["page_info"]
    bd_summary = pi.get("bd_calls_summary", {})
    bd_summary_str = "; ".join(
        f"{bd}: {', '.join(ms)}" for bd, ms in bd_summary.items()
    )

    lines: list[str] = [
        f"# 📋 作業頁面規格：{pi['operation']} ({pi['base_code']})",
        "",
        "---",
        "",
        "## 一、頁面技術資訊",
        "",
        "| 項目 | 值 |",
        "|-----|---|",
        f"| 作業名稱 | {pi['operation']} |",
        f"| base_code | `{pi['base_code']}` |",
        f"| BackingBean | `{pi['backing_bean']}.java` |",
        f"| JSP 路徑 | `{pi['jsp_path']}` |",
        f"| BD 委派 | {', '.join(pi['delegates'])} |",
    ]
    if bd_summary_str:
        lines.append(f"| 已知 BD 呼叫 | {bd_summary_str} |")
    lines += ["", "---", ""]

    # Fields
    if spec["fields"]:
        lines += [
            "## 二、欄位清單（BackingBean 屬性回推）",
            "",
            "> 🔵 **資料來源**：`code_source` BackingBean private 宣告",
            "",
            "| # | 欄位名稱 | 型別 | 業務說明 |",
            "|---|---------|-----|---------|",
        ]
        for i, f in enumerate(spec["fields"], 1):
            hint = f.get("hint") or "（待 BA 確認）"
            lines.append(f"| {i} | `{f['name']}` | `{f['type']}` | {hint} |")
        lines += ["", "---", ""]
    else:
        lines += [
            "## 二、欄位清單",
            "",
            "> ⚠️ 未能從 BackingBean 解析欄位，建議直接查閱 JSP 原始碼",
            "",
            "---",
            "",
        ]

    # Validation rules
    if spec["validation_rules"]:
        lines += [
            "## 三、檢查規則（BD 方法源碼回推）",
            "",
            "> 🔵 **資料來源**：`code_bd_methods` check/valid 方法",
            "",
        ]
        for m in spec["validation_rules"]:
            cond_str = "、".join(m.get("conditions", [])) or "（需進一步人工分析）"
            params_str = m.get("params", "") or ""
            body_preview = (m.get("body", "") or "")[:300].replace("\n", " ").strip()
            lines += [
                f"### `{m['bd']}.{m['method']}({params_str})`",
                "",
                f"- **適用條件（初步推導）**：{cond_str}",
                f"- **源碼摘要**：{body_preview}",
                "",
            ]
        lines += ["---", ""]
    else:
        lines += [
            "## 三、檢查規則",
            "",
            "> ⚠️ BD 委派層無 check/valid 方法，規則可能在 BackingBean 本體",
            "",
            "---",
            "",
        ]

    # Error messages
    if spec["error_messages"]:
        lines += [
            "## 四、錯誤訊息（源碼字串）",
            "",
            "> 🔵 **資料來源**：`code_source` 字串字面值",
            "",
        ]
        for msg in spec["error_messages"]:
            lines.append(f"- **[{msg['class']}]** `{msg['message']}`")
        lines += ["", "---", ""]

    # SRS/SDS
    if spec["srs_matches"]:
        lines += [
            "## 五、SRS/SDS 對應（語意搜尋）",
            "",
            "> 🟡 **資料來源**：`spec_docs` 語意向量搜尋",
            "",
        ]
        for h in spec["srs_matches"]:
            lines += [
                f"### [{h['score']}] {h['title']}",
                "",
                f"> {h['excerpt']}",
                "",
            ]
        lines += ["---", ""]

    lines += [
        "## 附記",
        "",
        "| 圖例 | 說明 |",
        "|-----|-----|",
        "| 🔵 KB自動 | 從程式源碼知識庫自動推導 |",
        "| 🟡 原文件 | 從 SRS/SDS 語意搜尋 |",
        "| ⚠️ 待確認 | 需 BA / 工程師補充 |",
    ]

    return "\n".join(lines)
