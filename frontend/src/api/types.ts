export type Intent =
  | 'RETURN_REFUND'
  | 'DELIVERY'
  | 'PRODUCT_AFTER_SALES'
  | 'ACCOUNT'
  | 'INVOICE'
  | 'OTHER'

export type Decision = 'AUTO_RESOLVE' | 'NEED_MORE_INFO' | 'ESCALATE_TO_HUMAN'
export type TicketStatus = 'open' | 'awaiting_customer' | 'under_review' | 'resolved' | 'closed'
export type AgentRunStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ESCALATED' | 'NEED_MORE_INFO'

export interface SuccessEnvelope<T> { ok: true; data: T; request_id: string }
export interface ErrorEnvelope { ok: false; error: { code: string; message: string }; request_id: string }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }

export interface Ticket {
  ticket_id: string
  customer_id: string
  order_id: string
  category: string
  status: TicketStatus
  decision: Decision | null
  priority: string
  subject: string
  created_at: string
  updated_at: string
}
export type TicketListResponse = Page<Ticket>

export interface CustomerSummary {
  customer_id: string
  display_name: string
  city: string | null
  state: string | null
}
export interface OrderSummary {
  order_id: string
  status: string
  purchase_at: string
  delivered_at: string | null
  estimated_delivery_at: string
  payment_total: number
  currency: string
}
export interface AgentRunRequest {
  message: string
  customer_id?: string
  order_id?: string
  ticket_id?: string
}
export interface AgentRunDetail {
  run_id: number
  ticket_id: string | null
  intent: Intent | null
  decision: Decision | null
  status: AgentRunStatus
  response: string | null
  agent_summary: string | null
  tool_call_count: number
  latency_ms: number | null
  started_at: string
  completed_at: string | null
}
export interface AgentRunResponse {
  run_id: number
  ticket_id: string | null
  intent: Intent | null
  decision: Decision
  ticket_status: TicketStatus | null
  response: string
  agent_summary: string
  tool_call_count: number
  latency_ms: number | null
}
export interface TicketDetail {
  ticket: Ticket
  customer: CustomerSummary | null
  order: OrderSummary | null
  latest_agent_run: AgentRunDetail | null
}
export interface AgentStep {
  sequence: number
  node: string
  action: string | null
  tool: string | null
  status: string
  latency_ms: number
  input_summary: string | null
  output_summary: string | null
  error_code: string | null
  created_at: string
}
export interface TraceSteps { run_id: number; items: AgentStep[] }
export interface NamedCount { name: string; count: number }
export interface DashboardSummary {
  total_tickets: number
  tickets_by_status: NamedCount[]
  runs_by_decision: NamedCount[]
  auto_resolve_count: number
  need_more_info_count: number
  human_escalation_count: number
  average_agent_latency_ms: number
  recent_runs: AgentRunDetail[]
}
export interface HumanReviewItem {
  ticket_id: string
  run_id: number
  intent: Intent | null
  priority: string
  customer: CustomerSummary | null
  order: OrderSummary | null
  agent_summary: string | null
  reason_codes: string[]
  created_at: string
}
export type HumanReviewAction = 'RESOLVE' | 'REQUEST_MORE_INFO' | 'KEEP_ESCALATED'
export interface HumanReviewResult {
  review_id: number
  ticket_id: string
  action: HumanReviewAction
  ticket_status: TicketStatus
  created_at: string
}
export type KnownSseEventType =
  | 'run_started' | 'classification' | 'tool_started' | 'tool_completed'
  | 'decision' | 'final_response' | 'run_completed' | 'error'
export interface SSEEvent {
  event: string
  timestamp: string
  run_id: number | null
  ticket_id: string | null
  detail: string | null
  intent: Intent | null
  decision: Decision | null
  tool: string | null
  tool_ok: boolean | null
  response: string | null
}
