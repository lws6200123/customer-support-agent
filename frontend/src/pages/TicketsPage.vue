<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { listTickets } from '../api/tickets'
import type { Decision, Intent, Ticket, TicketStatus } from '../api/types'
import { displayApiError } from '../api/client'
import DecisionTag from '../components/DecisionTag.vue'
import StatusTag from '../components/StatusTag.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate } from '../utils/format'
import { displayDecision, displayIntent, displayPriority, displayTicketStatus } from '../utils/display'

const tickets = ref<Ticket[]>([]); const total = ref(0); const loading = ref(true); const error = ref<string | null>(null)
const filters = reactive<{ page: number; pageSize: number; status?: TicketStatus; decision?: Decision; intent?: Intent }>({ page: 1, pageSize: 20 })
const statuses: TicketStatus[] = ['open', 'awaiting_customer', 'under_review', 'resolved', 'closed']
const decisions: Decision[] = ['AUTO_RESOLVE', 'NEED_MORE_INFO', 'ESCALATE_TO_HUMAN']
const intents: Intent[] = ['RETURN_REFUND', 'DELIVERY', 'PRODUCT_AFTER_SALES', 'ACCOUNT', 'INVOICE', 'OTHER']
async function load() { loading.value = true; error.value = null; try { const page = await listTickets(filters); tickets.value = page.items; total.value = page.total } catch (caught) { error.value = displayApiError(caught) } finally { loading.value = false } }
function resetPage() { filters.page = 1; void load() }
onMounted(load)
</script>

<template>
  <section>
    <div class="page-heading"><div><p class="eyebrow">客服运营</p><h1>工单列表</h1><p>查看并筛选由运行时 API 提供的 DemoShop 合成客服工单。</p></div><a-button :loading="loading" @click="load"><ReloadOutlined /> 刷新</a-button></div>
    <a-card class="filter-card"><div class="filter-row"><div><label>工单状态</label><a-select v-model:value="filters.status" allow-clear placeholder="全部状态" @change="resetPage"><a-select-option v-for="item in statuses" :key="item" :value="item">{{ displayTicketStatus(item) }}</a-select-option></a-select></div><div><label>Agent 决策</label><a-select v-model:value="filters.decision" allow-clear placeholder="全部决策" @change="resetPage"><a-select-option v-for="item in decisions" :key="item" :value="item">{{ displayDecision(item) }}</a-select-option></a-select></div><div><label>问题类型</label><a-select v-model:value="filters.intent" allow-clear placeholder="全部类型" @change="resetPage"><a-select-option v-for="item in intents" :key="item" :value="item">{{ displayIntent(item) }}</a-select-option></a-select></div><a-button type="primary" @click="resetPage"><SearchOutlined /> 应用筛选</a-button></div></a-card>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert"><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert>
    <a-card class="panel-card table-card"><a-spin :spinning="loading" tip="加载中..."><EmptyState v-if="!loading && !tickets.length" title="暂无符合条件的工单" description="可清除筛选条件，或运行 Agent 演示创建关联工单。" />
      <a-table v-else :data-source="tickets" :pagination="{ current: filters.page, pageSize: filters.pageSize, total, showSizeChanger: true, pageSizeOptions: ['10','20','50','100'] }" row-key="ticket_id" :scroll="{ x: 1050 }" @change="(p: { current?: number; pageSize?: number }) => { filters.page = p.current || 1; filters.pageSize = p.pageSize || 20; load() }">
        <a-table-column title="工单 ID" data-index="ticket_id" key="ticket"><template #default="{ text }"><router-link :to="`/tickets/${text}`" class="mono ticket-link">{{ text }}</router-link></template></a-table-column>
        <a-table-column title="问题类型" data-index="category" key="intent"><template #default="{ text }">{{ displayIntent(text) }}</template></a-table-column>
        <a-table-column title="优先级" data-index="priority" key="priority"><template #default="{ text }"><a-tag>{{ displayPriority(text) }}</a-tag></template></a-table-column>
        <a-table-column title="工单状态" data-index="status" key="status"><template #default="{ text }"><StatusTag :status="text" /></template></a-table-column>
        <a-table-column title="Agent 决策" data-index="decision" key="decision"><template #default="{ text }"><DecisionTag :decision="text" /></template></a-table-column>
        <a-table-column title="客户" data-index="customer_id" key="customer"><template #default="{ text }"><span class="mono">{{ text }}</span></template></a-table-column>
        <a-table-column title="订单" data-index="order_id" key="order"><template #default="{ text }"><span class="mono">{{ text }}</span></template></a-table-column>
        <a-table-column title="创建时间" data-index="created_at" key="created"><template #default="{ text }">{{ formatDate(text) }}</template></a-table-column>
      </a-table></a-spin></a-card>
  </section>
</template>
