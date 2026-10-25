#!/usr/bin/env bash
# 把指定服務的原始碼送上伺服器、在伺服器上建置並重啟。
#
#   deploy/scripts/ship.sh finlab            # 主站（本 repo 目前 HEAD）
#   deploy/scripts/ship.sh kb-web            # kb-web（本 repo 的 kb-web/）
#   deploy/scripts/ship.sh food              # 訂餐網站（food-ordering-system repo 的 HEAD）
#   deploy/scripts/ship.sh config            # 只更新 deploy/（compose、Caddyfile、腳本）
#
# 用 git archive 送「已 commit 的內容」，工作目錄沒 commit 的改動不會上去。
# 一次只建一個服務：4GB 主機同時建 kb-web（torch）和主站前端會很吃緊。
set -euo pipefail

SERVICE="${1:?usage: ship.sh finlab|kb-web|food|config}"
HOST="${DEPLOY_HOST:-ubuntu@43.133.44.216}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/finlab_lighthouse}"
FOOD_REPO="${FOOD_REPO:-$(cd "$(dirname "$0")/../../.." && pwd)/food-ordering-system}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
SSH=(ssh -i "$KEY" -o BatchMode=yes "$HOST")

push_tree() {  # $1 = 本機 repo，$2 = 伺服器目標資料夾，$3 = git 路徑（可省略）
  git -C "$1" archive --format=tar HEAD ${3:+"$3"} |
    "${SSH[@]}" "rm -rf '$2.new' && mkdir -p '$2.new' && tar -x -C '$2.new' && rm -rf '$2' && mv '$2.new' '$2'"
}

case "$SERVICE" in
  config)
    git -C "$REPO_ROOT" archive --format=tar HEAD deploy |
      "${SSH[@]}" "mkdir -p ~/finlab/backups && tar -x -C ~/finlab && chmod +x ~/finlab/deploy/scripts/*.sh"
    # 映像還沒建好（第一次部署）時不能 up：compose 會一次同時建三個映像
    "${SSH[@]}" 'cd ~/finlab/deploy && if docker image inspect finlab-stock-analyzer:prod kb-web:prod food-ordering-system:prod >/dev/null 2>&1; then docker compose up -d --no-build --remove-orphans; else echo "images missing: ship finlab / kb-web / food first"; fi'
    exit 0 ;;
  finlab|kb-web) push_tree "$REPO_ROOT" "finlab/src/finlab" ;;
  food) push_tree "$FOOD_REPO" "finlab/src/food" ;;
  *) echo "unknown service: $SERVICE" >&2; exit 2 ;;
esac

"${SSH[@]}" "cd ~/finlab/deploy && docker compose build '$SERVICE' && docker compose up -d '$SERVICE' && docker image prune -f >/dev/null"
echo "shipped $SERVICE ($(git -C "$([ "$SERVICE" = food ] && echo "$FOOD_REPO" || echo "$REPO_ROOT")" rev-parse --short HEAD))"
