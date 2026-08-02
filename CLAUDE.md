<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->

## Knowledge Base Web

A separate knowledge base (patent analysis methodology, and other domains as they're added) is queryable via the `kb-web` service. See `kb-web/README.md` for the `curl` invocation. Use it when a task touches patent-analysis terminology or methodology.

## Post-push dev notes

After every successful `git push`, a PostToolUse hook (`.claude/hooks/post_push_devnote.py`) reminds Claude to write a markdown dev note (what changed, observations, lessons) and import it into the Zeabur knowledge base via `scripts/import-dev-note.sh <note.md>` (doc_type=`dev_note`, requires `KB_API_TOKEN` in the Windows User environment). One note per batch of changes — skip on retry pushes.
