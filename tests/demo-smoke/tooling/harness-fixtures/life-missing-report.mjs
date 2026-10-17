import { probe } from './life-probe-core.mjs';
// LIFE_004：退出0但不提供报告，不能通过。
await probe('missing-report');
