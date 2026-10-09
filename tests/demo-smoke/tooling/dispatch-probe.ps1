#Requires -Version 7.4
param(
    [string]$BaseUrl, [string]$FrontendUrl, [string]$RunId,
    [string]$ArtifactDir, [string]$RuntimeDir, [string]$FixtureDir
)
# 任务2的调用协议哨兵；不请求API、不写分类报告，不是产品测试脚本。
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
[ordered]@{
    BaseUrl=$BaseUrl; FrontendUrl=$FrontendUrl; RunId=$RunId
    ArtifactDir=$ArtifactDir; RuntimeDir=$RuntimeDir; FixtureDir=$FixtureDir
    message='六参数中文调用成功'
} | ConvertTo-Json -Compress
