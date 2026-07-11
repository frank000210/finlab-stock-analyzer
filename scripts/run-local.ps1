<#
.SYNOPSIS
  Run FinLab Stock Analyzer locally in Docker (WSL), sourcing FINMIND_TOKEN
  from the Windows 11 environment variable instead of storing it in .env.

.DESCRIPTION
  - Reads FINMIND_TOKEN from the Windows environment (process -> User -> Machine).
  - Forwards it into the WSL "Ubuntu" distro via WSLENV.
  - Ensures the shared docker network + MongoDB container are up.
  - (Re)starts the app container with the real token and Mongo wired in.

  App:    http://localhost:8000   (host 8000 -> container 8080; the SPA
          hardcodes localhost:8000 for its API calls when on localhost)
  Mongo:  localhost:27017

.PARAMETER Name
  Container/image name suffix (default "test"). Use a distinct name when
  running a second, isolated instance alongside another one (see NOTES).

.PARAMETER Port
  Host port to publish (default 8000). Use a different port for a second
  instance so it doesn't collide with one already running on 8000.

.PARAMETER ProjPath
  WSL path to build from (default the main checkout). Point this at a git
  worktree's WSL-mapped path (e.g. /mnt/f/github/.../\.claude\worktrees\<name>,
  translated to /mnt/f/github/.../.claude/worktrees/<name>) when verifying a
  branch checked out in a worktree rather than the main repo.

.NOTES
  Requires: WSL distro "Ubuntu" with docker.io installed (see 交接SOP / README).

  F4 — running multiple Claude Code sessions/worktrees in parallel: this
  script's defaults (image/container "finlab-stock-analyzer:test" /
  "finlab-test", port 8000) are shared across every checkout that runs it
  unmodified. Two sessions both rebuilding/redeploying with the defaults at
  the same time WILL collide -- one session's pre-push Playwright gate can
  transiently hit the other session's (possibly stale/different-branch)
  container. Symptom: a test fails referencing behavior that doesn't match
  the code you just wrote; `docker inspect <container> --format '{{.Image}}'`
  not matching the image you just built is the tell.
  If you know another session may be active, give this invocation its own
  identity, e.g.:
      scripts\run-local.ps1 -Name shaw -Port 8001 -ProjPath /mnt/f/github/finlab-stock-analyzer/.claude/worktrees/<worktree-name>
  then run e2e against it with `$env:BASE_URL = "http://localhost:8001"`
  (both for ad-hoc `npm test` runs and for `git push`, since the pre-push
  hook reads BASE_URL too).
#>

param(
    [string]$Name = 'test',
    [int]$Port = 8000,
    [string]$ProjPath = '/mnt/f/github/finlab-stock-analyzer'
)

$ErrorActionPreference = 'Stop'
$Distro    = 'Ubuntu'
$Image     = "finlab-stock-analyzer:$Name"
$Container = "finlab-$Name"
$Network   = 'finlab-net'

# 1. Resolve FINMIND_TOKEN from the Windows environment (widest to narrowest).
$token = $env:FINMIND_TOKEN
if (-not $token) { $token = [Environment]::GetEnvironmentVariable('FINMIND_TOKEN', 'User') }
if (-not $token) { $token = [Environment]::GetEnvironmentVariable('FINMIND_TOKEN', 'Machine') }
if (-not $token) {
    Write-Error "FINMIND_TOKEN not found in the Windows environment. Set it via System Properties > Environment Variables (User or System scope), then open a new terminal."
    exit 1
}
Write-Host "FINMIND_TOKEN resolved from Windows env (length $($token.Length))." -ForegroundColor Green

# 2. Forward the token into WSL for this invocation only.
$env:FINMIND_TOKEN = $token
$env:WSLENV = 'FINMIND_TOKEN/u'

# 3. Ensure docker daemon, network and MongoDB are up, then (re)run the app.
$remote = @"
set -e
systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
docker network inspect $Network >/dev/null 2>&1 || docker network create $Network >/dev/null
docker volume inspect mongo-data >/dev/null 2>&1 || docker volume create mongo-data >/dev/null
if ! docker ps --format '{{.Names}}' | grep -qx mongo; then
  docker rm -f mongo >/dev/null 2>&1 || true
  docker run -d --name mongo --network $Network -p 27017:27017 \
    -v mongo-data:/data/db --restart unless-stopped mongo:7 >/dev/null
fi
cd $ProjPath
docker build -t $Image . >/dev/null
docker rm -f $Container >/dev/null 2>&1 || true
# .env always comes from the main checkout: worktrees don't have their own
# (it's gitignored and only exists where you first set it up).
docker run -d --name $Container --network $Network \
  --restart unless-stopped \
  --env-file /mnt/f/github/finlab-stock-analyzer/.env \
  -e MONGODB_URI=mongodb://mongo:27017 \
  -e FINMIND_TOKEN="`$FINMIND_TOKEN" \
  -p ${Port}:8080 $Image >/dev/null
echo "app container FINMIND_TOKEN length:"
docker exec $Container printenv FINMIND_TOKEN | tr -d '\n' | wc -c
"@

wsl -d $Distro -u root -- bash -lc $remote

Write-Host "`nApp starting at http://localhost:$Port  (Swagger: /api/docs)" -ForegroundColor Cyan
