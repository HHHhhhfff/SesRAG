import { assert } from '../lib/category-kit.mjs';
import { pgScenario } from '../tooling/pg-execution.mjs';

// 每条原blocked子目标绑定真实场景中的独立断言；同分类只运行一次共享场景。
export const executionRows = [
 ['MSG_006','TP-MSG-006','first_query_barrier','idempotency','锁'],
 ['MSG_007','TP-MSG-009','full-scenario','reentry','succeeded重复'],
 ['MSG_008','TP-MSG-010','full-scenario','message-sequence','共享seq'],
 ['RUN_002','TP-RUN-002','first_flush_failure','creation-flush','整组回滚'],
 ['RUN_002','TP-RUN-002','event_commit_failure','creation-commit','整组回滚'],
 ['RUN_003','TP-RUN-003','non_mock_model_snapshot','snapshot','快照冻结'],
 ['RUN_003','TP-RUN-004','changed_worker_configuration','snapshot','实际检索|HTTP请求'],
 ['RUN_004','TP-RUN-005','running','state-running','running正式API'],
 ['RUN_004','TP-RUN-005','retry_waiting','state-retry','retry_waiting正式API'],
 ['RUN_004','TP-RUN-005','failed','state-failed','failed正式API'],
 ['RUN_005','TP-RUN-006','final_commit_failure','final-rollback','final'],
 ['RUN_006','TP-RUN-007','full-scenario','reentry','重复handler'],
 ['WK_001','TP-WK-002','time-and-state-boundaries','queue-boundaries','拒绝|不被|不能|领取'],
 ['WK_002','TP-WK-004','full-scenario','dual-worker','SKIP LOCKED|竞争'],
 ['WK_004','TP-WK-006','full-scenario','long-lease','续租|有效|接管'],
 ['WK_005','TP-WK-007','full-scenario','lease-identity','错误task|非active'],
 ['WK_005','TP-WK-008','full-scenario','lease-identity','已过期'],
 ['WK_006','TP-WK-009','full-scenario','crash-recovery','TTL内|回收|第二代|重复'],
 ['WK_007','TP-WK-010','full-scenario','stale-generation','旧generation|旧写回'],
 ['WK_007','TP-WK-030','full-scenario','lost-lease','安全可关联拒绝'],
 ['WK_008','TP-WK-011','full-scenario','crash-exhausted','上限|同步失败|不再领取'],
 ['WK_009','TP-WK-012','full-scenario','commit-condition','旧SELECT'],
 ['WK_009','TP-WK-012','locked-select-commit','locked-write-boundaries','条件SELECT|旧commit'],
 ['WK_010','TP-WK-013','full-scenario','stale-generation','迟到retrieval'],
 ['WK_010','TP-WK-013','late-handler','lost-lease','新generation接管后'],
 ['WK_010','TP-WK-013','late-delta','late-delta','新generation接管后|第二片确实'],
 ['WK_011','TP-WK-014','full-scenario','late-error','异常确实|新generation接管后'],
 ['WK_012','TP-WK-015','full-scenario','lost-lease','昂贵步骤|拒绝日志'],
 ['WK_012','TP-WK-015','heartbeat-false','heartbeat-rejection','heartbeat|LEASE_LOST'],
 ['WK_013','TP-WK-016','persisted-availability','retry-exhausted','持久退避|之前不执行'],
 ['WK_014','TP-WK-017','full-scenario','retry-success','retry_waiting|最终succeeded'],
 ['WK_014','TP-WK-018','full-scenario','retry-success','身份|用户Message'],
 ['WK_015','TP-WK-019','full-scenario','retry-exhausted','最终failed|次数|结算一致'],
 ['WK_017','TP-WK-021','full-scenario','deadline-running','截止|deadline后'],
 ['WK_018','TP-WK-022','full-scenario','deadline-retry','截止|复活'],
 ['WK_019','TP-WK-023','full-scenario','signal-within','B保持queued|B仍queued|新Worker'],
 ['WK_020','TP-WK-024','full-scenario','signal-within','续租|原子成功|exit0'],
 ['WK_021','TP-WK-025','full-scenario','signal-outside','exit0|无迟到续租|释放|恢复'],
 ['WK_021','TP-WK-025','pg-lock-main-sigterm','signal-locks','锁等待|锁已释放'],
 ['WK_021','TP-WK-025','production-provider-sigterm','signal-production-provider','生产Provider|httpx|release|迟到'],
 ['WK_023','TP-WK-028','db-recovery','database-recovery','真实命中|退避|同进程'],
 ['WK_024','TP-WK-029','all-actions','action-logs','动作日志|关联task'],
 ['WK_025','TP-WK-031','full-scenario','expired-final','到期|租约'],
 ['CAN_001','TP-CAN-002','failed_repeat','reentry','failed重复'],
 ['CAN_002','TP-CAN-003','full-scenario','cancel-embed','search及模型'],
 ['CAN_003','TP-CAN-004','full-scenario','cancel-search','模型调用为零'],
 ['CAN_004','TP-CAN-005','full-scenario','cancel-delta','第一片|迟到delta|assistant'],
 ['CAN_005','TP-CAN-006','cancel_commits_first','cancel-first','唯一|一个终态|assistant'],
 ['CAN_005','TP-CAN-006','success_commits_first','success-first','唯一|一个终态|assistant'],
 ['CAN_006','TP-CAN-007','full-scenario','cancel-retry','复活'],
 ['EVT_002','TP-EVT-002','two_connection_append','journal','两连接竞争'],
 ['EVT_002','TP-EVT-002','rollback_then_append','journal','回滚Event'],
 ['SSE_002','TP-SSE-002','read_append_boundary','sse-boundary','三段完整|边界序列'],
 ['SSE_003','TP-SSE-004','disconnect_after_first_delta_running','sse-disconnect','socket|断流|补放'],
 ['SSE_004','TP-SSE-006','failed','sse-failed','正常EOF'],
 ['HLT_004','TP-HLT-004','full-scenario','readiness','readiness|Task lease'],
];
for (const [id,tp] of [['RUN_005','TP-RUN-006'],['WK_009','TP-WK-012'],['WK_025','TP-WK-031']]) {
  for (const stage of ['assistant','terminal']) for (const expiry of ['lease','deadline'])
    executionRows.push([id,tp,`final-${stage}-${expiry}`,'final-publication',`${stage}/${expiry}最终flush`]);
  executionRows.push([id,tp,'final-authorization-boundary','final-publication','最终授权边界']);
}
// 同一事实屏障分别归属Worker授权和Run/Event原子性；QLT读取本集合逐ID必测。
for (const [id,tp,group,match] of [
  ['WK_009','TP-WK-012','queue','末flush'],
  ['WK_009','TP-WK-012','failure','末flush'],
  ['WK_009','TP-WK-012','events','末flush'],
  ['WK_017','TP-WK-021','failure','scheduler'],
  ['RUN_005','TP-RUN-006','events','started|retrieval|delta'],
  ['EVT_002','TP-EVT-002','events','retrieval|delta'],
]) executionRows.push([id,tp,`last-flush-${group}`,`flush-${group}`,match]);

export async function executionCoverage(suite, onlySub) {
  const cache = new Map();
  const selected = executionRows.filter(row => row[0].split('_')[0].toLowerCase() === suite.name && (!onlySub || onlySub.split(',').includes(row[2])));
  assert.ok(selected.length, '专项筛选未命中任何check');
  for (const [id,tp,sub,scenario,match] of selected) {
    await suite.check(id,tp,sub,suite.cases.get(id).expected,async () => {
      if (!cache.has(scenario)) cache.set(scenario, pgScenario(suite.ctx, scenario));
      const report = await cache.get(scenario);
      suite.ctx.evidencePaths.push(...report.evidence);
      const assertions = report.assertions.filter(value => new RegExp(match).test(value));
      assert.ok(assertions.length, `${id}/${tp}真实目标断言未执行`);
      // 原始场景事实已完成独立assert；此处按TP呈现对应断言，而非复制总passed。
      return {scenario, database: report.database, assertions};
    });
  }
}
