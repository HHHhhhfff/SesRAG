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
        if ($db.Count -and $redis.Count -and $migrate.Count -and $migrate[0].State -eq 'exited' -and $migrate[0].ExitCode -eq 0) {
            try {
                $live = Invoke-RestMethod "$baseUrl/health/live" -TimeoutSec 3
                $ready = Invoke-RestMethod "$baseUrl/health/ready" -TimeoutSec 3
                Write-SmokeJson (Join-Path $artifactDir 'environment/health-live.json') $live
                Write-SmokeJson (Join-Path $artifactDir 'environment/health-ready.json') $ready
                $front = Invoke-WebRequest $frontendUrl -TimeoutSec 3
                $proxy = Invoke-RestMethod "$frontendUrl/health/live" -TimeoutSec 3
                # 补查实际数据库连接；ready当前固定database标记不足以证明依赖可用。
                $sql = Compose-Call @('exec','-T','postgres','psql','-U','sesrag','-d','sesrag','-Atc',"SELECT version_num FROM alembic_version; SELECT extname FROM pg_extension WHERE extname='vector';") 10
                if ($live.status -eq 'ok' -and $ready.database -eq 'ready' -and $ready.redis -eq 'ready' -and $ready.worker_count -ge 1 -and $front.StatusCode -eq 200 -and $proxy.status -eq 'ok' -and $sql.exit_code -eq 0 -and $sql.output -match '0001_initial_demo' -and $sql.output -match 'vector') {
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
    if ($KeepContainers -and $deploymentAttempted) { $cleanup.status = 'deferred'; return }
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
    if ($cleanup.status -eq 'passed') { Remove-SmokeChild $runtimeRoot $runId }
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
    $composeEnvironment = @{ SMOKE_PROJECT=$project; SMOKE_DB_PASSWORD=$password; SMOKE_OWNER_ID=$state.owner_id; SMOKE_API_PORT=$state.api_port; SMOKE_FRONTEND_PORT=$state.frontend_port }
    $composeArgs = @('compose','--project-name',$project,'--project-directory',$repoRoot,'--env-file',$envFile,'--file',(Join-Path $repoRoot 'docker-compose.yml'),'--file',(Join-Path $PSScriptRoot 'compose/docker-compose.demo-smoke.yml'))
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
        $cfg = Compose-Call @('config','--format','json')
        Write-Evidence 'environment/compose-config.txt' $cfg.output
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
        $up = Compose-Call @('up','--detach','--no-build') $WaitTimeoutSeconds
        Write-Evidence 'environment/compose-up.txt' $up.output
        if ($up.exit_code -ne 0) { throw "Compose启动失败（$($up.exit_code)）" }
        Wait-Environment
        $report.stages.startup = 'passed'
        Write-Host '隔离环境就绪。'
        $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'specific_test_script/manifest.json') -Raw | ConvertFrom-Json
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
            if ([int]$categoryItem.timeout_seconds -lt 1 -or [int]$categoryItem.timeout_seconds -gt 7200) { throw '分类超时必须1～7200秒' }
            $categoryPath = Join-Path $PSScriptRoot "specific_test_script/$($categoryItem.script)"
            if (-not (Test-Path -LiteralPath $categoryPath)) { throw 'enabled分类缺少脚本' }
            $argsList = @('-BaseUrl',$baseUrl,'-FrontendUrl',$frontendUrl,'-RunId',$runId,'-ArtifactDir',$artifactDir,'-RuntimeDir',$runtimeDir,'-FixtureDir',$fixtureDir)
            $scriptHash = (Get-FileHash -LiteralPath $categoryPath -Algorithm SHA256).Hash
            if ($categoryPath.EndsWith('.ps1')) { $exe = (Get-Process -Id $PID).Path; $argsList = @('-NoProfile','-File',$categoryPath) + $argsList } else { $exe='node'; $argsList=@($categoryPath) + $argsList }
            $result = Invoke-SmokeProcess $exe $argsList ([int]$categoryItem.timeout_seconds) $PSScriptRoot @{ PLAYWRIGHT_BROWSERS_PATH=(Join-Path $PSScriptRoot '.cache/ms-playwright') }
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
    }
} catch {
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
        @("# Demo Smoke $runId","","- 总体状态：$($report.status)","- 执行状态：$($report.test_status)","- 清理状态：$($cleanup.status)","- 退出码：$($report.exit_code)","- 启动：$($report.stages.startup)","- 分类尚未接入不代表产品通过；环境与业务验收分开。","- 详见summary.json、cleanup.json及logs/。") | Set-Content -LiteralPath (Join-Path $artifactDir 'summary.md') -Encoding utf8
        Write-Host "结果：$($report.status)；清理：$($cleanup.status)；报告：$artifactDir"
        if (-not $KeepArtifacts -and $cleanup.status -eq 'passed') { Remove-SmokeChild $artifactRoot $runId; Write-Host '本次报告已按KeepArtifacts=false删除，无法再从磁盘复查。' }
    } else { $report.exit_code = 2 }
}
exit $report.exit_code
