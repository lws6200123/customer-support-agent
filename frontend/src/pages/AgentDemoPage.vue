<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useAgentStream } from '../composables/useAgentStream'
import { getAgentRun } from '../api/agent'
import type { AgentRunDetail, AgentStep, SSEEvent } from '../api/types'
import AgentTimeline from '../components/AgentTimeline.vue'
import DecisionTag from '../components/DecisionTag.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatLatency } from '../utils/format'
import { displayIntent } from '../utils/display'

const examples = [
  { name: '查询物流状态', customerId: 'CUST-001716', orderId: 'ORD-000009', message: '请帮我查询订单 ORD-000009 的物流配送状态。' },
  { name: '申请退货', customerId: 'CUST-001716', orderId: 'ORD-000009', message: '我想为订单 ORD-000009 申请无理由退货。商品未使用、配件完整且状态良好，申请金额为 20 BRL。' },
  { name: '需要人工审核', customerId: 'CUST-000364', orderId: 'ORD-000351', message: '请处理订单 ORD-000351 的无理由退货。商品未使用且配件完整，申请金额为 20 BRL。' },
  { name: '缺少订单 ID', customerId: '', orderId: '', message: '我的包裹迟迟没有送达，但我找不到订单 ID。' },
]
const form = reactive({ customerId: '', orderId: '', message: '' }); const validationError = ref<string | null>(null); const result = ref<AgentRunDetail | null>(null)
const { events, isRunning, error, run, cancel } = useAgentStream()
function useExample(example: typeof examples[number]) { form.customerId = example.customerId; form.orderId = example.orderId; form.message = example.message; validationError.value = null; result.value = null }
function eventStatus(event: SSEEvent) { return event.event === 'error' || event.tool_ok === false ? 'FAILED' : event.event.endsWith('started') ? 'RUNNING' : 'SUCCESS' }
const liveSteps = computed<AgentStep[]>(() => events.value.map((event, index) => ({ sequence: index + 1, node: event.event, action: event.intent || event.decision, tool: event.tool, status: eventStatus(event), latency_ms: 0, input_summary: null, output_summary: event.response || event.detail, error_code: event.event === 'error' ? 'STREAM_ERROR' : null, created_at: event.timestamp })))
const latestDecision = computed(() => [...events.value].reverse().find((item) => item.decision)?.decision || result.value?.decision)
const latestResponse = computed(() => [...events.value].reverse().find((item) => item.response)?.response || result.value?.response)
async function submit() { if (!form.message.trim()) { validationError.value = '请输入客户问题后再运行 Agent。'; return } validationError.value = null; result.value = null; const completed = await run({ message: form.message.trim(), customer_id: form.customerId.trim() || undefined, order_id: form.orderId.trim() || undefined }); const runId = [...completed].reverse().find((item) => item.run_id)?.run_id; if (runId) try { result.value = await getAgentRun(runId) } catch { /* timeline still provides the safe terminal state */ } }
function reset() { events.value = []; result.value = null; validationError.value = null }
</script>

<template><section><div class="page-heading"><div><p class="eyebrow">实时工作流演示</p><h1>智能客服 Agent 演示</h1><p>通过 FastAPI → LangGraph → Tools → SQLite / RAGFlow 发送真实请求。</p></div><a-tag color="blue">真实 Stage 6 API</a-tag></div>
  <div class="demo-grid"><a-card title="请求信息" class="panel-card demo-form-card"><a-form layout="vertical" @submit.prevent="submit"><div class="form-grid"><a-form-item label="客户 ID（选填）"><a-input v-model:value="form.customerId" placeholder="CUST-001716" :disabled="isRunning" /></a-form-item><a-form-item label="订单 ID（选填）"><a-input v-model:value="form.orderId" placeholder="ORD-000009" :disabled="isRunning" /></a-form-item></div><a-form-item label="客户问题" required><a-textarea v-model:value="form.message" :rows="6" :maxlength="8000" show-count placeholder="请描述需要处理的客服问题…" :disabled="isRunning" /><div v-if="validationError" class="field-error" role="alert">{{ validationError }}</div></a-form-item><div class="demo-actions"><a-button type="primary" html-type="submit" size="large" :loading="isRunning" :disabled="isRunning"><PlayCircleOutlined /> {{ isRunning ? 'Agent 运行中…' : '开始运行 Agent' }}</a-button><a-button v-if="isRunning" danger @click="cancel">取消</a-button><a-button v-if="!isRunning && events.length" @click="reset"><ReloadOutlined /> 重置</a-button></div></a-form>
    <div class="examples"><span>已核实的演示示例</span><a-button v-for="example in examples" :key="example.name" size="small" :disabled="isRunning" @click="useExample(example)">{{ example.name }}</a-button></div><p class="safety-note">示例 ID 均为当前 Demo SQLite 数据库中已核实的匿名记录。浏览器不会直接调用 DeepSeek 或 RAGFlow。</p></a-card>
    <a-card title="Agent 实时执行轨迹" class="panel-card live-card"><a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" /><EmptyState v-if="!events.length && !isRunning" title="等待运行" description="选择示例或填写客户问题，即可查看受控工作流的实时执行过程。" /><AgentTimeline v-else :steps="liveSteps" live /></a-card></div>
  <a-card v-if="latestDecision || latestResponse" title="Agent 处理结果" class="panel-card outcome-card"><div class="outcome-header"><DecisionTag :decision="latestDecision" technical /><span v-if="latestDecision === 'NEED_MORE_INFO'" class="outcome-hint">需要客户补充信息后才能继续处理。</span><span v-if="latestDecision === 'ESCALATE_TO_HUMAN'" class="outcome-hint">需要人工审核</span></div><blockquote v-if="latestResponse" class="agent-response">{{ latestResponse }}</blockquote><div v-if="result" class="run-meta"><span>运行 ID <strong class="mono">#{{ result.run_id }}</strong></span><span>工单 ID <strong class="mono">{{ result.ticket_id || '未关联' }}</strong></span><span>{{ displayIntent(result.intent) }}</span><span>工具调用次数：{{ result.tool_call_count }}</span><span>总延迟：{{ formatLatency(result.latency_ms) }}</span></div><p class="safety-note">“自动处理”仅代表路由候选结果，不会执行真实退款或资金操作。</p></a-card>
</section></template>
