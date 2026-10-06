#Requires -Version 7.4
# 仅验证运行器的安全/生命周期基础设施，不是产品分类测试。
$ErrorActionPreference = 'Stop'
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

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        $occupied = $listener.LocalEndpoint.Port
        $free = Get-SmokePort $occupied @()
        Assert-Check ($free -ne $occupied) '被占用端口必须被安全替换'
    } finally { $listener.Stop() }
    Write-Output 'Harness self-tests passed: path safety, redaction, outcome, fixtures, report schema, child process, port conflict.'
} finally {
    # 临时目录为本脚本刚创建的随机目录，删除前确认绝对父目录。
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ((Split-Path ([IO.Path]::GetFullPath($sandbox)) -Parent) -ne $tempRoot) { throw '非法self-test清理路径' }
    Remove-Item -LiteralPath $sandbox -Recurse -Force
}
