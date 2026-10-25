#!/usr/bin/env bash
# 把伺服器上的 Mongo 備份拉回本機（異地備份；主機整台壞掉時還有一份）。
#   deploy/scripts/pull-backups.sh [本機目的資料夾]
set -euo pipefail
HOST="${DEPLOY_HOST:-ubuntu@43.133.44.216}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/finlab_lighthouse}"
DEST="${1:-$HOME/finlab-backups}"
mkdir -p "$DEST"
scp -q -i "$KEY" -o BatchMode=yes "$HOST:finlab/backups/mongo-*.archive.gz" "$DEST/"
ls -1t "$DEST"/mongo-*.archive.gz | tail -n +31 | xargs -r rm -f
echo "backups in $DEST: $(ls "$DEST"/mongo-*.archive.gz | wc -l)"
