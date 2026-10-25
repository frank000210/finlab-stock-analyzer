# 自架部署（取代 Zeabur）

Zeabur 於 2026-12-31 停運，正式站改跑在騰訊雲 Lighthouse（新加坡，2 核 4G、60G、Ubuntu 24.04）。
所有服務在同一台主機上用 Docker Compose 跑，Caddy 負責 HTTPS。

| 服務 | 網址 | 來源 |
|---|---|---|
| finlab-stock-analyzer | `https://finlab.43-133-44-216.sslip.io` | 本 repo 根目錄 Dockerfile |
| kb-web | `https://kb.43-133-44-216.sslip.io` | 本 repo `kb-web/` |
| 訂餐前台 / 後台 | `https://food.…` / `https://food-admin.…` | `food-ordering-system` repo |
| MongoDB 8 | 不對外開放 | `mongo:8.0` 映像 |

沒有自有網域，用 [sslip.io](https://sslip.io)：`<名稱>.43-133-44-216.sslip.io` 會解析回主機 IP。買網域後改 `deploy/.env` 的 `BASE_HOST`、各 `secrets/*.env` 的網址，再 `ship.sh config`。

## 伺服器目錄

```
~/finlab/deploy/    本資料夾（ship.sh config 同步）＋ .env（BASE_HOST）
~/finlab/secrets/   mongo.env finlab.env kbweb.env food.env（chmod 600，不進 git；範本在 secrets.example/）
~/finlab/src/       各服務原始碼（ship.sh 用 git archive 送上來，在伺服器上建置）
~/finlab/backups/   每日 Mongo 備份（保留 7 份）
```

## 日常操作（本機 Git Bash，金鑰 `~/.ssh/finlab_lighthouse`）

```bash
deploy/scripts/ship.sh finlab     # 部署主站（目前已 commit 的 HEAD）
deploy/scripts/ship.sh kb-web
deploy/scripts/ship.sh food       # 訂餐網站（../food-ordering-system 的 HEAD）
deploy/scripts/ship.sh config     # 只改了 compose / Caddyfile / 腳本時
deploy/scripts/pull-backups.sh    # 把備份拉回本機 ~/finlab-backups
```

上線前照舊先在 WSL Docker 跑 Playwright（`scripts/run-local.ps1` + pre-push hook）。

## 在伺服器上（`ssh -i ~/.ssh/finlab_lighthouse ubuntu@43.133.44.216`）

```bash
cd ~/finlab/deploy
docker compose ps                    # 狀態
docker compose logs -f --tail=100 finlab
docker compose restart finlab
docker stats --no-stream             # 記憶體（4GB 主機，各服務有 mem_limit）
```

還原備份：

```bash
docker compose exec -T mongo sh -c 'mongorestore -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --gzip --archive --drop' < ../backups/mongo-<時間>.archive.gz
```

## 安全設定

- SSH 只接受金鑰（密碼與 root 登入已關）；騰訊雲防火牆只開 22 / 80 / 443。
- Mongo 不開 port；應用程式用只有 readWrite 權限的 `app` 帳號，root 只給備份用。
- 後台（`/admin`）只接受 `ADMIN_SECRET` 密碼登入，同一 IP 10 分鐘內錯 10 次會被擋。
- 訂餐後台目前 `ADMIN_AUTH_DISABLED=1`（測試期免登入），正式上線前要從 `secrets/food.env` 刪掉。
