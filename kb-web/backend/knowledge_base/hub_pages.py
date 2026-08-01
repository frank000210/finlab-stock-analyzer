"""Generate Obsidian hub (樞紐) pages so the graph forms navigable clusters.

The vault is auto-imported and notes almost never link to each other, so the
Obsidian graph is an orphan dust cloud once tag-nodes are hidden. This module
builds a small set of hub notes that ``[[link]]`` to related documents:

* ~15 business-theme hubs for ``spec_docs`` (each doc joins its single
  highest-priority matching theme -> clean, mostly-disjoint clusters).
* knowledge-folder hubs (workflow / decisions / blindspots / innovation /
  session insights) built deterministically from the folder layout.
* a top-level ``_MOC`` (Map of Content) that links every hub into one spine.

Hub pages live in ``vault/hubs/`` and carry no ``tags:`` (so they never create
green tag-nodes). They reference members by ``[[doc_id|title]]``; because
``export_vault`` only writes files it has a Mongo doc for, re-exporting the
vault never touches ``hubs/``. Re-run after adding/removing source docs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SPEC_DIR = "spec_docs"
HUB_DIR = "hubs"

# Ordered, specific -> generic. First matching theme wins (primary cluster).
# Keywords are matched as substrings against title + summary + tags.
THEME_RULES: List[Tuple[str, List[str]]] = [
    ("CPMS帳號權限", ["cpms", "帳號管理", "帳戶域", "權限", "帳號"]),
    ("OCS計費", ["ocs", "計價", "計費"]),
    ("預付儲值", ["預付", "儲值"]),
    ("停復話拆機", ["停復話", "停話", "復話", "拆機", "欠費", "冒名", "susp", "reco", "disc大批"]),
    ("優惠折扣", ["優惠", "折扣", "促銷"]),
    ("門號設備SIM", ["sim", "換卡", "換機", "選號", "補卡", "門號", "證號", "np", "攜碼"]),
    ("帳務繳費發票", ["繳費", "發票", "退費", "核退", "補核", "保證金", "聯單", "帳單", "收費", "費率"]),
    ("受理申辦合約", ["受理", "申辦", "新申裝", "申裝", "合約", "新申"]),
    ("客戶用戶資料", ["客戶資料", "更客戶", "用戶資料", "主檔", "個資", "客戶", "用戶"]),
    ("代理商通路", ["代理商", "通路", "行銷", "廠商"]),
    ("介面IM", ["介面", "介接", "cbm", "im overview", "im架構", "overview"]),
    ("查核查詢", ["查核", "查詢"]),
    ("報表列印", ["報表", "列印"]),
    ("批次作業", ["大批", "批次"]),
    ("特殊業務", ["mdvpn", "emome", "漫遊", "vpn", "特業", "他網", "合作服務", "加值", "熱線", "定位"]),
    ("系統設計DB", ["schema", "資料庫", "sqlconstant", "sqlgenerator", "model2", "ifrs",
                   "收款域", "金流", "歷史域", "總覽", "im關聯", "表格列表", "code table",
                   "code-table", "mbms_im", "資料模型", "域"]),
    ("部署維運", ["部署", "維運", "排程", "健康狀態", "健康檢查", "記憶體", "監控", "維護工具"]),
    ("操作手冊", ["手冊", "操作說明", "使用說明", "操作手册"]),
]

# folder -> (hub display name, description)
KNOWLEDGE_FOLDERS: List[Tuple[str, str, str]] = [
    ("workflow_playbooks", "工作流程-Playbook", "可重複套用的工作流程劇本"),
    ("workflow_runs", "工作流程-執行紀錄", "每次 session 的實際工作流程執行"),
    ("decision_logs", "決策記錄", "決策過程與取捨"),
    ("decision_profiles", "決策風格", "累積的決策偏好輪廓"),
    ("blindspot_alerts", "盲點警示", "被提醒或發現的思考盲點"),
    ("innovation_logs", "創新提議", "創新想法與提案"),
    ("domain_pages", "Session洞察", "每個 session 萃取的重點洞察"),
]

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_TITLE_RE = re.compile(r"^title:\s*(.+)$", re.M)
_SUMMARY_RE = re.compile(r"^summary:\s*(.+)$", re.M)
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.M)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def parse_meta(text: str, stem: str) -> Dict[str, object]:
    """Extract title/summary/tags from a note's frontmatter (best effort)."""
    title = ""
    summary = ""
    tags: List[str] = []
    fm = _FM_RE.match(text)
    if fm:
        block = fm.group(1)
        tm = _TITLE_RE.search(block)
        if tm:
            title = tm.group(1).strip().strip("'\"")
        sm = _SUMMARY_RE.search(block)
        if sm:
            summary = sm.group(1).strip().strip("'\"")
        # collect simple "- tag" list items inside a tags: block
        in_tags = False
        for line in block.splitlines():
            if re.match(r"^tags:\s*$", line):
                in_tags = True
                continue
            if in_tags:
                m = re.match(r"^\s*-\s*(.+)$", line)
                if m:
                    tags.append(m.group(1).strip().strip("'\""))
                elif re.match(r"^\S", line):
                    in_tags = False
    if not title:
        hm = _HEADING_RE.search(text)
        title = hm.group(1).strip() if hm else stem
    return {"title": title, "summary": summary, "tags": tags}


def _doc_type(stem: str) -> str:
    low = stem.lower()
    if low.startswith("swds") or "swds" in low[:8]:
        return "SWDS"
    if low.startswith("srs"):
        return "SRS"
    if low.startswith("sds"):
        return "SDS"
    if low.startswith("scn"):
        return "SCN"
    if low.startswith("im-spec") or low.startswith("im_"):
        return "IM規格"
    if low.startswith("ref"):
        return "參考文件"
    return "其他"


def classify_theme(meta: Dict[str, object]) -> Optional[str]:
    hay = " ".join(
        [str(meta.get("title", "")), str(meta.get("summary", ""))]
        + [str(t) for t in meta.get("tags", [])]  # type: ignore[union-attr]
    ).lower()
    for theme, keywords in THEME_RULES:
        for kw in keywords:
            if kw in hay:
                return theme
    return None


def _sanitize_display(title: str, fallback: str) -> str:
    t = re.sub(r"[\[\]|]", " ", title).strip()
    t = re.sub(r"\s+", " ", t)
    return t or fallback


def _hub_filename(name: str) -> str:
    return f"hub-{name}.md"


def _write(path: Path, text: str, apply: bool) -> None:
    if apply:
        path.write_text(text, encoding="utf-8")


def _theme_page(name: str, members: List[Tuple[str, str, str]]) -> str:
    """members: list of (doc_type, doc_id, title)."""
    by_type: Dict[str, List[Tuple[str, str]]] = {}
    for dt, doc_id, title in members:
        by_type.setdefault(dt, []).append((doc_id, title))
    lines = [
        "---",
        "type: hub",
        "hub_kind: theme",
        f"title: {name}",
        "---",
        "",
        f"# 🧩 {name}｜主題樞紐",
        "",
        f"> 自動產生的業務主題樞紐頁，串接相關規格文件（共 {len(members)} 篇）。",
        "> 由 `python -m knowledge_base.cli build-hubs --apply` 產生，可重跑。",
        "",
        "[[_MOC|← 回知識庫地圖]]",
        "",
    ]
    for dt in sorted(by_type):
        docs = sorted(by_type[dt], key=lambda x: x[1])
        lines.append(f"## {dt}（{len(docs)}）")
        for doc_id, title in docs:
            disp = _sanitize_display(title, doc_id)
            lines.append(f"- [[{doc_id}|{disp}]]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _knowledge_page(name: str, desc: str, members: List[Tuple[str, str]]) -> str:
    """members: list of (doc_id, title)."""
    lines = [
        "---",
        "type: hub",
        "hub_kind: knowledge",
        f"title: {name}",
        "---",
        "",
        f"# 📚 {name}｜知識樞紐",
        "",
        f"> {desc}（共 {len(members)} 篇）。",
        "",
        "[[_MOC|← 回知識庫地圖]]",
        "",
    ]
    for doc_id, title in sorted(members, key=lambda x: x[1]):
        disp = _sanitize_display(title, doc_id)
        lines.append(f"- [[{doc_id}|{disp}]]")
    return "\n".join(lines).rstrip() + "\n"


def _moc_page(
    theme_counts: List[Tuple[str, int]],
    knowledge_counts: List[Tuple[str, int]],
) -> str:
    lines = [
        "---",
        "type: hub",
        "hub_kind: moc",
        "title: 知識庫地圖",
        "---",
        "",
        "# 🗺️ 知識庫地圖（MOC）",
        "",
        "> 全庫導覽主幹。每個樞紐頁把相關筆記串成一個可導覽的叢集。",
        "> 由 `python -m knowledge_base.cli build-hubs --apply` 自動產生。",
        "",
        "## 🧩 業務主題（規格文件）",
    ]
    for name, count in theme_counts:
        lines.append(f"- [[{_hub_filename(name)[:-3]}|{name}]]（{count}）")
    lines.append("")
    lines.append("## 📚 累積知識")
    for name, count in knowledge_counts:
        lines.append(f"- [[{_hub_filename(name)[:-3]}|{name}]]（{count}）")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_hub_pages(vault_path: Path, apply: bool = False) -> Dict[str, object]:
    vault_path = Path(vault_path)
    spec_dir = vault_path / SPEC_DIR
    hub_dir = vault_path / HUB_DIR

    # --- classify spec_docs into theme clusters ---
    theme_members: Dict[str, List[Tuple[str, str, str]]] = {}
    unmatched = 0
    total_specs = 0
    if spec_dir.is_dir():
        for f in sorted(spec_dir.glob("*.md")):
            total_specs += 1
            stem = f.stem
            meta = parse_meta(_read(f), stem)
            theme = classify_theme(meta)
            dt = _doc_type(stem)
            if theme is None:
                theme = f"其他-{dt}"
                unmatched += 1
            theme_members.setdefault(theme, []).append((dt, stem, str(meta["title"])))

    # --- knowledge-folder hubs ---
    knowledge_members: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for folder, name, desc in KNOWLEDGE_FOLDERS:
        fdir = vault_path / folder
        if not fdir.is_dir():
            continue
        members: List[Tuple[str, str]] = []
        for f in sorted(fdir.glob("*.md")):
            meta = parse_meta(_read(f), f.stem)
            members.append((f.stem, str(meta["title"])))
        if members:
            knowledge_members.append((folder, name, desc, members))

    # --- write files ---
    if apply:
        hub_dir.mkdir(parents=True, exist_ok=True)

    files_written = 0
    total_links = 0

    # order theme hubs: defined themes first (by rule order), then 其他-* buckets
    theme_order = [t for t, _ in THEME_RULES]
    ordered_themes = [t for t in theme_order if t in theme_members]
    ordered_themes += sorted(t for t in theme_members if t not in theme_order)

    theme_counts: List[Tuple[str, int]] = []
    for theme in ordered_themes:
        members = theme_members[theme]
        theme_counts.append((theme, len(members)))
        total_links += len(members)
        _write(hub_dir / _hub_filename(theme), _theme_page(theme, members), apply)
        files_written += 1

    knowledge_counts: List[Tuple[str, int]] = []
    for _folder, name, desc, members in knowledge_members:
        knowledge_counts.append((name, len(members)))
        total_links += len(members)
        _write(hub_dir / _hub_filename(name), _knowledge_page(name, desc, members), apply)
        files_written += 1

    _write(hub_dir / "_MOC.md", _moc_page(theme_counts, knowledge_counts), apply)
    files_written += 1
    total_links += len(theme_counts) + len(knowledge_counts)

    return {
        "apply": apply,
        "total_specs": total_specs,
        "unmatched_specs": unmatched,
        "theme_hubs": theme_counts,
        "knowledge_hubs": knowledge_counts,
        "hub_files": files_written,
        "total_links": total_links,
    }
