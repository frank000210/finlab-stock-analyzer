# 附錄：速查表與下一步

## 我該用哪個機制

| 你遇到的情況 | 用這個 | 單元 |
|---|---|---|
| 同一個慣例它錯了兩次 | CLAUDE.md | U1 |
| 規則只跟某些檔案有關 | `.claude/rules/` + `paths` | U1 |
| 想改變回應的語氣、長度、格式 | Output style | U1 |
| 某些指令不想每次都按允許 | 權限 allow 規則 | U2 |
| 某些檔案或指令絕對不能碰 | 權限 deny 規則 | U2 |
| 要查外部系統的資料 | MCP | U2 |
| 同一段提示詞打了第三次 | Skill（動作型） | U3 |
| 有一份參考資料偶爾才需要 | Skill（參考型） | U3 |
| 大改動怕改錯方向 | Plan mode | U4 |
| 改錯了想退回 | Esc 兩下 / `/rewind` | U4 |
| 支線任務把對話塞滿雜訊 | Subagent | U5 |
| 需要唯讀的審查角色 | Subagent + `tools` 限制 | U5 |
| 某件事每次都要發生、不能例外 | Hook | U6 |
| 讀過外部內容後要提高警戒 | PostToolUse + PreToolUse hook | U6 |
| 第二個 repo 也要同一套設定 | Plugin | L8 |
| 要分享給團隊並持續更新 | Marketplace | L9 |

## 各機制比較

| 機制 | 何時載入 | context 成本 | 強制性 |
|---|---|---|---|
| CLAUDE.md | 每個 session 開頭 | 每次請求都有 | 指示（不保證） |
| Output style | session 開頭、切換時 | 每次請求都有 | 指示（不保證） |
| Skill | 開頭只載 description，用到才載全文 | 低 | 指示（不保證） |
| MCP | 開頭只載工具名稱，用到才載完整定義 | 低 | — |
| Subagent | 派工時 | 獨立 context，不佔主對話 | 工具限制是強制的 |
| Hook | 事件發生時 | 零（除非有輸出） | **強制** |
| 權限規則 | 每次工具呼叫 | 零 | **強制** |

## 設定檔位置總表

| 東西 | 個人（所有專案） | 專案（進版控） | 本機（不進版控） |
|---|---|---|---|
| 指示 | `~/.claude/CLAUDE.md` | `./CLAUDE.md` | `./CLAUDE.local.md` |
| 設定、權限、hook | `~/.claude/settings.json` | `.claude/settings.json` | `.claude/settings.local.json` |
| Skill | `~/.claude/skills/` | `.claude/skills/` | — |
| Subagent | `~/.claude/agents/` | `.claude/agents/` | — |
| Output style | `~/.claude/output-styles/` | `.claude/output-styles/` | — |
| MCP | `~/.claude.json`（user scope） | `.mcp.json` | `~/.claude.json`（local scope） |
| Rules | `~/.claude/rules/` | `.claude/rules/` | — |

## 名詞表

| 名詞 | 英文 | 說明 |
|---|---|---|
| 代理 | Agent | 能自己決定使用工具、根據結果調整下一步的 AI 系統 |
| 上下文視窗 | Context window | 模型一次能讀的全部內容，就是它的工作記憶 |
| 工具呼叫 | Tool use / Function calling | 模型輸出結構化請求，由外層程式代為執行 |
| 外層程式 | Harness | 包在模型外面、提供工具與管理 context 的程式（Claude Code 本身） |
| 檢索增強生成 | RAG | 先找出相關資料，再放進 context 讓模型回答 |
| 漸進式載入 | Progressive disclosure | 先載入摘要，需要時才載入全文 |
| 提示注入 | Prompt injection | 外部內容裡藏著指令，誘導 Agent 做出非預期的事 |
| 前置資料 | Frontmatter | Markdown 檔開頭 `---` 之間的 YAML 設定 |
| 子代理 | Subagent | 在獨立 context 執行、只回傳摘要的代理 |
| 外掛 | Plugin | 把 skill、agent、hook、MCP 打包成一個可安裝單位 |

## 下一步：Agent SDK（方案 B）

Claude Code 的擴充點能處理大部分客製需求。如果你需要的是**自己的介面、嵌進自己的系統、或做成產品**，下一步是 **Claude Agent SDK**：

- 就是 Claude Code 底層的代理引擎，有 Python 與 TypeScript 版本
- 這門課學到的 skill、hook、subagent、MCP、權限，在 SDK 裡都能用程式控制
- 入門：[Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) → [Quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart)

## 持續學習

- 官方文件索引：<https://code.claude.com/docs/llms.txt>
- 每週更新：官方文件的 What's New
- 官方 plugin 範例：<https://github.com/anthropics/claude-code/tree/main/plugins>
- 部落格文章：[Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)
