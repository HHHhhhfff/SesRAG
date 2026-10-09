#Requires -Version 7.4
# 仅验证运行器的安全/生命周期基础设施，不是产品分类测试。
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
. "$PSScriptRoot/lib/smoke-common.ps1"

function Assert-Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ('sesrag-harness-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sandbox | Out-Null
try {
    $child = Join-Path $sandbox 'run-one'
    New-Item -ItemType Directory -Path $child | Out-Null
    Assert-Check ((Get-SmokeChildPath $sandbox 'run-one') -eq $child) '合法子路径应保持不变'
    $rejected = $false
    try { Get-SmokeChildPath $sandbox '../outside' | Out-Null } catch { $rejected = $true }
    Assert-Check $rejected '路径逃逸必须被拒绝'
    $rejected = $false
    try { Remove-SmokeChild $sandbox '.' } catch { $rejected = $true }
    Assert-Check $rejected '不能递归删除根目录'
    Remove-SmokeChild $sandbox 'run-one'
    Assert-Check (-not (Test-Path -LiteralPath $child)) '精确子目录必须删除'

    $secret = 'test-secret-not-a-real-password'
    $scrubbed = Protect-SmokeText "password=$secret postgresql+psycopg://user:pwd@postgres/db Bearer abc123" @($secret)
    Assert-Check (-not $scrubbed.Contains($secret)) '报告不能保留运行密码'
    Assert-Check (-not $scrubbed.Contains('user:pwd')) '报告不能保留连接串凭据'
    Assert-Check (-not $scrubbed.Contains('abc123')) '报告不能保留Bearer凭据'

    $outcome = Get-SmokeOutcome 'not_ready' 'passed'
    Assert-Check ($outcome.status -eq 'not_ready' -and $outcome.exit_code -eq 3) '没有分类不能通过'
    $outcome = Get-SmokeOutcome 'failed' 'failed'
    Assert-Check ($outcome.status -eq 'cleanup_failed' -and $outcome.exit_code -eq 4) '清理失败不能被测试失败覆盖'
    $outcome = Get-SmokeOutcome 'passed' 'deferred'
    Assert-Check ($outcome.exit_code -ne 0) '保留容器不能正式通过'

    $firstFixtures = New-SmokeFixtureSet "$PSScriptRoot/fixtures" (Join-Path $sandbox 'fixtures-one')
    $secondFixtures = New-SmokeFixtureSet "$PSScriptRoot/fixtures" (Join-Path $sandbox 'fixtures-two')
    $firstDocx = Join-Path $firstFixtures 'upload-safe/smoke.docx'
    Assert-Check ((Get-FileHash $firstDocx).Hash -eq (Get-FileHash (Join-Path $secondFixtures 'upload-safe/smoke.docx')).Hash) 'docx数据必须可重复生成'
    $archive = [IO.Compression.ZipFile]::OpenRead($firstDocx)
    try { Assert-Check ($null -ne $archive.GetEntry('word/document.xml')) '生成docx必须有正文部件' } finally { $archive.Dispose() }

    $schemaPath = "$PSScriptRoot/specific_test_script/category-result.schema.json"
    $emptyPassed = '{"schema_version":1,"run_id":"r","category":"service-health","status":"passed","started_at":"2026-10-06T00:00:00Z","finished_at":"2026-10-06T00:00:01Z","checks":[],"evidence":[]}'
    Assert-Check (-not (Test-Json -Json $emptyPassed -SchemaFile $schemaPath -ErrorAction SilentlyContinue)) '没有检查项的passed报告必须拒绝'
    $validNotReady = '{"schema_version":1,"run_id":"r","category":"service-health","status":"not_ready","started_at":"2026-10-06T00:00:00Z","finished_at":"2026-10-06T00:00:01Z","checks":[],"evidence":[]}'
    Assert-Check (Test-Json -Json $validNotReady -SchemaFile $schemaPath) '未接入分类应能明确生成无检查的not_ready报告'

    $process = Invoke-SmokeProcess (Get-Process -Id $PID).Path @('-NoProfile','-Command','Write-Output "ok"; exit 7') 10
    Assert-Check ($process.exit_code -eq 7 -and $process.output.Trim() -eq 'ok') '必须保留子进程真实退出码'
    $process = Invoke-SmokeProcess (Get-Process -Id $PID).Path @('-NoProfile','-Command','Start-Sleep -Seconds 30') 1
    Assert-Check ($process.timed_out -and $process.exit_code -ne 0) '超时必须终止进程并返回失败'

    # 任务2：按总入口同一进程适配器验证PowerShell/Node六参数与中文输出。
    # 只调用tooling哨兵，不启用假产品分类或修改正式manifest。
    $expectedArgs = [ordered]@{
        BaseUrl='http://127.0.0.1:18000'; FrontendUrl='http://127.0.0.1:15173'
        RunId='protocol-probe'; ArtifactDir=(Join-Path $sandbox 'report with spaces')
        RuntimeDir=(Join-Path $sandbox 'runtime'); FixtureDir=(Join-Path $sandbox 'fixtures-one')
    }
    $sixArgs = @()
    foreach ($key in $expectedArgs.Keys) { $sixArgs += @("-$key",$expectedArgs[$key]) }
    foreach ($extension in @('ps1','mjs')) {
        $probePath = Join-Path $PSScriptRoot "tooling/dispatch-probe.$extension"
        if ($extension -eq 'ps1') {
            $executable=(Get-Process -Id $PID).Path
            $probeArgs=@('-NoProfile','-File',$probePath)+$sixArgs
        } else { $executable='node'; $probeArgs=@($probePath)+$sixArgs }
        $process=Invoke-SmokeProcess $executable $probeArgs 10 $PSScriptRoot
        Assert-Check ($process.exit_code -eq 0) "${extension}调用协议应成功"
        $received=$process.output | ConvertFrom-Json
        foreach ($key in $expectedArgs.Keys) { Assert-Check ($received.$key -eq $expectedArgs[$key]) "${extension}参数不可丢失/被空格拆分：$key" }
        Assert-Check ($received.message -eq '六参数中文调用成功') "${extension}中文输出不可乱码"
    }

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        $occupied = $listener.LocalEndpoint.Port
        $free = Get-SmokePort $occupied @()
        Assert-Check ($free -ne $occupied) '被占用端口必须被安全替换'
    } finally { $listener.Stop() }
    Write-Output '运行器自检通过：路径安全、脱敏、状态、fixture、报告Schema、子进程/超时、PowerShell与Node六参数中文协议、端口冲突；未执行产品分类。'
} finally {
    # 临时目录为本脚本刚创建的随机目录，删除前确认绝对父目录。
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ((Split-Path ([IO.Path]::GetFullPath($sandbox)) -Parent) -ne $tempRoot) { throw '非法self-test清理路径' }
    Remove-Item -LiteralPath $sandbox -Recurse -Force
}
