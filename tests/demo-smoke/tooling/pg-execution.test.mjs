import test from 'node:test';
import assert from 'node:assert/strict';
import { parseScenarioOutput, resourceIdentity } from './pg-execution.mjs';

// 工具哨兵：失败/缺失输出不能被分类驱动误判成产品通过。
test('PG驱动拒绝非零、缺少结果及未执行断言', () => {
  assert.throws(() => parseScenarioOutput({code: 1, stdout: 'PG_SCENARIO:{"status":"passed","assertions":["a"]}'}));
  assert.throws(() => parseScenarioOutput({code: 0, stdout: ''}));
  assert.throws(() => parseScenarioOutput({code: 0, stdout: 'PG_SCENARIO:{"status":"passed","assertions":[]}'}));
  assert.throws(() => parseScenarioOutput({code: 0, stdout: 'PG_SCENARIO:{"status":"failed","assertions":["a"]}'}));
  assert.throws(() => parseScenarioOutput({code: 0, stdout: 'PG_SCENARIO:{"status":"passed","assertions":["a"]}\nPG_SCENARIO:{"status":"passed","assertions":["b"]}'}));
  assert.equal(parseScenarioOutput({code: 0, stdout: 'PG_SCENARIO:{"status":"passed","assertions":["真实断言"]}'}).status, 'passed');
});

test('资源身份必须约束到本次project/run', () => {
  const result = resourceIdentity('sesrag-demo-smoke-abcd', '20261012-abcd', '1234abcd');
  assert.equal(result.name, 'sesrag-demo-smoke-abcd-5a-1234abcd');
  assert.equal(result.labels['sesrag.smoke.run_id'], '20261012-abcd');
  assert.throws(() => resourceIdentity('development', '20261012-abcd', '1234abcd'));
  assert.throws(() => resourceIdentity('sesrag-demo-smoke-abcd', '../else', '1234abcd'));
});
