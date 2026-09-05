import type { Decision, HumanReviewAction, Intent, TicketStatus } from '../api/types'

export const intentLabels: Record<Intent, string> = {
  RETURN_REFUND: '退款/退货',
  DELIVERY: '物流配送',
  PRODUCT_AFTER_SALES: '商品售后',
  ACCOUNT: '账户问题',
  INVOICE: '发票问题',
  OTHER: '其他',
}

export const decisionLabels: Record<Decision, string> = {
  AUTO_RESOLVE: '自动处理',
  NEED_MORE_INFO: '待补充信息',
  ESCALATE_TO_HUMAN: '需要人工审核',
}

export const ticketStatusLabels: Record<TicketStatus, string> = {
  open: '待处理',
  awaiting_customer: '等待客户补充',
  under_review: '审核中',
  resolved: '已解决',
  closed: '已关闭',
}

export const orderStatusLabels: Record<string, string> = {
  delivered: '已送达',
  shipped: '已发货',
  canceled: '已取消',
  unavailable: '暂不可用',
  invoiced: '已开票',
  processing: '处理中',
  created: '已创建',
  approved: '已批准',
}

export const executionStatusLabels: Record<string, string> = {
  RUNNING: '执行中',
  COMPLETED: '已完成',
  SUCCESS: '成功',
  FAILED: '失败',
  ESCALATED: '已升级人工',
  NEED_MORE_INFO: '待补充信息',
  FALLBACK: '降级处理',
  SKIPPED: '已跳过',
}

export const traceLabels: Record<string, string> = {
  initialize_run: '初始化运行',
  classify_ticket: '意图识别',
  classification: '意图识别',
  plan_actions: '动作规划',
  validate_plan: '校验动作计划',
  execute_action: '执行工具动作',
  evaluate_resolution: '评估处理结果',
  draft_response: '生成客服回复',
  persist_result: '保存运行结果',
  lookup_customer: '查询客户',
  lookup_order: '查询订单',
  list_customer_orders: '查询客户订单',
  search_knowledge: '检索客服政策',
  evaluate_refund: '退款规则评估',
  run_started: '运行开始',
  tool_started: '工具调用开始',
  tool_completed: '工具调用完成',
  decision: '生成决策',
  final_response: '生成最终回复',
  run_completed: '运行完成',
  error: '执行异常',
}

export const reviewActionLabels: Record<HumanReviewAction, string> = {
  RESOLVE: '标记已解决',
  REQUEST_MORE_INFO: '请求补充信息',
  KEEP_ESCALATED: '保持人工审核',
}

const priorityLabels: Record<string, string> = {
  low: '低',
  normal: '普通',
  medium: '中',
  high: '高',
  urgent: '紧急',
}

function mapped(value: string | null | undefined, labels: Record<string, string>): string {
  if (!value) return '—'
  return labels[value] ?? value
}

export const displayIntent = (value: string | null | undefined) => mapped(value, intentLabels)
export const displayDecision = (value: string | null | undefined) => mapped(value, decisionLabels)
export const displayTicketStatus = (value: string | null | undefined) => mapped(value, ticketStatusLabels)
export const displayOrderStatus = (value: string | null | undefined) => mapped(value, orderStatusLabels)
export const displayExecutionStatus = (value: string | null | undefined) => mapped(value, executionStatusLabels)
export const displayReviewAction = (value: string | null | undefined) => mapped(value, reviewActionLabels)
export const displayPriority = (value: string | null | undefined) => mapped(value, priorityLabels)

export function displayTraceName(value: string | null | undefined): string {
  if (!value) return '—'
  const label = traceLabels[value]
  return label ? `${label} (${value})` : value
}

export function formatBrl(value: number, currency = 'BRL'): string {
  return `${value.toFixed(2)} ${currency}`
}
