#requires -Version 7.4
<# 宿主仅需要Python辅助依赖；浏览器/Node在独立tools镜像锁定并准备。 #>
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskBootstrap = if ($IsWindows) { Join-Path $taskRoot '.venv/Scripts/python.exe' } else { Join-Path $taskRoot '.venv/bin/python' }
if (-not (Test-Path -LiteralPath $taskBootstrap)) { $taskBootstrap = (Get-Command python3,python -ErrorAction SilentlyContinue | Select-Object -First 1).Source }
if (-not $taskBootstrap) { throw '请先安装Python 3.11+，Docker Linux Engine与Compose 2.24.4+；本脚本不提升权限安装系统工具。' }
& $taskBootstrap -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$taskEnvironment = Join-Path $PSScriptRoot '.cache/host-python'
$taskPython = if ($IsWindows) { Join-Path $taskEnvironment 'Scripts/python.exe' } else { Join-Path $taskEnvironment 'bin/python' }
if (-not (Test-Path -LiteralPath $taskPython)) {
    & $taskBootstrap -m venv $taskEnvironment
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $taskPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-test.lock')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host '专属.cache虚拟环境已准备，未修改项目依赖。Environment将构建tools并验证Chromium/离线词表；尚未执行产品测试。'
