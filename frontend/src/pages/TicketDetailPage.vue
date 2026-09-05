<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useRoute } from 'vue-router'
import { getTicket } from '../api/tickets'
import { getAgentRun, getAgentSteps } from '../api/agent'
import type { AgentRunDetail, AgentStep, TicketDetail } from '../api/types'
import { displayApiError } from '../api/client'
import DecisionTag from '../components/DecisionTag.vue'
import StatusTag from '../components/StatusTag.vue'
import AgentTimeline from '../components/AgentTimeline.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate, formatLatency } from '../utils/format'
import { displayIntent, displayPriority, formatBrl } from '../utils/display'

const route = useRoute(); const detail = ref<TicketDetail | null>(null); const run = ref<AgentRunDetail | null>(null); const steps = ref<AgentStep[]>([]); const loading = ref(true); const error = ref<string | null>(null)
async function load() { loading.value = true; error.value = null; detail.value = null; run.value = null; steps.value = []; try { detail.value = await getTicket(String(route.params.ticketId)); const runId = detail.value.latest_agent_run?.run_id; if (runId) [run.value, steps.value] = await Promise.all([getAgentRun(runId), getAgentSteps(runId)]) } catch (caught) { error.value = displayApiError(caught) } finally { loading.value = false } }
onMounted(load); watch(() => route.params.ticketId, load)
</script>

<template><section><div class="page-heading"><div><router-link to="/tickets" class="back-link"><ArrowLeftOutlined /> 返回工单列表</router-link><h1>工单详情</h1><p v-if="detail" class="mono">{{ detail.ticket.ticket_id }}</p></div><a-button :loading="loading" @click="load"><ReloadOutlined /> 刷新</a-button></div>
  <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert"><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert>
  <a-spin :spinning="loading" tip="加载中..."><template v-if="detail"><div class="detail-status-bar"><div><span>问题类型</span><strong>{{ displayIntent(run?.intent || detail.ticket.category) }}</strong></div><div><span>工单状态</span><StatusTag :status="detail.ticket.status" /></div><div><span>Agent 决策</span><DecisionTag :decision="run?.decision || detail.ticket.decision" technical /></div><div><span>优先级</span><a-tag>{{ displayPriority(detail.ticket.priority) }}</a-tag></div></div>
    <div class="detail-grid"><a-card title="客户问题" class="panel-card wide-card"><blockquote class="customer-message">{{ detail.ticket.subject }}</blockquote><p class="safety-note">面向客户的内容不会展示内部风险判断原因。</p></a-card>
      <a-card title="客户信息" class="panel-card"><a-descriptions v-if="detail.customer" :column="1" size="small"><a-descriptions-item label="客户 ID"><span class="mono">{{ detail.customer.customer_id }}</span></a-descriptions-item><a-descriptions-item label="显示名称">{{ detail.customer.display_name }}</a-descriptions-item><a-descriptions-item label="所在地区">{{ detail.customer.city || '—' }}, {{ detail.customer.state || '—' }}</a-descriptions-item></a-descriptions><EmptyState v-else title="暂无客户信息" /></a-card>
      <a-card title="订单信息" class="panel-card"><a-descriptions v-if="detail.order" :column="1" size="small"><a-descriptions-item label="订单 ID"><span class="mono">{{ detail.order.order_id }}</span></a-descriptions-item><a-descriptions-item label="订单状态"><StatusTag :status="detail.order.status" kind="order" /></a-descriptions-item><a-descriptions-item label="支付金额">{{ formatBrl(detail.order.payment_total, detail.order.currency) }}</a-descriptions-item><a-descriptions-item label="预计送达时间">{{ formatDate(detail.order.estimated_delivery_at) }}</a-descriptions-item></a-descriptions><EmptyState v-else title="暂无订单信息" /></a-card>
      <a-card title="Agent 最终回复" class="panel-card wide-card"><p v-if="run?.response" class="agent-response">{{ run.response }}</p><EmptyState v-else title="暂无 Agent 回复" /><div v-if="run" class="run-meta"><span>运行 ID <strong class="mono">#{{ run.run_id }}</strong></span><span>工具调用 {{ run.tool_call_count }} 次</span><span>总延迟 {{ formatLatency(run.latency_ms) }}</span><span>{{ formatDate(run.completed_at) }}</span></div></a-card>
    </div>
    <a-card title="Agent 执行轨迹" class="panel-card trace-card"><p class="section-caption">仅展示已脱敏的运营轨迹，不会暴露完整 Prompt、凭据或政策正文。</p><AgentTimeline :steps="steps" /></a-card>
  </template></a-spin></section></template>
