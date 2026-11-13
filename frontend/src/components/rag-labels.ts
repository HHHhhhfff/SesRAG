// 仅负责持久状态的中文投影，不据显示文本推断终态。
const labels: Record<string, string> = {
  queued: '排队中', building: '构建中', running: '处理中', waiting: '等待外部结果',
  succeeded: '已完成', failed: '失败', cancelled: '已取消', interrupted: '执行已中断',
  preparing: '准备中', submitting: '申请云端作业', uploading: '上传原件',
  remote_waiting: '云端排队', remote_running: '云端解析', remote_converting: '云端转换',
  downloading: '下载结果', local_parsing: '本地结构解析', parse: '解析文档',
  chunk: '切分文本', embedding: '计算向量', publish: '发布候选', completed: '已完成',
  query_embedding: '计算查询向量', dense: '向量召回', rerank: '候选重排',
  dense_search: '向量召回', enhancement: '拼接来源证据',
  stopped: '本地已停止', submission_unknown: '云端受理结果未知',
  ready: '当前批次可检索', reindex_required: '需要重新索引', none: '尚无可用批次',
  ok: '检索成功', empty: '无可用证据', degraded: '已明确降级',
}
export function ragLabel(value: string): string { return labels[value] ?? value }
