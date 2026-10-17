import { allComponentChecks } from '../specific_test_script/fe-component-checks.mjs'
import { persistentChecks } from './frontend-persistent.mjs'

// QLT_007交接：旧19浏览器目标、原两个恢复目标和9个持久目标都必须逐ID存在并通过。
export const legacyBrowserCheckIds = [
  'FE_001__TP-FE-001__browser-http-upload-sse',
  'FE_001__TP-FE-002__browser-create-select',
  'FE_002__TP-FE-003__browser-no-thread',
  'FE_002__TP-FE-003__browser-empty-input',
  'FE_002__TP-FE-003__browser-button',
  'FE_002__TP-FE-003__browser-ctrl-enter',
  'FE_004__TP-FE-005__browser-no-refresh',
  'FE_006__TP-FE-007__browser-request-failure',
  'FE_007__TP-FE-008__browser-normal-timeline',
  'FE_009__TP-FE-010__browser-disconnect-no-cancel',
  'FE_009__TP-FE-010__browser-reconnect-entry',
  'FE_011__TP-FE-012__browser-terminal-restore',
  'FE_012__TP-FE-013__browser-indexed-initial',
  'FE_012__TP-FE-013__browser-indexed-automatic-terminal',
  'FE_012__TP-FE-013__browser-failed-initial',
  'FE_012__TP-FE-013__browser-failed-automatic-terminal',
  'FE_013__TP-FE-014__browser-citation-label',
  'FE_013__TP-FE-014__browser-citation-expand',
  'FE_014__TP-FE-016__browser-health-panels',
]
export const requiredBrowserCheckIds = [...legacyBrowserCheckIds,
  'FE_010__TP-FE-011__fresh-context', 'FE_010__TP-FE-018__frontend-restart',
  ...persistentChecks.map(row => row.slice(0, 3).join('__'))]
export const requiredComponentCheckIds = allComponentChecks.map(row => row.slice(0, 3).join('__'))
