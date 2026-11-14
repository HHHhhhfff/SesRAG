# PRD-004主入口：Python持有资源账本和finally清理，PS仅转发参数。
param(
    [ValidateSet('Environment','Http','Metrics','Trace','Recovery','Security','Budget','Handoff','All')]
    [string]$Group = 'All',
    [string]$RunId,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw '请先准备项目Python3.12虚拟环境和dev依赖。' }
$runnerArguments = @((Join-Path $PSScriptRoot 'tooling\runner.py'), '--group', $Group)
if ($RunId) { $runnerArguments += @('--run-id', $RunId) }
if ($SkipBuild) { $runnerArguments += '--skip-build' }
& $projectPython @runnerArguments
exit $LASTEXITCODE
