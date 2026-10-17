import { runCategory } from '../lib/category-kit.mjs';

export const coveredCases = ['OWN_001'];
await runCategory('own', async s => {
  // OWN_001：完整双owner应用及各自Worker条件尚未建立，不能通过换请求头伪造身份。
  const reason = 'O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner';
  for (const [tp, subs, expected] of [
    ['TP-TH-007', ['a_list', 'b_list'], 'Thread列表只含当前owner创建的会话'],
    ['TP-TH-008', ['detail', 'archive', 'message'], '双向跨owner Thread详情/归档/消息均404且无副作用'],
    ['TP-RUN-008', ['detail', 'events', 'cancel'], '双向跨owner Run读取/events/cancel均404且不泄露存在性、无副作用'],
    ['TP-DOC-009', ['a_list', 'b_list'], 'Document列表只含本owner文档'],
    ['TP-DOC-012', ['index'], '双向跨owner index请求404且不新建Task'],
    ['TP-RAG-002', ['a_retrieval', 'b_retrieval'], '回答检索证据仅含本owner的已索引Document'],
    ['TP-SSE-008', ['a_to_b', 'b_to_a'], '双向跨owner SSE在握手前404/RUN_NOT_FOUND且无泄漏'],
  ]) {
    for (const sub of subs) s.block('OWN_001', tp, sub, expected, reason);
  }
});
