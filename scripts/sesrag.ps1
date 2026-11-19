#Requires -Version 7.4
param(
    [ValidateSet('Prepare','Start','Status','Verify','Stop','Destroy','Update')]
    [string]$Action = 'Start'
)
$ErrorActionPreference = 'Stop'
# 专用依赖环境保持与监控模块一致，不读取或输出业务凭据。
$repoPath = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoPath 'docker/monitoring/.cache/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv (Join-Path $repoPath 'docker/monitoring/.cache/venv')
    if ($LASTEXITCODE -ne 0) { throw '创建部署工具环境失败' }
}
# 安装失败后留下的venv也能在下一次重试，不因python.exe存在就跳过依赖。
$lockPath = Join-Path $repoPath 'docker/monitoring/requirements-host.lock'
$stampPath = Join-Path $repoPath 'docker/monitoring/.cache/deployment-requirements.sha256'
$lockHash = (Get-FileHash -LiteralPath $lockPath -Algorithm SHA256).Hash
& $pythonPath -c 'import jsonschema' *> $null
$needsDependencies = $LASTEXITCODE -ne 0
if ($needsDependencies -or -not (Test-Path -LiteralPath $stampPath) -or (Get-Content -Raw -LiteralPath $stampPath).Trim() -ne $lockHash) {
    & $pythonPath -m pip install --require-hashes -r $lockPath
    if ($LASTEXITCODE -ne 0) { throw '安装锁定依赖失败，可修复网络后重试同一命令' }
    Set-Content -LiteralPath $stampPath -Value $lockHash -Encoding utf8
}
& $pythonPath -X utf8 (Join-Path $PSScriptRoot 'deployment/stack.py') $Action
exit $LASTEXITCODE
