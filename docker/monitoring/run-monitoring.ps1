param(
    [Parameter(Mandatory)][ValidateSet('Prepare','RefreshBinding','Pull','Validate','Start','Status','Verify','Stop','Destroy','Backup','Restore')][string]$Action,
    [string]$EnvironmentId = 'local', [string]$ApplicationContract,
    [ValidateRange(1024,65535)][int]$GrafanaPort = 3000,
    [switch]$HostOtlp, [switch]$EraseMonitoringData, [string]$BackupId
)
$ErrorActionPreference = 'Stop'
# 只使用模块专属工具环境，不改系统Python或项目venv。
$pythonPath = Join-Path $PSScriptRoot '.cache/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先按模块README准备.cache/venv及hash锁定依赖。' }
$arguments = @('-X', 'utf8', (Join-Path $PSScriptRoot 'helpers/cli.py'), $Action, '--environment', $EnvironmentId, '--grafana-port', $GrafanaPort)
if ($ApplicationContract) { $arguments += @('--application-contract', (Resolve-Path -LiteralPath $ApplicationContract).Path) }
if ($HostOtlp) { $arguments += '--host-otlp' }
if ($EraseMonitoringData) { $arguments += '--erase-monitoring-data' }
if ($BackupId) { $arguments += @('--backup-id', $BackupId) }
& $pythonPath @arguments
exit $LASTEXITCODE
