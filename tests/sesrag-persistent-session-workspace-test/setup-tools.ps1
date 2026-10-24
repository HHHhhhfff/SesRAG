#Requires -Version 7.4
<#
安装本 suite 的 Chromium 并执行空页启动/关闭自检；不安装 Docker、不修改 PATH。
Linux 缺系统共享库时不擅自 sudo，请根据安装器诊断由管理员补齐。
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$oldBrowserPath = $env:PLAYWRIGHT_BROWSERS_PATH
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$cacheRoot = Join-Path $PSScriptRoot '.cache'
$setupTemp = $null
$setupOwner = [guid]::NewGuid().ToString('N')
$tempCreated = $false
$resultCode = 2

function Assert-NoLinkedAncestor([string] $Target) {
    # 检查整条祖先链，不能只检查叶目录而越过已存在的 junction/symlink。
    $cursor = [System.IO.Path]::GetFullPath($Target)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw '工具缓存或临时目录的祖先包含链接，拒绝安装或删除。'
            }
        }
        $parent = [System.IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

try {
    Assert-NoLinkedAncestor $cacheRoot
    $nodeCommand = Get-Command node -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $nodeVersion = & $nodeCommand.Source --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v24\.') { throw "需要 Node.js 24 LTS，当前为 $nodeVersion" }
    $cli = Join-Path $PSScriptRoot 'node_modules/playwright/cli.js'
    if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
        throw '缺少本套件 npm 依赖；先执行 README 中的 npm ci --prefix 命令。'
    }
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $cacheRoot 'ms-playwright'
    Assert-NoLinkedAncestor $env:PLAYWRIGHT_BROWSERS_PATH
    $setupTemp = Join-Path $cacheRoot "setup-tmp-$setupOwner"
    if (Test-Path -LiteralPath $setupTemp) { throw '随机安装临时目录已存在，拒绝接管。' }
    New-Item -ItemType Directory -Path $setupTemp | Out-Null
    $tempCreated = $true
    [System.IO.File]::WriteAllText((Join-Path $setupTemp '.setup-owner'), $setupOwner)
    $env:TEMP = $setupTemp
    $env:TMP = $setupTemp
    Write-Host '安装/校验本项目 Chromium（不使用全局浏览器缓存）……'
    & $nodeCommand.Source $cli install --no-progress chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium 安装失败；检查网络或安装器输出的系统依赖，不可当作自检通过。' }
    Write-Host '执行 Node、Schema、分类注册和浏览器启动/关闭自检……'
    $probeOutput = & $nodeCommand.Source (Join-Path $PSScriptRoot 'tooling/preflight.mjs') --browser-self-test
    if ($LASTEXITCODE -ne 0) { throw '工具自检失败；Linux 缺系统库时需管理员按 Playwright 的诊断安装，禁止跳过浏览器检查。' }
    $report = ($probeOutput -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if ($report.status -ne 'passed' -or $report.browser.status -ne 'passed') { throw '工具自检未返回有效成功状态。' }
    $outputPath = Join-Path $PSScriptRoot '.cache/tools-setup.json'
    Assert-NoLinkedAncestor $outputPath
    [System.IO.File]::WriteAllText($outputPath, ($probeOutput -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
    Write-Host "工具自检通过：Node $($report.node_version)，Chromium $($report.browser.browser_version)；结果 .cache/tools-setup.json。"
    $resultCode = 0
}
catch {
    Write-Error "工具准备失败：$($_.Exception.Message)" -ErrorAction Continue
}
finally {
    $env:PLAYWRIGHT_BROWSERS_PATH = $oldBrowserPath
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    # 只删除本脚本创建的安装临时目录，不删除工具缓存或工作区其它内容。
    if ($tempCreated -and (Test-Path -LiteralPath $setupTemp)) {
        try {
            Assert-NoLinkedAncestor $setupTemp
            $marker = Join-Path $setupTemp '.setup-owner'
            Assert-NoLinkedAncestor $marker
            if ([System.IO.File]::ReadAllText($marker) -ne $setupOwner) { throw '安装临时目录所有权不符，拒绝删除。' }
            if ((Get-ChildItem -LiteralPath $setupTemp -Recurse -Force | Where-Object {
                ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
            } | Measure-Object).Count -gt 0) { throw '安装临时目录内出现链接，拒绝递归删除。' }
            Remove-Item -LiteralPath $setupTemp -Recurse -Force
        }
        catch { Write-Warning $_.Exception.Message; $resultCode = 2 }
    }
}
exit $resultCode
