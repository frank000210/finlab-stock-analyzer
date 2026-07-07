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

.NOTES
  Requires: WSL distro "Ubuntu" with docker.io installed (see 交接SOP / README).
#>

$ErrorActionPreference = 'Stop'
$Distro    = 'Ubuntu'
$Image     = 'finlab-stock-analyzer:test'
$Network   = 'finlab-net'
$ProjPath  = '/mnt/f/github/finlab-stock-analyzer'

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
docker rm -f finlab-test >/dev/null 2>&1 || true
docker run -d --name finlab-test --network $Network \
  --restart unless-stopped \
  --env-file .env \
  -e MONGODB_URI=mongodb://mongo:27017 \
  -e FINMIND_TOKEN="`$FINMIND_TOKEN" \
  -p 8000:8080 $Image >/dev/null
echo "app container FINMIND_TOKEN length:"
docker exec finlab-test printenv FINMIND_TOKEN | tr -d '\n' | wc -c
"@

wsl -d $Distro -u root -- bash -lc $remote

Write-Host "`nApp starting at http://localhost:8000  (Swagger: /api/docs)" -ForegroundColor Cyan
