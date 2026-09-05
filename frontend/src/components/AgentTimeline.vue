<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons-vue'
import type { AgentStep } from '../api/types'
import StatusTag from './StatusTag.vue'
import EmptyState from './EmptyState.vue'
import { displayTraceName } from '../utils/display'

const props = defineProps<{ steps: AgentStep[]; live?: boolean }>()
const ordered = computed(() => [...props.steps].sort((a, b) => a.sequence - b.sequence))
function iconFor(status: string) {
  if (status === 'FAILED') return CloseCircleOutlined
  if (status === 'RUNNING') return ClockCircleOutlined
  return CheckCircleOutlined
}
</script>

<template>
  <div v-if="ordered.length" class="agent-timeline" data-testid="agent-timeline">
    <a-timeline>
      <a-timeline-item v-for="step in ordered" :key="`${step.sequence}-${step.node}-${step.tool}`" :color="step.status === 'FAILED' ? 'red' : step.status === 'RUNNING' ? 'blue' : 'green'">
        <template #dot><component :is="iconFor(step.status)" /></template>
        <div class="timeline-heading">
          <span class="step-number">{{ String(step.sequence).padStart(2, '0') }}</span>
          <strong>{{ displayTraceName(step.tool || step.action || step.node) }}</strong>
          <StatusTag :status="step.status" kind="execution" />
          <span class="latency">延迟 {{ step.latency_ms.toFixed(1) }} ms</span>
        </div>
        <div class="timeline-node">{{ step.node }}<span v-if="step.action"> · {{ step.action }}</span></div>
        <a-alert v-if="step.error_code" type="warning" :message="`错误码：${step.error_code}`" show-icon class="timeline-alert" />
        <a-collapse v-if="step.input_summary || step.output_summary" ghost size="small">
          <a-collapse-panel key="summary" header="执行详情（已脱敏）">
            <p v-if="step.input_summary">{{ step.input_summary }}</p>
            <p v-if="step.output_summary">{{ step.output_summary }}</p>
          </a-collapse-panel>
        </a-collapse>
      </a-timeline-item>
    </a-timeline>
  </div>
  <EmptyState v-else title="暂无执行步骤" description="运行 Agent 后可查看受控工作流轨迹。" />
</template>
