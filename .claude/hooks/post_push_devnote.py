"""PostToolUse hook: 偵測成功的 git push 後，提醒 Claude 整理本次上版的
優化內容/觀察/心得成 dev note，並匯入 Zeabur 知識庫（doc_type=dev_note）。

只做「提醒＋給明確指令」——筆記內容需要 AI 判斷與撰寫，shell hook 自己
寫不出有意義的心得，所以把工作交回給對話中的 Claude 執行。
"""

import json
import re
import sys


def main() -> int:
    # Windows 主控台預設 cp1252，印中文會 UnicodeEncodeError。
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command", "")
    # 只匹配位於指令開頭或 ;/&&/|| 之後的 git push，避免像
    # echo "...git push..." 這種只是字串內容提到的誤觸。
    if not re.search(r"(?:^|[;&|]\s*|&&\s*|\|\|\s*)git\s+[^\n|;&]*\bpush\b", command):
        return 0
    if "--dry-run" in command:
        return 0

    context = (
        "【上版 dev note hook】剛偵測到 git push。若這次 push 成功完成（請自行確認"
        "推送結果，失敗就忽略本提醒），請執行上版後的知識庫歸檔流程：\n"
        "1. 整理本次上版內容，寫成一份 markdown 開發筆記。內容須包含三段：\n"
        "   - 本次優化/變更內容（做了什麼、為什麼）\n"
        "   - 過程觀察（撞到什麼問題、根因是什麼）\n"
        "   - 心得與可複用的原則（下次遇到同類問題怎麼更快）\n"
        "2. 優先用 kb_write MCP 工具（domain='dev_note'，title='dev-note-YYYY-MM-DD-主題'）"
        "直接匯入 Zeabur 知識庫。\n"
        "   若 kb_write 不可用（工具未載入），則退而用 scripts/import-dev-note.sh。\n"
        "3. 匯入成功後在回覆中告知使用者已歸檔。\n"
        "同一次上版只要歸檔一次：若這次 push 只是重試或先前已為同批變更寫過"
        " dev note，跳過即可。"
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
