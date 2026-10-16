#Requires -Version 7.4
Set-StrictMode -Version Latest

function Get-SmokeChildPath([string]$Root, [string]$Child) {
    # 只允许一个命名子目录；拒绝根目录、绝对路径、路径逃逸及链接目录。
    if ($Child -notmatch '^[a-z0-9][a-z0-9-]{0,100}$') { throw '非法运行子目录名' }
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $target = [IO.Path]::GetFullPath((Join-Path $rootPath $Child))
    if ((Split-Path $target -Parent) -ne $rootPath) { throw '运行路径逃逸' }
    foreach ($path in @($rootPath, $target)) {
        if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '不允许链接运行目录'
        }
    }
    return $target
}

function Remove-SmokeChild([string]$Root, [string]$Child) {
    $target = Get-SmokeChildPath $Root $Child
    if (Test-Path -LiteralPath $target) {
        # 运行目录内也不允许junction/symlink，避免递归清理越过本次边界。
        $links = @(Get-ChildItem -LiteralPath $target -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count) { throw '运行目录包含链接，拒绝递归删除，请人工核对' }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

# I2：胶囊只包含固定恢复文件，作为单个原子文件放在同一ignored runtime根；不进入artifact。
function Get-SmokeRecoveryNames {
    return @('context.json','compose.env','harness-override.json','resources.json','nested-runs.json','process-resources.json','frontend-resources.json','execution-resources.json','frontend-resources.json.tmp')
}
function Get-SmokeRecoveryPath([string]$Root, [string]$RunId) {
    $runtime = Get-SmokeChildPath $Root $RunId
    $capsule = $runtime + '-recovery.json'
    foreach ($file in @($capsule,($capsule+'.tmp'))) {
        if ((Test-Path -LiteralPath $file) -and ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '不允许链接恢复胶囊' }
    }
    return $capsule
}
function Read-SmokeRecovery([string]$Root, [string]$RunId) {
    $capsule = Get-SmokeRecoveryPath $Root $RunId
    $data = Get-Content -LiteralPath $capsule -Raw | ConvertFrom-Json -AsHashtable
    if ($data.marker -ne 'sesrag-smoke-recovery-v1' -or $data.run_id -ne $RunId) { throw '恢复胶囊身份不匹配' }
    if (-not $data.files.ContainsKey('context.json') -or -not $data.files.ContainsKey('compose.env')) { throw '恢复胶囊不完整' }
    foreach ($name in $data.files.Keys) { if ($name -notin (Get-SmokeRecoveryNames)) { throw '恢复胶囊包含非法路径' } }
    $context = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($data.files['context.json'])).TrimStart([char]0xFEFF) | ConvertFrom-Json
    if ($context.marker -ne 'sesrag-demo-smoke-v1' -or $context.run_id -ne $RunId -or $context.compose_project -ne $data.project -or $data.project -notmatch '^sesrag-demo-smoke-[a-z0-9-]+$' -or -not $data.project.EndsWith($RunId.Split('-')[-1])) { throw '恢复胶囊context身份不匹配' }
    return $data
}
function Save-SmokeRecovery([string]$Root, [string]$RunId) {
    $runtime = Get-SmokeChildPath $Root $RunId
    $capsule = Get-SmokeRecoveryPath $Root $RunId
    $files = @{}
    foreach ($name in (Get-SmokeRecoveryNames)) {
        $file = Join-Path $runtime $name
        if (Test-Path -LiteralPath $file) {
            $item = Get-Item -LiteralPath $file
            if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '恢复材料必须为普通文件' }
            $files[$name] = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
        }
    }
    $context = Get-Content -LiteralPath (Join-Path $runtime 'context.json') -Raw | ConvertFrom-Json
    if ($context.marker -ne 'sesrag-demo-smoke-v1' -or $context.run_id -ne $RunId -or $context.compose_project -notmatch '^sesrag-demo-smoke-[a-z0-9-]+$' -or -not $context.compose_project.EndsWith($RunId.Split('-')[-1]) -or -not $files.ContainsKey('compose.env')) { throw '拒绝保存不完整或错误身份胶囊' }
    $data = @{marker='sesrag-smoke-recovery-v1';run_id=$RunId;project=$context.compose_project;files=$files}
    [IO.File]::WriteAllText($capsule+'.tmp',($data | ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
    [IO.File]::Move($capsule+'.tmp',$capsule,$true)
    [void](Read-SmokeRecovery $Root $RunId)
    return $capsule
}
function Restore-SmokeRecovery([string]$Root, [string]$RunId) {
    $data = Read-SmokeRecovery $Root $RunId
    $runtime = Get-SmokeChildPath $Root $RunId
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    # 先核验所有已有材料再写任何缺失项，避免冲突context之前已写入其他凭据。
    foreach ($name in $data.files.Keys) {
        $file = Join-Path $runtime $name
        if (Test-Path -LiteralPath $file) {
            $item = Get-Item -LiteralPath $file
            if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '不允许覆盖链接恢复材料' }
            # 已存在且相同的锁定文件不重写；任何身份/内容冲突直接拒绝。
            if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($file)) -ne $data.files[$name]) { throw '已有恢复材料与胶囊冲突' }
        }
    }
    foreach ($name in $data.files.Keys) {
        $file = Join-Path $runtime $name
        if (-not (Test-Path -LiteralPath $file)) { [IO.File]::WriteAllBytes($file,[Convert]::FromBase64String($data.files[$name])) }
    }
}

function Protect-SmokeText([string]$Value, [string[]]$Secrets = @()) {
    foreach ($secret in $Secrets) {
        if ($secret) { $Value = $Value.Replace($secret, '[REDACTED]') }
    }
    $Value = [regex]::Replace($Value, '(?i)(postgres(?:ql)?(?:\+\w+)?://)[^\s/@]+(?::[^\s/@]+)?@', '$1[REDACTED]@')
    $Value = [regex]::Replace($Value, '(?i)(Bearer\s+)[a-z0-9._~+/-]+', '$1[REDACTED]')
    $Value = [regex]::Replace($Value, '(?im)((?:password|api[_-]?key|secret)\s*[:=]\s*)[^\r\n,}]+', '$1[REDACTED]')
    return $Value
}

function Write-SmokeJson([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $Path -Encoding utf8
}

function Get-SmokeOutcome([string]$TestStatus, [string]$CleanupStatus) {
    if ($CleanupStatus -eq 'failed') { return @{ status = 'cleanup_failed'; exit_code = 4 } }
    if ($CleanupStatus -eq 'deferred') { return @{ status = 'cleanup_deferred'; exit_code = 5 } }
    $codes = @{ passed = 0; failed = 1; blocked = 2; not_ready = 3 }
    if (-not $codes.ContainsKey($TestStatus)) { throw '非法测试状态' }
    return @{ status = $TestStatus; exit_code = $codes[$TestStatus] }
}

function Get-SmokePort([int]$Preferred, [int[]]$Excluded = @()) {
    foreach ($candidate in @($Preferred, 0)) {
        if ($candidate -in $Excluded) { continue }
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidate)
        try {
            $listener.Start()
            $port = $listener.LocalEndpoint.Port
            if ($port -notin $Excluded) { return $port }
        } catch [Net.Sockets.SocketException] {
            # 占用首选端口时改用OS分配的空闲端口，不终止其他服务。
        } finally { $listener.Stop() }
    }
    throw '无法选择测试端口'
}

function Invoke-SmokeProcess(
    [string]$Executable, [string[]]$Arguments, [int]$TimeoutSeconds = 60,
    [string]$WorkingDirectory = '', [hashtable]$Environment = @{},
    [string]$RegistryPath = '', [hashtable]$RegistryOwner = @{}
) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    # 启动前解析且真正使用同一exe绝对路径；Windows早期MainModule可能尚未加载，不能作为身份来源。
    $application = Get-Command -Name $Executable -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $startInfo.FileName = [IO.Path]::GetFullPath($application.Path)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    # 后续所有分类的中文证据统一UTF-8，避免Windows父进程按本地代码页解码。
    $startInfo.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $startInfo.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $startInfo.Environment['PYTHONIOENCODING'] = 'utf-8'
    if ($WorkingDirectory) { $startInfo.WorkingDirectory = $WorkingDirectory }
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    foreach ($key in $Environment.Keys) { $startInfo.Environment[$key] = [string]$Environment[$key] }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $timedOut = $false
    $started = $false
    $registry = $null
    $registryEntry = $null
    try {
        if ($RegistryPath) {
            $registry = @{ schema_version=1; parent_run_id=$RegistryOwner.run_id; project=$RegistryOwner.project; resources=@() }
            if (Test-Path -LiteralPath $RegistryPath) { $registry = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json -AsHashtable }
            if ($registry.parent_run_id -ne $RegistryOwner.run_id -or $registry.project -ne $RegistryOwner.project) { throw '进程登记身份不匹配' }
            $registryEntry = @{ id=[guid]::NewGuid().ToString('N'); kind='category-process'; status='planned' }
            $registry.resources += $registryEntry
            Write-SmokeJson $RegistryPath $registry
        }
        [void]$process.Start()
        $started = $true
        if ($registryEntry) {
            try {
                # 快速退出可能发生于任何一次属性采样之间，不能凭数值PID伪造可恢复身份。
                if ($process.HasExited) { throw 'process-exited-before-identity' }
                $identity = @{ pid=$process.Id; started=$process.StartTime.ToUniversalTime().Ticks.ToString(); executable=$startInfo.FileName }
                if (-not $identity.started -or -not $identity.executable) { throw '活跃子进程缺少完整出生身份' }
                $registryEntry.status='running'
                $registryEntry.process_identity=$identity
            } catch {
                # 再观察一次真实退出，覆盖HasExited与StartTime查询间的退出竞争；活跃错误仍失败。
                if (-not $process.HasExited -and -not $process.WaitForExit(50)) { throw }
                $registryEntry.status='closed'
                $registryEntry.observed_process_closed=$true
                $registryEntry.identity_not_observed_due_to_exit=$true
                $registryEntry.process_exit_code=$process.ExitCode
            }
            Write-SmokeJson $RegistryPath $registry
        }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while (-not $process.WaitForExit(200)) {
            if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                $process.Kill($true)
                break
            }
        }
        $process.WaitForExit()
        $output = $stdout.GetAwaiter().GetResult()
        $errorOutput = $stderr.GetAwaiter().GetResult()
        if ($errorOutput) { $output += "`n$errorOutput" }
        return @{ exit_code = $(if ($timedOut) { 124 } else { $process.ExitCode }); output = $output; timed_out = $timedOut }
    } finally {
        # 异常/可捕获Ctrl+C先关闭分类子进程树，再由总入口清理Compose资源。
        if ($started -and -not $process.HasExited) { $process.Kill($true); $process.WaitForExit() }
        if ($registryEntry) {
            $registryEntry.status='closed'; $registryEntry.observed_process_closed=$true
            if ($started) { $registryEntry.process_exit_code=$process.ExitCode }
            Write-SmokeJson $RegistryPath $registry
        }
        $process.Dispose()
    }
}

function New-SmokeFixtureSet([string]$Source, [string]$Destination) {
    # docx按固定XML/时间生成在本次tmp，Git只维护可审计的文本源。
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $Source 'upload-safe'),(Join-Path $Source 'upload-invalid'),(Join-Path $Source 'expected') -Destination $Destination -Recurse
    $documentXml = Get-Content -LiteralPath (Join-Path $Source 'upload-safe/smoke-docx.document.xml') -Raw
    $entries = [ordered]@{
        '[Content_Types].xml' = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
        '_rels/.rels' = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
        'word/document.xml' = $documentXml
    }
    $zipPath = Join-Path $Destination 'upload-safe/smoke.docx'
    $archive = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $entries.Keys) {
            $entry = $archive.CreateEntry($name)
            $entry.LastWriteTime = [DateTimeOffset]::new(2000,1,1,0,0,0,[TimeSpan]::Zero)
            $writer = [IO.StreamWriter]::new($entry.Open(), [Text.UTF8Encoding]::new($false))
            try { $writer.Write($entries[$name]) } finally { $writer.Dispose() }
        }
    } finally { $archive.Dispose() }
    return $Destination
}
