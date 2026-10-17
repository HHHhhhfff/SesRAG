import fs from 'node:fs'
import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

// 固定测试编排故障，仅测试runner可选；生产Compose与API不增加控制入口。
export const deploymentScenarios = ['compose-config-failure', 'migration-failure', 'redis-cold', 'redis-strict', 'real-db-probe-failure', 'worker-readiness-timeout', 'frontend-readiness-timeout', 'cleanup-failure', 'cleanup-share-read', 'hard-kill-recovery']
export function harnessOverride(scenario) {
  assert.ok(deploymentScenarios.includes(scenario))
  if (scenario === 'compose-config-failure') return 'services: [invalid-compose-object]'
  const services = {}
  if (scenario === 'migration-failure') services.migrate = { command: ['python', '-c', 'raise SystemExit(42)'] }
  if (['redis-cold','redis-strict'].includes(scenario)) services.redis = { command: ['sh', '-c', 'sleep 300'], healthcheck: { test: ['CMD', 'redis-cli', 'ping'], interval: '1s', timeout: '1s', retries: 1 } }
  if (scenario === 'worker-readiness-timeout') services.worker = { command: ['python', '-c', 'import time;time.sleep(300)'] }
  if (scenario === 'frontend-readiness-timeout') services.frontend = { command: ['node', '-e', 'setTimeout(()=>{},300000)'] }
  return JSON.stringify({ services })
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) fs.writeFileSync(process.argv[3], harnessOverride(process.argv[2]))
