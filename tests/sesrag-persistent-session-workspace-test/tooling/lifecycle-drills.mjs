import fs from 'node:fs';
import path from 'node:path';
import { mainRun } from './orchestrator.mjs';
import { runPath } from './resources.mjs';

// 仅为 TEST-002 环境框架演练：基础容器已健康后抛出预期故障，验证真正的 finally。
// 不注入产品错误，不编造业务用例，也不提供跳过清理/长期保留环境的开关。
if (process.argv.length !== 3 || process.argv[2] !== '--partial-deployment') {
  process.stderr.write('用法：node tooling/lifecycle-drills.mjs --partial-deployment\n');
  process.exitCode = 2;
} else {
  process.exitCode = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0, runId: null, frozenBuild: null, purgeToolCache: false }, {
    async afterBaseServices(session, project) {
      const evidence = {
        schema_version: 1, run_id: session.run_id, project,
        stage: 'after_base_services_before_migration',
        expected_failure: 'FRAMEWORK_PARTIAL_DEPLOYMENT_DRILL',
        product_acceptance: 'not_run',
      };
      fs.writeFileSync(path.join(runPath('artifacts', session.run_id), 'diagnostics/partial-deployment-drill.json'), JSON.stringify(evidence, null, 2) + '\n');
      throw new Error('FRAMEWORK_PARTIAL_DEPLOYMENT_DRILL：基础服务就绪后主动中止部署，预期环境失败且清理通过');
    },
  });
}
