import { apiFetch } from './http'
import type { HealthReady } from '../types/api'

export function getHealth() {
  // readiness的503也是依赖事实，不能被一般HTTP异常分支丢弃。
  return apiFetch<HealthReady>('/health/ready', undefined, [503])
}
