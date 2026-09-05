<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'
import { listHumanReviews, submitHumanReview } from '../api/reviews'
import type { HumanReviewAction, HumanReviewItem } from '../api/types'
import { displayApiError } from '../api/client'
import DecisionTag from '../components/DecisionTag.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate } from '../utils/format'
import { displayIntent, displayPriority, displayReviewAction } from '../utils/display'

const items = ref<HumanReviewItem[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20); const loading = ref(true); const submitting = ref(false); const error = ref<string | null>(null)
const modalOpen = ref(false); const selected = ref<HumanReviewItem | null>(null); const action = ref<HumanReviewAction>('RESOLVE'); const note = ref('')
async function load() { loading.value = true; error.value = null; try { const result = await listHumanReviews(page.value, pageSize.value); items.value = result.items; total.value = result.total } catch (caught) { error.value = displayApiError(caught) } finally { loading.value = false } }
function openReview(item: HumanReviewItem, nextAction: HumanReviewAction) { selected.value = item; action.value = nextAction; note.value = ''; modalOpen.value = true }
async function confirm() { if (!selected.value) return; submitting.value = true; try { await submitHumanReview(selected.value.ticket_id, action.value, note.value); modalOpen.value = false; await load() } catch (caught) { error.value = displayApiError(caught); modalOpen.value = false } finally { submitting.value = false } }
onMounted(load)
</script>

<template><section><div class="page-heading"><div><p class="eyebrow">人机协同</p><h1>人工审核队列</h1><p>处理需要客服专员决策的规范化升级工单。</p></div><a-button :loading="loading" @click="load"><ReloadOutlined /> 刷新</a-button></div>
  <a-alert type="warning" show-icon class="page-alert"><template #icon><SafetyCertificateOutlined /></template><template #message>这是演示环境中的人工审核流程，不会执行真实退款或资金操作。</template><template #description>操作只会更新合成工单生命周期并追加可审计的审核记录；本控制台未配置生产级身份认证。</template></a-alert>
  <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert"><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert>
  <a-spin :spinning="loading" tip="加载中..."><EmptyState v-if="!loading && !items.length" title="人工审核队列为空" description="当前没有同时符合 ESCALATE_TO_HUMAN 与 under_review 的工单。" />
    <div v-else class="review-list"><a-card v-for="item in items" :key="item.ticket_id" class="review-card"><div class="review-card-header"><div><router-link :to="`/tickets/${item.ticket_id}`" class="mono ticket-link">{{ item.ticket_id }}</router-link><p>运行 <span class="mono">#{{ item.run_id }}</span> · {{ formatDate(item.created_at) }}</p></div><DecisionTag decision="ESCALATE_TO_HUMAN" /></div>
      <div class="review-facts"><span><small>问题类型</small><strong>{{ displayIntent(item.intent) }}</strong></span><span><small>优先级</small><strong>{{ displayPriority(item.priority) }}</strong></span><span><small>客户 ID</small><strong class="mono">{{ item.customer?.customer_id || '—' }}</strong></span><span><small>订单 ID</small><strong class="mono">{{ item.order?.order_id || '—' }}</strong></span></div>
      <p class="review-summary">{{ item.agent_summary || '未记录可安全展示的 Agent 摘要。' }}</p><div v-if="item.reason_codes.length" class="reason-row"><a-tag v-for="reason in item.reason_codes" :key="reason" color="orange">{{ reason }}</a-tag></div>
      <div class="review-actions"><a-button @click="openReview(item, 'KEEP_ESCALATED')">保持人工审核</a-button><a-button @click="openReview(item, 'REQUEST_MORE_INFO')">请求补充信息</a-button><a-button type="primary" @click="openReview(item, 'RESOLVE')">标记已解决</a-button></div></a-card></div>
    <a-pagination v-if="total > pageSize" v-model:current="page" v-model:page-size="pageSize" :total="total" show-size-changer @change="load" />
  </a-spin>
  <a-modal v-model:open="modalOpen" title="确认人工审核操作" :confirm-loading="submitting" ok-text="确认操作" cancel-text="取消" @ok="confirm"><a-alert type="info" :message="displayReviewAction(action)" show-icon class="modal-alert" /><a-form layout="vertical"><a-form-item label="审核备注（选填）"><a-textarea v-model:value="note" :maxlength="4000" :rows="4" placeholder="填写简洁的运营备注，请勿包含任何凭据。" show-count /></a-form-item></a-form><p class="safety-note">此操作不会执行退款，也不会修改支付系统。</p></a-modal>
</section></template>
