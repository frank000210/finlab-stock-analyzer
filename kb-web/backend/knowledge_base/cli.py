from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowledge_base.db import get_db
from knowledge_base.config import load_settings
from knowledge_base.eventlog_ingest import ingest_event_logs
from knowledge_base.hub_pages import build_hub_pages
from knowledge_base.ingest import ingest_session_file
from knowledge_base.im_confidence import validate_im_business_confidence
from knowledge_base.markdown_sync import export_vault, import_vault
from knowledge_base.query import (
    build_system_prompt_injection,
    format_knowledge_context,
    search_knowledge,
)
from knowledge_base.schema import init_schema
from knowledge_base.semantic_search import rebuild_semantic_index
from knowledge_base.session_lifecycle import on_session_close, on_session_open
from knowledge_base.spec_ingest import ingest_spec_documents
from knowledge_base.swds_ingest import draft_swds, ingest_swds, suggest_swds
from knowledge_base.ui_screen_ingest import ingest_ui_screens
from knowledge_base.vault_clean import clean_spec_docs
from knowledge_base.vsd_ingest import ingest_vsd_files, ingest_ppt_files

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local knowledge base CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-schema", help="Create MongoDB collections and indexes")

    ingest_cmd = sub.add_parser("ingest-session", help="Ingest one session JSON file")
    ingest_cmd.add_argument("--file", required=True, help="Path to session JSON")

    ingest_events_cmd = sub.add_parser(
        "ingest-event-logs",
        help="Ingest all Copilot session events.jsonl logs from a root directory",
    )
    ingest_events_cmd.add_argument(
        "--root",
        default=r"C:\Users\user\.copilot\session-state",
        help="Root folder that contains session-state subfolders",
    )
    ingest_events_cmd.add_argument(
        "--profile-key",
        default="owner-default",
        help="Decision profile key to update",
    )
    ingest_specs_cmd = sub.add_parser(
        "ingest-specs",
        help="Ingest SRS/SDS/spec documents into isolated spec_docs collection",
    )
    ingest_specs_cmd.add_argument(
        "--root",
        required=True,
        help="Root directory containing specs (.md/.txt/.rst/.doc/.docx/.ppt/.pptx/.xls/.xlsx/.vsd/.java)",
    )
    ingest_specs_cmd.add_argument(
        "--doc-type",
        help="Optional forced document type (e.g., srs, sds)",
    )
    ingest_specs_cmd.add_argument(
        "--content-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep only main chapter content and remove leading revision-history section (default: true)",
    )
    ingest_specs_cmd.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Progress batch size for large imports (default: 50)",
    )
    ingest_specs_cmd.add_argument(
        "--max-files",
        type=int,
        help="Optional limit for number of files to ingest",
    )
    ingest_specs_cmd.add_argument(
        "--strict-quality",
        action="store_true",
        help="Skip files that fail quality checks",
    )
    ingest_specs_cmd.add_argument(
        "--report-path",
        help="Optional path to write detailed JSON report",
    )
    validate_im_cmd = sub.add_parser(
        "validate-im-confidence",
        help="Cross-validate IM business descriptions and upgrade confidence levels",
    )
    validate_im_cmd.add_argument(
        "--doc-type",
        default="im-spec",
        help="Target IM-like doc_type to validate (default: im-spec)",
    )
    validate_im_cmd.add_argument(
        "--top-k-evidence",
        type=int,
        default=5,
        help="Number of evidence documents to keep per IM document (default: 5)",
    )
    validate_im_cmd.add_argument(
        "--report-path",
        help="Optional path to write detailed JSON validation report",
    )

    sub.add_parser("export-vault", help="Export MongoDB docs into markdown vault")
    sub.add_parser("import-vault", help="Import markdown vault edits into MongoDB")
    sub.add_parser("sync", help="Run export then import")

    clean_specs_cmd = sub.add_parser(
        "clean-specs",
        help="Strip structure/history noise tags and leading revision-history blocks from spec_docs",
    )
    clean_specs_cmd.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes to MongoDB (default is a dry-run report)",
    )

    build_hubs_cmd = sub.add_parser(
        "build-hubs",
        help="Generate Obsidian hub/MOC pages so the graph forms navigable clusters",
    )
    build_hubs_cmd.add_argument(
        "--apply",
        action="store_true",
        help="Write hub files into vault/hubs/ (default is a dry-run report)",
    )

    ingest_vsd_cmd = sub.add_parser(
        "ingest-vsd",
        help="Ingest Visio VSD diagram files into spec_docs (requires LibreOffice)",
    )
    ingest_vsd_cmd.add_argument(
        "path",
        nargs="+",
        help="One or more VSD file paths (or a directory containing VSD files)",
    )
    ingest_vsd_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without writing to MongoDB",
    )

    ingest_ppt_cmd = sub.add_parser(
        "ingest-ppt",
        help="Ingest PowerPoint PPT/PPTX presentation files into spec_docs (via LibreOffice)",
    )
    ingest_ppt_cmd.add_argument(
        "path",
        nargs="+",
        help="One or more PPT/PPTX file paths (or a directory containing PPT/PPTX files)",
    )
    ingest_ppt_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without writing to MongoDB",
    )

    ingest_ui_cmd = sub.add_parser(
        "ingest-ui-screens",
        help="Ingest UI screen walkthrough DOCX files into the ui_screens collection",
    )
    ingest_ui_cmd.add_argument(
        "path",
        nargs="+",
        help="One or more DOCX file paths (or a directory containing DOCX files)",
    )
    ingest_ui_cmd.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip Windows OCR step (faster, no OCR text extracted from screenshots)",
    )

    swds_ingest_cmd = sub.add_parser(
        "swds-ingest",
        help="Extract OR SWDS documents into swds_precedents (SCN→改表/配合功能 corpus)",
    )
    swds_ingest_cmd.add_argument(
        "--root",
        default=None,
        help="Root folder of SWDS docs (default: REF/OR作業處理流程)",
    )
    swds_ingest_cmd.add_argument(
        "--apply",
        action="store_true",
        help="Persist parsed precedents to MongoDB (default is a dry-run report)",
    )
    swds_ingest_cmd.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N files (for smoke testing)",
    )

    swds_suggest_cmd = sub.add_parser(
        "swds-suggest",
        help="Given an SCN description, list similar SWDS precedents with changed tables/functions",
    )
    swds_suggest_cmd.add_argument("scn_text", help="SCN / requirement description text")
    swds_suggest_cmd.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of precedents to return",
    )

    swds_draft_cmd = sub.add_parser(
        "swds-draft",
        help="Given an SCN, generate a ready-to-edit SWDS skeleton (candidate 第2章 tables + 第3章 functions from precedents)",
    )
    swds_draft_cmd.add_argument("scn_text", help="SCN / requirement description text")
    swds_draft_cmd.add_argument(
        "--top-k", type=int, default=8, help="Number of precedents to aggregate"
    )
    swds_draft_cmd.add_argument(
        "--title", default=None, help="Title for the new SWDS draft"
    )
    swds_draft_cmd.add_argument(
        "--category", default=None, help="領域分類 for the new SWDS draft"
    )
    swds_draft_cmd.add_argument(
        "--out", default=None, help="Write the drafted markdown to this file (UTF-8)"
    )

    page_spec_cmd = sub.add_parser(
        "page-spec",
        help="Given an operation name, list its page fields and validation rules from source code + SRS/SDS",
    )
    page_spec_cmd.add_argument("operation_name", help="Chinese operation name or base_code (e.g. 個案增刪優惠 or addDiscnt)")
    page_spec_cmd.add_argument("--top-k", type=int, default=3, help="SRS/SDS semantic search results")
    page_spec_cmd.add_argument("--out", default=None, help="Write Markdown report to this file")
    page_spec_cmd.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON instead of Markdown")

    src_query_cmd = sub.add_parser(
        "source-query",
        help="Query source code KB: given a Chinese name, OR-code, or BackingBean name, return the E2E chain",
    )
    src_query_cmd.add_argument("search_term", help="Chinese operation name, OR-code, or BackingBean code")
    src_query_cmd.add_argument("--top-k", type=int, default=5, help="Max results to return")

    src_ingest_cmd = sub.add_parser(
        "source-ingest",
        help="Ingest MO2_Sourcetree source code into MongoDB (code_menu, code_beans, code_e2e_chain)",
    )
    src_ingest_cmd.add_argument(
        "--source-root",
        default=r"C:\Users\user\Documents\github\nextBSS\MO2_Sourcetree",
        help="Path to MO2_Sourcetree root directory",
    )
    src_ingest_cmd.add_argument(
        "--codefunction-json",
        required=True,
        help="Path to exported codefunction JSON (from Informix tableutil query)",
    )

    query_cmd = sub.add_parser(
        "query",
        help="Query knowledge base for related insights",
    )
    query_cmd.add_argument("query_text", nargs="?", default="", help="Query string")
    query_cmd.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return",
    )
    query_cmd.add_argument(
        "--tags",
        nargs="*",
        help="Optional tag filters (e.g., --tags mongodb decision)",
    )
    query_cmd.add_argument(
        "--format",
        choices=["json", "markdown", "injection"],
        default="markdown",
        help="Output format",
    )
    query_cmd.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic vector search and use lexical tags only",
    )
    query_cmd.add_argument(
        "--scope",
        choices=["session", "spec", "all"],
        default="session",
        help="Search scope isolation (default: session)",
    )

    semantic_cmd = sub.add_parser(
        "semantic-reindex",
        help="Rebuild semantic vector index for hybrid search",
    )
    semantic_cmd.add_argument(
        "--force",
        action="store_true",
        help="Rebuild vectors even when text hash has not changed",
    )

    session_open_cmd = sub.add_parser(
        "session-open",
        help="Auto-inject knowledge context when a session starts",
    )
    session_open_cmd.add_argument("--session-id", required=True, help="Session id")
    session_open_cmd.add_argument(
        "--prompt",
        required=True,
        help="User prompt or session goal for context retrieval",
    )
    session_open_cmd.add_argument("--top-k", type=int, default=5, help="Number of context items")
    session_open_cmd.add_argument(
        "--scope",
        choices=["session", "spec", "all"],
        default="session",
        help="Context scope for auto-injection (default: session)",
    )
    session_open_cmd.add_argument(
        "--format",
        choices=["json", "injection"],
        default="injection",
        help="Output format",
    )

    session_close_cmd = sub.add_parser(
        "session-close",
        help="Auto-learn from session event logs and rebuild index",
    )
    session_close_cmd.add_argument("--session-id", required=True, help="Session id")
    session_close_cmd.add_argument(
        "--root",
        default=r"C:\Users\user\.copilot\session-state",
        help="Root folder that contains session-state subfolders",
    )
    session_close_cmd.add_argument(
        "--profile-key",
        default="owner-default",
        help="Decision profile key to update",
    )
    session_close_cmd.add_argument(
        "--sync",
        action="store_true",
        help="Run markdown sync (export+import) after learning",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    db = get_db()

    if args.command == "init-schema":
        init_schema(db)
        print("Schema initialized.")
        return

    if args.command == "ingest-session":
        counts = ingest_session_file(db, Path(args.file))
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "ingest-event-logs":
        counts = ingest_event_logs(
            db=db,
            root_path=Path(args.root),
            profile_key=args.profile_key,
        )
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "ingest-specs":
        counts = ingest_spec_documents(
            db=db,
            root_path=Path(args.root),
            forced_doc_type=args.doc_type,
            content_only=args.content_only,
            batch_size=args.batch_size,
            max_files=args.max_files,
            strict_quality=args.strict_quality,
            report_path=Path(args.report_path) if args.report_path else None,
        )
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "validate-im-confidence":
        counts = validate_im_business_confidence(
            db=db,
            doc_type=args.doc_type,
            top_k_evidence=args.top_k_evidence,
            report_path=Path(args.report_path) if args.report_path else None,
        )
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "export-vault":
        result = export_vault(db)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "clean-specs":
        result = clean_spec_docs(db, apply=args.apply)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "build-hubs":
        result = build_hub_pages(load_settings().vault_path, apply=args.apply)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "ingest-vsd":
        source_paths: list[Path] = []
        for p in args.path:
            resolved = Path(p)
            if resolved.is_dir():
                source_paths.extend(resolved.glob("*.vsd"))
                source_paths.extend(resolved.glob("*.VSD"))
            elif resolved.suffix.lower() == ".vsd":
                source_paths.append(resolved)
        if not source_paths:
            print(json.dumps({"status": "error", "message": "No VSD files found"}))
            return
        result = ingest_vsd_files(source_paths, db, apply=not args.dry_run)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, default=str))
        return

    if args.command == "ingest-ppt":
        source_paths: list[Path] = []
        for p in args.path:
            resolved = Path(p)
            if resolved.is_dir():
                for ext in ("*.ppt", "*.PPT", "*.pptx", "*.PPTX"):
                    source_paths.extend(resolved.glob(ext))
            elif resolved.suffix.lower() in {".ppt", ".pptx"}:
                source_paths.append(resolved)
        if not source_paths:
            print(json.dumps({"status": "error", "message": "No PPT/PPTX files found"}))
            return
        result = ingest_ppt_files(source_paths, db, apply=not args.dry_run)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, default=str))
        return

    if args.command == "ingest-ui-screens":
        # Expand paths: each arg can be a file or directory
        source_paths: list[Path] = []
        for p in args.path:
            resolved = Path(p)
            if resolved.is_dir():
                source_paths.extend(resolved.glob("*.docx"))
            elif resolved.suffix.lower() == ".docx":
                source_paths.append(resolved)
        if not source_paths:
            print(json.dumps({"status": "error", "message": "No DOCX files found"}))
            return
        counts = ingest_ui_screens(db, source_paths, do_ocr=not args.no_ocr)
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "swds-ingest":
        root = Path(args.root) if args.root else None
        result = ingest_swds(db, root=root, apply=args.apply, limit=args.limit)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "swds-suggest":
        result = suggest_swds(db, args.scn_text, top_k=args.top_k)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "swds-draft":
        result = draft_swds(
            db,
            args.scn_text,
            top_k=args.top_k,
            title=args.title,
            category=args.category,
        )
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(result["draft_markdown"], encoding="utf-8")
            result["written_to"] = str(out_path)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "import-vault":
        result = import_vault(db)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        return

    if args.command == "sync":
        exported = export_vault(db)
        imported = import_vault(db)
        print(
            json.dumps(
                {"status": "ok", "export": exported, "import": imported},
                ensure_ascii=False,
            )
        )
        return

    if args.command == "query":
        query_text = args.query_text or input("Enter query: ")
        if not query_text.strip():
            print(json.dumps({"status": "error", "message": "Empty query"}, ensure_ascii=False))
            return

        results = search_knowledge(
            db,
            query_text,
            top_k=args.top_k,
            include_tags=args.tags,
            use_semantic=not args.no_semantic,
            scope=args.scope,
        )

        if args.format == "json":
            output = {
                "status": "ok",
                "query": query_text,
                "results": [
                    {
                        "type": r["type"],
                        "title": r["doc"].get("title") or r["doc"].get("slug") or r["doc"].get("decision_id"),
                        "relevance_score": r["relevance_score"],
                        "document": {k: v for k, v in r["doc"].items() if k != "_id"},
                    }
                    for r in results
                ],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))

        elif args.format == "markdown":
            formatted = format_knowledge_context(results)
            print(f"Query: {query_text}\n")
            if formatted:
                print(formatted)
            else:
                print("No related knowledge found.")

        elif args.format == "injection":
            injection = build_system_prompt_injection(
                db,
                query_text,
                top_k=args.top_k,
                use_semantic=not args.no_semantic,
                scope=args.scope,
            )
            print(injection if injection else "No related knowledge found.")

        return

    if args.command == "page-spec":
        from knowledge_base.page_spec import query_page_spec, render_page_spec
        spec = query_page_spec(db, args.operation_name, top_k=args.top_k)
        if args.as_json:
            print(json.dumps({"status": "ok", "spec": spec}, ensure_ascii=False, indent=2))
        else:
            md = render_page_spec(spec)
            if args.out:
                out_path = Path(args.out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(md, encoding="utf-8")
                print(f"Written to {out_path}")
            else:
                print(md)
        return

    if args.command == "source-query":
        from knowledge_base.source_query import query_source_chain
        results = query_source_chain(db, args.search_term, limit=args.top_k)
        print(results)
        return

    if args.command == "source-ingest":
        from knowledge_base.source_ingest import ingest_source_code
        with open(args.codefunction_json, encoding="utf-8") as fh:
            cf_rows = json.load(fh)
        counts = ingest_source_code(db, source_root=args.source_root, codefunction_rows=cf_rows)
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "semantic-reindex":
        counts = rebuild_semantic_index(db, force=args.force)
        print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False))
        return

    if args.command == "session-open":
        payload = on_session_open(
            db=db,
            session_id=args.session_id,
            prompt_text=args.prompt,
            top_k=args.top_k,
            scope=args.scope,
        )
        if args.format == "json":
            print(json.dumps({"status": "ok", **payload}, ensure_ascii=False, indent=2))
        else:
            print(payload["injection"] if payload["injection"] else "No related knowledge found.")
        return

    if args.command == "session-close":
        payload = on_session_close(
            db=db,
            session_id=args.session_id,
            root_path=Path(args.root),
            profile_key=args.profile_key,
            sync_after_ingest=args.sync,
        )
        print(json.dumps({"status": "ok", **payload}, ensure_ascii=False, indent=2))
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
