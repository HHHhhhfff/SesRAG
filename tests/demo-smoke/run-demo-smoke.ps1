#Requires -Version 7.4
[CmdletBinding()]
param(
    [string]$ProjectName = 'sesrag-demo-smoke',
    [ValidateRange(1024,65535)][int]$ApiPort = 18000,
    [ValidateRange(1024,65535)][int]$FrontendPort = 15173,
    [bool]$Build = $true,
    [string]$BackendImage,
    [string]$FrontendImage,
    [string]$Category = 'all',
    # LIFE专项只允许固定自检场景；普通产品分类仍使用正式manifest，不接收任意路径。
    [ValidateSet('not-ready','disabled','protocol','missing-script','rag-empty','doc-limit','nested-recovery','compose-config-failure','migration-failure','redis-cold','redis-strict','real-db-probe-failure','worker-readiness-timeout','frontend-readiness-timeout','cleanup-failure','cleanup-share-read','hard-kill-recovery')][string]$HarnessScenario,
    [bool]$KeepArtifacts = $true,
    [switch]$KeepContainers,
    [ValidateRange(10,3600)][int]$WaitTimeoutSeconds = 180,
    [ValidateRange(30,7200)][int]$BuildTimeoutSeconds = 900,
    [ValidateRange(0,3600)][int]$SessionSeconds = 0,
    [switch]$Interactive,
    [string]$CleanupRunId
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# 总入口及后续PowerShell分类都遵循UTF-8输出约定，保留中文可读证据。
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
. "$PSScriptRoot/lib/smoke-common.ps1"

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$runtimeRoot = Join-Path $PSScriptRoot 'runtime'
$artifactRoot = Join-Path $PSScriptRoot 'artifacts'
$tmpRoot = Join-Path $PSScriptRoot 'tmp'
$runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss').ToLowerInvariant() + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$project = ''
$password = ''
$dockerReady = $false
$deploymentAttempted = $false
$composeArgs = @()
$composeEnvironment = @{}
$runtimeDir = ''
$artifactDir = ''
$tmpDir = ''
$fixtureDir = ''
$state = $null
$anonymousVolumes = @()
$cleanupLock = $null
$recoveryRejected = $false
$deploymentScenarios = @('compose-config-failure','migration-failure','redis-cold','redis-strict','real-db-probe-failure','worker-readiness-timeout','frontend-readiness-timeout','cleanup-failure','cleanup-share-read','hard-kill-recovery')
$report = @{ schema_version = 1; run_id = $runId; started_at = [DateTime]::UtcNow.ToString('o'); test_status = 'blocked'; stages = @{ startup='not_run'; tests='not_run'; report_collection='not_run' }; categories = @(); errors = @() }
$cleanup = @{ status = 'passed'; steps = @(); residuals = @{} }

function Write-Evidence([string]$RelativePath, [string]$Content) {
    $path = Join-Path $artifactDir $RelativePath
    $safe = Protect-SmokeText $Content @($password)
    Set-Content -LiteralPath $path -Value $safe -Encoding utf8
}

function Docker-Call([string[]]$Arguments, [int]$Timeout = 60) {
    return Invoke-SmokeProcess 'docker' $Arguments $Timeout $repoRoot $composeEnvironment
}

function Compose-Call([string[]]$Arguments, [int]$Timeout = 60) {
    return Docker-Call (@($composeArgs) + $Arguments) $Timeout
}

function Resource-Ids([string]$Kind) {
    $argsList = switch ($Kind) {
        containers { @('ps','-aq','--filter',"label=com.docker.compose.project=$project") }
        networks { @('network','ls','-q','--filter',"label=com.docker.compose.project=$project") }
        volumes { @('volume','ls','-q','--filter',"label=com.docker.compose.project=$project") }
    }
    $result = Docker-Call $argsList
    if ($result.exit_code -ne 0) { throw "Docker资源查询失败：$Kind" }
    return @($result.output.Trim() -split '\r?\n' | Where-Object { $_ })
}

function Wait-Environment {
    $repositoryPython = Join-Path $repoRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $repositoryPython)) { $repositoryPython = 'python' }
    $headResult = Invoke-SmokeProcess $repositoryPython @('-c', 'from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config("alembic.ini")).get_current_head())') 15 $repoRoot
    if ($headResult.exit_code -ne 0 -or [string]::IsNullOrWhiteSpace($headResult.output)) { throw '无法读取当前仓库 Alembic head，拒绝以旧版本宣告环境就绪' }
    $expectedHead = $headResult.output.Trim()
    $coldRun = $null
    $until = $startupDeadline
    $last = '尚未获得服务状态'
    while ([DateTime]::UtcNow -lt $until) {
        $statesResult = Compose-Call @('ps','-a','--format','json') 15
        if ($statesResult.exit_code -ne 0) { throw '无法读取Compose服务状态' }
        $states = @($statesResult.output -split '\r?\n' | Where-Object { $_.StartsWith('{') } | ForEach-Object { $_ | ConvertFrom-Json })
        if ($states.Count -eq 0 -and $statesResult.output.Trim().StartsWith('[')) { $states = @($statesResult.output | ConvertFrom-Json) }
        $last = ($states | ForEach-Object { "$($_.Service):$($_.State)/$($_.Health)" }) -join ', '
        $migrate = @($states | Where-Object Service -eq 'migrate')
        if ($migrate.Count -and $migrate[0].State -eq 'exited' -and $migrate[0].ExitCode -ne 0) { throw "迁移退出码非0：$($migrate[0].ExitCode)" }
        foreach ($service in @('api','worker','frontend','postgres','redis')) {
            if (@($states | Where-Object { $_.Service -eq $service -and $_.State -in @('exited','dead') }).Count) { throw "服务提前退出：$service" }
        }
        $db = @($states | Where-Object { $_.Service -eq 'postgres' -and $_.Health -eq 'healthy' })
        $redis = @($states | Where-Object { $_.Service -eq 'redis' -and $_.Health -eq 'healthy' })
        if ($db.Count -and ($redis.Count -or $HarnessScenario -eq 'redis-cold') -and $migrate.Count -and $migrate[0].State -eq 'exited' -and $migrate[0].ExitCode -eq 0) {
            try {
                $live = Invoke-RestMethod "$baseUrl/health/live" -TimeoutSec 3
                $ready = Invoke-RestMethod "$baseUrl/health/ready" -TimeoutSec 3
                Write-SmokeJson (Join-Path $artifactDir 'environment/health-live.json') $live
                Write-SmokeJson (Join-Path $artifactDir 'environment/health-ready.json') $ready
                $front = Invoke-WebRequest $frontendUrl -TimeoutSec 3
                $proxy = Invoke-RestMethod "$frontendUrl/health/live" -TimeoutSec 3
                # 实际目录必须精确匹配当前仓库 head，不能把旧镜像迁移成功当作本轮通过。
                $probeDatabase = $(if ($HarnessScenario -eq 'real-db-probe-failure') { 'missing_smoke_database' } else { 'sesrag' })
                $sql = Compose-Call @('exec','-T','postgres','psql','-U','sesrag','-d',$probeDatabase,'-Atc',"SELECT version_num FROM alembic_version; SELECT extname FROM pg_extension WHERE extname='vector';") 10
                Write-Evidence 'environment/database-probe.txt' $sql.output
                Write-SmokeJson (Join-Path $artifactDir 'environment/database-probe-process.json') @{exit_code=$sql.exit_code;expected_head=$expectedHead}
                $databaseLines = @($sql.output -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.Trim() })
                $redisExpected = $(if ($HarnessScenario -eq 'redis-cold') { 'degraded' } else { 'ready' })
                $workerProven = $ready.worker_count -ge 1
                if ($HarnessScenario -eq 'redis-cold') {
                    # Redis不可用时worker readiness正确为unknown；用正式Run完成证明真实Worker可执行。
                    if (-not $coldRun) {
                        $thread = Invoke-RestMethod "$baseUrl/api/v1/threads" -Method Post -ContentType 'application/json' -Body '{"title":"redis cold probe"}' -TimeoutSec 3
                        $coldRun = Invoke-RestMethod "$baseUrl/api/v1/threads/$($thread.thread_id)/messages" -Method Post -ContentType 'application/json' -Body '{"content":"cold startup probe"}' -TimeoutSec 3
                    }
                    $coldState = Invoke-RestMethod "$baseUrl/api/v1/runs/$($coldRun.run_id)" -TimeoutSec 3
                    Write-SmokeJson (Join-Path $artifactDir 'environment/redis-cold-run.json') $coldState
                    $workerProven = $coldState.status -eq 'succeeded'
                }
                if ($live.status -eq 'ok' -and $ready.database -eq 'ready' -and $ready.redis -eq $redisExpected -and $workerProven -and $front.StatusCode -eq 200 -and $proxy.status -eq 'ok' -and $sql.exit_code -eq 0 -and $databaseLines.Count -eq 2 -and $databaseLines[0] -ceq $expectedHead -and $databaseLines[1] -ceq 'vector') {
                    Write-Evidence 'environment/database-probe.txt' $sql.output
                    return
                }
                $last += "; worker_count=$($ready.worker_count)"
            } catch { $last += '; HTTP/依赖检查未就绪' }
        }
        Write-Host "等待环境就绪：$last"
        Start-Sleep -Seconds 2
    }
    throw "等待环境超时（${WaitTimeoutSeconds}s）：$last"
}

function Collect-Evidence {
    $failed = $false
    $ps = Compose-Call @('ps','-a','--format','json')
    Write-Evidence 'environment/compose-ps-before.txt' $ps.output
    if ($ps.exit_code -ne 0) { $failed = $true }
    foreach ($service in @('migrate','api','worker','frontend','postgres','redis')) {
        $log = Compose-Call @('logs','--no-color','--tail','2000',$service)
        Write-Evidence "logs/$service.log" $log.output
        if ($log.exit_code -ne 0) { $failed = $true }
    }
    foreach ($id in @(Resource-Ids 'containers')) {
        $inspect = Docker-Call @('inspect',$id)
        if ($inspect.exit_code -ne 0) { $failed = $true; continue }
        foreach ($container in @($inspect.output | ConvertFrom-Json)) {
            # Redis等基础镜像可能产生匿名volume，记录其精确名称并在down后核对。
            foreach ($mount in @($container.Mounts)) {
                if ($mount.Type -eq 'volume') { $script:anonymousVolumes += $mount.Name }
            }
        }
    }
    Write-SmokeJson (Join-Path $runtimeDir 'resources.json') @{ volume_names = @($anonymousVolumes | Sort-Object -Unique) }
    foreach ($endpoint in @('live','ready')) {
        try {
            $snapshot = Invoke-RestMethod "$baseUrl/health/$endpoint" -TimeoutSec 3
            Write-SmokeJson (Join-Path $artifactDir "environment/health-$endpoint-final.json") $snapshot
        } catch {
            # 故障测试结束依赖可能仍不可达，保存事实，不捏造就绪快照。
            Write-SmokeJson (Join-Path $artifactDir "environment/health-$endpoint-final.json") @{ status='unreachable'; observed_at=[DateTime]::UtcNow.ToString('o') }
        }
    }
    $report.stages.report_collection = $(if ($failed) { 'failed' } else { 'passed' })
    if ($failed -and $report.test_status -in @('passed','not_ready')) { $report.test_status = 'failed'; $report.errors += '部分环境报告收集失败' }
}

function Cleanup-Environment {
    if ($recoveryRejected) { $cleanup.status='failed'; $cleanup.steps += @{name='recovery_rejected';message='胶囊校验/恢复失败，保留原材料且不销毁资源'}; return }
    if ($KeepContainers -and $deploymentAttempted) { $cleanup.status = 'deferred'; return }
    # 先回收登记的宿主进程/独立执行容器，再销毁同一project；PID须核对出生身份。
    $registered = Invoke-SmokeProcess 'node' @((Join-Path $PSScriptRoot 'tooling/cleanup-registered.mjs'),$runtimeDir,$runId,$project) 180 $repoRoot
    Write-Evidence 'environment/registered-cleanup.json' $registered.output
    $cleanup.steps += @{ name='registered_resources'; exit_code=$registered.exit_code }
    if ($registered.exit_code -ne 0) { $cleanup.status='failed' }
    # 分类超时/树被终止时Node finally不保证执行，父runtime登记作为最后精确兜底。
    try {
    $nestedPath = Join-Path $runtimeDir 'nested-runs.json'
    if (Test-Path -LiteralPath $nestedPath) {
        $registry = Get-Content -LiteralPath $nestedPath -Raw | ConvertFrom-Json
        if ($registry.schema_version -ne 1 -or $registry.parent_run_id -ne $runId) { throw '嵌套资源登记身份不匹配，拒绝任意清理' }
        foreach ($nested in @($registry.nested)) {
            $nestedDir = Get-SmokeChildPath $runtimeRoot $nested.run_id
            if ($nested.run_id -eq $runId -or $nested.compose_project -eq $project -or $nested.compose_project -notmatch '^sesrag-demo-smoke-[a-z0-9-]+$') { throw '嵌套清理目标不合法' }
            $nestedCapsule = Get-SmokeRecoveryPath $runtimeRoot $nested.run_id
            if ((Test-Path -LiteralPath $nestedDir) -or (Test-Path -LiteralPath $nestedCapsule)) {
                if (Test-Path -LiteralPath $nestedCapsule) { Restore-SmokeRecovery $runtimeRoot $nested.run_id }
                $nestedState = Get-Content -LiteralPath (Join-Path $nestedDir 'context.json') -Raw | ConvertFrom-Json
                if ($nestedState.run_id -ne $nested.run_id -or $nestedState.compose_project -ne $nested.compose_project -or $nestedState.marker -ne 'sesrag-demo-smoke-v1') { throw '嵌套清理凭据不匹配' }
                $recovery = Invoke-SmokeProcess (Get-Process -Id $PID).Path @('-NoProfile','-File',$PSCommandPath,'-CleanupRunId',$nested.run_id) 240 $repoRoot
                Write-Evidence "logs/nested-recovery-$($nested.run_id).log" $recovery.output
                $nestedCleanupPath = Join-Path (Get-SmokeChildPath $artifactRoot $nested.run_id) 'cleanup.json'
                $nestedCleaned = -not (Test-Path -LiteralPath $nestedDir) -and -not (Test-Path -LiteralPath $nestedCapsule)
                if (Test-Path -LiteralPath $nestedCleanupPath) { $nestedCleaned = $nestedCleaned -and ((Get-Content -LiteralPath $nestedCleanupPath -Raw | ConvertFrom-Json).status -eq 'passed') } else { $nestedCleaned = $false }
                $cleanup.steps += @{ name='nested_recovery'; run_id=$nested.run_id; project=$nested.compose_project; exit_code=$recovery.exit_code; cleaned=$nestedCleaned }
                if (-not $nestedCleaned) { $cleanup.status='failed' }
            }
        }
    }
    } catch {
        # 拒绝异常嵌套目标仍要继续释放已校验的主project，保留父runtime供恢复。
        $cleanup.status='failed'
        $cleanup.steps += @{ name='nested_recovery_exception'; message=(Protect-SmokeText $_.Exception.Message @($password)) }
    }
    if ($dockerReady -and $deploymentAttempted) {
        # 所有删除命令绑定本次安全project及同一份运行配置，无global prune。
        $down = Compose-Call @('down','--volumes','--remove-orphans','--timeout','30') 120
        Write-Evidence 'environment/compose-down.txt' $down.output
        $cleanup.steps += @{ name = 'compose_down'; exit_code = $down.exit_code }
        if ($down.exit_code -ne 0) { $cleanup.status = 'failed' }
        foreach ($kind in @('containers','networks','volumes')) {
            try {
                $remaining = @(Resource-Ids $kind)
                $cleanup.residuals[$kind] = $remaining
                if ($remaining.Count) { $cleanup.status = 'failed' }
            } catch { $cleanup.status = 'failed'; $cleanup.residuals[$kind] = @('query_failed') }
        }
        $danglingMounts = @()
        $volumeList = Docker-Call @('volume','ls','-q') 15
        if ($volumeList.exit_code -ne 0) {
            $cleanup.status = 'failed'
            $danglingMounts = @('query_failed')
        } else {
            $knownVolumes = @($volumeList.output.Trim() -split '\r?\n' | Where-Object { $_ })
            $danglingMounts = @($anonymousVolumes | Sort-Object -Unique | Where-Object { $_ -in $knownVolumes })
        }
        $cleanup.residuals.anonymous_volumes = $danglingMounts
        if ($danglingMounts.Count) { $cleanup.status = 'failed' }
        $after = Compose-Call @('ps','-a','--format','json')
        Write-Evidence 'environment/compose-ps-after.txt' $after.output
        if ($after.exit_code -ne 0) { $cleanup.status = 'failed' }
    }
    if ($dockerReady -and $deploymentAttempted -and -not $KeepContainers) {
        # 删除本次唯一镜像tag，防止run-id镜像累计；共享层/BuildKit缓存不做全局删除。
        foreach ($tag in @("${project}-backend:local", "${project}-frontend:local")) {
            $present = Docker-Call @('image','ls','-q',$tag)
            if ($present.exit_code -ne 0) { $cleanup.status = 'failed'; continue }
            if ($present.output.Trim()) {
                $removed = Docker-Call @('image','rm',$tag) 60
                $cleanup.steps += @{ name = 'image_tag'; tag = $tag; exit_code = $removed.exit_code }
                if ($removed.exit_code -ne 0) { $cleanup.status = 'failed' }
            }
            $check = Docker-Call @('image','ls','-q',$tag)
            if ($check.exit_code -ne 0 -or $check.output.Trim()) { $cleanup.status = 'failed' }
        }
    }
    Remove-SmokeChild $tmpRoot $runId
    # 清理失败保留最小运行凭据以便精确重试，不能毁掉恢复依据；仍删除业务临时文件。
    if ($cleanup.status -eq 'passed') {
        # 可读不代表可删除；整个递归删除期间独立单文件胶囊始终保持完整，覆盖共享锁/新锁竞争。
        $capsule = $null
        if ($state -and $state.marker -eq 'sesrag-demo-smoke-v1' -and (Test-Path -LiteralPath (Join-Path $runtimeDir 'compose.env'))) {
            $capsule = Save-SmokeRecovery $runtimeRoot $runId
        }
        try {
            Remove-SmokeChild $runtimeRoot $runId
            if ($capsule) { [IO.File]::Delete($capsule) }
        } catch {
            $original = $_
            if ($capsule -and (Test-Path -LiteralPath $capsule)) {
                try { Restore-SmokeRecovery $runtimeRoot $runId }
                catch { $cleanup.steps += @{name='recovery_capsule_restore';message='恢复胶囊保留；部分恢复失败，须检查文件共享锁后重试'} }
            }
            throw $original
        }
    }
    $cleanup.steps += @{ name = 'local_paths'; tmp_removed = -not (Test-Path -LiteralPath $tmpDir); runtime_removed = -not (Test-Path -LiteralPath $runtimeDir) }
}

try {
    foreach ($dir in @($runtimeRoot,$artifactRoot,$tmpRoot)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if ($CleanupRunId) { $runId = $CleanupRunId; $report.run_id = $runId }
    $runtimeDir = Get-SmokeChildPath $runtimeRoot $runId
    $artifactDir = Get-SmokeChildPath $artifactRoot $runId
    $tmpDir = Get-SmokeChildPath $tmpRoot $runId
    foreach ($dir in @($artifactDir,(Join-Path $artifactDir 'categories'),(Join-Path $artifactDir 'environment'),(Join-Path $artifactDir 'logs'))) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if ($CleanupRunId) {
        $savedCapsule = Get-SmokeRecoveryPath $runtimeRoot $runId
        if (Test-Path -LiteralPath $savedCapsule) {
            try { Restore-SmokeRecovery $runtimeRoot $runId } catch { $recoveryRejected=$true; throw }
        }
        if (Test-Path -LiteralPath (Join-Path $artifactDir 'summary.json')) {
            Copy-Item -LiteralPath (Join-Path $artifactDir 'summary.json') -Destination (Join-Path $artifactDir ('summary-before-cleanup-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmss') + '.json'))
        }
        $state = Get-Content -LiteralPath (Join-Path $runtimeDir 'context.json') -Raw | ConvertFrom-Json
        if ($state.run_id -ne $runId -or $state.compose_project -notmatch '^sesrag-demo-smoke-[a-z0-9-]+$' -or -not $state.compose_project.EndsWith($runId.Split('-')[-1]) -or $state.marker -ne 'sesrag-demo-smoke-v1') { throw '恢复清理凭据校验失败' }
        $project = $state.compose_project
        $envFile = Join-Path $runtimeDir 'compose.env'
        $passwordLine = Get-Content -LiteralPath $envFile | Where-Object { $_.StartsWith('SMOKE_DB_PASSWORD=') }
        $password = $passwordLine.Substring('SMOKE_DB_PASSWORD='.Length)
        $savedResources = Join-Path $runtimeDir 'resources.json'
        if (Test-Path -LiteralPath $savedResources) { $anonymousVolumes = @((Get-Content -LiteralPath $savedResources -Raw | ConvertFrom-Json).volume_names) }
        $deploymentAttempted = $true
        $report.test_status = 'not_ready'
        $report.stages.cleanup_only = 'requested'
    } else {
        if ($ProjectName -notmatch '^sesrag-demo-smoke(?:-[a-z0-9][a-z0-9-]{0,25})?$') { throw 'ProjectName只能是sesrag-demo-smoke或其安全小写后缀' }
        $project = "$ProjectName-$($runId.Split('-')[-1])"
        $localConfig = Join-Path $PSScriptRoot 'compose/.env.demo-smoke.local'
        $configFile = $(if (Test-Path -LiteralPath $localConfig) { $localConfig } else { Join-Path $PSScriptRoot 'compose/.env.demo-smoke.example' })
        $config = @{}
        foreach ($line in Get-Content -LiteralPath $configFile) {
            if (-not $line.Trim() -or $line.Trim().StartsWith('#')) { continue }
            if ($line -notmatch '^(SMOKE_[A-Z_]+)=(\d+)$') { throw '测试配置仅允许模板中的整数选项' }
            if ($Matches[1] -notin @('SMOKE_API_PORT','SMOKE_FRONTEND_PORT','SMOKE_WAIT_TIMEOUT_SECONDS','SMOKE_BUILD_TIMEOUT_SECONDS')) { throw '未知本地配置键' }
            $config[$Matches[1]] = [int]$Matches[2]
        }
        foreach ($item in @(@('ApiPort','SMOKE_API_PORT'),@('FrontendPort','SMOKE_FRONTEND_PORT'),@('WaitTimeoutSeconds','SMOKE_WAIT_TIMEOUT_SECONDS'),@('BuildTimeoutSeconds','SMOKE_BUILD_TIMEOUT_SECONDS'))) {
            if (-not $PSBoundParameters.ContainsKey($item[0]) -and $config.ContainsKey($item[1])) { Set-Variable -Name $item[0] -Value $config[$item[1]] }
        }
        if ($ApiPort -lt 1024 -or $ApiPort -gt 65535 -or $FrontendPort -lt 1024 -or $FrontendPort -gt 65535 -or $WaitTimeoutSeconds -lt 10 -or $WaitTimeoutSeconds -gt 3600 -or $BuildTimeoutSeconds -lt 30 -or $BuildTimeoutSeconds -gt 7200) { throw '本地配置值越界' }
        $ApiPort = Get-SmokePort $ApiPort @()
        $FrontendPort = Get-SmokePort $FrontendPort @($ApiPort)
        $password = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(24)).ToLowerInvariant()
        $owner = "demo-smoke-$runId"
        New-Item -ItemType Directory -Path $runtimeDir,$tmpDir | Out-Null
        $envFile = Join-Path $runtimeDir 'compose.env'
        @("SMOKE_PROJECT=$project","SMOKE_API_PORT=$ApiPort","SMOKE_FRONTEND_PORT=$FrontendPort","SMOKE_OWNER_ID=$owner","SMOKE_DB_PASSWORD=$password") | Set-Content -LiteralPath $envFile -Encoding utf8
        $state = @{ marker='sesrag-demo-smoke-v1'; run_id=$runId; compose_project=$project; api_port=$ApiPort; frontend_port=$FrontendPort; owner_id=$owner }
        Write-SmokeJson (Join-Path $runtimeDir 'context.json') $state
        $fixtureDir = New-SmokeFixtureSet (Join-Path $PSScriptRoot 'fixtures') (Join-Path $tmpDir 'fixtures')
    }
    $baseUrl = "http://127.0.0.1:$($state.api_port)"
    $frontendUrl = "http://127.0.0.1:$($state.frontend_port)"
    $report.compose_project = $project
    $report.api_url = $baseUrl
    $report.frontend_url = $frontendUrl
    $report.mock_provider = $true
    $report.category_selection = $Category
    $report.git_commit = (Invoke-SmokeProcess 'git' @('rev-parse','HEAD') 10 $repoRoot).output.Trim()
    $report.runner_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
    $report.compose_override_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'compose/docker-compose.demo-smoke.yml') -Algorithm SHA256).Hash
    $report.git_dirty = [bool](Invoke-SmokeProcess 'git' @('status','--porcelain') 10 $repoRoot).output.Trim()
    $report.owner_summary = "isolated-owner:$runId"
    # Shell环境变量优先于--env-file；显式传入本次值防止宿主环境污染。
    # 根 Compose 强制运行时 Secret；隔离工程注入本次随机凭据，避免回退到开发密码。
    $composeEnvironment = @{ SMOKE_PROJECT=$project; SMOKE_DB_PASSWORD=$password; SMOKE_OWNER_ID=$state.owner_id; SMOKE_API_PORT=$state.api_port; SMOKE_FRONTEND_PORT=$state.frontend_port; POSTGRES_PASSWORD=$password; DATABASE_URL="postgresql+psycopg://sesrag:${password}@postgres:5432/sesrag" }
    $composeArgs = @('compose','--project-name',$project,'--project-directory',$repoRoot,'--env-file',$envFile,'--file',(Join-Path $repoRoot 'docker-compose.yml'),'--file',(Join-Path $PSScriptRoot 'compose/docker-compose.demo-smoke.yml'))
    $faultOverride = Join-Path $runtimeDir 'harness-override.json'
    if (-not $CleanupRunId -and $HarnessScenario -in $deploymentScenarios) {
        $generated = Invoke-SmokeProcess 'node' @((Join-Path $PSScriptRoot 'tooling/harness-overrides.mjs'),$HarnessScenario,$faultOverride) 15 $repoRoot
        if ($generated.exit_code -ne 0) { throw '固定故障编排生成失败' }
    }
    if (Test-Path -LiteralPath $faultOverride) { $composeArgs += @('--file',$faultOverride) }
    Write-Host "Run: $runId；project: $project"
    Write-Host "API: $baseUrl；frontend: $frontendUrl"
    $info = Docker-Call @('info','--format','{{.ServerVersion}}') 15
    if ($info.exit_code -ne 0) { throw 'Docker daemon不可用，请启动Docker Desktop的Linux Engine' }
    $dockerReady = $true
    $report.docker_version = $info.output.Trim()
    if ($CleanupRunId) { $report.stages.preflight = 'passed' } else {
        foreach ($kind in @('containers','networks','volumes')) { if (@(Resource-Ids $kind).Count) { throw '随机测试project已存在，拒绝接管或清理未知资源' } }
        foreach ($tag in @("${project}-backend:local", "${project}-frontend:local")) {
            if ((Docker-Call @('image','ls','-q',$tag)).output.Trim()) { throw '测试镜像tag已存在，拒绝复用未知镜像' }
        }
        $report.stages.preflight = 'running'
        $cfg = Compose-Call @('config','--format','json')
        Write-Evidence 'environment/compose-config.txt' $cfg.output
        Write-SmokeJson (Join-Path $artifactDir 'environment/compose-config-process.json') @{exit_code=$cfg.exit_code}
        if ($cfg.exit_code -ne 0) { throw 'Compose覆盖配置不能解析（需支持!override的Compose 2.24.4+）' }
        $parsedConfig = $cfg.output | ConvertFrom-Json
        foreach ($entry in @(@('api',$state.api_port),@('frontend',$state.frontend_port))) {
            $ports = @($parsedConfig.services.($entry[0]).ports)
            if ($ports.Count -ne 1 -or [int]$ports[0].published -ne $entry[1] -or $ports[0].host_ip -ne '127.0.0.1') { throw '隔离端口覆盖失败，拒绝占用开发端口' }
        }
        foreach ($group in @('volumes','networks')) {
            foreach ($resource in $parsedConfig.$group.PSObject.Properties) {
                $spec = $resource.Value
                if (($spec.PSObject.Properties['external'] -and $spec.external) -or -not $spec.name.StartsWith("${project}_")) { throw '编排包含非本次project资源，拒绝启动/删除' }
            }
        }
        $report.stages.preflight = 'passed'
        if (-not $Build -and (-not $BackendImage -or -not $FrontendImage)) { throw '关闭Build必须显式提供BackendImage和FrontendImage本地镜像；不自动复用开发镜像' }
        # 构建和健康等待分开计时；后续up禁用隐式重建，所有后端服务使用同一image。
        $deploymentAttempted = $true
        if ($Build) {
            Write-Host '构建本次临时镜像…'
            $built = Compose-Call @('build','api','frontend') $BuildTimeoutSeconds
            Write-Evidence 'logs/build.log' $built.output
            if ($built.exit_code -ne 0) { throw "镜像构建失败/超时（$($built.exit_code)），见build.log" }
        } else {
            foreach ($pair in @(@($BackendImage,"${project}-backend:local"),@($FrontendImage,"${project}-frontend:local"))) {
                $sourceImage = Docker-Call @('image','inspect',$pair[0],'--format','{{.Id}}')
                if ($sourceImage.exit_code -ne 0) { throw '显式复用的本地镜像不存在' }
                $tagged = Docker-Call @('image','tag',$pair[0],$pair[1])
                if ($tagged.exit_code -ne 0) { throw '本地镜像添加本次tag失败' }
                $report.stages[$pair[1]] = @{ reused_image_id=$sourceImage.output.Trim() }
            }
        }
        $startupDeadline = [DateTime]::UtcNow.AddSeconds($WaitTimeoutSeconds)
        $report.stages.startup = 'running'
        $up = Compose-Call @('up','--detach','--no-build') $WaitTimeoutSeconds
        Write-Evidence 'environment/compose-up.txt' $up.output
        Write-SmokeJson (Join-Path $artifactDir 'environment/compose-up-process.json') @{exit_code=$up.exit_code}
        if ($up.exit_code -ne 0) { throw "Compose启动失败（$($up.exit_code)）" }
        Wait-Environment
        $report.stages.startup = 'passed'
        Write-Host '隔离环境就绪。'
        $categoryRoot = Join-Path $PSScriptRoot 'specific_test_script'
        $manifestPath = Join-Path $categoryRoot 'manifest.json'
        if ($HarnessScenario) {
            $categoryRoot = Join-Path $PSScriptRoot 'tooling/harness-fixtures'
            $manifestName = $(if ($HarnessScenario -in $deploymentScenarios -and $HarnessScenario -ne 'hard-kill-recovery') { 'deployment' } else { $HarnessScenario })
            $manifestPath = Join-Path $categoryRoot "$manifestName.json"
            $report.harness_scenario = $HarnessScenario
        }
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schema_version -ne 1) { throw '未知manifest版本' }
        if (@($manifest.categories | Group-Object name | Where-Object Count -gt 1).Count) { throw 'manifest分类名称重复' }
        Write-SmokeJson (Join-Path $artifactDir 'manifest.json') $manifest
        $selected = @($manifest.categories | Where-Object { $Category -eq 'all' -or $_.name -eq $Category })
        if ($Category -ne 'all' -and -not $selected.Count) { throw 'Category不在manifest中' }
        $report.test_status = 'passed'
        if (-not $selected.Count) { $report.test_status = 'not_ready' }
        foreach ($categoryItem in $selected) {
            if ($categoryItem.name -notmatch '^[a-z0-9-]+$' -or $categoryItem.status -notin @('enabled','not_implemented','disabled')) { throw '非法分类manifest' }
            if ($categoryItem.status -eq 'disabled') {
                $report.categories += @{ name=$categoryItem.name; status='skipped' }
                if ($report.test_status -eq 'passed') { $report.test_status='not_ready' }
                continue
            }
            if ($categoryItem.status -eq 'not_implemented') {
                $report.categories += @{ name=$categoryItem.name; status='not_ready' }
                Write-SmokeJson (Join-Path $artifactDir "categories/$($categoryItem.name).json") @{ schema_version=1; run_id=$runId; category=$categoryItem.name; status='not_ready'; started_at=[DateTime]::UtcNow.ToString('o'); finished_at=[DateTime]::UtcNow.ToString('o'); checks=@(); evidence=@(); reason='分类脚本尚未接入；没有执行产品检查' }
                if ($report.test_status -eq 'passed') { $report.test_status='not_ready' }
                continue
            }
            # 分类路径只能是当前目录下一个.ps1/.mjs文件，不接受目录逃逸。
            if ($categoryItem.script -notmatch '^[a-z0-9-]+\.(ps1|mjs)$') { throw '非法分类脚本路径' }
            if ([int]$categoryItem.timeout_seconds -lt 1 -or [int]$categoryItem.timeout_seconds -gt 21600) { throw '分类超时必须1～21600秒（独立QLT需驱动缺失分类）' }
            $categoryPath = Join-Path $categoryRoot $categoryItem.script
            if (-not (Test-Path -LiteralPath $categoryPath)) { throw 'enabled分类缺少脚本' }
            $argsList = @('-BaseUrl',$baseUrl,'-FrontendUrl',$frontendUrl,'-RunId',$runId,'-ArtifactDir',$artifactDir,'-RuntimeDir',$runtimeDir,'-FixtureDir',$fixtureDir)
            $scriptHash = (Get-FileHash -LiteralPath $categoryPath -Algorithm SHA256).Hash
            if ($categoryPath.EndsWith('.ps1')) { $exe = (Get-Process -Id $PID).Path; $argsList = @('-NoProfile','-File',$categoryPath) + $argsList } else { $exe='node'; $argsList=@($categoryPath) + $argsList }
            $result = Invoke-SmokeProcess $exe $argsList ([int]$categoryItem.timeout_seconds) $PSScriptRoot @{ PLAYWRIGHT_BROWSERS_PATH=(Join-Path $PSScriptRoot '.cache/ms-playwright') } (Join-Path $runtimeDir 'process-resources.json') @{run_id=$runId;project=$project}
            Write-Host "分类 $($categoryItem.name) 完成（退出码 $($result.exit_code)），中文过程证据：logs/category-$($categoryItem.name).log"
            Write-Evidence "logs/category-$($categoryItem.name).log" $result.output
            $jsonPath = Join-Path $artifactDir "categories/$($categoryItem.name).json"
            $validReport = $false
            if (Test-Path -LiteralPath $jsonPath) {
                $raw = Get-Content -LiteralPath $jsonPath -Raw
                $validReport = Test-Json -Json $raw -SchemaFile (Join-Path $PSScriptRoot 'specific_test_script/category-result.schema.json') -ErrorAction SilentlyContinue
                if ($validReport) {
                    $categoryReport = $raw | ConvertFrom-Json
                    $validReport = $categoryReport.run_id -eq $runId -and $categoryReport.category -eq $categoryItem.name -and $categoryReport.status -eq 'passed' -and @($categoryReport.checks | Where-Object status -ne 'passed').Count -eq 0
                }
                Write-Evidence "categories/$($categoryItem.name).json" $raw
            }
            $status = $(if ($result.exit_code -eq 0 -and $validReport) { 'passed' } else { 'failed' })
            $report.categories += @{ name=$categoryItem.name; status=$status; exit_code=$result.exit_code; script_sha256=$scriptHash }
            if ($status -ne 'passed') { $report.test_status='failed' }
        }
        if ($Interactive) { [void](Read-Host '可在打印的地址手工测试；完成后按Enter收集报告并销毁环境') }
        if ($SessionSeconds) { Write-Host "保留${SessionSeconds}秒用于环境检查，之后自动销毁…"; Start-Sleep -Seconds $SessionSeconds }
        $report.stages.tests = $report.test_status
        if ($HarnessScenario -in @('cleanup-failure','cleanup-share-read')) {
            $share = $(if ($HarnessScenario -eq 'cleanup-share-read') { [IO.FileShare]::Read } else { [IO.FileShare]::None })
            $cleanupLock = [IO.File]::Open((Join-Path $runtimeDir 'locked-cleanup-sentinel'),[IO.FileMode]::Create,[IO.FileAccess]::ReadWrite,$share)
            Write-Host 'CLEANUP_LOCK_ARMED'
        }
    }
} catch {
    foreach ($stage in @('preflight','startup','tests')) { if ($report.stages[$stage] -eq 'running') { $report.stages[$stage]='failed' } }
    $report.errors += (Protect-SmokeText $_.Exception.Message @($password))
    if ($deploymentAttempted -and -not $CleanupRunId) { $report.test_status = 'failed' } else { $report.test_status = 'blocked' }
    Write-Warning $report.errors[-1]
} finally {
    if ($artifactDir -and (Test-Path -LiteralPath $artifactDir)) {
        if ($dockerReady -and $deploymentAttempted) {
            try { Collect-Evidence } catch { $report.stages.report_collection='failed'; $report.errors += (Protect-SmokeText $_.Exception.Message @($password)); if ($report.test_status -in @('passed','not_ready')) { $report.test_status='failed' } }
        }
        try { Cleanup-Environment } catch { $cleanup.status='failed'; $cleanup.steps += @{ name='cleanup_exception'; message=(Protect-SmokeText $_.Exception.Message @($password)) } }
        # 即使Docker清理异常也尝试释放本次业务临时文件；失败时保留凭据供CleanupRunId重试。
        try { if (-not $KeepContainers) { Remove-SmokeChild $tmpRoot $runId } } catch { $cleanup.status='failed'; $cleanup.steps += @{ name='tmp_cleanup'; message=$_.Exception.Message } }
        $cleanup.finished_at = [DateTime]::UtcNow.ToString('o')
        Write-SmokeJson (Join-Path $artifactDir 'cleanup.json') $cleanup
        $outcome = Get-SmokeOutcome $report.test_status $cleanup.status
        $report.status = $outcome.status
        $report.exit_code = $outcome.exit_code
        $report.cleanup_status = $cleanup.status
        $report.finished_at = [DateTime]::UtcNow.ToString('o')
        $report.stages.cleanup = $cleanup.status
        Write-SmokeJson (Join-Path $artifactDir 'summary.json') $report
        # 产品/运行器分类均提供人读逐项投影；汇总失败不能伪装成报告收集通过。
        $rendered = Invoke-SmokeProcess 'node' @((Join-Path $PSScriptRoot 'tooling/render-summary.mjs'),$artifactDir) 30 $repoRoot
        if ($rendered.exit_code -ne 0) {
            $report.errors += '中文详细摘要生成失败，见renderer.log'
            Write-Evidence 'logs/renderer.log' $rendered.output
            $report.stages.report_collection='failed'
            if ($report.test_status -in @('passed','not_ready')) { $report.test_status='failed' }
            $outcome=Get-SmokeOutcome $report.test_status $cleanup.status
            $report.status=$outcome.status; $report.exit_code=$outcome.exit_code
            Write-SmokeJson (Join-Path $artifactDir 'summary.json') $report
        }
        @("# Demo Smoke $runId","","- 总体状态：$($report.status)","- 执行状态：$($report.test_status)","- 清理状态：$($cleanup.status)","- 退出码：$($report.exit_code)","- 启动：$($report.stages.startup)","- 子项failed/blocked/未执行不得报通过；环境与业务验收分开。","- 详见summary-详细.md、summary.json、cleanup.json及logs/。") | Set-Content -LiteralPath (Join-Path $artifactDir 'summary.md') -Encoding utf8
        Write-Host "结果：$($report.status)；清理：$($cleanup.status)；报告：$artifactDir"
        if (-not $KeepArtifacts -and $cleanup.status -eq 'passed') { Remove-SmokeChild $artifactRoot $runId; Write-Host '本次报告已按KeepArtifacts=false删除，无法再从磁盘复查。' }
    } else { $report.exit_code = 2 }
}
if ($cleanupLock) { $cleanupLock.Dispose() }
exit $report.exit_code
