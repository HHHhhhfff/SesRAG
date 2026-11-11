#requires -Version 7.4
<# TEST-003总入口；PowerShell只包装，生命周期由Python唯一实现。 #>
[CmdletBinding()]
param(
    [ValidateSet('Environment','Selected','All','Real','Cleanup')][string]$Mode = 'Environment',
    [string]$RunId,
    [string[]]$Categories,
    [ValidateRange(0,300)][int]$HoldSeconds = 0,
    [ValidateRange(1,300)][int]$StartupTimeoutSeconds = 300,
    [string]$FrozenBuild,
    [ValidateSet('Business','Acceptance')][string]$RealPlan = 'Business',
    [switch]$AllowRealRequests,
    [string]$LivePlan,
    [ValidateSet('startup','child-failure','child-timeout')][string]$EngineeringFault
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskPython = if ($IsWindows) { Join-Path $PSScriptRoot '.cache/host-python/Scripts/python.exe' } else { Join-Path $PSScriptRoot '.cache/host-python/bin/python' }
if (-not (Test-Path -LiteralPath $taskPython)) { Write-Error '尚未准备专属宿主工具环境，请先执行setup-tools.ps1。'; exit 2 }
$taskArguments = @((Join-Path $PSScriptRoot 'helpers/orchestrate.py'), '--mode', $Mode, '--hold-seconds', "$HoldSeconds", '--startup-timeout-seconds', "$StartupTimeoutSeconds")
if ($RunId) { $taskArguments += @('--run-id', $RunId) }
if ($Categories) {
    # pwsh -File不展开数组字面量；同时接受逗号列表和PowerShell内部字符串数组。
    $taskCategories = @($Categories | ForEach-Object { $_.Split(',') } | ForEach-Object { $_.Trim() })
    if ($taskCategories | Where-Object { -not $_ }) { throw 'Categories不能包含空分类。' }
    $taskArguments += '--categories'
    $taskArguments += $taskCategories
}
if ($FrozenBuild) { $taskArguments += @('--frozen-build', $FrozenBuild) }
if ($Mode -eq 'Real') { $taskArguments += @('--real-plan', $RealPlan) }
if ($AllowRealRequests) { $taskArguments += '--allow-real-requests' }
if ($LivePlan) { $taskArguments += @('--live-plan', $LivePlan) }
if ($EngineeringFault) { $taskArguments += @('--engineering-fault', $EngineeringFault) }
$env:PYTHONIOENCODING = 'utf-8'
& $taskPython @taskArguments
exit $LASTEXITCODE
