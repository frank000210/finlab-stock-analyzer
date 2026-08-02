<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->

## Knowledge Base MCP Server (kb-web)

A **global MCP server** (`kb-web`) is installed at `C:\Users\frank\.claude\mcp-servers\kb-web\server.py` and registered in `~/.claude.json`. It is available in **every local Claude Code session** without any extra setup.

Three tools are exposed:

| Tool | Purpose |
|---|---|
| `kb_ask(question, domain?)` | 向知識庫提問，回傳 AI 答案 + 引用來源 |
| `kb_list_domains()` | 列出所有領域與文件數 |
| `kb_write(content, domain, title)` | 匯入 markdown 文件（post-commit 優化紀錄用） |

**When to use:**
- Before implementing a feature that might overlap with past decisions, call `kb_ask` to check for prior art or constraints.
- After every successful `git push`, call `kb_write` with `domain='dev_note'` to record what changed, what problems were encountered, and reusable lessons learned.

Auth is automatic: `KB_API_TOKEN` is read from the process env, falling back to the Windows User environment registry (`HKCU\Environment`).

## Post-push dev notes

After every successful `git push`, a PostToolUse hook (`.claude/hooks/post_push_devnote.py`) reminds Claude to write a markdown dev note (what changed, observations, lessons) and import it into the Zeabur knowledge base using the `kb_write` MCP tool (preferred) or `scripts/import-dev-note.sh` as fallback. One note per batch of changes — skip on retry pushes.
