// FE 组件子项唯一清单：标题同时用于 Vitest 与分类报告，不以进程退出码代替逐项结果。
export const componentChecks = [
  ['FE_003', 'TP-FE-004', 'component-partial-answer', '无最终assistant时，首delta立即显示临时回答且不改持久事实'],
  ['FE_004', 'TP-FE-005', 'component-terminal-refresh', '终态后无需刷新自动读取最终Message与引用，恰一个assistant'],
  ['FE_005', 'TP-FE-006', 'component-running', 'run.started后从接口事实更新为running'],
  ['FE_005', 'TP-FE-006', 'component-succeeded', 'run.succeeded后显示succeeded并移除停止按钮'],
  ['FE_005', 'TP-FE-015', 'component-cancel', '停止调用当前run_id，cancelled后移除按钮并保持终态'],
  ['FE_006', 'TP-FE-007', 'component-async-failure', '异步failed及稳定原因可见，不能一直running'],
  ['FE_006', 'TP-FE-007', 'component-failure-reason', '已读取failed事实时也展示稳定last_error_code原因'],
  ['FE_006', 'TP-FE-007', 'component-retry-history', '成功重试保留历史错误但不宣称当前失败，等待重试和failed语义明确'],
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

// Task4新增18项逐一映射；保留原17项标题及定义，不能以Vitest退出0冒充完整收集。
export const additionalComponentChecks = [
  ['FE_014', 'TP-FE-016', 'component-health-dependencies', '健康503显示PG不可用、Redis降级和Worker未知'],
  ['FE_014', 'TP-FE-016', 'component-health-network', '健康网络失败不固定绿灯'],
  ['FE_015', 'TP-FE-017', 'component-late-thread-http', '切Thread丢弃迟到详情HTTP'],
  ['FE_015', 'TP-FE-017', 'component-queued-old-callback', '切Thread后已排队的旧SSE回调不污染新会话'],
  ['FE_013', 'TP-FE-014', 'component-citation-location-safety', '引用展开显示真实批次和基础位置且Markdown保持安全'],
  ['FE_012', 'TP-FE-013', 'component-document-failure-poll', 'Document非终态刷新到失败展示错误并停止轮询'],
  ['FE_012', 'TP-FE-013', 'component-document-bounded-poll', 'Document长期非终态自动刷新有上限并可手动恢复'],
  ['FE_005', 'TP-FE-006', 'component-terminal-fact-authority', 'terminal事件仅触发GET不本地宣布终态'],
  ['FE_007', 'TP-FE-008', 'component-terminal-journal-suffix', 'message.completed触发终态GET后补齐未送达的terminal Journal'],
  ['FE_007', 'TP-FE-008', 'component-delta-order-scope', '乱序增量按seq投影且外来Run同seq不污染'],
  ['FE_009', 'TP-FE-010', 'component-bounded-reconnect-cleanup', '连续断线自动重连有界且卸载清理timer和stream'],
  ['FE_012', 'TP-FE-013', 'component-upload-error-safety', '上传失败展示服务端稳定错误码且不回显路径'],
  ['FE_015', 'TP-FE-017', 'component-late-run-get', '切Run丢弃旧GET返回且旧连接关闭'],
  ['FE_014', 'TP-FE-016', 'component-unmount-late-http', '卸载使迟到健康Document HTTP失效并停止刷新'],
  ['FE_008', 'TP-FE-009', 'component-retry-live-draft', 'I1 实时重试不拼接不同attempt草稿'],
  ['FE_008', 'TP-FE-009', 'component-retry-replay-draft', 'I1 刷新replay只投影最新attempt草稿并保留完整Journal'],
  ['FE_005', 'TP-FE-015', 'component-old-cancel-new-terminal', 'I2 旧cancel返回不能使新Run终态GET和最终Message失效'],
  ['FE_015', 'TP-FE-017', 'component-submission-response-order', 'I3 同Thread连续提交A B反序响应保持B观察权和事实历史'],
]

export const allComponentChecks = [...componentChecks.map(row => [...row, componentTitle(row)]), ...additionalComponentChecks.map(row => [...row, row[3]])]
