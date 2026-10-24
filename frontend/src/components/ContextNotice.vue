<script setup lang="ts">
import type { ContextPlan, ContextPlanSummary } from '../types/api-v2'
defineProps<{ plan: ContextPlanSummary | null; detail?: ContextPlan | null }>()
</script>
<template>
  <p
    v-if="plan"
    class="context-notice"
    role="status"
  >
    上下文：{{ plan.status === 'budget_exceeded' ? '预算超限' : '已规划' }} · {{ plan.estimated_input_tokens }}/{{ plan.context_window_tokens }} tokens · 保留输出 {{ plan.reserved_output_tokens }} · 裁剪 {{ plan.omitted_message_count }} 条 · 摘要 {{ plan.summary_count }} 条
  </p>
  <div
    v-if="detail"
    class="context-detail"
  >
    <p>策略 {{ detail.trim_policy_version }} · 计数 {{ detail.counter_version }} · 安全余量 {{ detail.safety_margin_tokens }}</p>
    <p
      v-for="(range, index) in detail.omitted_ranges"
      :key="index"
    >
      消息 {{ range.from_seq }}–{{ range.to_seq }} · {{ range.count }} 条 · {{ range.reason }}
    </p>
    <p
      v-for="summary in detail.summaries"
      :key="summary.summary_id"
    >
      摘要范围 {{ summary.from_seq }}–{{ summary.to_seq }} · {{ summary.summary_policy_version }}
    </p>
  </div>
</template>
