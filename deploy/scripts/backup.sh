#!/usr/bin/env bash
# 每日 Mongo 備份（伺服器 crontab 執行），保留最近 7 份。
#   15 3 * * * ~/finlab/deploy/scripts/backup.sh >> ~/finlab/backups/backup.log 2>&1
# 這只防「資料被刪/改壞」；防「整台主機掛掉」要再把 ~/finlab/backups 拉回別處
# （本機：deploy/scripts/pull-backups.sh）。
set -euo pipefail
cd ~/finlab/deploy
STAMP="$(date -u +%Y%m%d-%H%M)"
docker compose exec -T mongo sh -c \
  'mongodump --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --gzip --archive' \
  > "../backups/mongo-$STAMP.archive.gz"
ls -1t ../backups/mongo-*.archive.gz | tail -n +8 | xargs -r rm -f
echo "$(date -u +%FT%TZ) backup ok mongo-$STAMP.archive.gz $(du -h "../backups/mongo-$STAMP.archive.gz" | cut -f1)"
