#Requires -Version 7.4
<#
唯一公开生命周期入口；Node 工具负责账本、分类协议、报告和有界清理。
不读取根 .env，不拼接 shell 命令；所有参数以独立 argv 传递。
#>
[CmdletBinding()]
param(
    [ValidateSet('Environment', 'Selected', 'All', 'Cleanup')]
    [string]$Mode = 'Environment',
    [string]$Categories,
    [string]$RunId,
    [int]$HoldSeconds = 0,
    [string]$FrozenBuild,
    [switch]$PurgeToolCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
try {
    $nodeCommand = Get-Command node -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $entryFile = Join-Path $PSScriptRoot 'tooling/orchestrator.mjs'
    $nodeArgs = @($entryFile, '--mode', $Mode)
    if ($PSBoundParameters.ContainsKey('Categories')) { $nodeArgs += @('--categories', $Categories) }
    if ($PSBoundParameters.ContainsKey('RunId')) { $nodeArgs += @('--run-id', $RunId) }
    if ($PSBoundParameters.ContainsKey('HoldSeconds')) { $nodeArgs += @('--hold-seconds', [string]$HoldSeconds) }
    if ($PSBoundParameters.ContainsKey('FrozenBuild')) { $nodeArgs += @('--frozen-build', $FrozenBuild) }
    if ($PurgeToolCache) { $nodeArgs += '--purge-tool-cache' }
    & $nodeCommand.Source @nodeArgs
    exit $LASTEXITCODE
}
catch {
    Write-Error "无法调用测试入口：$($_.Exception.Message)" -ErrorAction Continue
    exit 2
}
