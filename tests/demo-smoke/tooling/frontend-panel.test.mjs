import assert from 'node:assert/strict'
import { test } from 'node:test'
import { assertThreadRunPanel } from './frontend-persistent.mjs'

// FE_015 I1负哨兵：只改变内存观测，不注入产品状态/事件/HTTP。
const expected = { run_id: 'B', status: 'cancelled', events: [
  { run_id: 'B', seq: 1, type: 'run.created' }, { run_id: 'B', seq: 2, type: 'run.cancelled' },
] }
const valid = () => ({ ...structuredClone(expected), visible_status: 'cancelled', visible_events: expected.events.map(({ seq, type }) => ({ seq, type })) })

test('FE015正确B cancelled及完整Journal观测通过', () => assertThreadRunPanel(valid(), expected))
test('FE015 A面板身份即使状态和seq相同也被拒绝', () => {
  assert.throws(() => assertThreadRunPanel({ ...valid(), run_id: 'A' }, expected), /Run身份/)
})
test('FE015 A running或succeeded可见状态混入均被拒绝', () => {
  for (const status of ['running', 'succeeded']) assert.throws(() => assertThreadRunPanel({ ...valid(), visible_status: status }, expected), /可见状态/)
})
test('FE015 A同seq事件身份或时间线类型混入均被拒绝', () => {
  const foreign = valid(); foreign.events[0].run_id = 'A'
  assert.throws(() => assertThreadRunPanel(foreign, expected), /事件身份/)
  const timeline = valid(); timeline.visible_events[1].type = 'run.succeeded'
  assert.throws(() => assertThreadRunPanel(timeline, expected), /可见时间线/)
})
