import { probe } from './life-probe-core.mjs';
// LIFE_004：运行器须超时终止该哨兵及其自有子进程树。
await probe('timeout');
