#!/bin/sh
# 把一份開發筆記（markdown）匯入 Zeabur 上的 kb-web 知識庫，doc_type=dev_note。
# 用法: scripts/import-dev-note.sh <note.md>
# 需要: 環境變數 KB_API_TOKEN（Windows User env，同 FINMIND_TOKEN 慣例）。
# 覆寫目標站台: 設 KB_WEB_URL（預設正式站）。
set -e

NOTE_FILE="$1"
KB_WEB_URL="${KB_WEB_URL:-https://frank210-kb-web.zeabur.app}"

if [ -z "$NOTE_FILE" ] || [ ! -f "$NOTE_FILE" ]; then
  echo "usage: $0 <note.md>  (file not found: $NOTE_FILE)" >&2
  exit 1
fi
if [ -z "$KB_API_TOKEN" ]; then
  echo "KB_API_TOKEN not set (add it to Windows User env vars)" >&2
  exit 1
fi

# 檔名會成為 KB 內的 doc 標題基底，匯入前確認有意義（建議格式:
# dev-note-YYYY-MM-DD-<主題>.md）。
curl -sf -X POST "$KB_WEB_URL/api/import/file" \
  -H "Authorization: Bearer $KB_API_TOKEN" \
  -F "file=@$NOTE_FILE;type=text/markdown" \
  -F "domain=dev_note"
echo ""
echo "imported $NOTE_FILE -> $KB_WEB_URL (doc_type=dev_note)"
