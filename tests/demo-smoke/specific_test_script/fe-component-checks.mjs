// FE 组件子项唯一清单：标题同时用于 Vitest 与分类报告，不以进程退出码代替逐项结果。
export const componentChecks = [
  ['FE_003', 'TP-FE-004', 'component-partial-answer', '无最终assistant时，首delta立即显示临时回答且不改持久事实'],
  ['FE_004', 'TP-FE-005', 'component-terminal-refresh', '终态后无需刷新自动读取最终Message与引用，恰一个assistant'],
  ['FE_005', 'TP-FE-006', 'component-running', 'run.started后从接口事实更新为running'],
  ['FE_005', 'TP-FE-006', 'component-succeeded', 'run.succeeded后显示succeeded并移除停止按钮'],
  ['FE_005', 'TP-FE-015', 'component-cancel', '停止调用当前run_id，cancelled后移除按钮并保持终态'],
  ['FE_006', 'TP-FE-007', 'component-async-failure', '异步failed及稳定原因可见，不能一直running'],
  ['FE_006', 'TP-FE-007', 'component-failure-reason', '已读取failed事实时也展示稳定last_error_code原因'],
  ['FE_007', 'TP-FE-008', 'component-seq-order', '真实store和时间线对3/1/2/2显示1/2/3且seq2仅一次'],
  ['FE_007', 'TP-FE-008', 'component-run-scope', 'observe另一个Run后另Run的seq1仍保留'],
  ['FE_008', 'TP-FE-009', 'component-replay-stream-overlap', 'replay与SSE同时交付同seq增量，正文只追加一次'],
  ['FE_008', 'TP-FE-009', 'component-stream-after-replay', 'replay先到达而SSE随后交付同seq增量，正文只追加一次'],
  ['FE_008', 'TP-FE-009', 'component-final-history', '读取最终Message后重放历史delta，最终正文不追加或翻倍'],
  ['FE_009', 'TP-FE-010', 'component-reconnect-cursor', '断线后存在自动或明确重连，从最后处理seq补放且无重复'],
  ['FE_009', 'TP-FE-010', 'component-disconnect-no-cancel', 'SSE断线关闭观察而不发送取消请求'],
  ['FE_011', 'TP-FE-012', 'component-active-restore', '重新挂载并选择活动会话后恢复Run与事件并继续订阅'],
  ['FE_015', 'TP-FE-017', 'component-switch-isolation', '切换Thread关闭旧流，B不显示A的Run或迟到正文，切回读取A事实'],
  ['FE_015', 'TP-FE-017', 'component-switch-back-history', 'A终态持久事实形成后从B切回A，准确读取最终Message'],
]

export const componentTitle = ([id, point, sub]) => `${id}__${point}__${sub}`
