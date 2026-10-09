#Requires -Version 7.4
param([Parameter(Mandatory)][string]$SandboxRoot)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Console]::OutputEncoding
$ErrorActionPreference='Stop'
. "$PSScriptRoot/../lib/smoke-common.ps1"

# LIFE_009：只在本run fixture兄弟目录准备随机sandbox，危险输入只解析/拒绝，不删除仓库根。
$resolved = [IO.Path]::GetFullPath($SandboxRoot)
if ($resolved -notmatch '[\\/]tests[\\/]demo-smoke[\\/]tmp[\\/][a-z0-9-]+$') { throw 'LIFE_009 sandbox父目录必须是本次tmp run目录' }
$sandbox=Join-Path $resolved ('life-path-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sandbox | Out-Null
$results=@()
$junction=''
try {
    $child=Get-SmokeChildPath $sandbox 'safe-run'
    New-Item -ItemType Directory -Path $child | Out-Null
    Remove-SmokeChild $sandbox 'safe-run'
    $results+=@{sub='exact_child';passed=(-not (Test-Path -LiteralPath $child))}
    foreach ($inputName in @('.', '..', '../outside', 'C:\', '/', 'safe-run/child', '')) {
        $rejected=$false
        try { Get-SmokeChildPath $sandbox $inputName | Out-Null } catch { $rejected=$true }
        $results+=@{sub=('dangerous_'+$results.Count);passed=$rejected}
    }
    $outside=Join-Path $sandbox 'outside-owned'
    New-Item -ItemType Directory -Path $outside | Out-Null
    $junction=Join-Path $sandbox 'linked-run'
    New-Item -ItemType Junction -Path $junction -Target $outside | Out-Null
    $rejected=$false
    try { Remove-SmokeChild $sandbox 'linked-run' } catch { $rejected=$true }
    $results+=@{sub='reparse_target';passed=$rejected}
    Remove-Item -LiteralPath $junction -Force
    $junction=''
    $parent=Join-Path $sandbox 'nested-run'
    New-Item -ItemType Directory -Path $parent | Out-Null
    $junction=Join-Path $parent 'linked-child'
    New-Item -ItemType Junction -Path $junction -Target $outside | Out-Null
    $rejected=$false
    try { Remove-SmokeChild $sandbox 'nested-run' } catch { $rejected=$true }
    $results+=@{sub='reparse_descendant';passed=$rejected}
    Remove-Item -LiteralPath $junction -Force
    $junction=''
    $results+=@{sub='outside_preserved';passed=(Test-Path -LiteralPath $outside)}
    Write-Output ('SMOKE_JSON:'+(@{checks=$results}|ConvertTo-Json -Compress -Depth 8))
} finally {
    if ($junction -and (Test-Path -LiteralPath $junction)) { Remove-Item -LiteralPath $junction -Force }
    # LIFE_009：唯一刚创建sandbox，绝对父目录已核对，junction先移除后才允许递归清理。
    if ((Split-Path ([IO.Path]::GetFullPath($sandbox)) -Parent) -ne $resolved) { throw 'LIFE_009 清理越界' }
    if (@(Get-ChildItem -LiteralPath $sandbox -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'LIFE_009 sandbox仍有链接，拒绝递归删除' }
    Remove-Item -LiteralPath $sandbox -Recurse -Force
}
