# Demo 本地开发 Runbook

本文用于在本机通过 Docker Compose 部署 SesRAG Demo。所有命令均从仓库根目录执行；Windows 使用 PowerShell 7.4+ 和 Docker Desktop Linux Engine，Linux 使用 Bash、Docker Engine 和 Docker Compose v2；首次 Linux 凭据生成还需要 `openssl` 命令。先运行 `docker version` 与 `docker compose version`，确认 Docker daemon 可用。

`.env.example` 是模板，不含可直接使用的密码；Compose 自动读取仓库根目录的 `.env`。真实凭据只写入 `.env`（该文件已被 Git 忽略），不要修改 `.env.example`、提交 `.env`、把密码贴入命令行或把完整 DSN 写入日志。

## 凭据准备

### 全新空数据库

仅在该 Compose 项目尚无已初始化的 PostgreSQL 数据卷时生成新密码。若 `.env` 已存在，以下步骤只替换其中两个凭据字段并保留其他设置；如果有现存数据库，跳到“已有数据库和数据卷”。

首次判断时先查看本项目是否已有 PostgreSQL 容器或数据卷：

```bash
docker compose ps -a postgres
docker volume ls --filter label=com.docker.compose.project=sesrag --filter label=com.docker.compose.volume=postgres_data
```

若存在 PostgreSQL 容器或匹配的数据卷，即使容器当前已停止，也按“已有数据库和数据卷”处理，不要重新生成密码。若启动 Compose 时使用过自定义项目名（`-p`/`COMPOSE_PROJECT_NAME`），把过滤条件中的 `sesrag` 换成那个项目名。无法确认数据卷归属或初始化状态时，先保留现状并恢复旧凭据，不要尝试新密码或删除卷。

Windows PowerShell：

```powershell
Set-Location D:\Agentic_RAG\SesRAG
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item '.env.example' '.env' }

$pgPassword = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
$urlPassword = [Uri]::EscapeDataString($pgPassword)
$envPath = (Resolve-Path -LiteralPath '.env').Path
$lines = [System.Collections.Generic.List[string]]::new()
foreach ($line in [IO.File]::ReadAllLines($envPath)) {
    if ($line -notmatch '^\s*(POSTGRES_PASSWORD|DATABASE_URL)\s*=') { $lines.Add($line) }
}
$lines.Add("POSTGRES_PASSWORD=$pgPassword")
$lines.Add("DATABASE_URL=postgresql+psycopg://sesrag:$urlPassword@postgres:5432/sesrag")
[IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
$pgPassword = $null
$urlPassword = $null

docker compose config -q
if ($LASTEXITCODE -ne 0) { throw 'Compose 配置校验失败；不要继续启动' }
Write-Host '凭据已写入 .env，Compose 配置校验通过；密码未输出。'
```

Linux Bash：

```bash
cd /path/to/SesRAG
set -euo pipefail
umask 077
if [ ! -f .env ]; then cp .env.example .env; fi

sesrag_pg_password="$(openssl rand -hex 32)"
tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT
awk '!/^[[:space:]]*(POSTGRES_PASSWORD|DATABASE_URL)[[:space:]]*=/' .env > "$tmp_file"
printf 'POSTGRES_PASSWORD=%s\nDATABASE_URL=postgresql+psycopg://sesrag:%s@postgres:5432/sesrag\n' \
    "$sesrag_pg_password" "$sesrag_pg_password" >> "$tmp_file"
mv -f "$tmp_file" .env
trap - EXIT
chmod 600 .env
unset sesrag_pg_password

docker compose config -q
echo '凭据已写入 .env，Compose 配置校验通过；密码未输出。'
```

`POSTGRES_PASSWORD` 是 PostgreSQL 初始化用户的原始密码；`DATABASE_URL` 使用同一个密码经过 URL 编码后的值。两套命令都生成 256 位十六进制密码，字符均为 URI 非保留字符，因此编码结果与原值相同；如果使用其他密码，PowerShell 可用 `[Uri]::EscapeDataString($password)` 编码，Linux 可用 Python 标准库 `urllib.parse.quote(value, safe='')` 编码。格式为 `postgresql+psycopg://sesrag:<编码密码>@postgres:5432/sesrag`：`sesrag` 是数据库用户和库名，`postgres` 是 Compose 内部服务名，端口为 `5432`。不要把 `.env.example` 的尖括号占位符原样保留。

### 已有数据库和数据卷

不要重新生成密码，也不要为解决认证问题执行 `docker compose down -v`。已初始化的数据卷不会因为修改 `POSTGRES_PASSWORD` 环境变量而更改数据库内的用户密码；`DATABASE_URL` 必须继续使用该数据库当前有效的凭据。优先从现存 `.env` 备份或密码管理器恢复。如果本机旧 Compose 容器仍存在，可在当前 PowerShell 会话中从容器配置恢复值，不在终端回显：

```powershell
$postgresId = docker compose ps -a -q postgres
$apiId = docker compose ps -a -q api
if (-not $postgresId -or -not $apiId) { throw '没有找到旧 postgres/api 容器；请从原凭据备份恢复' }

$postgresInfo = @(docker inspect $postgresId | ConvertFrom-Json)
$apiInfo = @(docker inspect $apiId | ConvertFrom-Json)
$pgEntry = @($postgresInfo[0].Config.Env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' })
$dsnEntry = @($apiInfo[0].Config.Env | Where-Object { $_ -like 'DATABASE_URL=*' })
if ($pgEntry.Count -ne 1 -or $dsnEntry.Count -ne 1) { throw '旧容器未保存唯一的数据库凭据' }

$env:POSTGRES_PASSWORD = $pgEntry[0].Substring('POSTGRES_PASSWORD='.Length)
$env:DATABASE_URL = $dsnEntry[0].Substring('DATABASE_URL='.Length)
$dsn = [Uri]::new($env:DATABASE_URL)
$parts = $dsn.UserInfo -split ':', 2
if ($dsn.Scheme -ne 'postgresql+psycopg' -or $dsn.Host -ne 'postgres' -or
    $dsn.Port -ne 5432 -or $dsn.AbsolutePath -ne '/sesrag' -or
    $parts.Count -ne 2 -or [Uri]::UnescapeDataString($parts[1]) -cne $env:POSTGRES_PASSWORD) {
    Remove-Item Env:POSTGRES_PASSWORD, Env:DATABASE_URL -ErrorAction SilentlyContinue
    throw '旧容器中的密码和 DSN 不匹配；停止操作并检查凭据来源'
}

docker compose config -q
if ($LASTEXITCODE -ne 0) { throw 'Compose 配置校验失败；不要继续启动' }
Write-Host '已在当前会话恢复并校验旧凭据；密码未输出。'
```

此恢复方式依赖旧容器仍在，且只设置当前 PowerShell 会话环境变量；在同一窗口继续执行部署命令。容器环境变量只能证明创建该容器时传入的值，不证明后来通过 SQL 手工轮换过的数据库密码仍相同；如果曾手工轮换密码，必须从最新凭据记录恢复。Docker daemon 管理员可以查看容器环境变量，因此这只是本机恢复途径，不是长期 Secret 存储。新开终端后应恢复原凭据或将其安全写入被忽略的 `.env`。

Linux 上的旧容器恢复：

```bash
set -euo pipefail
command -v python3 >/dev/null || { echo '恢复旧凭据需要宿主机 Python 3；请先安装，或从安全备份恢复 .env' >&2; exit 1; }
postgres_id="$(docker compose ps -a -q postgres | head -n 1)"
api_id="$(docker compose ps -a -q api | head -n 1)"
test -n "$postgres_id" && test -n "$api_id" || { echo '没有旧容器；请从原凭据备份恢复' >&2; exit 1; }

export POSTGRES_PASSWORD="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$postgres_id" | sed -n 's/^POSTGRES_PASSWORD=//p')"
export DATABASE_URL="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$api_id" | sed -n 's/^DATABASE_URL=//p')"
test -n "$POSTGRES_PASSWORD" && test -n "$DATABASE_URL" || { echo '旧容器未保存凭据' >&2; exit 1; }
python3 - <<'PY'
import os
from urllib.parse import unquote, urlsplit

dsn = urlsplit(os.environ['DATABASE_URL'])
assert (dsn.scheme, dsn.hostname, dsn.port, dsn.path) == ('postgresql+psycopg', 'postgres', 5432, '/sesrag')
assert unquote(dsn.password or '') == os.environ['POSTGRES_PASSWORD']
PY
docker compose config -q
echo '已在当前 Bash 会话恢复并校验旧凭据；密码未输出。'
```

## Windows 部署

在 PowerShell 7.4+ 中从仓库根目录执行。第一次部署前，先按“凭据准备”完成全新空库凭据配置，或恢复已有数据库的凭据。

```powershell
Set-Location D:\Agentic_RAG\SesRAG
docker version
docker compose version
docker compose config -q
if ($LASTEXITCODE -ne 0) { throw 'Compose 配置无效；停止部署' }

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Compose 启动失败；检查上方错误' }
docker compose ps -a
```

确认 `postgres`、`redis` 为 healthy，`migrate` 为 `Exited (0)`，`api` healthy，`worker` 和 `frontend` 正常运行。显式核对迁移退出码：

```powershell
$migrateId = docker compose ps -a -q migrate
if (-not $migrateId) { throw '没有找到 migrate 容器' }
$migrateExit = docker inspect $migrateId --format '{{.State.ExitCode}}'
if ($migrateExit -ne '0') {
    docker compose logs --no-color migrate
    throw "migrate 退出码为 $migrateExit；不要继续验收"
}

Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Start-Process http://localhost:5173
```

## Linux 部署

确认 Docker daemon 已启动，并使用有权限访问 Docker 的账号。从仓库根目录执行；第一次部署前，先按“凭据准备”配置 `.env`。

```bash
cd /path/to/SesRAG
docker version
docker compose version
docker compose config -q

docker compose up -d --build
docker compose ps -a
```

确认 `postgres`、`redis` 为 healthy，`migrate` 为 `Exited (0)`，`api` healthy，`worker` 和 `frontend` 正常运行。显式核对迁移退出码并检查 API：

```bash
migrate_id="$(docker compose ps -a -q migrate)"
test -n "$migrate_id" || { echo '没有找到 migrate 容器' >&2; exit 1; }
migrate_exit="$(docker inspect "$migrate_id" --format '{{.State.ExitCode}}')"
if [ "$migrate_exit" != 0 ]; then
    docker compose logs --no-color migrate
    echo "migrate 退出码为 $migrate_exit；不要继续验收" >&2
    exit 1
fi

curl --fail --silent --show-error http://localhost:8000/health/live
curl --fail --silent --show-error http://localhost:8000/health/ready
```

浏览器访问前端 `http://localhost:5173`，API 文档为 `http://localhost:8000/docs`。Compose 使用 PostgreSQL `pgvector/pgvector:pg16`、Redis、一次性迁移服务、API、Worker 和前端；数据库数据保存在 `postgres_data`，上传文件保存在 `uploads` named volume。

## 主流程验收

1. 创建 Thread。
2. 上传 `.txt`、`.md` 或 `.docx`。
3. 等待文档状态变为 `indexed`。
4. 在 Thread 中发送问题，观察 Run 状态、Event 时间线和 citations。
5. 刷新页面，确认 Message、Run 和文档状态从服务端恢复。
6. 执行 `docker compose restart worker`，确认未完成 Task 在 lease 到期后可以重新领取。

## 故障检查

- `api` 失败：查看 `docker compose logs --tail=100 api migrate`，检查迁移结果和 `DATABASE_URL`；不要粘贴完整 DSN。
- `worker` 不领取：查看 `docker compose logs --tail=100 worker`，检查 PostgreSQL 连接、Task 状态和 lease。
- Redis 不可用：系统仍应使用 PostgreSQL 事实和轮询；SSE 延迟增加，但任务事实不能丢失。
- `/health/live` 只表示 API 进程存活；`/health/ready` 实际探测 PG/Redis，PG 故障返回 503 和 `DATABASE_UNAVAILABLE`，Redis 不可用返回 degraded，Worker 无可见心跳返回 unknown，不能据此宣称 Worker 已停止。
- 文档失败：查看 Document 的 `last_error_code` 和 Worker 日志，不要把基础设施错误当成“无相关资料”。
- 端口冲突：查看 `docker compose ps -a` 和本机 8000/5173 端口占用；停止占用服务或调整 Compose 端口映射后重试。

## 停止

```bash
docker compose down
```

PowerShell 和 Bash 都使用同一条命令。`docker compose down` 会停止并删除本项目容器/网络，但保留 `postgres_data` 和 `uploads` 数据卷。只有明确确认要永久清空本项目数据库与上传文件、且已做好所需备份时，才运行：

```bash
docker compose down -v
```

不要把 `down -v` 用作常规更新、迁移失败处理或密码修复步骤。

## 数据库升级和安全回退

当前迁移链为 `0001_initial_demo -> 0002_demo_integrity -> 0003_chunk_locations`；以仓库的 `migrations/versions/` 为准。数据库升级必须在维护窗口执行，顺序为：记录当前 revision、停止会写数据库的 API/Worker（并停止前端入口）、确认服务已停止、创建并校验备份、执行迁移、核对 revision 和健康状态。**不要在 API/Worker 仍运行时创建本次升级用的备份**，否则备份期间仍可能继续提交新事实。数据库备份包含业务表数据，但不包含 `uploads` named volume 中的原始文件；它不是完整应用备份。备份文件放在仓库外并按敏感数据保护。

### 开始维护窗口并停止写入

先在当前部署版本下记录 revision，再停服务。PostgreSQL 和 Redis 保持运行；后续备份、迁移和恢复命令都要求从仓库根目录执行。下列命令可在 PowerShell 和 Bash 中使用；逐步确认命令成功及服务状态后再继续。

```bash
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic history
docker compose stop api worker frontend
docker compose ps -a
```

确认 `api`、`worker`、`frontend` 均已停止，`postgres` 仍为 healthy 后再继续。若 `stop` 或状态核对失败，不要开始备份/迁移；先查明是否仍有写入来源。

### 创建并检查数据库备份

Windows PowerShell 7.4+：

```powershell
$backupDir = Join-Path $env:LOCALAPPDATA 'SesRAG\backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$backupFile = Join-Path $backupDir "sesrag-$stamp.dump"
$postgresId = docker compose ps -q postgres
if (-not $postgresId) { throw 'PostgreSQL 未运行；无法备份' }

docker compose exec -T postgres pg_dump -U sesrag -d sesrag --format=custom -f "/tmp/sesrag-$stamp.dump"
if ($LASTEXITCODE -ne 0) { throw 'pg_dump 失败；不要继续迁移' }
docker cp "${postgresId}:/tmp/sesrag-$stamp.dump" $backupFile
if ($LASTEXITCODE -ne 0) { throw '复制备份到主机失败；不要继续迁移' }
docker compose exec -T postgres pg_restore --list "/tmp/sesrag-$stamp.dump" | Out-Null
if ($LASTEXITCODE -ne 0 -or (Get-Item $backupFile).Length -eq 0) { throw '备份校验失败；不要继续迁移' }
docker compose exec -T postgres rm -f "/tmp/sesrag-$stamp.dump"
Write-Host "数据库备份已创建并检查：$backupFile"
```

Linux Bash：

```bash
set -euo pipefail
umask 077
backup_dir="$HOME/.local/share/sesrag/backups"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/sesrag-$stamp.dump"
postgres_id="$(docker compose ps -q postgres)"
test -n "$postgres_id" || { echo 'PostgreSQL 未运行；无法备份' >&2; exit 1; }

docker compose exec -T postgres pg_dump -U sesrag -d sesrag --format=custom -f "/tmp/sesrag-$stamp.dump"
docker cp "$postgres_id:/tmp/sesrag-$stamp.dump" "$backup_file"
docker compose exec -T postgres pg_restore --list "/tmp/sesrag-$stamp.dump" >/dev/null
test -s "$backup_file"
docker compose exec -T postgres rm -f "/tmp/sesrag-$stamp.dump"
printf '数据库备份已创建并检查：%s\n' "$backup_file"
```

### 应用迁移

维护窗口和备份已完成后，构建目标版本的迁移/API/Worker/前端镜像并应用迁移。PostgreSQL 保持运行：

Windows PowerShell 7.4+：

```powershell
$ErrorActionPreference = 'Stop'
docker compose build migrate api worker frontend
if ($LASTEXITCODE -ne 0) { throw '构建目标镜像失败；不要继续迁移' }

docker compose run --rm migrate alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    docker compose logs --no-color migrate
    throw 'upgrade head 失败；保持 API/Worker 停止并检查备份和日志'
}

docker compose run --rm migrate alembic current
if ($LASTEXITCODE -ne 0) { throw '无法读取迁移后的 revision；不要启动业务服务' }

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw '迁移已执行但服务启动失败；检查日志，不要删除数据卷' }
docker compose ps -a
docker compose logs --tail=100 migrate api worker
```

Linux Bash：

```bash
set -euo pipefail
docker compose build migrate api worker frontend
if ! docker compose run --rm migrate alembic upgrade head; then
    docker compose logs --no-color migrate
    echo 'upgrade head 失败；保持 API/Worker 停止并检查备份和日志' >&2
    exit 1
fi
docker compose run --rm migrate alembic current
docker compose up -d --build
docker compose ps -a
docker compose logs --tail=100 migrate api worker
```

`upgrade head` 失败时保留日志和备份，不要启动新 API/Worker 或手工改 `alembic_version`。检查失败原因及数据冲突后决定修复数据、回退代码或恢复备份。`docker compose run --rm` 执行的是一次性迁移容器；之后的 `up -d --build` 可能因镜像变化再次运行 Compose 的 `migrate` 服务，Alembic 已在 head 时再次执行 `upgrade head` 是幂等的。最终以迁移容器退出码、`alembic current` 和服务健康状态为准。

当前仓库的预期 head 是 `0003_chunk_locations`；以后新增 revision 时，应以 `docker compose run --rm migrate alembic heads` 的实际输出核对。再次 `upgrade head` 不应重复改动已在 head 的数据库。

### 回退迁移和应用代码

回退前进入维护窗口：先记录当前 revision，停止 `api`、`worker`、`frontend`，再创建并校验备份，并确认目标旧应用兼容目标 revision。先用当前已部署/新版本代码中的迁移执行 downgrade，再切换旧应用代码。将 `<目标revision>` 替换为 `alembic history` 中真实存在的 revision；例如回到当前代码的 `0002_demo_integrity`：

Windows PowerShell 7.4+：

```powershell
$ErrorActionPreference = 'Stop'
docker compose stop api worker frontend
if ($LASTEXITCODE -ne 0) { throw '停止业务服务失败；不要继续回退' }
docker compose build migrate
if ($LASTEXITCODE -ne 0) { throw '构建当前迁移镜像失败；不要继续回退' }
docker compose run --rm migrate alembic current
if ($LASTEXITCODE -ne 0) { throw '无法确认当前 revision；不要继续回退' }
docker compose run --rm migrate alembic downgrade 0002_demo_integrity
if ($LASTEXITCODE -ne 0) {
    docker compose logs --no-color migrate
    throw '迁移降级失败；保持业务服务停止并检查日志'
}
docker compose run --rm migrate alembic current
if ($LASTEXITCODE -ne 0) { throw '无法确认降级后的 revision；不要启动旧应用' }
```

Linux Bash：

```bash
set -euo pipefail
docker compose stop api worker frontend
docker compose build migrate
docker compose run --rm migrate alembic current
if ! docker compose run --rm migrate alembic downgrade 0002_demo_integrity; then
    docker compose logs --no-color migrate
    echo '迁移降级失败；保持业务服务停止并检查日志' >&2
    exit 1
fi
docker compose run --rm migrate alembic current
```

确认 revision 后，切换到与该 schema 兼容的旧代码版本并重建/启动：

```bash
docker compose up -d --build
docker compose ps -a
```

本迁移链中 `0003_chunk_locations` 的 downgrade 保留 `locations_json` 列和已有证据位置；`0002_demo_integrity` 的 downgrade 移除约束并将来源列改为可空，但保留来源值。降级不会恢复被新应用语义修改的数据。降到 `base` 会触发 `0001_initial_demo` 删除业务表；当前迁移会拒绝非空库，不能用它做常规回退。

### 从备份恢复数据库

仅当迁移降级不能恢复可用状态、并已决定用备份覆盖当前数据库时执行。以下操作会删除当前 `sesrag` 数据库内容；先停写并确认所选备份文件正确。还原数据库不会还原 `uploads` volume 中的原始上传文件。

Windows PowerShell（`$backupFile` 应是上面生成的 `.dump` 完整路径）：

```powershell
$ErrorActionPreference = 'Stop'
$backupFile = (Resolve-Path -LiteralPath $backupFile).Path
if ((Get-Item -LiteralPath $backupFile).Length -eq 0) { throw '备份文件为空；停止恢复' }
$postgresId = docker compose ps -q postgres
if (-not $postgresId) { throw 'PostgreSQL 未运行' }

docker compose stop api worker frontend
if ($LASTEXITCODE -ne 0) { throw '停止 API/Worker/前端失败；不要继续恢复' }
docker cp $backupFile "${postgresId}:/tmp/sesrag-restore.dump"
if ($LASTEXITCODE -ne 0) { throw '复制备份到 PostgreSQL 容器失败' }
docker compose exec -u 0 -T postgres chown postgres:postgres /tmp/sesrag-restore.dump
if ($LASTEXITCODE -ne 0) { throw '设置恢复文件权限失败；不要继续恢复' }

docker compose exec -T postgres dropdb --if-exists -U sesrag sesrag
if ($LASTEXITCODE -ne 0) { throw '删除旧 sesrag 数据库失败；不要继续恢复' }
docker compose exec -T postgres createdb -U sesrag --template=template0 sesrag
if ($LASTEXITCODE -ne 0) { throw '创建空 sesrag 数据库失败；不要继续恢复' }
docker compose exec -T postgres pg_restore --exit-on-error --no-owner --no-acl -U sesrag -d sesrag /tmp/sesrag-restore.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_restore 失败；保持 API/Worker 停止并检查日志' }
docker compose exec -T postgres rm -f /tmp/sesrag-restore.dump
if ($LASTEXITCODE -ne 0) { Write-Warning '恢复成功，但容器内临时备份文件未删除：/tmp/sesrag-restore.dump' }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw '数据库已恢复但服务启动失败；检查日志，勿删除数据卷' }
```

Linux Bash（`backup_file` 应是上面生成的 `.dump` 完整路径）：

```bash
set -euo pipefail
test -s "$backup_file" || { echo '备份文件不存在或为空；停止恢复' >&2; exit 1; }
postgres_id="$(docker compose ps -q postgres)"
test -n "$postgres_id" || { echo 'PostgreSQL 未运行' >&2; exit 1; }

docker compose stop api worker frontend
docker cp "$backup_file" "$postgres_id:/tmp/sesrag-restore.dump"
docker compose exec -u 0 -T postgres chown postgres:postgres /tmp/sesrag-restore.dump
docker compose exec -T postgres dropdb --if-exists -U sesrag sesrag
docker compose exec -T postgres createdb -U sesrag --template=template0 sesrag
docker compose exec -T postgres pg_restore --exit-on-error --no-owner --no-acl -U sesrag -d sesrag /tmp/sesrag-restore.dump
docker compose exec -T postgres rm -f /tmp/sesrag-restore.dump
docker compose up -d --build
```

若 `pg_restore` 失败，不要启动 API/Worker；保留备份和错误输出，修正原因后从本节开头重新执行恢复流程（包括删除部分恢复的数据库并重新创建空库）。恢复完成后确认 `alembic current`、迁移日志和 `/health/ready` 与将要运行的代码版本一致。若准备运行旧应用代码，应先切换到兼容版本，再用对应迁移代码核对 revision；不要让当前新版本自动把旧 schema 升级后再运行旧应用。数据库迁移或容器更新不会删除 named volumes；不要通过删卷模拟数据库回退。

## Docker 容器更新

更新前检查将要部署的代码版本和工作区改动；涉及迁移时先按上节创建并检查数据库备份。只更新本地构建的 API、Worker、迁移和前端镜像时，在仓库根目录执行：

```bash
docker compose config -q
docker compose up -d --build
docker compose ps -a
docker compose logs --tail=100 migrate api worker frontend
```

`up -d --build` 会按当前 Dockerfile 重建镜像、按 Compose 依赖先执行 `migrate`，然后重建/启动有变化的服务；成功后再次检查迁移容器为 `Exited (0)`，API 为 healthy，Worker/前端正常，再检查 `/health/ready`。Windows PowerShell 与 Linux Bash 使用相同的 Docker 命令。它不会删除 `postgres_data` 或 `uploads`。

如只需刷新构建基础镜像，可先执行 `docker compose build --pull api worker migrate frontend`，再执行 `docker compose up -d`。若有意更新 PostgreSQL/Redis 镜像，先备份数据库，再显式执行 `docker compose pull postgres redis` 和 `docker compose up -d`；不要把 PostgreSQL 主版本升级当作普通容器刷新，主版本升级需单独制定并验证数据库迁移/数据迁移方案。

应用更新失败时保留 `docker compose logs` 和 `docker compose ps -a` 输出，回到兼容的代码版本后执行 `docker compose up -d --build`。如果失败由 schema 不兼容引起，应先按“回退迁移和应用代码”处理；不要删除数据卷、手工更新 `alembic_version`，也不要假定旧代码能兼容新 schema。

## 持久执行故障诊断

- 以 `task_id` 及适用的 `run_id`（Run 任务）或 `document_id`（索引任务）关联 Worker JSON 日志，核对 `worker_id/generation/attempt/error_code` 和 claim、renew、retry、release、success、failure 动作；另一业务关联为空合法。旧代数的 reject 不代表新执行者失败；不要手工修改 state/generation 来“解锁”。
- `retry_waiting` 是退避期；到期仅 Task 回 queued，Run 保持 retry_waiting，重新开始才回 running。超过硬截止或耗尽尝试会统一结算业务对象，查看 `TASK_DEADLINE_EXCEEDED` / `TASK_ATTEMPTS_EXHAUSTED`。
- 关停 Worker 先停止领取，当前任务在 `WORKER_SHUTDOWN_GRACE` 内完成或释放；容器停止超时应大于应用宽限期，不能把 Docker 强杀当作优雅完成。
- 控制面 DB 阶段最多 5 秒，超宽限后释放最多 1 秒，每轮取消清理 0.5 秒。释放超时会停止续租并记录 `RELEASE_TIMEOUT_OR_UNAVAILABLE`，租约到期后由正常回收器处理；观察此拒绝不能写成成功释放。数据库取消回滚和真正 Linux SIGTERM 需要分别验证，不以调用停止方法代替进程信号验收。
- 升级后的旧 Mock Run 按旧快照协议恢复；`INVALID_RUN_SNAPSHOT` 表示冻结配置无法安全恢复。保留原事实并定位创建时配置，不能使用当前模型默认值替换旧快照。
- DB 暂断恢复无需手工重启 Worker；验证时必须观察同进程安全错误、退避和恢复后新任务执行，不能只看 Docker restart policy 或容器状态。
