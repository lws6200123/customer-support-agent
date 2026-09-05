<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ReloadOutlined, InboxOutlined, CheckCircleOutlined, InfoCircleOutlined, TeamOutlined, FieldTimeOutlined } from '@ant-design/icons-vue'
import { getDashboardSummary } from '../api/dashboard'
import type { DashboardSummary } from '../api/types'
import { displayApiError } from '../api/client'
import DecisionTag from '../components/DecisionTag.vue'
import StatusTag from '../components/StatusTag.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate, formatLatency } from '../utils/format'
import { displayIntent } from '../utils/display'

const data = ref<DashboardSummary | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const refreshedAt = ref<Date | null>(null)

async function load() {
  loading.value = true; error.value = null
  try { data.value = await getDashboardSummary(); refreshedAt.value = new Date() }
  catch (caught) { error.value = displayApiError(caught) }
  finally { loading.value = false }
}
onMounted(load)

const cards = computed(() => [
  { label: '工单总数', value: data.value?.total_tickets || 0, icon: InboxOutlined, tone: 'blue' },
  { label: '自动处理', value: data.value?.auto_resolve_count || 0, icon: CheckCircleOutlined, tone: 'green' },
  { label: '待补充信息', value: data.value?.need_more_info_count || 0, icon: InfoCircleOutlined, tone: 'gold' },
  { label: '人工升级', value: data.value?.human_escalation_count || 0, icon: TeamOutlined, tone: 'red' },
  { label: '平均 Agent 延迟', value: formatLatency(data.value?.average_agent_latency_ms), icon: FieldTimeOutlined, tone: 'purple' },
])
function percent(count: number, rows: { count: number }[]) { const total = rows.reduce((sum, row) => sum + row.count, 0); return total ? Math.round(count / total * 100) : 0 }
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">运营概览</p><h1>数据看板</h1><p>展示 Demo SQLite 运行数据中的实时客服工作量与 Agent 路由结果。</p></div><div class="heading-actions"><span class="refresh-time">最后刷新时间：{{ refreshedAt?.toLocaleTimeString('zh-CN') || '—' }}</span><a-button :loading="loading" @click="load"><ReloadOutlined /> 刷新</a-button></div></div>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert"><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert>
    <a-spin :spinning="loading">
      <div class="metric-grid">
        <a-card v-for="card in cards" :key="card.label" class="metric-card"><div class="metric-content"><div :class="['metric-icon', `tone-${card.tone}`]"><component :is="card.icon" /></div><div><span>{{ card.label }}</span><strong>{{ card.value }}</strong></div></div></a-card>
      </div>
      <div class="dashboard-grid">
        <a-card title="决策分布" class="panel-card">
          <EmptyState v-if="!data?.runs_by_decision.length" title="暂无 Agent 决策数据" />
          <div v-else class="distribution-list"><div v-for="row in data.runs_by_decision" :key="row.name"><div class="distribution-label"><DecisionTag :decision="row.name" /><strong>{{ row.count }}</strong></div><a-progress :percent="percent(row.count, data.runs_by_decision)" :show-info="false" stroke-color="#2f6fed" /></div></div>
        </a-card>
        <a-card title="工单状态分布" class="panel-card">
          <EmptyState v-if="!data?.tickets_by_status.length" title="暂无工单数据" />
          <div v-else class="distribution-list"><div v-for="row in data.tickets_by_status" :key="row.name"><div class="distribution-label"><StatusTag :status="row.name" /><strong>{{ row.count }}</strong></div><a-progress :percent="percent(row.count, data.tickets_by_status)" :show-info="false" stroke-color="#6c7a91" /></div></div>
        </a-card>
      </div>
      <a-card title="最近 Agent 运行" class="panel-card recent-card">
        <EmptyState v-if="!data?.recent_runs.length" title="暂无 Agent 运行记录" description="可前往 Agent 演示创建首次运行。" />
        <a-table v-else :data-source="data.recent_runs" :pagination="false" row-key="run_id" size="middle" :scroll="{ x: 900 }">
          <a-table-column title="运行 ID" data-index="run_id" key="run_id"><template #default="{ text, record }"><router-link v-if="record.ticket_id" :to="`/tickets/${record.ticket_id}`" class="mono">#{{ text }}</router-link><span v-else class="mono">#{{ text }}</span></template></a-table-column>
          <a-table-column title="问题类型" data-index="intent" key="intent"><template #default="{ text }">{{ displayIntent(text) }}</template></a-table-column>
          <a-table-column title="Agent 决策" data-index="decision" key="decision"><template #default="{ text }"><DecisionTag :decision="text" /></template></a-table-column>
          <a-table-column title="运行状态" data-index="status" key="status"><template #default="{ text }"><StatusTag :status="text" kind="execution" /></template></a-table-column>
          <a-table-column title="延迟" data-index="latency_ms" key="latency"><template #default="{ text }">{{ formatLatency(text) }}</template></a-table-column>
          <a-table-column title="开始时间" data-index="started_at" key="started"><template #default="{ text }">{{ formatDate(text) }}</template></a-table-column>
        </a-table>
      </a-card>
    </a-spin>
  </section>
</template>
