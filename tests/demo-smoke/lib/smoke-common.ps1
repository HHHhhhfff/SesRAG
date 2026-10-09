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
    [string]$WorkingDirectory = '', [hashtable]$Environment = @{}
) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
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
    try {
        [void]$process.Start()
        $started = $true
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
